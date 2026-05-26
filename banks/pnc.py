"""
banks/pnc.py
------------
PNC Bank statement parser.

Detected by: "PNC Bank" in header.

PNC summary block:
  "N Credit(s) This Period    $X,XXX.XX"
  "N Debit(s) This Period     $X,XXX.XX"

Alternate layout:
  "Credits This Period        $X,XXX.XX"
  "Debits This Period         $X,XXX.XX"
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class PNCParser(BankParser):

    NAME = "PNC"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        return bool(re.search(r"\bPNC\s*BANK\b|\bPNC\b", text, re.IGNORECASE))

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        credit_m = re.search(
            r"(\d+)\s+Credit(?:s)?\s*(?:This\s+Period)?\s+\$?([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        debit_m = re.search(
            r"(\d+)\s+Debit(?:s)?\s*(?:This\s+Period)?\s+\$?([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )

        credits = abs(clean_money(credit_m.group(2))) if credit_m else 0.0
        credit_count = int(credit_m.group(1)) if credit_m else 0
        debits = abs(clean_money(debit_m.group(2))) if debit_m else 0.0
        debit_count = int(debit_m.group(1)) if debit_m else 0

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": credit_count,
            "debit_count": debit_count,
        }
