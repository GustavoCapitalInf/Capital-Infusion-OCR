"""
banks/usbank.py
---------------
U.S. Bank statement parser.

Detected by: "U.S. Bank" or "US BANK" in header.

Summary structure:
  "N Deposits/Credits   $X,XXX.XX"
  "N Checks/Debits      $X,XXX.XX"

Or the credit/debit totals block at the bottom of the Account Summary.
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class USBankParser(BankParser):

    NAME = "US Bank"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        return bool(re.search(r"U\.?S\.?\s*BANK", text, re.IGNORECASE))

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        # "N Deposits/Credits $X,XXX.XX"
        credit_m = re.search(
            r"(\d+)\s+Deposits\s*/?\s*Credits\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        debit_m = re.search(
            r"(\d+)\s+(?:Checks|Withdrawals)\s*/?\s*(?:Debits)?\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )

        credits = abs(clean_money(credit_m.group(2))) if credit_m else 0.0
        credit_count = int(credit_m.group(1)) if credit_m else 0
        debits = abs(clean_money(debit_m.group(2))) if debit_m else 0.0
        debit_count = int(debit_m.group(1)) if debit_m else 0

        # Fallback labels
        if credits == 0.0:
            credits = cls._grab_amount(
                r"Total\s+(?:Deposits?\s*/?|)Credits?\s+\$?\s*([\d,]+\.\d{2})", flat
            )
        if debits == 0.0:
            debits = cls._grab_amount(
                r"Total\s+(?:Withdrawals?\s*/?|)Debits?\s+\$?\s*([\d,]+\.\d{2})", flat
            )

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": credit_count,
            "debit_count": debit_count,
        }
