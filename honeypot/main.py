"""
ScamBait-X Honeypot System
FastAPI Main Application
"""

import asyncio
import json
from contextlib import asynccontextmanager
from typing import Dict
from uuid import UUID, uuid4
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Header, Depends, BackgroundTasks, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse

from .config import settings
from .models.schemas import (
    Session,
    SessionSummary,
    FraudIntelligenceReport,
    ExtractionMode,
    WSMessageType,
    WSIncomingMessage,
    WSOutgoingMessage,
    # Hackathon models
    HoneypotRequest,
    HoneypotResponse,
    HoneypotErrorResponse,
    GuviCallbackPayload,
    ExtractedIntelligence,
)
from .agent import create_agent, list_personas
from .mock import create_mock_scammer, list_scam_types


# In-memory session store
active_sessions: Dict[str, Session] = {}
session_agents: Dict[str, any] = {}


async def cleanup_session(session_id: str):
    """Clean up a session."""
    if session_id in active_sessions:
        del active_sessions[session_id]
    if session_id in session_agents:
        del session_agents[session_id]


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler for startup/shutdown."""
    # Startup
    print("🎣 ScamBait-X Honeypot V2 starting...")
    
    if not settings.validate():
        print("⚠️  WARNING: GROQ_API_KEY not configured. LLM features will use fallbacks.")
    else:
        print("✅ Groq API configured")
    
    # V2: Initialize Redis
    try:
        from .db import redis_store
        await redis_store.connect()
    except Exception as e:
        print(f"⚠️  Redis: {e}")
    
    # V2: Initialize PostgreSQL
    try:
        from .db import postgres_store
        await postgres_store.connect()
    except Exception as e:
        print(f"⚠️  PostgreSQL: {e}")
    
    # V2: Initialize ML engines (lazy load)
    try:
        from .ml import embedding_engine, ner_extractor
        if embedding_engine.is_available():
            await embedding_engine.initialize()
        if ner_extractor.is_available():
            await ner_extractor.initialize()
    except Exception as e:
        print(f"⚠️  ML engines: {e}")
    
    # V2: Initialize threat graph
    try:
        from .intel import threat_graph
        print(f"✅ Threat graph: {threat_graph.get_stats()}")
    except Exception as e:
        print(f"⚠️  Threat graph: {e}")
    
    yield
    
    # Shutdown: cleanup all sessions
    print("🛑 Shutting down, cleaning up sessions...")
    for session_id in list(active_sessions.keys()):
        await cleanup_session(session_id)
    
    # V2: Disconnect databases
    try:
        from .db import redis_store, postgres_store
        await redis_store.disconnect()
        await postgres_store.disconnect()
    except Exception:
        pass
    
    print("✅ All sessions cleaned up")



# Create FastAPI app
app = FastAPI(
    title="ScamBait-X Honeypot",
    description="Agentic honeypot system for scam intelligence gathering",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
frontend_path = Path(__file__).parent.parent / "frontend"
if frontend_path.exists():
    app.mount("/static", StaticFiles(directory=str(frontend_path)), name="static")


# --- REST Endpoints ---

@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the LIVE voice demo page (auto-persona mode)."""
    voice_file = frontend_path / "voice.html"
    if voice_file.exists():
        return FileResponse(voice_file)
    return HTMLResponse("<h1>ScamBait-X Live Demo</h1><p>Voice demo not found.</p>")


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "groq_configured": settings.validate(),
        "active_sessions": len(active_sessions)
    }


@app.get("/api/personas")
async def get_personas():
    """List available personas."""
    return list_personas()


@app.get("/api/scam-types")
async def get_scam_types():
    """List available mock scam types."""
    return list_scam_types()


@app.get("/api/sessions")
async def get_sessions():
    """List active sessions."""
    summaries = []
    for session_id, session in active_sessions.items():
        summaries.append(SessionSummary(
            session_id=session.session_id,
            persona_id=session.persona_id,
            current_mode=session.current_mode,
            turn_count=session.turn_count,
            entity_count=session.extracted_entities.total_count,
            duration_seconds=session.duration_seconds
        ))
    return summaries


@app.post("/api/sessions")
async def create_session(persona_id: str):
    """Create a new honeypot session."""
    if persona_id not in list_personas():
        raise HTTPException(status_code=400, detail=f"Unknown persona: {persona_id}")
    
    session = Session(persona_id=persona_id)
    session_id = str(session.session_id)
    
    active_sessions[session_id] = session
    session_agents[session_id] = create_agent(session)
    
    return {"session_id": session_id, "persona_id": persona_id}


@app.delete("/api/sessions/{session_id}")
async def end_session(session_id: str):
    """End and cleanup a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await cleanup_session(session_id)
    return {"status": "ended", "session_id": session_id}


@app.get("/api/report/{session_id}")
async def get_report(session_id: str):
    """Get intelligence report for a session."""
    if session_id not in active_sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    
    session = active_sessions[session_id]
    report = FraudIntelligenceReport.from_session(session)
    
    return report.model_dump(mode="json")


# --- WebSocket Endpoints ---

@app.websocket("/ws/honeypot/{persona_id}")
async def websocket_honeypot(websocket: WebSocket, persona_id: str):
    """
    Main honeypot WebSocket endpoint.
    Clients send scammer messages, receive honeypot responses.
    """
    await websocket.accept()
    
    # Validate persona
    if persona_id not in list_personas():
        await websocket.send_json({
            "type": "error",
            "error": f"Unknown persona: {persona_id}"
        })
        await websocket.close()
        return
    
    # Create session
    session = Session(persona_id=persona_id)
    session_id = str(session.session_id)
    active_sessions[session_id] = session
    agent = create_agent(session)
    session_agents[session_id] = agent
    
    # Send session info
    await websocket.send_json({
        "type": "session_started",
        "session_id": session_id,
        "persona": list_personas()[persona_id]
    })
    
    try:
        while True:
            # Receive message
            data = await websocket.receive_json()
            msg = WSIncomingMessage(**data)
            
            if msg.type == WSMessageType.SCAMMER_MESSAGE and msg.content:
                # Process scammer message
                response, delay, entities, switch_signal = await agent.process_scammer_message(
                    msg.content
                )
                
                # Send mode switch notification if applicable
                if switch_signal and switch_signal.should_switch:
                    await websocket.send_json(WSOutgoingMessage(
                        type=WSMessageType.STATUS_UPDATE,
                        mode_switched=True,
                        new_mode=switch_signal.new_mode,
                        reason=switch_signal.reason
                    ).model_dump(mode="json"))
                
                # Send honeypot response
                await websocket.send_json(WSOutgoingMessage(
                    type=WSMessageType.HONEYPOT_RESPONSE,
                    content=response,
                    mode=session.current_mode,
                    entities_extracted=entities,
                    typing_delay_ms=delay
                ).model_dump(mode="json"))
            
            elif msg.type == WSMessageType.RESUME_SESSION and msg.session_id:
                # Resume existing session
                if msg.session_id in active_sessions:
                    session = active_sessions[msg.session_id]
                    agent = session_agents[msg.session_id]
                    await websocket.send_json({
                        "type": "session_resumed",
                        "session_id": msg.session_id,
                        "turn_count": session.turn_count,
                        "mode": session.current_mode.value
                    })
    
    except WebSocketDisconnect:
        print(f"Client disconnected from session {session_id}")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })
    finally:
        # Keep session alive for potential reconnection
        pass


@app.websocket("/ws/mock-scammer/{scam_type}")
async def websocket_mock_scammer(websocket: WebSocket, scam_type: str):
    """
    Mock scammer WebSocket for testing.
    Runs a scripted scam conversation.
    """
    await websocket.accept()
    
    # Validate scam type
    available_types = list_scam_types()
    if scam_type not in available_types:
        await websocket.send_json({
            "type": "error",
            "error": f"Unknown scam type: {scam_type}. Available: {list(available_types.keys())}"
        })
        await websocket.close()
        return
    
    # Create mock scammer
    scammer = create_mock_scammer(scam_type)
    
    await websocket.send_json({
        "type": "scam_started",
        "scam_type": scam_type,
        "scam_name": available_types[scam_type]
    })
    
    try:
        # Send first message
        first_msg = await scammer.get_next_message()
        if first_msg:
            await websocket.send_json({
                "type": "scammer_message",
                "content": first_msg,
                "progress": scammer.get_progress()
            })
        
        while not scammer.is_ended():
            # Wait for honeypot response
            data = await websocket.receive_json()
            
            if data.get("type") == "honeypot_response":
                # Get next scammer message
                next_msg = await scammer.get_next_message(data.get("content"))
                
                if next_msg:
                    await websocket.send_json({
                        "type": "scammer_message", 
                        "content": next_msg,
                        "progress": scammer.get_progress()
                    })
                else:
                    # Scam ended
                    await websocket.send_json({
                        "type": "scam_ended",
                        "reason": "Script completed",
                        "revealed_iocs": scammer.get_revealed_iocs()
                    })
                    break
    
    except WebSocketDisconnect:
        print(f"Mock scammer session disconnected")
    except Exception as e:
        await websocket.send_json({
            "type": "error",
            "error": str(e)
        })


@app.websocket("/ws/auto-demo/{persona_id}/{scam_type}")
async def websocket_auto_demo(websocket: WebSocket, persona_id: str, scam_type: str):
    """
    Automated demo: connects mock scammer to honeypot for observation.
    Client just watches the conversation unfold.
    """
    await websocket.accept()
    
    # Validate
    if persona_id not in list_personas():
        await websocket.send_json({"type": "error", "error": f"Unknown persona: {persona_id}"})
        await websocket.close()
        return
    
    if scam_type not in list_scam_types():
        await websocket.send_json({"type": "error", "error": f"Unknown scam type: {scam_type}"})
        await websocket.close()
        return
    
    # Create session and mock scammer
    session = Session(persona_id=persona_id)
    agent = create_agent(session)
    scammer = create_mock_scammer(scam_type)
    
    await websocket.send_json({
        "type": "demo_started",
        "session_id": str(session.session_id),
        "persona": list_personas()[persona_id],
        "scam_name": list_scam_types()[scam_type]
    })
    
    try:
        while not scammer.is_ended():
            # Get scammer message
            scammer_msg = await scammer.get_next_message()
            if not scammer_msg:
                break
            
            # Send to client
            await websocket.send_json({
                "type": "scammer_message",
                "content": scammer_msg
            })
            
            # Process with honeypot
            response, delay, entities, switch = await agent.process_scammer_message(scammer_msg)
            
            # Simulate typing delay (shortened for demo)
            await asyncio.sleep(min(delay / 1000, 2.0))
            
            # Send mode switch if occurred
            if switch and switch.should_switch:
                await websocket.send_json({
                    "type": "status_update",
                    "mode_switched": True,
                    "new_mode": switch.new_mode.value,
                    "reason": switch.reason
                })
            
            # Send honeypot response
            await websocket.send_json({
                "type": "honeypot_response",
                "content": response,
                "mode": session.current_mode.value,
                "entities_extracted": entities
            })
        
        # Demo ended
        report = FraudIntelligenceReport.from_session(session)
        await websocket.send_json({
            "type": "demo_ended",
            "report": report.model_dump(mode="json")
        })
    
    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.send_json({"type": "error", "error": str(e)})


# --- Hackathon API (Problem Statement 2) ---

async def verify_api_key(x_api_key: str = Header(...)):
    """Validate API key for hackathon endpoint."""
    import os
    expected_key = os.getenv("HONEYPOT_API_KEY", "")
    
    if not x_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )
    
    # If HONEYPOT_API_KEY is set, validate strictly
    # If not set (for testing), accept any non-empty key
    if expected_key and x_api_key != expected_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key"
        )
    
    return x_api_key


async def send_guvi_callback(payload: GuviCallbackPayload):
    """
    Send mandatory callback to GUVI endpoint.
    This runs in the background to avoid blocking the response.
    """
    import httpx
    url = "https://hackathon.guvi.in/api/updateHoneyPotFinalResult"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(url, json=payload.model_dump(), timeout=10.0)
            if response.status_code == 200:
                print(f"✅ GUVI Callback Success: {response.text}")
            else:
                print(f"⚠️ GUVI Callback Failed ({response.status_code}): {response.text}")
    except Exception as e:
        print(f"❌ GUVI Callback Error: {e}")


@app.post("/api/honeypot", response_model=HoneypotResponse)
async def hackathon_honeypot_api(
    request: HoneypotRequest,
    background_tasks: BackgroundTasks,
    api_key: str = Depends(verify_api_key)
):
    """
    REST API endpoint for Hackathon Problem Statement 2.
    Accepts scam message, triggers Agent, returns response.
    """
    # 1. Create or retrieve session
    session_id = request.sessionId
    
    # Check if session exists in our memory store
    if session_id not in voice_sessions:
        # Create new session (reusing our voice session structure for consistency)
        from .voice import create_detector
        from .detection import EntityExtractor
        
        # Auto-select persona for API requests
        persona_id = "young_professional"
        
        detector = create_detector()
        extractor = EntityExtractor()
        session = Session(session_id=UUID(hex=session_id.replace("-", "") if len(session_id) == 36 else uuid4().hex), persona_id=persona_id)
        agent = create_agent(session)
        
        voice_sessions[session_id] = {
            "detector": detector,
            "session": session,
            "agent": agent,
            "is_scammer_mode": True # Always active for API
        }
        print(f"🆕 New API Session: {session_id}")
    else:
        print(f"🔄 Continuing API Session: {session_id}")
        
    session_data = voice_sessions[session_id]
    agent = session_data["agent"]
    session = session_data["session"]
    detector = session_data["detector"]
    extractor = session_data["extractor"] if "extractor" in session_data else EntityExtractor() # Ensure extractor exists
    
    # 2. Process the incoming message
    scammer_text = request.message.text
    
    # Detect scam
    analysis = detector.analyze(scammer_text)
    
    # Extract entities
    entities = extractor.extract_all(scammer_text)
    
    # 3. Generate AI Response
    try:
        response_text, _, _, _ = await agent.process_scammer_message(scammer_text)
    except Exception as e:
        print(f"Agent generation error: {e}")
        response_text = "I am not sure I understand. Can you explain?"

    # 4. Prepare Intelligence for Callback
    # Merge extracted entities into a summary format for the callback
    all_entities = session.extracted_entities
    
    extracted_intel = ExtractedIntelligence(
        bankAccounts=[acc.account_number for acc in all_entities.bank_accounts],
        upiIds=all_entities.upi_ids,
        phishingLinks=all_entities.urls,
        phoneNumbers=all_entities.phone_numbers,
        suspiciousKeywords=analysis.indicators
    )
    
    # 5. Schedule MANDATORY Callback
    # We send this every turn updates, or maybe logic to send only at 'end'?
    # The instructions say: "Send only after scam intent is confirmed... and engagement completed"
    # For this API, we can send an update on every turn or check a threshold.
    # Let's send it if scam confidence is high.
    
    if analysis.is_scammer or session.turn_count > 2:
        callback_payload = GuviCallbackPayload(
            sessionId=session_id,
            scamDetected=True,
            totalMessagesExchanged=session.turn_count,
            extractedIntelligence=extracted_intel,
            agentNotes=f"Scam type: {analysis.scam_type}. Confidence: {analysis.confidence}"
        )
        background_tasks.add_task(send_guvi_callback, callback_payload)

    # 6. Return Response
    return HoneypotResponse(
        status="success",
        reply=response_text
    )

@app.get("/voice", response_class=HTMLResponse)
async def voice_page():
    """Serve the voice detector page."""
    voice_file = frontend_path / "voice.html"
    if voice_file.exists():
        return FileResponse(voice_file)
    return HTMLResponse("<h1>Voice detector not found</h1>")


# Voice session storage
voice_sessions: Dict[str, dict] = {}


@app.websocket("/ws/voice/{persona_id}")
async def websocket_voice(websocket: WebSocket, persona_id: str):
    """
    Voice detection WebSocket endpoint.
    Receives voice transcripts and returns scam analysis + AI responses.
    """
    await websocket.accept()
    
    # Validate persona
    if persona_id not in list_personas():
        await websocket.send_json({
            "type": "error",
            "message": f"Unknown persona: {persona_id}"
        })
        await websocket.close()
        return
    
    # Create session
    from .voice import create_detector
    from .detection import EntityExtractor
    
    session_id = str(uuid4())
    detector = create_detector(threshold=0.6)
    extractor = EntityExtractor()
    session = Session(persona_id=persona_id)
    agent = create_agent(session)
    
    voice_sessions[session_id] = {
        "detector": detector,
        "session": session,
        "agent": agent,
        "is_scammer_mode": False
    }
    
    await websocket.send_json({
        "type": "session_started",
        "session_id": session_id,
        "persona": list_personas()[persona_id]
    })
    
    # Send AI greeting - AI answers the call first
    greetings = {
        "elderly_widow": "Hello? Who is this calling?",
        "young_professional": "Yeah, hello?",
        "small_business_owner": "Hello, this is Priya speaking."
    }
    greeting = greetings.get(persona_id, "Hello?")
    
    await websocket.send_json({
        "type": "ai_response",
        "content": greeting,
        "is_greeting": True
    })
    
    try:
        while True:
            data = await websocket.receive_json()
            
            if data.get("type") == "transcript":
                transcript = data.get("content", "")
                
                # Analyze for scam indicators
                analysis = detector.analyze(transcript)
                
                # Extract entities
                entities = extractor.extract_all(transcript)
                entities_dict = {
                    "upi_ids": entities.upi_ids,
                    "phone_numbers": entities.phone_numbers,
                    "bank_accounts": [acc.account_number for acc in entities.bank_accounts] if entities.bank_accounts else [],
                    "crypto_addresses": [addr.address for addr in entities.crypto_addresses] if entities.crypto_addresses else [],
                    "urls": entities.urls,
                    "emails": entities.email_addresses,
                }
                
                # Send scam analysis
                await websocket.send_json({
                    "type": "scam_analysis",
                    "score": analysis.score,
                    "scam_type": analysis.scam_type,
                    "indicators": analysis.indicators,
                    "confidence": analysis.confidence
                })
                
                # Send entities if found
                if entities.total_count > 0:
                    await websocket.send_json({
                        "type": "entities_found",
                        "entities": entities_dict
                    })
                
                # Check if should activate AI mode
                if analysis.is_scammer and not voice_sessions[session_id]["is_scammer_mode"]:
                    voice_sessions[session_id]["is_scammer_mode"] = True
                    
                    await websocket.send_json({
                        "type": "mode_switch",
                        "is_scammer": True,
                        "reason": f"Detected: {analysis.scam_type} scam ({int(analysis.score * 100)}% confidence)"
                    })
                
                # Generate AI response - ALWAYS respond for live demo
                # (Removed is_scammer_mode check so AI always engages)
                try:
                    response, delay, _, _ = await agent.process_scammer_message(transcript)
                    await websocket.send_json({
                        "type": "ai_response",
                        "content": response,
                        "typing_delay": delay
                    })
                except Exception as e:
                    print(f"Agent error: {e}")
                    # Fallback response if LLM fails
                    fallback_responses = [
                        "Oh my, that sounds very concerning! Tell me more...",
                        "I'm so confused, can you explain that again?",
                        "What should I do? This is so worrying!",
                        "I don't understand these technical things. Please help me!",
                        "Who did you say you were calling from?",
                        "My Ramesh used to handle all these things... What should I do?",
                    ]
                    import random
                    await websocket.send_json({
                        "type": "ai_response",
                        "content": random.choice(fallback_responses)
                    })
    
    except WebSocketDisconnect:
        print(f"Voice session {session_id} disconnected")
    except Exception as e:
        await websocket.send_json({"type": "error", "message": str(e)})
    finally:
        if session_id in voice_sessions:
            del voice_sessions[session_id]


# Run with: uvicorn honeypot.main:app --reload
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port, reload=True)

