"""
banks/chase.py
--------------
Chase Bank statement parser.

Detected by: "JPMorgan Chase" or "Chase" header, plus "through" date range.

Summary extraction reads the Account Activity Summary block which has:
  - "Deposits and Additions         $X,XXX.XX"
  - "ATM & Debit Card Withdrawals   $X,XXX.XX"
  - "Electronic Withdrawals          $X,XXX.XX"
  - "Checks Paid                     $X,XXX.XX"
  - "Service Fees                    $X,XXX.XX"

NSF: Chase prints returned items in an "Items returned unpaid" section.
POS: Counted from transaction descriptions containing "POS".
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class ChaseParser(BankParser):

    NAME = "Chase"

    # -----------------------------------------------------------------------
    # Bank identification
    # -----------------------------------------------------------------------

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        return bool(
            re.search(r"\bJPMORGAN\b|\bCHASE\b", flat)
            and re.search(r"\bTHROUGH\b", flat)
        )

    # -----------------------------------------------------------------------
    # Summary extraction
    # -----------------------------------------------------------------------

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        credits = cls._grab_amount(
            r"Deposits\s+and\s+Additions\s+\$?([\d,]+\.\d{2})",
            flat,
        )

        # Debits: sum all withdrawal/fee categories
        debit_patterns = [
            r"ATM\s*&?\s*Debit\s+Card\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Checks\s*Paid\s+\$?([\d,]+\.\d{2})",
            r"Service\s+Fees?\s+\$?([\d,]+\.\d{2})",
            r"Other\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
        ]
        debits = sum(
            abs(clean_money(m.group(1)))
            for p in debit_patterns
            for m in re.finditer(p, flat, re.IGNORECASE)
        )

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }

    # -----------------------------------------------------------------------
    # NSF helper
    # -----------------------------------------------------------------------

    @classmethod
    def count_nsf(cls, text: str) -> int:
        """
        Count items in the 'Items returned unpaid' section.
        Each dated line = one NSF event.
        """
        section_match = re.search(
            r"Items\s+returned\s+unpaid(.*?)(?:\n\n|\Z)",
            text, re.IGNORECASE | re.DOTALL,
        )
        if not section_match:
            return 0
        section_text = section_match.group(1)
        return len(re.findall(r"^\s*\d{1,2}/\d{1,2}", section_text, re.MULTILINE))
