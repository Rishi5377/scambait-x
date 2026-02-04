"""
ScamBait-X V2 - spaCy Named Entity Recognition
Enhanced entity extraction using NLP models
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass

try:
    import spacy
    from spacy.tokens import Doc
    HAS_SPACY = True
except ImportError:
    HAS_SPACY = False
    spacy = None


@dataclass
class ExtractedEntity:
    """Extracted entity with metadata."""
    text: str
    label: str
    start: int
    end: int
    confidence: float = 1.0


# Custom entity labels for fraud detection
FRAUD_ENTITY_LABELS = {
    "MONEY": "money_amount",
    "CARDINAL": "number",
    "ORG": "organization",
    "PERSON": "person_name",
    "GPE": "location",
    "DATE": "date",
    "TIME": "time",
    "PERCENT": "percentage",
}


class NERExtractor:
    """
    Named Entity Recognition for enhanced entity extraction.
    Complements regex-based extraction with ML-based NER.
    """
    
    MODEL_NAME = "en_core_web_sm"
    
    def __init__(self):
        self._nlp = None
        self._loaded = False
    
    def is_available(self) -> bool:
        return HAS_SPACY
    
    async def initialize(self) -> bool:
        """Load the spaCy model."""
        if not HAS_SPACY:
            print("⚠️  spaCy not available, NER disabled")
            return False
        
        try:
            print(f"📦 Loading spaCy model: {self.MODEL_NAME}...")
            self._nlp = spacy.load(self.MODEL_NAME)
            self._loaded = True
            print("✅ NER engine ready")
            return True
        except OSError:
            # Model not downloaded
            print(f"⚠️  spaCy model '{self.MODEL_NAME}' not found, attempting download...")
            try:
                import subprocess
                subprocess.run(
                    ["python", "-m", "spacy", "download", self.MODEL_NAME],
                    check=True,
                    capture_output=True
                )
                self._nlp = spacy.load(self.MODEL_NAME)
                self._loaded = True
                print("✅ NER engine ready (model downloaded)")
                return True
            except Exception as e:
                print(f"⚠️  Failed to download spaCy model: {e}")
                return False
        except Exception as e:
            print(f"⚠️  Failed to load spaCy: {e}")
            return False
    
    def extract(self, text: str) -> List[ExtractedEntity]:
        """Extract named entities from text."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        entities = []
        
        for ent in doc.ents:
            mapped_label = FRAUD_ENTITY_LABELS.get(ent.label_, ent.label_.lower())
            entities.append(ExtractedEntity(
                text=ent.text,
                label=mapped_label,
                start=ent.start_char,
                end=ent.end_char,
                confidence=1.0  # spaCy doesn't provide confidence by default
            ))
        
        return entities
    
    def extract_money_amounts(self, text: str) -> List[Dict[str, Any]]:
        """Extract money amounts with context."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        amounts = []
        
        for ent in doc.ents:
            if ent.label_ == "MONEY":
                # Get surrounding context
                start = max(0, ent.start - 3)
                end = min(len(doc), ent.end + 3)
                context = doc[start:end].text
                
                amounts.append({
                    "amount": ent.text,
                    "context": context,
                    "position": (ent.start_char, ent.end_char)
                })
        
        return amounts
    
    def extract_organizations(self, text: str) -> List[str]:
        """Extract organization names (banks, companies)."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        orgs = []
        
        for ent in doc.ents:
            if ent.label_ == "ORG":
                orgs.append(ent.text)
        
        return list(set(orgs))
    
    def extract_persons(self, text: str) -> List[str]:
        """Extract person names."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        persons = []
        
        for ent in doc.ents:
            if ent.label_ == "PERSON":
                persons.append(ent.text)
        
        return list(set(persons))
    
    def extract_locations(self, text: str) -> List[str]:
        """Extract location names."""
        if not self._nlp:
            return []
        
        doc = self._nlp(text)
        locations = []
        
        for ent in doc.ents:
            if ent.label_ == "GPE":
                locations.append(ent.text)
        
        return list(set(locations))
    
    def get_text_stats(self, text: str) -> Dict[str, Any]:
        """Get text statistics for analysis."""
        if not self._nlp:
            return {}
        
        doc = self._nlp(text)
        
        return {
            "word_count": len([t for t in doc if not t.is_punct and not t.is_space]),
            "sentence_count": len(list(doc.sents)),
            "entity_count": len(doc.ents),
            "has_money": any(e.label_ == "MONEY" for e in doc.ents),
            "has_org": any(e.label_ == "ORG" for e in doc.ents),
            "has_person": any(e.label_ == "PERSON" for e in doc.ents),
        }
    
    def analyze_urgency(self, text: str) -> Dict[str, Any]:
        """Analyze text for urgency indicators using NLP."""
        if not self._nlp:
            return {"urgency_score": 0}
        
        doc = self._nlp(text)
        
        # Check for imperative sentences and urgency markers
        urgency_words = {"urgent", "immediately", "now", "hurry", "quick", "fast", "asap"}
        deadline_words = {"today", "hour", "minute", "deadline", "expires", "limited"}
        
        has_urgency = any(token.lemma_.lower() in urgency_words for token in doc)
        has_deadline = any(token.lemma_.lower() in deadline_words for token in doc)
        has_exclamation = "!" in text
        
        score = sum([has_urgency, has_deadline, has_exclamation])
        
        return {
            "urgency_score": score,
            "has_urgency_words": has_urgency,
            "has_deadline": has_deadline,
            "has_exclamation": has_exclamation
        }


# Singleton instance
ner_extractor = NERExtractor()


async def get_ner() -> NERExtractor:
    """Get NER extractor instance."""
    if not ner_extractor._loaded and ner_extractor.is_available():
        await ner_extractor.initialize()
    return ner_extractor
