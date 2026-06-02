"""
banks/bofa.py
-------------
Bank of America statement parser.
"""

from __future__ import annotations

import re
import pandas as pd

from banks.base import BankParser
from utils.cleaning import clean_money


class BofAParser(BankParser):

    NAME = "Bank of America"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", str(text)).upper()
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
        checks = grab(r"\bChecks\s*(?:\(\d+\))?")
        service_fees = grab(r"Service\s+fees?")
        debits = withdrawals + checks + service_fees

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }

    @classmethod
    def parse_transactions(cls, text: str) -> pd.DataFrame:
        rows = []
        current_section = ""

        section_map = {
            "DEPOSITS AND OTHER CREDITS": "Credit",
            "WITHDRAWALS AND OTHER DEBITS": "Debit",
            "CHECKS": "Debit",
            "SERVICE FEES": "Debit",
        }

        date_re = re.compile(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.+)$")
        money_re = re.compile(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}")

        for line in str(text).splitlines():
            clean = re.sub(r"\s+", " ", line).strip()
            if not clean:
                continue

            upper = clean.upper()

            for label, section in section_map.items():
                if label in upper:
                    current_section = section
                    break

            if not current_section:
                continue

            m = date_re.match(clean)
            if not m:
                continue

            date = m.group(1)
            rest = m.group(2).strip()

            money_matches = list(money_re.finditer(rest))
            if not money_matches:
                continue

            amounts = [abs(clean_money(x.group(0))) for x in money_matches]
            amounts = [a for a in amounts if a != 0]
            if not amounts:
                continue

            amount = amounts[-2] if len(amounts) >= 2 else amounts[-1]
            last_money = money_matches[-2] if len(money_matches) >= 2 else money_matches[-1]

            desc = re.sub(r"\s+", " ", rest[:last_money.start()]).strip()

            debit = amount if current_section == "Debit" else 0.0
            credit = amount if current_section == "Credit" else 0.0

            rows.append({
                "Date": date,
                "Description": desc,
                "Debit": round(debit, 2),
                "Credit": round(credit, 2),
                "Amount": round(credit - debit, 2),
                "Balance": 0.0,
                "Section": current_section,
                "Raw Line": clean,
            })

        return pd.DataFrame(rows)