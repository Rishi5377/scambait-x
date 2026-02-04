"""
ScamBait-X Honeypot System
Configuration and Groq LLM Integration
"""

import asyncio
import os
from time import time
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv
from langchain_groq import ChatGroq

# Load environment variables
load_dotenv()


@dataclass
class Settings:
    """Application settings."""
    groq_api_key: str = os.getenv("GROQ_API_KEY", "")
    groq_model: str = "llama-3.3-70b-versatile"  # Updated from decommissioned llama3-70b-8192
    rate_limit_per_minute: int = 30
    max_conversation_turns: int = 10
    host: str = "0.0.0.0"
    port: int = 8000
    
    def validate(self) -> bool:
        """Validate required settings."""
        if not self.groq_api_key or self.groq_api_key == "gsk_your_api_key_here":
            return False
        return True


class TokenBucketRateLimiter:
    """
    Token bucket algorithm for Groq API rate limiting.
    Refills 30 tokens per minute (1 token every 2 seconds).
    """
    
    def __init__(self, tokens_per_minute: int = 30):
        self.max_tokens = tokens_per_minute
        self.tokens = float(tokens_per_minute)
        self.refill_rate = tokens_per_minute / 60.0  # tokens per second
        self.last_refill = time()
        self._lock = asyncio.Lock()
    
    async def acquire(self, timeout: float = 30.0) -> bool:
        """
        Acquire a token. Blocks until token available or timeout.
        Returns True if acquired, False if timeout.
        """
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
        """Refill tokens based on elapsed time."""
        now = time()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
    
    @property
    def available_tokens(self) -> int:
        """Get current available tokens."""
        self._refill()
        return int(self.tokens)


class GroqClient:
    """Wrapper for Groq LLM with rate limiting."""
    
    def __init__(self, settings: Settings):
        self.settings = settings
        self.rate_limiter = TokenBucketRateLimiter(settings.rate_limit_per_minute)
        self._llm: Optional[ChatGroq] = None
    
    @property
    def llm(self) -> ChatGroq:
        """Lazy initialization of LLM client."""
        if self._llm is None:
            self._llm = ChatGroq(
                api_key=self.settings.groq_api_key,
                model=self.settings.groq_model,
                temperature=0.7,
                max_tokens=512,
            )
        return self._llm
    
    async def generate(self, prompt: str, system_prompt: str = "") -> str:
        """
        Generate a response with rate limiting.
        Returns response text or raises exception on timeout.
        """
        if not await self.rate_limiter.acquire(timeout=15.0):
            raise RateLimitExceeded("Rate limit exceeded. Please wait.")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        
        try:
            response = await asyncio.to_thread(
                self.llm.invoke, messages
            )
            return response.content
        except Exception as e:
            raise LLMError(f"LLM generation failed: {str(e)}")
    
    async def classify_with_structured_output(
        self, 
        text: str, 
        system_prompt: str
    ) -> str:
        """
        Classify text and return structured JSON response.
        """
        if not await self.rate_limiter.acquire(timeout=10.0):
            raise RateLimitExceeded("Rate limit exceeded for classification.")
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": f"Analyze this message:\n\n{text}"}
        ]
        
        try:
            response = await asyncio.to_thread(
                self.llm.invoke, messages
            )
            return response.content
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
groq_client = GroqClient(settings)
