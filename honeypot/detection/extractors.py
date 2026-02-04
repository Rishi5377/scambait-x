"""
ScamBait-X Honeypot System
Entity Extraction Pipeline
"""

from typing import List, Set
import re

from ..models.schemas import (
    ExtractedEntities,
    BankAccount,
    CryptoAddress,
)
from .patterns import (
    UPI_PATTERN,
    INDIAN_PHONE_PATTERN,
    BANK_ACCOUNT_PATTERN,
    IFSC_PATTERN,
    BITCOIN_PATTERN,
    ETHEREUM_PATTERN,
    URL_PATTERN,
    SHORT_URL_PATTERN,
    EMAIL_PATTERN,
)


class EntityExtractor:
    """
    Extracts fraud-related entities from text.
    Supports UPI IDs, phone numbers, bank accounts, crypto addresses, URLs, and emails.
    """
    
    # Known UPI handles to validate UPI IDs
    KNOWN_UPI_HANDLES: Set[str] = {
        "upi", "paytm", "ybl", "oksbi", "okaxis", "okicici", "okhdfcbank",
        "apl", "axisb", "barodampay", "cboi", "citi", "citibank", "dbs",
        "fbl", "federal", "hdfcbank", "hsbc", "ibl", "icici", "idbi",
        "idbibank", "idfcbank", "ikwik", "indus", "kotak", "mahb",
        "obc", "pnb", "pockets", "PSB", "rbl", "sbi", "sc", "scb",
        "scbl", "sib", "syndicate", "ubi", "uboi", "uco", "unionbank",
        "united", "utbi", "vijb", "yesbank"
    }
    
    def __init__(self):
        self._extracted: ExtractedEntities = ExtractedEntities()
    
    def extract_all(self, text: str) -> ExtractedEntities:
        """
        Extract all entities from text.
        Returns ExtractedEntities with deduplicated results.
        """
        return ExtractedEntities(
            upi_ids=self._extract_upi_ids(text),
            phone_numbers=self._extract_phone_numbers(text),
            bank_accounts=self._extract_bank_accounts(text),
            crypto_addresses=self._extract_crypto_addresses(text),
            urls=self._extract_urls(text),
            email_addresses=self._extract_emails(text),
        )
    
    def _extract_upi_ids(self, text: str) -> List[str]:
        """Extract valid UPI IDs."""
        candidates = UPI_PATTERN.findall(text)
        valid_upis = []
        
        for candidate in candidates:
            # Check if it looks like a valid UPI (not an email or general handle)
            parts = candidate.split("@")
            if len(parts) == 2:
                handle = parts[1].lower()
                # Either known handle or looks phone-based
                if handle in self.KNOWN_UPI_HANDLES or parts[0].isdigit():
                    if candidate.lower() not in [u.lower() for u in valid_upis]:
                        valid_upis.append(candidate)
        
        return valid_upis
    
    def _extract_phone_numbers(self, text: str) -> List[str]:
        """Extract and normalize Indian phone numbers."""
        matches = INDIAN_PHONE_PATTERN.findall(text)
        normalized = []
        seen_normalized = set()
        
        for match in matches:
            # Normalize: keep only digits
            digits = re.sub(r'\D', '', match)
            
            # Handle +91 prefix
            if len(digits) > 10 and digits.startswith("91"):
                digits = digits[2:]
            
            # Must be 10 digits for Indian mobile
            if len(digits) == 10 and digits[0] in "6789":
                norm_key = digits
                if norm_key not in seen_normalized:
                    seen_normalized.add(norm_key)
                    # Format nicely
                    formatted = f"+91 {digits[:5]} {digits[5:]}"
                    normalized.append(formatted)
        
        return normalized
    
    def _extract_bank_accounts(self, text: str) -> List[BankAccount]:
        """Extract bank account numbers with IFSC codes."""
        accounts = []
        seen = set()
        
        # Find potential account numbers
        account_matches = BANK_ACCOUNT_PATTERN.findall(text)
        
        # Find IFSC codes
        ifsc_matches = IFSC_PATTERN.findall(text)
        
        # Try to pair accounts with IFSC codes
        for acc_num in account_matches:
            if acc_num in seen:
                continue
            
            # Validate: not a phone number (10 digits starting with 6-9)
            if len(acc_num) == 10 and acc_num[0] in "6789":
                continue
            
            # Check if too short (likely not an account)
            if len(acc_num) < 9:
                continue
            
            seen.add(acc_num)
            
            # Try to find nearby IFSC
            ifsc = None
            if ifsc_matches:
                # Use first available IFSC (simple heuristic)
                ifsc = ifsc_matches[0].upper()
            
            # Guess bank from IFSC
            bank_name = self._bank_from_ifsc(ifsc) if ifsc else None
            
            accounts.append(BankAccount(
                account_number=acc_num,
                ifsc_code=ifsc,
                bank_name=bank_name
            ))
        
        return accounts
    
    def _bank_from_ifsc(self, ifsc: str) -> str:
        """Guess bank name from IFSC prefix."""
        if not ifsc:
            return None
        
        prefix = ifsc[:4].upper()
        bank_map = {
            "SBIN": "State Bank of India",
            "HDFC": "HDFC Bank",
            "ICIC": "ICICI Bank",
            "AXIS": "Axis Bank",
            "KKBK": "Kotak Mahindra Bank",
            "UTIB": "Axis Bank",
            "PUNB": "Punjab National Bank",
            "BARB": "Bank of Baroda",
            "CNRB": "Canara Bank",
            "UBIN": "Union Bank of India",
            "IDIB": "IDBI Bank",
            "YESB": "Yes Bank",
            "INDB": "IndusInd Bank",
            "FDRL": "Federal Bank",
            "IDFB": "IDFC First Bank",
        }
        return bank_map.get(prefix, None)
    
    def _extract_crypto_addresses(self, text: str) -> List[CryptoAddress]:
        """Extract cryptocurrency addresses."""
        addresses = []
        seen = set()
        
        # Bitcoin
        for match in BITCOIN_PATTERN.findall(text):
            if match not in seen:
                seen.add(match)
                addresses.append(CryptoAddress(address=match, currency="BTC"))
        
        # Ethereum
        for match in ETHEREUM_PATTERN.findall(text):
            if match.lower() not in [a.address.lower() for a in addresses]:
                addresses.append(CryptoAddress(address=match, currency="ETH"))
        
        return addresses
    
    def _extract_urls(self, text: str) -> List[str]:
        """Extract URLs including shortened ones."""
        urls = []
        seen = set()
        
        # Full URLs
        for match in URL_PATTERN.findall(text):
            normalized = match.lower().rstrip("/")
            if normalized not in seen:
                seen.add(normalized)
                urls.append(match)
        
        # Shortened URLs without https://
        for match in SHORT_URL_PATTERN.findall(text):
            full_url = f"https://{match}"
            normalized = full_url.lower()
            if normalized not in seen:
                seen.add(normalized)
                urls.append(full_url)
        
        return urls
    
    def _extract_emails(self, text: str) -> List[str]:
        """Extract email addresses (excluding UPI IDs)."""
        all_emails = EMAIL_PATTERN.findall(text)
        
        # Filter out UPI IDs (which look like emails)
        valid_emails = []
        seen = set()
        
        for email in all_emails:
            domain = email.split("@")[1].lower() if "@" in email else ""
            
            # Skip UPI handles
            handle = domain.split(".")[0] if "." in domain else domain
            if handle in self.KNOWN_UPI_HANDLES:
                continue
            
            # Must have proper domain
            if "." not in domain:
                continue
            
            lower_email = email.lower()
            if lower_email not in seen:
                seen.add(lower_email)
                valid_emails.append(email)
        
        return valid_emails


# Singleton instance
extractor = EntityExtractor()


def extract_entities(text: str) -> ExtractedEntities:
    """Convenience function to extract all entities from text."""
    return extractor.extract_all(text)
