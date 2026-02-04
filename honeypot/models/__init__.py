"""ScamBait-X Models Package"""

from .schemas import (
    # Enums
    ScamType,
    ExtractionMode,
    ThreatLevel,
    MessageRole,
    WSMessageType,
    
    # Entity Models
    BankAccount,
    CryptoAddress,
    ExtractedEntities,
    
    # Message Models
    Message,
    
    # Classification
    ScamClassification,
    
    # Session
    Session,
    SessionSummary,
    
    # Report
    FraudIntelligenceReport,
    calculate_threat_level,
    
    # Persona
    Persona,
    
    # WebSocket
    WSIncomingMessage,
    WSOutgoingMessage,
)

__all__ = [
    "ScamType",
    "ExtractionMode", 
    "ThreatLevel",
    "MessageRole",
    "WSMessageType",
    "BankAccount",
    "CryptoAddress",
    "ExtractedEntities",
    "Message",
    "ScamClassification",
    "Session",
    "SessionSummary",
    "FraudIntelligenceReport",
    "calculate_threat_level",
    "Persona",
    "WSIncomingMessage",
    "WSOutgoingMessage",
]
