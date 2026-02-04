"""
ScamBait-X Honeypot System
Pydantic Models and Schemas
"""

from datetime import datetime
from enum import Enum
from typing import List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class ScamType(str, Enum):
    """Types of scams detected."""
    LOTTERY = "lottery"
    UPI_FRAUD = "upi_fraud"
    TECH_SUPPORT = "tech_support"
    ROMANCE = "romance"
    INVESTMENT = "investment"
    UNKNOWN = "unknown"


class ExtractionMode(str, Enum):
    """Honeypot extraction modes."""
    PATIENCE = "patience"
    AGGRESSIVE = "aggressive"


class ThreatLevel(str, Enum):
    """Threat severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class MessageRole(str, Enum):
    """Message sender roles."""
    HONEYPOT = "honeypot"
    SCAMMER = "scammer"


# --- Entity Models ---

class BankAccount(BaseModel):
    """Extracted bank account details."""
    account_number: str
    ifsc_code: Optional[str] = None
    bank_name: Optional[str] = None


class CryptoAddress(BaseModel):
    """Extracted cryptocurrency address."""
    address: str
    currency: str = "unknown"  # btc, eth, etc.


class ExtractedEntities(BaseModel):
    """All entities extracted from conversation."""
    upi_ids: List[str] = Field(default_factory=list)
    phone_numbers: List[str] = Field(default_factory=list)
    bank_accounts: List[BankAccount] = Field(default_factory=list)
    crypto_addresses: List[CryptoAddress] = Field(default_factory=list)
    urls: List[str] = Field(default_factory=list)
    email_addresses: List[str] = Field(default_factory=list)
    
    def merge_with_dedup(self, other: "ExtractedEntities") -> "ExtractedEntities":
        """Merge entities with deduplication."""
        return ExtractedEntities(
            upi_ids=deduplicate_case_insensitive(self.upi_ids + other.upi_ids),
            phone_numbers=deduplicate_phones(self.phone_numbers + other.phone_numbers),
            bank_accounts=deduplicate_bank_accounts(self.bank_accounts + other.bank_accounts),
            crypto_addresses=deduplicate_crypto(self.crypto_addresses + other.crypto_addresses),
            urls=list(set(self.urls + other.urls)),
            email_addresses=deduplicate_case_insensitive(self.email_addresses + other.email_addresses),
        )
    
    @property
    def total_count(self) -> int:
        """Total number of extracted entities."""
        return (
            len(self.upi_ids) + 
            len(self.phone_numbers) + 
            len(self.bank_accounts) + 
            len(self.crypto_addresses) + 
            len(self.urls) + 
            len(self.email_addresses)
        )
    
    def to_list(self) -> List[str]:
        """Convert all entities to a flat list for display."""
        result = []
        result.extend([f"UPI: {u}" for u in self.upi_ids])
        result.extend([f"Phone: {p}" for p in self.phone_numbers])
        result.extend([f"Bank: {b.account_number} ({b.ifsc_code or 'N/A'})" for b in self.bank_accounts])
        result.extend([f"Crypto: {c.address[:20]}..." for c in self.crypto_addresses])
        result.extend([f"URL: {u}" for u in self.urls])
        result.extend([f"Email: {e}" for e in self.email_addresses])
        return result


# --- Deduplication Helpers ---

def normalize_phone(phone: str) -> str:
    """Normalize phone number for comparison."""
    # Remove all non-digits
    digits = "".join(c for c in phone if c.isdigit())
    # Remove leading 91 if present
    if len(digits) > 10 and digits.startswith("91"):
        digits = digits[2:]
    return digits[-10:] if len(digits) >= 10 else digits


def deduplicate_phones(phones: List[str]) -> List[str]:
    """Deduplicate phone numbers with normalization."""
    seen = {}
    for phone in phones:
        normalized = normalize_phone(phone)
        if normalized not in seen:
            seen[normalized] = phone  # Keep original format
    return list(seen.values())


def deduplicate_case_insensitive(items: List[str]) -> List[str]:
    """Deduplicate strings case-insensitively."""
    seen = {}
    for item in items:
        lower = item.lower()
        if lower not in seen:
            seen[lower] = item
    return list(seen.values())


def deduplicate_bank_accounts(accounts: List[BankAccount]) -> List[BankAccount]:
    """Deduplicate bank accounts by account number."""
    seen = {}
    for acc in accounts:
        if acc.account_number not in seen:
            seen[acc.account_number] = acc
    return list(seen.values())


def deduplicate_crypto(addresses: List[CryptoAddress]) -> List[CryptoAddress]:
    """Deduplicate crypto addresses."""
    seen = {}
    for addr in addresses:
        if addr.address not in seen:
            seen[addr.address] = addr
    return list(seen.values())


# --- Message Models ---

class Message(BaseModel):
    """A single message in the conversation."""
    role: MessageRole
    content: str
    timestamp: datetime = Field(default_factory=datetime.now)
    raw_content: Optional[str] = None  # Before humanization (for honeypot)
    entities_found: List[str] = Field(default_factory=list)


# --- Classification Models ---

class ScamClassification(BaseModel):
    """Result of scam classification."""
    scam_type: ScamType = ScamType.UNKNOWN
    confidence: float = Field(ge=0.0, le=1.0, default=0.0)
    indicators: List[str] = Field(default_factory=list)


# --- Session Models ---

class Session(BaseModel):
    """Active honeypot session."""
    session_id: UUID = Field(default_factory=uuid4)
    persona_id: str
    current_mode: ExtractionMode = ExtractionMode.PATIENCE
    conversation_history: List[Message] = Field(default_factory=list)
    extracted_entities: ExtractedEntities = Field(default_factory=ExtractedEntities)
    scam_classification: Optional[ScamClassification] = None
    created_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    turn_count: int = 0
    urgency_signals: int = 0
    greed_signals: int = 0
    
    def add_message(self, role: MessageRole, content: str, raw_content: str = None, entities: List[str] = None):
        """Add a message to conversation history."""
        self.conversation_history.append(Message(
            role=role,
            content=content,
            raw_content=raw_content,
            entities_found=entities or []
        ))
        self.last_activity = datetime.now()
        self.turn_count += 1
    
    @property
    def duration_seconds(self) -> float:
        """Get session duration in seconds."""
        return (datetime.now() - self.created_at).total_seconds()


class SessionSummary(BaseModel):
    """Summary of a session for listing."""
    session_id: UUID
    persona_id: str
    current_mode: ExtractionMode
    turn_count: int
    entity_count: int
    duration_seconds: float
    threat_level: Optional[ThreatLevel] = None


# --- Intelligence Report ---

def calculate_threat_level(
    classification: ScamClassification, 
    entities: ExtractedEntities
) -> ThreatLevel:
    """Calculate threat level based on confidence and extracted IOCs."""
    score = classification.confidence * 0.4
    score += min(len(entities.upi_ids) * 0.15, 0.3)
    score += min(len(entities.bank_accounts) * 0.2, 0.3)
    score += min(len(entities.phone_numbers) * 0.1, 0.2)
    score += min(len(entities.crypto_addresses) * 0.25, 0.3)
    
    if score >= 0.8:
        return ThreatLevel.CRITICAL
    elif score >= 0.6:
        return ThreatLevel.HIGH
    elif score >= 0.4:
        return ThreatLevel.MEDIUM
    return ThreatLevel.LOW


class FraudIntelligenceReport(BaseModel):
    """Complete fraud intelligence report."""
    session_id: UUID
    classification: ScamClassification
    threat_level: ThreatLevel
    extracted_iocs: ExtractedEntities
    tactics_observed: List[str] = Field(default_factory=list)
    conversation_transcript: List[Message] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)
    generated_at: datetime = Field(default_factory=datetime.now)
    persona_used: str = ""
    session_duration_seconds: float = 0.0
    
    @classmethod
    def from_session(cls, session: Session) -> "FraudIntelligenceReport":
        """Generate report from a session."""
        classification = session.scam_classification or ScamClassification()
        threat_level = calculate_threat_level(classification, session.extracted_entities)
        
        # Generate recommendations based on findings
        recommendations = []
        if session.extracted_entities.upi_ids:
            recommendations.append(f"Report UPI IDs to NPCI: {', '.join(session.extracted_entities.upi_ids)}")
        if session.extracted_entities.phone_numbers:
            recommendations.append(f"Report phone numbers to cybercrime.gov.in: {', '.join(session.extracted_entities.phone_numbers)}")
        if session.extracted_entities.bank_accounts:
            recommendations.append("Report bank accounts to respective banks' fraud departments")
        if session.extracted_entities.urls:
            recommendations.append(f"Submit URLs to Google Safe Browsing and PhishTank")
        
        # Observed tactics
        tactics = []
        if session.urgency_signals > 0:
            tactics.append(f"Urgency tactics detected ({session.urgency_signals} instances)")
        if session.greed_signals > 0:
            tactics.append(f"Greed exploitation detected ({session.greed_signals} instances)")
        if classification.scam_type != ScamType.UNKNOWN:
            tactics.append(f"Scam pattern: {classification.scam_type.value}")
        
        return cls(
            session_id=session.session_id,
            classification=classification,
            threat_level=threat_level,
            extracted_iocs=session.extracted_entities,
            tactics_observed=tactics,
            conversation_transcript=session.conversation_history,
            recommendations=recommendations,
            persona_used=session.persona_id,
            session_duration_seconds=session.duration_seconds,
        )


# --- Persona Models ---

class Persona(BaseModel):
    """Victim persona definition."""
    id: str
    name: str
    age: int
    description: str
    typing_speed: float = 0.5  # 0-1 scale
    typo_rate: float = 0.01
    patience_prompt: str
    aggressive_prompt: str


# --- WebSocket Message Models ---

class WSMessageType(str, Enum):
    """WebSocket message types."""
    SCAMMER_MESSAGE = "scammer_message"
    HONEYPOT_RESPONSE = "honeypot_response"
    STATUS_UPDATE = "status_update"
    SESSION_COMPLETE = "session_complete"
    ERROR = "error"
    RESUME_SESSION = "resume_session"


class WSIncomingMessage(BaseModel):
    """Incoming WebSocket message from client."""
    type: WSMessageType
    content: Optional[str] = None
    session_id: Optional[str] = None


class WSOutgoingMessage(BaseModel):
    """Outgoing WebSocket message to client."""
    type: WSMessageType
    content: Optional[str] = None
    mode: Optional[ExtractionMode] = None
    entities_extracted: List[str] = Field(default_factory=list)
    typing_delay_ms: int = 0
    mode_switched: bool = False
    new_mode: Optional[ExtractionMode] = None
    reason: Optional[str] = None
    report_url: Optional[str] = None
    error: Optional[str] = None


# --- Hackathon API Models (Problem Statement 2) ---

class HoneypotMessageInput(BaseModel):
    """Single message in the conversation."""
    sender: str  # "scammer" or "user"
    text: str
    timestamp: int  # Epoch time in milliseconds


class HoneypotMetadata(BaseModel):
    """Optional metadata for the request."""
    channel: Optional[str] = "SMS"  # SMS / WhatsApp / Email / Chat
    language: Optional[str] = "English"
    locale: Optional[str] = "IN"


class HoneypotRequest(BaseModel):
    """
    Hackathon API Request Format.
    Matches the exact format required by GUVI evaluation.
    """
    sessionId: str
    message: HoneypotMessageInput
    conversationHistory: List[HoneypotMessageInput] = Field(default_factory=list)
    metadata: Optional[HoneypotMetadata] = None


class HoneypotResponse(BaseModel):
    """
    Hackathon API Response Format.
    Must return exactly this format for evaluation.
    """
    status: str = "success"  # "success" or "error"
    reply: str  # AI agent's response


class HoneypotErrorResponse(BaseModel):
    """Error response format."""
    status: str = "error"
    message: str


class ExtractedIntelligence(BaseModel):
    """Intelligence extracted from the scam conversation."""
    bankAccounts: List[str] = Field(default_factory=list)
    upiIds: List[str] = Field(default_factory=list)
    phishingLinks: List[str] = Field(default_factory=list)
    phoneNumbers: List[str] = Field(default_factory=list)
    suspiciousKeywords: List[str] = Field(default_factory=list)


class GuviCallbackPayload(BaseModel):
    """
    MANDATORY callback payload to send to GUVI after engagement.
    POST to: https://hackathon.guvi.in/api/updateHoneyPotFinalResult
    """
    sessionId: str
    scamDetected: bool = True
    totalMessagesExchanged: int
    extractedIntelligence: ExtractedIntelligence
    agentNotes: str = ""

