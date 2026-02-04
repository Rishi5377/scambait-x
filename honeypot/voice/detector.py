"""
ScamBait-X Voice Detection Module
Real-time scam detection from voice transcripts
"""

import re
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass

# Scam indicator keywords with weights
SCAM_INDICATORS = {
    # Tech support scam
    "your computer": 0.3,
    "virus": 0.4,
    "malware": 0.4,
    "microsoft": 0.2,
    "tech support": 0.5,
    "remote access": 0.5,
    "infected": 0.4,
    "hacked": 0.4,
    
    # Lottery/Prize scam
    "congratulations": 0.3,
    "you have won": 0.5,
    "lucky winner": 0.5,
    "prize money": 0.5,
    "lottery": 0.5,
    "lucky draw": 0.5,
    "kbc": 0.6,
    "kaun banega crorepati": 0.6,
    "lakh": 0.2,
    "crore": 0.2,
    
    # UPI/Banking fraud
    "kyc": 0.3,
    "kyc verification": 0.5,
    "account blocked": 0.5,
    "account suspended": 0.5,
    "update your details": 0.4,
    "bank account": 0.2,
    "pan card": 0.2,
    "aadhaar": 0.2,
    "upi": 0.2,
    "paytm": 0.2,
    "google pay": 0.2,
    "phonepe": 0.2,
    
    # Urgency indicators
    "urgent": 0.3,
    "immediately": 0.3,
    "right now": 0.3,
    "within 24 hours": 0.4,
    "last chance": 0.4,
    "act now": 0.4,
    "don't delay": 0.4,
    "limited time": 0.3,
    
    # Money request
    "send money": 0.5,
    "transfer": 0.2,
    "processing fee": 0.5,
    "registration fee": 0.5,
    "tax": 0.2,
    "pay first": 0.5,
    "advance payment": 0.5,
    
    # Impersonation
    "government": 0.2,
    "police": 0.3,
    "income tax": 0.3,
    "department": 0.2,
    "official": 0.2,
    "officer": 0.2,
    
    # Fear tactics
    "arrest": 0.4,
    "legal action": 0.4,
    "case filed": 0.4,
    "fir": 0.4,
    "court": 0.3,
    "jail": 0.4,
}

# Scam type patterns
SCAM_TYPE_PATTERNS = {
    "tech_support": [
        r"your (?:computer|pc|laptop) (?:is|has)",
        r"microsoft|windows|apple",
        r"virus|malware|infected|hacked",
        r"remote (?:access|desktop)",
    ],
    "lottery": [
        r"(?:won|winner|prize|lottery)",
        r"kbc|lucky draw",
        r"(?:lakh|crore) (?:rupees)?",
        r"congratulations",
    ],
    "upi_fraud": [
        r"kyc|account (?:blocked|suspended)",
        r"bank|upi|paytm|phonepe",
        r"update (?:your )?(?:details|information)",
        r"(?:pan|aadhaar) (?:card|number)?",
    ],
    "investment": [
        r"invest|investment|returns",
        r"(?:double|triple) your money",
        r"guaranteed (?:returns|profit)",
        r"crypto|bitcoin|trading",
    ],
}


@dataclass
class ScamAnalysis:
    """Result of scam analysis."""
    score: float  # 0.0 to 1.0
    scam_type: str
    indicators: List[str]
    is_scammer: bool
    confidence: str  # "low", "medium", "high"


class VoiceScamDetector:
    """
    Detects potential scam calls from voice transcripts.
    Uses keyword matching and pattern analysis.
    """
    
    def __init__(self, threshold: float = 0.6):
        self.threshold = threshold
        self.history: List[str] = []
        self.cumulative_score = 0.0
        self.detected_indicators: List[str] = []
    
    def analyze(self, transcript: str) -> ScamAnalysis:
        """
        Analyze a transcript segment for scam indicators.
        Returns ScamAnalysis with score and detected patterns.
        """
        self.history.append(transcript)
        
        # Combine recent history for context
        context = " ".join(self.history[-5:]).lower()
        
        # Calculate score from indicators
        score = 0.0
        indicators = []
        
        for keyword, weight in SCAM_INDICATORS.items():
            if keyword.lower() in context:
                score += weight
                indicators.append(keyword)
        
        # Detect scam type
        scam_type = self._detect_scam_type(context)
        
        # Normalize score (cap at 1.0)
        score = min(score, 1.0)
        
        # Update cumulative (rolling average)
        self.cumulative_score = (self.cumulative_score * 0.7) + (score * 0.3)
        self.detected_indicators.extend(indicators)
        self.detected_indicators = list(set(self.detected_indicators))
        
        # Use cumulative for final score
        final_score = max(score, self.cumulative_score)
        
        # Determine confidence level
        if final_score < 0.3:
            confidence = "low"
        elif final_score < 0.6:
            confidence = "medium"
        else:
            confidence = "high"
        
        return ScamAnalysis(
            score=round(final_score, 2),
            scam_type=scam_type,
            indicators=indicators,
            is_scammer=final_score >= self.threshold,
            confidence=confidence
        )
    
    def _detect_scam_type(self, text: str) -> str:
        """Detect the type of scam based on patterns."""
        scores = {}
        
        for scam_type, patterns in SCAM_TYPE_PATTERNS.items():
            count = 0
            for pattern in patterns:
                if re.search(pattern, text, re.IGNORECASE):
                    count += 1
            scores[scam_type] = count
        
        if max(scores.values()) == 0:
            return "unknown"
        
        return max(scores, key=scores.get)
    
    def reset(self):
        """Reset detector state for new call."""
        self.history = []
        self.cumulative_score = 0.0
        self.detected_indicators = []
    
    def get_summary(self) -> Dict[str, Any]:
        """Get detection summary."""
        return {
            "total_segments": len(self.history),
            "cumulative_score": round(self.cumulative_score, 2),
            "all_indicators": self.detected_indicators,
            "is_scammer": self.cumulative_score >= self.threshold
        }


# Singleton for easy access
voice_detector = VoiceScamDetector()


def analyze_transcript(transcript: str) -> ScamAnalysis:
    """Quick function to analyze a single transcript."""
    return voice_detector.analyze(transcript)


def create_detector(threshold: float = 0.6) -> VoiceScamDetector:
    """Create a new detector instance."""
    return VoiceScamDetector(threshold=threshold)
