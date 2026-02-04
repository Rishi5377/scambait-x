"""
ScamBait-X Honeypot System
Hybrid Scam Classification (Regex + LLM)
"""

import json
from typing import Optional

from ..config import groq_client, RateLimitExceeded, LLMError
from ..models.schemas import ScamClassification, ScamType
from .patterns import (
    quick_scam_indicators,
    LOTTERY_SCAM_INDICATORS,
    UPI_FRAUD_INDICATORS,
    TECH_SUPPORT_INDICATORS,
    INVESTMENT_INDICATORS,
    ROMANCE_INDICATORS,
)


# System prompt for LLM classification
CLASSIFICATION_SYSTEM_PROMPT = """You are a fraud detection AI specializing in Indian scam patterns.
Analyze the given message and classify it.

Output ONLY valid JSON in this exact format:
{
    "scam_type": "lottery|upi_fraud|tech_support|investment|romance|unknown",
    "confidence": 0.0-1.0,
    "indicators": ["list", "of", "detected", "patterns"]
}

Scam types:
- lottery: Fake prize/lottery/lucky draw schemes
- upi_fraud: UPI payment frauds, processing fee scams
- tech_support: Fake Microsoft/tech support, remote access scams  
- investment: Fake investment, trading, crypto schemes
- romance: Romance scams, emergency money requests
- unknown: Cannot determine or not a scam

Be precise. Look for Indian context: UPI, rupees, Indian banks, etc."""


class ScamClassifier:
    """
    Hybrid scam classifier using regex pre-filter + LLM.
    Fast regex check first, LLM for confirmation and detailed analysis.
    """
    
    def __init__(self, use_llm: bool = True):
        self.use_llm = use_llm
    
    async def classify(self, text: str) -> ScamClassification:
        """
        Classify text for scam indicators.
        Uses regex first, then LLM for confirmation if available.
        """
        # Step 1: Fast regex pre-filter
        regex_result = self._regex_classify(text)
        
        # If clear regex match with high confidence, skip LLM
        if regex_result.confidence >= 0.8:
            return regex_result
        
        # Step 2: LLM classification for uncertain cases
        if self.use_llm and regex_result.confidence < 0.8:
            try:
                llm_result = await self._llm_classify(text)
                
                # Merge results - prefer LLM but keep regex indicators
                if llm_result.confidence > regex_result.confidence:
                    llm_result.indicators = list(set(
                        llm_result.indicators + regex_result.indicators
                    ))
                    return llm_result
            except (RateLimitExceeded, LLMError):
                # Fall back to regex result
                pass
        
        return regex_result
    
    def _regex_classify(self, text: str) -> ScamClassification:
        """Fast regex-based classification."""
        text_lower = text.lower()
        indicators = quick_scam_indicators(text)
        
        # Count matches for each scam type
        scores = {
            ScamType.LOTTERY: sum(1 for w in LOTTERY_SCAM_INDICATORS if w.lower() in text_lower),
            ScamType.UPI_FRAUD: sum(1 for w in UPI_FRAUD_INDICATORS if w.lower() in text_lower),
            ScamType.TECH_SUPPORT: sum(1 for w in TECH_SUPPORT_INDICATORS if w.lower() in text_lower),
            ScamType.INVESTMENT: sum(1 for w in INVESTMENT_INDICATORS if w.lower() in text_lower),
            ScamType.ROMANCE: sum(1 for w in ROMANCE_INDICATORS if w.lower() in text_lower),
        }
        
        # Find highest scoring type
        max_score = max(scores.values())
        
        if max_score == 0:
            return ScamClassification(
                scam_type=ScamType.UNKNOWN,
                confidence=0.0,
                indicators=indicators
            )
        
        # Get scam type with highest score
        scam_type = max(scores, key=scores.get)
        
        # Calculate confidence based on match count
        # More matches = higher confidence
        confidence = min(0.3 + (max_score * 0.15), 0.9)
        
        # Boost confidence if multiple signal types detected
        if len(indicators) >= 3:
            confidence = min(confidence + 0.1, 0.95)
        
        return ScamClassification(
            scam_type=scam_type,
            confidence=round(confidence, 2),
            indicators=indicators
        )
    
    async def _llm_classify(self, text: str) -> ScamClassification:
        """LLM-based classification for detailed analysis."""
        try:
            response = await groq_client.classify_with_structured_output(
                text=text,
                system_prompt=CLASSIFICATION_SYSTEM_PROMPT
            )
            
            # Parse JSON response
            return self._parse_llm_response(response)
            
        except Exception as e:
            raise LLMError(f"Classification failed: {str(e)}")
    
    def _parse_llm_response(self, response: str) -> ScamClassification:
        """Parse LLM JSON response into ScamClassification."""
        try:
            # Try to extract JSON from response
            # Handle cases where LLM adds extra text
            json_start = response.find("{")
            json_end = response.rfind("}") + 1
            
            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")
            
            json_str = response[json_start:json_end]
            data = json.loads(json_str)
            
            # Map scam type string to enum
            scam_type_str = data.get("scam_type", "unknown").lower()
            scam_type_map = {
                "lottery": ScamType.LOTTERY,
                "upi_fraud": ScamType.UPI_FRAUD,
                "tech_support": ScamType.TECH_SUPPORT,
                "investment": ScamType.INVESTMENT,
                "romance": ScamType.ROMANCE,
                "unknown": ScamType.UNKNOWN,
            }
            scam_type = scam_type_map.get(scam_type_str, ScamType.UNKNOWN)
            
            return ScamClassification(
                scam_type=scam_type,
                confidence=min(max(float(data.get("confidence", 0.5)), 0.0), 1.0),
                indicators=data.get("indicators", [])
            )
            
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            # Return low-confidence unknown if parsing fails
            return ScamClassification(
                scam_type=ScamType.UNKNOWN,
                confidence=0.3,
                indicators=["llm_parse_error"]
            )


# Singleton instance
classifier = ScamClassifier(use_llm=True)


async def classify_scam(text: str) -> ScamClassification:
    """Convenience function to classify text for scams."""
    return await classifier.classify(text)
