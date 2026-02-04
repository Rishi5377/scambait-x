"""ScamBait-X Detection Package"""

from .patterns import (
    detect_urgency_level,
    detect_greed_signals,
    detect_fear_tactics,
    detect_authority_impersonation,
    quick_scam_indicators,
)
from .extractors import extract_entities, EntityExtractor
from .classifier import classify_scam, ScamClassifier

__all__ = [
    "detect_urgency_level",
    "detect_greed_signals",
    "detect_fear_tactics",
    "detect_authority_impersonation",
    "quick_scam_indicators",
    "extract_entities",
    "EntityExtractor",
    "classify_scam",
    "ScamClassifier",
]
