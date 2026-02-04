"""
ScamBait-X Honeypot System
Mock Scammer API for Testing
"""

import asyncio
import random
from typing import List, Dict, Optional
from dataclasses import dataclass, field


@dataclass
class ScamScript:
    """Scripted scam conversation."""
    name: str
    scam_type: str
    messages: List[str]
    iocs_to_reveal: Dict[str, List[str]]  # turn_index -> IOCs to reveal
    end_trigger_turns: int = 12


# Scripted scam scenarios
SCAM_SCRIPTS: Dict[str, ScamScript] = {
    "lottery": ScamScript(
        name="KBC Lottery Scam",
        scam_type="lottery",
        messages=[
            "Congratulations! 🎉 You have won ₹25,00,000 in the KBC Lucky Draw! Your ticket number KBC-2024-7829 has been selected!",
            "Sir/Madam, this is 100% genuine. I am calling from KBC Mumbai office. You just need to pay small processing fee.",
            "The processing fee is only ₹4,999. Very small amount for 25 lakh prize money. You are very lucky!",
            "You need to pay registration fee through UPI or bank transfer. Very simple process.",
            "Please hurry! This offer expires in 24 hours only. Many people are waiting for this prize.",
            "My senior manager UPI ID is: kbcprize2024@ybl. Send ₹4,999 and your prize will be released immediately.",
            "You can also transfer to our official account: 9876543210123456 IFSC: SBIN0001234. State Bank of India.",
            "I understand your concern. Call our helpline +91 98765 43210 to verify. Ask for Mr. Sharma.",
            "Sir, time is running out! If you don't pay now, your prize will go to next winner. Don't miss this chance!",
            "Okay, one final offer - pay just ₹2,999 now and remaining after receiving prize. My Google Pay: 8765432109",
            "This is last warning. Prize pool closing in 1 hour. Decide now or lose ₹25,00,000 forever!",
            "Fine, you are missing once in lifetime opportunity. [SCAM ENDS - Target did not pay]"
        ],
        iocs_to_reveal={
            5: ["kbcprize2024@ybl"],
            6: ["9876543210123456", "SBIN0001234"],
            7: ["+91 98765 43210"],
            9: ["8765432109"],
        },
        end_trigger_turns=12
    ),
    
    "upi_fraud": ScamScript(
        name="Bank KYC UPI Fraud",
        scam_type="upi_fraud",
        messages=[
            "Dear Customer, your bank account will be BLOCKED in 24 hours. Complete KYC immediately to avoid account freeze.",
            "I am calling from SBI head office. Your KYC is pending. Account number ending 4567 will be suspended.",
            "No worry sir. Very simple process. Just need to verify your details and pay small verification fee.",
            "Sir, RBI has made this mandatory. Without KYC, all transactions will be blocked. Even ATM will not work.",
            "Verification fee is only ₹99. After that your account is safe for 5 years. No further charges.",
            "Please send ₹99 to our official verification UPI: sbikyc.verify@oksbi",
            "Sir, I can see your account is already flagged. If not done today, recovery will cost ₹5000 tomorrow.",
            "You can also pay through IMPS to: Account 1122334455667788 IFSC SBIN0000123. Immediate processing.",
            "For quick support call our KYC helpdesk: 7896541230. Open 24/7 for customer service.",
            "Sir your account showing CRITICAL status. Last chance - pay now or face legal action from bank.",
            "[System: Account blocked. Customer did not comply with KYC verification process]"
        ],
        iocs_to_reveal={
            5: ["sbikyc.verify@oksbi"],
            7: ["1122334455667788", "SBIN0000123"],
            8: ["7896541230"],
        },
        end_trigger_turns=11
    ),
    
    "tech_support": ScamScript(
        name="Microsoft Tech Support Scam",
        scam_type="tech_support",
        messages=[
            "ALERT! Your computer has been infected with TROJAN virus! Microsoft has detected suspicious activity from your IP address!",
            "Hello, I am John from Microsoft Windows Security Team. Your computer is sending virus to other computers.",
            "This is very serious. Hackers from China are using your computer. Your bank details may be compromised.",
            "Don't worry, I will help you. First download AnyDesk from anydesk.com. I will remove virus remotely.",
            "AnyDesk ID please? I need to connect to your computer to see the virus location.",
            "I can see the virus now. Very dangerous! I need to install Microsoft Security Tool. Cost is ₹15,999 for lifetime.",
            "Sir, without this tool, hackers will steal all your money. Your bank account is at risk RIGHT NOW.",
            "Payment options: UPI to microsoftsecurity@paytm or bank transfer to 5566778899001122 ICIC0000456",
            "You can also buy Google Play gift cards worth ₹16,000 and share the codes. This is secure payment method.",
            "Your computer will crash in 30 minutes if not fixed! Call our emergency line: +91 99887 76655",
            "I am disconnecting. Your computer is now permanently damaged. [SCAM ENDS]"
        ],
        iocs_to_reveal={
            3: ["https://anydesk.com"],
            7: ["microsoftsecurity@paytm", "5566778899001122", "ICIC0000456"],
            9: ["+91 99887 76655"],
        },
        end_trigger_turns=11
    ),
}


class MockScammer:
    """
    Mock scammer that follows scripted scenarios.
    Reveals IOCs progressively through the conversation.
    """
    
    def __init__(self, scam_type: str):
        if scam_type not in SCAM_SCRIPTS:
            raise ValueError(f"Unknown scam type: {scam_type}. Available: {list(SCAM_SCRIPTS.keys())}")
        
        self.script = SCAM_SCRIPTS[scam_type]
        self.current_turn = 0
        self.revealed_iocs: List[str] = []
        self.conversation_ended = False
    
    async def get_next_message(self, honeypot_response: Optional[str] = None) -> Optional[str]:
        """
        Get next scammer message based on turn count.
        Returns None if conversation has ended.
        """
        if self.conversation_ended:
            return None
        
        if self.current_turn >= len(self.script.messages):
            self.conversation_ended = True
            return None
        
        # Get current message
        message = self.script.messages[self.current_turn]
        
        # Check for IOCs to reveal at this turn
        if self.current_turn in self.script.iocs_to_reveal:
            self.revealed_iocs.extend(self.script.iocs_to_reveal[self.current_turn])
        
        # Add realistic delay (scammer "typing")
        delay = random.uniform(1.5, 4.0)
        await asyncio.sleep(delay)
        
        self.current_turn += 1
        
        # Check end trigger
        if self.current_turn >= self.script.end_trigger_turns:
            self.conversation_ended = True
        
        return message
    
    def get_revealed_iocs(self) -> List[str]:
        """Get all IOCs revealed so far."""
        return self.revealed_iocs.copy()
    
    def is_ended(self) -> bool:
        """Check if scam conversation has ended."""
        return self.conversation_ended
    
    def get_progress(self) -> dict:
        """Get conversation progress."""
        return {
            "scam_type": self.script.scam_type,
            "scam_name": self.script.name,
            "current_turn": self.current_turn,
            "total_turns": len(self.script.messages),
            "revealed_iocs": len(self.revealed_iocs),
            "ended": self.conversation_ended
        }


def create_mock_scammer(scam_type: str) -> MockScammer:
    """Create a mock scammer for testing."""
    return MockScammer(scam_type)


def list_scam_types() -> Dict[str, str]:
    """List available scam types with descriptions."""
    return {
        scam_type: script.name 
        for scam_type, script in SCAM_SCRIPTS.items()
    }
