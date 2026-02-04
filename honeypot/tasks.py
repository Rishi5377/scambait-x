"""
ScamBait-X V2 - Celery Background Tasks
Async processing for ML, database operations, and reporting
"""

import os

try:
    from celery import Celery
    HAS_CELERY = True
except ImportError:
    HAS_CELERY = False
    Celery = None

# Initialize Celery
if HAS_CELERY:
    celery_app = Celery(
        "scambait",
        broker=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
        backend=os.getenv("CELERY_BROKER_URL", "redis://localhost:6379/1"),
    )
    
    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
    )
else:
    celery_app = None


# ==================== Task Definitions ====================

if HAS_CELERY and celery_app:
    
    @celery_app.task(name="scambait.analyze_message")
    def analyze_message_task(session_id: str, message: str):
        """
        Background task to analyze scammer message.
        - Compute embeddings
        - Run NER
        - Update threat graph
        """
        from honeypot.ml import embedding_engine, ner_extractor
        from honeypot.intel import threat_graph
        
        result = {
            "session_id": session_id,
            "scam_score": 0.0,
            "entities": {},
            "matching_patterns": []
        }
        
        # Compute scam score using embeddings
        if embedding_engine._model:
            score, patterns = embedding_engine.compute_scam_score(message)
            result["scam_score"] = score
            result["matching_patterns"] = patterns
        
        # Extract entities using NER
        if ner_extractor._nlp:
            ner_entities = ner_extractor.extract(message)
            result["entities"] = {
                "money": [e.text for e in ner_entities if e.label == "money_amount"],
                "orgs": [e.text for e in ner_entities if e.label == "organization"],
                "persons": [e.text for e in ner_entities if e.label == "person_name"],
                "locations": [e.text for e in ner_entities if e.label == "location"],
            }
        
        return result
    
    @celery_app.task(name="scambait.save_to_database")
    def save_to_database_task(
        session_id: str, 
        persona_id: str, 
        message: str, 
        role: str,
        entities: dict
    ):
        """
        Background task to persist session data to PostgreSQL.
        """
        import asyncio
        from honeypot.db import postgres_store
        
        async def save():
            if not postgres_store.is_connected:
                await postgres_store.connect()
            
            if postgres_store.is_connected:
                await postgres_store.save_message(session_id, role, message)
                
                for entity_type, values in entities.items():
                    for value in values:
                        await postgres_store.save_entity(session_id, entity_type, value)
        
        asyncio.get_event_loop().run_until_complete(save())
        return {"status": "saved", "session_id": session_id}
    
    @celery_app.task(name="scambait.update_threat_graph")
    def update_threat_graph_task(session_id: str, entities: dict):
        """
        Background task to update threat graph with new entities.
        """
        from honeypot.intel import threat_graph
        
        threat_graph.add_session_entities(session_id, entities)
        
        return {
            "status": "updated",
            "session_id": session_id,
            "stats": threat_graph.get_stats()
        }
    
    @celery_app.task(name="scambait.generate_report")
    def generate_report_task(session_id: str):
        """
        Background task to generate intelligence report.
        """
        import asyncio
        from honeypot.db import postgres_store
        from honeypot.intel import threat_graph
        
        async def gen_report():
            # Get session data
            messages = await postgres_store.get_messages(session_id) if postgres_store.is_connected else []
            
            # Get connected entities
            connected = threat_graph.find_connected_entities("session", session_id)
            
            # Get campaigns
            campaigns = threat_graph.find_campaigns()
            related_campaigns = [c for c in campaigns if session_id in c.get("sessions", [])]
            
            return {
                "session_id": session_id,
                "message_count": len(messages),
                "connected_entities": connected,
                "related_campaigns": related_campaigns,
                "graph_stats": threat_graph.get_stats()
            }
        
        return asyncio.get_event_loop().run_until_complete(gen_report())


# ==================== Sync Fallbacks ====================

def analyze_message_sync(session_id: str, message: str) -> dict:
    """Synchronous fallback when Celery not available."""
    return {"session_id": session_id, "scam_score": 0.0, "entities": {}}


def dispatch_analysis(session_id: str, message: str):
    """
    Dispatch message analysis - uses Celery if available, otherwise sync.
    """
    if HAS_CELERY and celery_app:
        return analyze_message_task.delay(session_id, message)
    else:
        return analyze_message_sync(session_id, message)


def dispatch_database_save(session_id: str, persona_id: str, message: str, role: str, entities: dict):
    """Dispatch database save."""
    if HAS_CELERY and celery_app:
        return save_to_database_task.delay(session_id, persona_id, message, role, entities)
    # No-op if Celery not available


def dispatch_threat_update(session_id: str, entities: dict):
    """Dispatch threat graph update."""
    if HAS_CELERY and celery_app:
        return update_threat_graph_task.delay(session_id, entities)
    else:
        # Sync fallback
        from honeypot.intel import threat_graph
        threat_graph.add_session_entities(session_id, entities)
