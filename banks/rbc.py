"""
banks/rbc.py
------------
Royal Bank of Canada (RBC) statement parser.

Detected by: "RBC" or "Royal Bank of Canada" + "cheques" in text.

RBC summary uses:
  "Deposits & credits    $X,XXX.XX"
  "Cheques & debits     -$X,XXX.XX"

French characters and em-dashes are normalized before parsing.
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class RBCParser(BankParser):

    NAME = "RBC"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        return bool(
            re.search(r"\bRBC\b|ROYAL\s+BANK\s+OF\s+CANADA", flat)
            and re.search(r"CHEQUES?", flat)
        )

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = str(text).replace("&amp;", "&")
        flat = re.sub(r"[–—−]", "-", flat)
        flat = re.sub(r"\s+", " ", flat)

        credit_m = re.search(
            r"deposits.*?credits.*?([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        debit_m = re.search(
            r"cheques?.*?debits?.*?([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )

        credits = abs(clean_money(credit_m.group(1))) if credit_m else 0.0
        debits = abs(clean_money(debit_m.group(1))) if debit_m else 0.0

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }
