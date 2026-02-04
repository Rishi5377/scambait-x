"""
ScamBait-X Honeypot System
Configuration and Google Gemini LLM Integration
"""

import asyncio
import os
from time import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# Load environment variables
load_dotenv()


@dataclass
class Settings:
    """Application settings."""
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_model: str = "gemini-1.5-flash"  # Fast and capable
    rate_limit_per_minute: int = 60  # Gemini has higher limits
    max_conversation_turns: int = 10
    host: str = "0.0.0.0"
    port: int = 8000
    
    # Fallback to Groq if Gemini not available
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    
    def validate(self) -> bool:
        """Validate required settings."""
        return bool(self.gemini_api_key or self.groq_api_key)


class TokenBucketRateLimiter:
    """
    Token bucket algorithm for API rate limiting.
    """
    
    def __init__(self, tokens_per_minute: int = 60):
        self.max_tokens = tokens_per_minute
        self.tokens = float(tokens_per_minute)
        self.refill_rate = tokens_per_minute / 60.0
        self.last_refill = time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, timeout: float = 30.0) -> bool:
        start = time()
        while True:
            async with self._lock:
                self._refill()
                if self.tokens >= 1:
                    self.tokens -= 1
                    return True
            
            if time() - start > timeout:
                return False
            
            await asyncio.sleep(0.5)
    
    def _refill(self):
        now = time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    @property
    def available_tokens(self) -> int:
        self._refill()
        return int(self.tokens)


class GeminiClient:
    """Wrapper for Google Gemini LLM with rate limiting."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rate_limiter = TokenBucketRateLimiter(settings.rate_limit_per_minute)
        self._model = None
    
    @property
    def model(self):
        """Lazy initialization of Gemini model."""
        if self._model is None:
            import google.generativeai as genai
            
            if not self.settings.gemini_api_key:
                print("❌ GEMINI_API_KEY not set!")
                raise LLMError("GEMINI_API_KEY not configured")
            
            print(f"🔧 Configuring Gemini with key: {self.settings.gemini_api_key[:10]}...")
            genai.configure(api_key=self.settings.gemini_api_key)
            
            self._model = genai.GenerativeModel(
                model_name=self.settings.gemini_model,
                generation_config={
                    "temperature": 0.8,
                    "max_output_tokens": 256,
                }
            )
            print(f"✅ Gemini model '{self.settings.gemini_model}' ready!")
        return self._model
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Generate a response with rate limiting.
        """
        if not await self.rate_limiter.acquire(timeout=15.0):
            raise RateLimitExceeded("Rate limit exceeded. Please wait.")
        
        # Combine system prompt and user prompt for Gemini
        full_prompt = f"{system_prompt}\n\n{prompt}" if system_prompt else prompt
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, full_prompt
            )
            return response.text
        except Exception as e:
            raise LLMError(f"Gemini generation failed: {str(e)}")
    
    async def classify_with_structured_output(self, text: str, system_prompt: str) -> str:
        """Classify text and return structured response."""
        if not await self.rate_limiter.acquire(timeout=10.0):
            raise RateLimitExceeded("Rate limit exceeded for classification.")
        
        full_prompt = f"{system_prompt}\n\nAnalyze this message:\n\n{text}"
        
        try:
            response = await asyncio.to_thread(
                self.model.generate_content, full_prompt
            )
            return response.text
        except Exception as e:
            raise LLMError(f"Classification failed: {str(e)}")


class RateLimitExceeded(Exception):
    """Raised when rate limit is exceeded."""
    pass


class LLMError(Exception):
    """Raised when LLM call fails."""
    pass


# Global instances
settings = Settings()

# Use Gemini as primary, keep groq_client name for compatibility
groq_client = GeminiClient(settings)
