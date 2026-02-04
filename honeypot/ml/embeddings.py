"""
ScamBait-X V2 - Sentence Embeddings for Semantic Scam Detection
Uses sentence-transformers for similarity matching
"""

import os
from typing import List, Dict, Tuple, Optional
import hashlib

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_TRANSFORMERS = True
except ImportError:
    HAS_TRANSFORMERS = False
    SentenceTransformer = None
    np = None


# Known scam patterns with embeddings (will be computed on first load)
KNOWN_SCAM_PATTERNS = [
    # Lottery/Prize scams
    "Congratulations! You have won a lottery prize of 25 lakhs!",
    "Your lucky draw ticket has been selected for KBC prize money.",
    "You are the winner of our annual sweepstakes lottery.",
    
    # UPI/Banking fraud
    "Your bank account will be blocked if KYC is not updated.",
    "Complete your KYC verification to avoid account suspension.",
    "Your account has been flagged for suspicious activity.",
    
    # Tech support scams
    "Your computer has been infected with a dangerous virus.",
    "Microsoft has detected malware on your system.",
    "Your IP address has been compromised by hackers.",
    
    # Investment scams
    "Invest now and get 10x returns in just 30 days!",
    "Join our crypto trading group for guaranteed profits.",
    "Double your money with our exclusive investment opportunity.",
    
    # Romance scams
    "I need money for a medical emergency, please help.",
    "I am stuck abroad and need funds to come meet you.",
    "Send me gift cards so I can book my flight to see you.",
]


class EmbeddingEngine:
    """
    Semantic embedding engine for scam pattern matching.
    Uses sentence-transformers for fast, accurate similarity.
    """
    
    MODEL_NAME = "all-MiniLM-L6-v2"  # Fast, 384-dim embeddings
    
    def __init__(self):
        self._model: Optional[SentenceTransformer] = None
        self._pattern_embeddings: Optional[np.ndarray] = None
        self._embedding_cache: Dict[str, np.ndarray] = {}
    
    def is_available(self) -> bool:
        return HAS_TRANSFORMERS
    
    async def initialize(self) -> bool:
        """Load the model and compute pattern embeddings."""
        if not HAS_TRANSFORMERS:
            print("⚠️  sentence-transformers not available, semantic matching disabled")
            return False
        
        try:
            print(f"📦 Loading embedding model: {self.MODEL_NAME}...")
            self._model = SentenceTransformer(self.MODEL_NAME)
            
            # Pre-compute embeddings for known scam patterns
            self._pattern_embeddings = self._model.encode(
                KNOWN_SCAM_PATTERNS, 
                convert_to_numpy=True,
                show_progress_bar=False
            )
            
            print(f"✅ Embedding engine ready ({len(KNOWN_SCAM_PATTERNS)} patterns loaded)")
            return True
        except Exception as e:
            print(f"⚠️  Failed to load embedding model: {e}")
            return False
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key for text."""
        return hashlib.md5(text.encode()).hexdigest()
    
    def embed(self, text: str) -> Optional[np.ndarray]:
        """Get embedding for text (with caching)."""
        if not self._model:
            return None
        
        cache_key = self._get_cache_key(text)
        
        if cache_key in self._embedding_cache:
            return self._embedding_cache[cache_key]
        
        embedding = self._model.encode([text], convert_to_numpy=True)[0]
        self._embedding_cache[cache_key] = embedding
        
        return embedding
    
    def embed_batch(self, texts: List[str]) -> Optional[np.ndarray]:
        """Embed multiple texts efficiently."""
        if not self._model:
            return None
        
        return self._model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
    
    def find_similar_patterns(
        self, 
        text: str, 
        top_k: int = 3, 
        threshold: float = 0.5
    ) -> List[Tuple[str, float]]:
        """
        Find similar known scam patterns.
        Returns list of (pattern, similarity_score) tuples.
        """
        if not self._model or self._pattern_embeddings is None:
            return []
        
        text_embedding = self.embed(text)
        if text_embedding is None:
            return []
        
        # Compute cosine similarities
        similarities = np.dot(self._pattern_embeddings, text_embedding)
        similarities = similarities / (
            np.linalg.norm(self._pattern_embeddings, axis=1) * 
            np.linalg.norm(text_embedding)
        )
        
        # Get top-k above threshold
        results = []
        sorted_indices = np.argsort(similarities)[::-1]
        
        for idx in sorted_indices[:top_k]:
            score = float(similarities[idx])
            if score >= threshold:
                results.append((KNOWN_SCAM_PATTERNS[idx], score))
        
        return results
    
    def compute_scam_score(self, text: str) -> Tuple[float, List[str]]:
        """
        Compute overall scam probability based on similarity to known patterns.
        Returns (score, matching_patterns).
        """
        similar = self.find_similar_patterns(text, top_k=5, threshold=0.4)
        
        if not similar:
            return 0.0, []
        
        # Weighted score based on top matches
        max_score = similar[0][1] if similar else 0.0
        avg_score = sum(s for _, s in similar) / len(similar)
        
        # Combine max and avg (max weighted more heavily)
        combined_score = 0.7 * max_score + 0.3 * avg_score
        
        matching_patterns = [p for p, _ in similar]
        
        return round(combined_score, 3), matching_patterns
    
    def semantic_similarity(self, text1: str, text2: str) -> float:
        """Compute semantic similarity between two texts."""
        if not self._model:
            return 0.0
        
        emb1 = self.embed(text1)
        emb2 = self.embed(text2)
        
        if emb1 is None or emb2 is None:
            return 0.0
        
        similarity = np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2))
        return float(similarity)


# Singleton instance
embedding_engine = EmbeddingEngine()


async def get_embeddings() -> EmbeddingEngine:
    """Get embedding engine instance."""
    if not embedding_engine._model and embedding_engine.is_available():
        await embedding_engine.initialize()
    return embedding_engine
