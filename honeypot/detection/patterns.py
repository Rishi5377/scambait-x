"""
ScamBait-X Honeypot System
Regex Patterns for Indian Fraud Detection
"""

import re
from typing import List, Pattern


# --- Entity Extraction Patterns ---

# UPI ID pattern: username@bankhandle
UPI_PATTERN: Pattern = re.compile(
    r'[a-zA-Z0-9._-]+@[a-zA-Z]{2,}',
    re.IGNORECASE
)

# Indian phone numbers: +91, 0, or direct 10 digits starting with 6-9
INDIAN_PHONE_PATTERN: Pattern = re.compile(
    r'(?:\+91[\s.-]?|0)?[6-9]\d{4}[\s.-]?\d{5}',
    re.IGNORECASE
)

# Bank account: 9-18 digits (most Indian banks)
BANK_ACCOUNT_PATTERN: Pattern = re.compile(
    r'\b\d{9,18}\b'
)

# IFSC Code: 4 letters + 0 + 6 alphanumeric
IFSC_PATTERN: Pattern = re.compile(
    r'\b[A-Z]{4}0[A-Z0-9]{6}\b',
    re.IGNORECASE
)

# Bitcoin address
BITCOIN_PATTERN: Pattern = re.compile(
    r'\b[13][a-km-zA-HJ-NP-Z1-9]{25,34}\b'
)

# Ethereum address
ETHEREUM_PATTERN: Pattern = re.compile(
    r'\b0x[a-fA-F0-9]{40}\b'
)

# URL pattern (http/https)
URL_PATTERN: Pattern = re.compile(
    r'https?://[^\s<>"{}|\\^`\[\]]+',
    re.IGNORECASE
)

# Shortened URLs (common in scams)
SHORT_URL_PATTERN: Pattern = re.compile(
    r'\b(?:bit\.ly|tinyurl\.com|goo\.gl|t\.co|rb\.gy|shorturl\.at|cutt\.ly)/[a-zA-Z0-9]+',
    re.IGNORECASE
)

# Email pattern
EMAIL_PATTERN: Pattern = re.compile(
    r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}',
    re.IGNORECASE
)


# --- Behavioral Signal Patterns ---

# Urgency indicators (case-insensitive word boundaries)
URGENCY_WORDS: List[str] = [
    "hurry", "urgent", "immediately", "now", "quick", "fast",
    "limited time", "expires", "deadline", "last chance",
    "don't delay", "act fast", "time sensitive", "asap",
    "within 24 hours", "today only", "right now", "jaldi",
    "abhi", "turant"  # Hindi urgency words
]

URGENCY_PATTERN: Pattern = re.compile(
    r'\b(' + '|'.join(re.escape(word) for word in URGENCY_WORDS) + r')\b',
    re.IGNORECASE
)

# Greed indicators
GREED_WORDS: List[str] = [
    "won", "winner", "prize", "lottery", "lucky", "million",
    "crore", "lakh", "jackpot", "reward", "bonus", "free money",
    "guaranteed", "100%", "double your money", "investment return",
    "profit", "earn from home", "passive income", "get rich"
]

GREED_PATTERN: Pattern = re.compile(
    r'\b(' + '|'.join(re.escape(word) for word in GREED_WORDS) + r')\b',
    re.IGNORECASE
)

# Fear/threat indicators
FEAR_WORDS: List[str] = [
    "blocked", "suspended", "arrested", "police", "legal action",
    "court", "warrant", "investigation", "fraud detected",
    "account frozen", "security alert", "compromised", "hacked",
    "unauthorized", "violation"
]

FEAR_PATTERN: Pattern = re.compile(
    r'\b(' + '|'.join(re.escape(word) for word in FEAR_WORDS) + r')\b',
    re.IGNORECASE
)

# Authority impersonation
AUTHORITY_WORDS: List[str] = [
    "rbi", "reserve bank", "income tax", "government", "ministry",
    "police", "cyber cell", "cbi", "ed", "enforcement directorate",
    "sebi", "bank manager", "official", "department", "authority"
]

AUTHORITY_PATTERN: Pattern = re.compile(
    r'\b(' + '|'.join(re.escape(word) for word in AUTHORITY_WORDS) + r')\b',
    re.IGNORECASE
)


# --- Scam Type Detection Patterns ---

LOTTERY_SCAM_INDICATORS: List[str] = [
    "lottery", "prize money", "lucky draw", "raffle", "sweepstakes",
    "you have won", "claim your prize", "winning amount", "jackpot winner"
]

UPI_FRAUD_INDICATORS: List[str] = [
    "send ₹", "pay rupees", "processing fee", "registration fee",
    "upi id", "phonepe", "paytm", "google pay", "gpay", "bhim",
    "transfer amount", "small fee", "verification charge"
]

TECH_SUPPORT_INDICATORS: List[str] = [
    "microsoft", "windows", "virus", "malware", "trojan",
    "remote access", "anydesk", "teamviewer", "computer problem",
    "technical support", "customer care", "toll free"
]

INVESTMENT_INDICATORS: List[str] = [
    "investment", "trading", "forex", "crypto", "bitcoin",
    "stock tips", "guaranteed returns", "double", "triple",
    "monthly income", "work from home", "mlm", "network marketing"
]

ROMANCE_INDICATORS: List[str] = [
    "lonely", "love", "relationship", "marriage", "partner",
    "stuck abroad", "send money", "visa", "customs", "gift",
    "military", "oil rig", "engineer abroad"
]


def count_pattern_matches(text: str, pattern: Pattern) -> int:
    """Count matches of a pattern in text."""
    return len(pattern.findall(text))


def detect_urgency_level(text: str) -> int:
    """Detect urgency signals in text. Returns count of urgency indicators."""
    return count_pattern_matches(text, URGENCY_PATTERN)


def detect_greed_signals(text: str) -> int:
    """Detect greed exploitation signals. Returns count of greed indicators."""
    return count_pattern_matches(text, GREED_PATTERN)


def detect_fear_tactics(text: str) -> int:
    """Detect fear/threat tactics. Returns count of fear indicators."""
    return count_pattern_matches(text, FEAR_PATTERN)


def detect_authority_impersonation(text: str) -> int:
    """Detect authority impersonation. Returns count of authority claims."""
    return count_pattern_matches(text, AUTHORITY_PATTERN)


def quick_scam_indicators(text: str) -> List[str]:
    """Quick check for obvious scam indicators."""
    indicators = []
    
    if any(word.lower() in text.lower() for word in LOTTERY_SCAM_INDICATORS):
        indicators.append("lottery_scam_language")
    
    if any(word.lower() in text.lower() for word in UPI_FRAUD_INDICATORS):
        indicators.append("upi_fraud_language")
    
    if any(word.lower() in text.lower() for word in TECH_SUPPORT_INDICATORS):
        indicators.append("tech_support_language")
    
    if any(word.lower() in text.lower() for word in INVESTMENT_INDICATORS):
        indicators.append("investment_scam_language")
    
    if any(word.lower() in text.lower() for word in ROMANCE_INDICATORS):
        indicators.append("romance_scam_language")
    
    if detect_urgency_level(text) >= 2:
        indicators.append("high_urgency")
    
    if detect_greed_signals(text) >= 2:
        indicators.append("greed_exploitation")
    
    if detect_fear_tactics(text) >= 1:
        indicators.append("fear_tactics")
    
    if detect_authority_impersonation(text) >= 1:
        indicators.append("authority_impersonation")
    
    return indicators
