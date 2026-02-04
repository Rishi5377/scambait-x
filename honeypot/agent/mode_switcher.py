"""
ScamBait-X Honeypot System
Dynamic Mode Switcher - Patience ↔ Aggressive
"""

from dataclasses import dataclass
from typing import List, Tuple
from ..models.schemas import ExtractionMode, Session
from ..detection.patterns import (
    detect_urgency_level,
    detect_greed_signals,
    detect_fear_tactics,
)


@dataclass
class ModeSwitchSignal:
    """Signal indicating mode should switch."""
    should_switch: bool
    new_mode: ExtractionMode
    reason: str
    urgency_score: int
    greed_score: int
    turn_count: int


class ModeSwitcher:
    """
    Analyzes scammer behavior to determine optimal extraction mode.
    
    Switches from PATIENCE to AGGRESSIVE when:
    - High urgency signals detected (scammer getting impatient)
    - Sufficient turns completed (enough rapport built)
    - Greed indicators high (scammer showing their hand)
    
    Stays in PATIENCE when:
    - Few turns completed (need more engagement)
    - Low urgency (scammer still building trust)
    """
    
    # Thresholds for mode switching
    MIN_TURNS_FOR_AGGRESSIVE: int = 4      # Need at least 4 turns
    URGENCY_THRESHOLD: int = 3             # 3+ urgency signals
    GREED_THRESHOLD: int = 2               # 2+ greed signals
    MAX_PATIENCE_TURNS: int = 12           # Switch after 12 turns regardless
    
    def __init__(self):
        self.switch_history: List[Tuple[int, ExtractionMode, str]] = []
    
    def analyze(self, session: Session, latest_scammer_message: str) -> ModeSwitchSignal:
        """
        Analyze session and latest message to determine if mode should switch.
        """
        current_mode = session.current_mode
        
        # Detect signals in latest message
        urgency = detect_urgency_level(latest_scammer_message)
        greed = detect_greed_signals(latest_scammer_message)
        fear = detect_fear_tactics(latest_scammer_message)
        
        # Update session counters
        session.urgency_signals += urgency
        session.greed_signals += greed
        
        # Cumulative signals
        total_urgency = session.urgency_signals
        total_greed = session.greed_signals
        turn_count = session.turn_count
        
        # Decision logic
        if current_mode == ExtractionMode.PATIENCE:
            should_switch, reason = self._should_switch_to_aggressive(
                turn_count, total_urgency, total_greed, fear
            )
            
            if should_switch:
                return ModeSwitchSignal(
                    should_switch=True,
                    new_mode=ExtractionMode.AGGRESSIVE,
                    reason=reason,
                    urgency_score=total_urgency,
                    greed_score=total_greed,
                    turn_count=turn_count
                )
        
        # Already aggressive or no switch needed
        return ModeSwitchSignal(
            should_switch=False,
            new_mode=current_mode,
            reason="Maintaining current mode",
            urgency_score=total_urgency,
            greed_score=total_greed,
            turn_count=turn_count
        )
    
    def _should_switch_to_aggressive(
        self, 
        turns: int, 
        urgency: int, 
        greed: int,
        fear: int
    ) -> Tuple[bool, str]:
        """
        Determine if should switch from PATIENCE to AGGRESSIVE.
        Returns (should_switch, reason).
        """
        # Too early - build more rapport
        if turns < self.MIN_TURNS_FOR_AGGRESSIVE:
            return False, "Building rapport (early turns)"
        
        # Max turns reached - time to extract
        if turns >= self.MAX_PATIENCE_TURNS:
            return True, f"Maximum patience turns reached ({turns})"
        
        # High urgency - scammer is impatient, time to extract
        if urgency >= self.URGENCY_THRESHOLD:
            return True, f"High urgency detected ({urgency} signals)"
        
        # Scammer showing greed - they're committed, time to extract
        if greed >= self.GREED_THRESHOLD:
            return True, f"Greed indicators high ({greed} signals)"
        
        # Fear tactics used - scammer getting aggressive, match them
        if fear >= 2:
            return True, f"Fear tactics detected ({fear} threats)"
        
        # Quick response pattern (implied urgency)
        # This would need timestamp analysis in full implementation
        
        return False, "Continuing patience mode"
    
    def force_switch(self, session: Session, mode: ExtractionMode, reason: str) -> None:
        """Force switch to a specific mode."""
        old_mode = session.current_mode
        session.current_mode = mode
        self.switch_history.append((session.turn_count, mode, reason))
    
    def get_mode_context(self, session: Session) -> str:
        """Get context string about current mode for prompts."""
        mode = session.current_mode
        turns = session.turn_count
        
        if mode == ExtractionMode.PATIENCE:
            return f"[MODE: PATIENCE | Turn {turns}] Building rapport, keep them engaged."
        else:
            return f"[MODE: AGGRESSIVE | Turn {turns}] Extract payment details NOW."


# Singleton instance
mode_switcher = ModeSwitcher()


def analyze_and_switch(session: Session, message: str) -> ModeSwitchSignal:
    """Convenience function to analyze message and get switch signal."""
    signal = mode_switcher.analyze(session, message)
    
    if signal.should_switch:
        session.current_mode = signal.new_mode
    
    return signal
