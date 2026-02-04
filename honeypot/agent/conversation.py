"""
ScamBait-X Honeypot System
Conversation Agent - LangChain + Groq Integration
"""

from typing import List, Optional, Tuple
from ..config import groq_client, RateLimitExceeded, LLMError
from ..models.schemas import (
    Session, 
    Message, 
    MessageRole, 
    ExtractionMode,
    ExtractedEntities,
)
from ..detection import extract_entities, classify_scam
from .personas import get_persona, get_persona_prompt, PERSONAS
from .humanizer import ResponseHumanizer
from .mode_switcher import analyze_and_switch, ModeSwitchSignal


# Fallback responses when rate limited
FALLBACK_RESPONSES = {
    "elderly_widow": {
        ExtractionMode.PATIENCE: [
            "Oh my... I need to think about this beta...",
            "Let me understand... you said I won money?",
            "Arre, this is confusing for me...",
            "My Ramesh used to handle these things...",
        ],
        ExtractionMode.AGGRESSIVE: [
            "Okay beta, I am ready. What is your account number?",
            "Tell me your UPI ID, I will send money.",
            "Give me your details, my neighbor will help.",
        ]
    },
    "young_professional": {
        ExtractionMode.PATIENCE: [
            "Interesting... can you share more details?",
            "I'm a bit busy rn, but tell me more.",
            "What's the verification process for this?",
        ],
        ExtractionMode.AGGRESSIVE: [
            "Okay sounds good, share your UPI.",
            "What account should I transfer to?",
            "Send me your number, let's do this.",
        ]
    },
    "small_business_owner": {
        ExtractionMode.PATIENCE: [
            "I've heard of frauds like this...",
            "How do I know this is genuine?",
            "My business is struggling, I need to be careful...",
        ],
        ExtractionMode.AGGRESSIVE: [
            "Okay bhai, I'm ready. Give me the details.",
            "I need this money urgently. What's your UPI?",
            "Share your account number, I'll transfer now.",
        ]
    }
}


class ConversationAgent:
    """
    Main conversation agent orchestrating:
    - LLM response generation with persona
    - Entity extraction
    - Scam classification
    - Mode switching
    - Response humanization
    """
    
    def __init__(self, session: Session):
        self.session = session
        self.persona = get_persona(session.persona_id)
        self.humanizer = ResponseHumanizer(self.persona)
    
    async def process_scammer_message(
        self, 
        scammer_message: str
    ) -> Tuple[str, int, List[str], Optional[ModeSwitchSignal]]:
        """
        Process incoming scammer message and generate response.
        
        Returns:
            - response: Humanized honeypot response
            - typing_delay_ms: Delay before showing response
            - new_entities: List of newly extracted entity strings
            - switch_signal: Mode switch signal if mode changed
        """
        # 1. Extract entities from scammer message
        entities = extract_entities(scammer_message)
        new_entity_strings = entities.to_list()
        
        # Merge with session entities
        self.session.extracted_entities = self.session.extracted_entities.merge_with_dedup(entities)
        
        # 2. Classify if not already done
        if self.session.scam_classification is None:
            try:
                self.session.scam_classification = await classify_scam(scammer_message)
            except (RateLimitExceeded, LLMError):
                pass  # Will classify later
        
        # 3. Analyze for mode switch
        switch_signal = analyze_and_switch(self.session, scammer_message)
        
        # 4. Record scammer message
        self.session.add_message(
            role=MessageRole.SCAMMER,
            content=scammer_message,
            entities=new_entity_strings
        )
        
        # 5. Generate response
        try:
            raw_response = await self._generate_response(scammer_message)
        except (RateLimitExceeded, LLMError):
            raw_response = self._get_fallback_response()
        
        # 6. Humanize response
        humanized_response, typing_delay = self.humanizer.humanize(raw_response)
        
        # 7. Record honeypot message
        self.session.add_message(
            role=MessageRole.HONEYPOT,
            content=humanized_response,
            raw_content=raw_response
        )
        
        return humanized_response, typing_delay, new_entity_strings, switch_signal
    
    async def _generate_response(self, scammer_message: str) -> str:
        """Generate AI response using Groq."""
        # Build conversation context
        context = self._build_context()
        
        # Get appropriate prompt for current mode
        system_prompt = get_persona_prompt(self.session.persona_id, self.session.current_mode)
        
        # Add mode context
        mode_context = f"\n\n[Current mode: {self.session.current_mode.value.upper()}]"
        if self.session.current_mode == ExtractionMode.AGGRESSIVE:
            mode_context += "\nYou must try to get their payment details in this response."
        
        full_system = system_prompt + mode_context
        
        # Build the user message with context
        user_message = f"""Conversation so far:
{context}

Scammer's latest message: "{scammer_message}"

Respond as {self.persona.name}:"""
        
        response = await groq_client.generate(
            prompt=user_message,
            system_prompt=full_system
        )
        
        # Clean up response (remove quotes if AI wrapped them)
        response = response.strip().strip('"').strip("'")
        
        return response
    
    def _build_context(self) -> str:
        """Build conversation context from history."""
        if not self.session.conversation_history:
            return "[This is the start of the conversation]"
        
        # Use last N turns for context
        max_turns = 6
        recent = self.session.conversation_history[-max_turns:]
        
        lines = []
        for msg in recent:
            role_label = "SCAMMER" if msg.role == MessageRole.SCAMMER else self.persona.name
            lines.append(f"{role_label}: {msg.content}")
        
        return "\n".join(lines)
    
    def _get_fallback_response(self) -> str:
        """Get a fallback response when LLM is unavailable."""
        import random
        
        persona_fallbacks = FALLBACK_RESPONSES.get(
            self.session.persona_id, 
            FALLBACK_RESPONSES["elderly_widow"]
        )
        
        mode_fallbacks = persona_fallbacks.get(
            self.session.current_mode,
            persona_fallbacks[ExtractionMode.PATIENCE]
        )
        
        return random.choice(mode_fallbacks)
    
    def get_session_summary(self) -> dict:
        """Get current session summary."""
        return {
            "session_id": str(self.session.session_id),
            "persona": self.persona.name,
            "mode": self.session.current_mode.value,
            "turns": self.session.turn_count,
            "entities_extracted": self.session.extracted_entities.total_count,
            "scam_type": (
                self.session.scam_classification.scam_type.value 
                if self.session.scam_classification 
                else "unknown"
            ),
            "duration_seconds": self.session.duration_seconds,
        }


# Agent factory
def create_agent(session: Session) -> ConversationAgent:
    """Create a conversation agent for a session."""
    return ConversationAgent(session)
