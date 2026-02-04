"""
ScamBait-X Honeypot System
Response Humanizer - Add realistic typing delays, typos, and hesitation
"""

import random
import asyncio
from typing import List, Tuple
from ..models.schemas import Persona


# Hesitation markers by persona age
ELDERLY_HESITATIONS: List[str] = [
    "um...", "well...", "let me think...", "hmm...", 
    "I'm not sure...", "what was I saying...", "oh dear...",
    "one moment beta...", "arre..."
]

YOUNG_HESITATIONS: List[str] = [
    "hmm", "let me check", "one sec", "wait",
    "actually", "so basically"
]

BUSINESS_HESITATIONS: List[str] = [
    "well...", "let me think about this...", "hmm...",
    "one moment...", "okay so..."
]

# Common typos (character swaps)
TYPO_SWAPS: List[Tuple[str, str]] = [
    ("the", "teh"),
    ("and", "adn"),
    ("you", "yuo"),
    ("money", "monye"),
    ("send", "sedn"),
    ("bank", "bnak"),
    ("account", "accoutn"),
    ("please", "plase"),
    ("transfer", "tranfer"),
    ("payment", "paymnet"),
]


class ResponseHumanizer:
    """
    Add human-like characteristics to AI responses:
    - Typing delays based on message length and persona
    - Occasional typos (more for elderly)
    - Hesitation markers
    - Message fragmentation
    """
    
    def __init__(self, persona: Persona):
        self.persona = persona
    
    def calculate_typing_delay_ms(self, message: str) -> int:
        """
        Calculate realistic typing delay based on message length and persona.
        Returns delay in milliseconds.
        """
        # Base: 50ms per character for average typist
        base_per_char = 50
        
        # Adjust by persona typing speed (0.3 = slow, 0.8 = fast)
        speed_multiplier = 1.5 - self.persona.typing_speed  # 0.3 -> 1.2x, 0.8 -> 0.7x
        
        char_count = len(message)
        
        # Base delay
        delay = char_count * base_per_char * speed_multiplier
        
        # Add "thinking" time (1-3 seconds)
        thinking_time = random.randint(1000, 3000)
        
        # Elderly personas think longer
        if self.persona.age > 60:
            thinking_time += random.randint(1000, 2000)
        
        total_delay = int(delay + thinking_time)
        
        # Cap at reasonable bounds
        return max(1500, min(total_delay, 8000))
    
    def inject_typos(self, message: str) -> str:
        """
        Inject typos based on persona's typo rate.
        """
        if random.random() > self.persona.typo_rate * 20:  # Scale up for visibility
            return message
        
        # Pick a random typo to inject
        eligible_swaps = [(old, new) for old, new in TYPO_SWAPS if old in message.lower()]
        
        if not eligible_swaps:
            return message
        
        old, new = random.choice(eligible_swaps)
        
        # Replace first occurrence (case-insensitive but preserve some case)
        import re
        pattern = re.compile(re.escape(old), re.IGNORECASE)
        result = pattern.sub(new, message, count=1)
        
        return result
    
    def add_hesitation(self, message: str) -> str:
        """
        Optionally add hesitation markers at the start.
        """
        # 30% chance for elderly, 10% for others
        hesitation_chance = 0.3 if self.persona.age > 60 else 0.1
        
        if random.random() > hesitation_chance:
            return message
        
        # Pick appropriate hesitations
        if self.persona.age > 60:
            hesitations = ELDERLY_HESITATIONS
        elif self.persona.age < 35:
            hesitations = YOUNG_HESITATIONS
        else:
            hesitations = BUSINESS_HESITATIONS
        
        hesitation = random.choice(hesitations)
        
        # Add at start with proper capitalization
        if message and message[0].isupper():
            message = message[0].lower() + message[1:]
        
        return f"{hesitation} {message}"
    
    def fragment_message(self, message: str) -> List[str]:
        """
        Split long messages into fragments (like real texting).
        Only for elderly personas or long messages.
        """
        # Only fragment for elderly or long messages
        if self.persona.age <= 60 and len(message) < 100:
            return [message]
        
        # 40% chance to fragment
        if random.random() > 0.4:
            return [message]
        
        # Split on sentence boundaries
        import re
        sentences = re.split(r'(?<=[.!?])\s+', message)
        
        if len(sentences) <= 1:
            return [message]
        
        # Group into 1-2 sentence fragments
        fragments = []
        current = []
        
        for sentence in sentences:
            current.append(sentence)
            if len(current) >= random.randint(1, 2):
                fragments.append(" ".join(current))
                current = []
        
        if current:
            fragments.append(" ".join(current))
        
        return fragments if fragments else [message]
    
    def humanize(self, message: str) -> Tuple[str, int]:
        """
        Apply all humanization to a message.
        Returns (humanized_message, typing_delay_ms).
        """
        # Apply transformations
        result = message
        result = self.add_hesitation(result)
        result = self.inject_typos(result)
        
        # Calculate delay
        delay = self.calculate_typing_delay_ms(message)
        
        return result, delay
    
    async def humanize_and_wait(self, message: str) -> str:
        """
        Humanize message and wait for typing delay.
        """
        humanized, delay = self.humanize(message)
        await asyncio.sleep(delay / 1000)  # Convert to seconds
        return humanized


def create_humanizer(persona: Persona) -> ResponseHumanizer:
    """Create a humanizer for a persona."""
    return ResponseHumanizer(persona)
