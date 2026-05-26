"""
banks/wells_fargo.py
--------------------
Wells Fargo statement parser.

Detected by: "Wells Fargo" in header.

Summary structure:
  Deposits/Credits      $X,XXX.XX
  Withdrawals/Debits   -$X,XXX.XX

Or the "Beginning balance on MM/DD" + "Ending balance on MM/DD" block for
average-balance calculation (handled in utils/balance.py Level 2).

NSF: Descriptions or section text containing "Non-Sufficient Funds", "NSF",
     or "Returned Items".
POS: Descriptions containing "PURCHASE" or "POS".
"""

from __future__ import annotations

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class WellsFargoParser(BankParser):

    NAME = "Wells Fargo"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        return bool(re.search(r"WELLS\s+FARGO", text, re.IGNORECASE))

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        # Primary: "N Deposits/Credits $X" / "N Checks/Debits $X"
        credit_m = re.search(
            r"(\d+)\s+Deposits\s*/?\s*Credits\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        debit_m = re.search(
            r"(\d+)\s+Checks\s*/?\s*Debits\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )

        credits = abs(clean_money(credit_m.group(2))) if credit_m else 0.0
        credit_count = int(credit_m.group(1)) if credit_m else 0
        debits = abs(clean_money(debit_m.group(2))) if debit_m else 0.0
        debit_count = int(debit_m.group(1)) if debit_m else 0

        # Fallback: look for bare "Deposits/Credits" label
        if credits == 0.0:
            credits = cls._grab_amount(
                r"Deposits\s*/?\s*Credits\s+\$?\s*([\d,]+\.\d{2})", flat
            )
        if debits == 0.0:
            debits = cls._grab_amount(
                r"(?:Withdrawals|Checks)\s*/?\s*Debits\s*-?\s*\$?\s*([\d,]+\.\d{2})", flat
            )

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": credit_count,
            "debit_count": debit_count,
        }
