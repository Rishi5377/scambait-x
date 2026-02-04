"""ScamBait-X Agent Package"""

from .personas import get_persona, get_persona_prompt, list_personas, PERSONAS
from .humanizer import ResponseHumanizer, create_humanizer
from .mode_switcher import ModeSwitcher, analyze_and_switch, mode_switcher
from .conversation import ConversationAgent, create_agent

__all__ = [
    "get_persona",
    "get_persona_prompt", 
    "list_personas",
    "PERSONAS",
    "ResponseHumanizer",
    "create_humanizer",
    "ModeSwitcher",
    "analyze_and_switch",
    "mode_switcher",
    "ConversationAgent",
    "create_agent",
]
