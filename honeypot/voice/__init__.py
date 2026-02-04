"""ScamBait-X Voice Detection Package"""

from .detector import (
    VoiceScamDetector,
    ScamAnalysis,
    voice_detector,
    analyze_transcript,
    create_detector,
)

__all__ = [
    "VoiceScamDetector",
    "ScamAnalysis",
    "voice_detector",
    "analyze_transcript",
    "create_detector",
]
