"""
banks/bofa.py
-------------
Bank of America (BofA) statement parser.

Detected by: "Bank of America" header + summary labels
  "Deposits and other credits" / "Withdrawals and other debits"

BofA summary block structure:
  Deposits and other credits (N)    $X,XXX.XX
  Withdrawals and other debits (N)  $X,XXX.XX
  Checks (N)                        $X,XXX.XX
  Service fees (N)                  $X,XXX.XX

NSF: Descriptions containing "Non-Sufficient Funds" or "NSF Fee".
POS: Descriptions containing "POS".
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class BofAParser(BankParser):

    NAME = "Bank of America"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        return bool(
            re.search(r"BANK\s+OF\s+AMERICA", flat)
            and re.search(r"DEPOSITS\s+AND\s+OTHER\s+CREDITS", flat)
        )

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = re.sub(r"\s+", " ", str(text).replace("\n", " "))

        def grab(label: str) -> float:
            pattern = rf"{label}\s*(?:\(\d+\))?\s*-?\s*\$?\s*([\d,]+\.\d{{2}})"
            m = re.search(pattern, flat, re.IGNORECASE)
            return abs(clean_money(m.group(1))) if m else 0.0

        credits = grab(r"Deposits\s+and\s+other\s+credits")

        withdrawals = grab(r"Withdrawals\s+and\s+other\s+debits")
        checks = grab(r"\bChecks\b")
        service_fees = grab(r"Service\s+fees?")
        debits = withdrawals + checks + service_fees

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }
