"""
banks/capital_one.py
--------------------
Capital One statement parser.

Detected by: "Capital One" in header.

Capital One business checking summary:
  "Deposits and Credits   $X,XXX.XX"
  "Withdrawals and Debits $X,XXX.XX"
  "Service Charges        $X,XXX.XX"

NSF: "Returned Item Fee" or "NSF Fee" in transaction descriptions.
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class CapitalOneParser(BankParser):

    NAME = "Capital One"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        return bool(re.search(r"CAPITAL\s+ONE", text, re.IGNORECASE))

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        credits = cls._grab_amount(
            r"Deposits\s+and\s+(?:Other\s+)?Credits\s+\$?\s*([\d,]+\.\d{2})", flat
        )
        withdrawals = cls._grab_amount(
            r"Withdrawals\s+and\s+(?:Other\s+)?Debits\s+\$?\s*([\d,]+\.\d{2})", flat
        )
        fees = cls._grab_amount(
            r"Service\s+Charges?\s+\$?\s*([\d,]+\.\d{2})", flat
        )
        debits = withdrawals + fees

        # Fallback: Totals row
        if credits == 0.0 and debits == 0.0:
            totals_m = re.search(
                r"Totals\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if totals_m:
                credits = abs(clean_money(totals_m.group(1)))
                debits = abs(clean_money(totals_m.group(2)))

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }
