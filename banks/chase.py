"""
banks/chase.py
--------------
Chase Bank statement parser.
"""

from __future__ import annotations

import re
import pandas as pd

from banks.base import BankParser
from utils.cleaning import clean_money


class ChaseParser(BankParser):

    NAME = "Chase"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", str(text)).upper()
        has_chase = bool(re.search(r"\bJPMORGAN\b|\bCHASE\b", flat))
        # "THROUGH" may be squished to adjacent word (e.g. "THROUGHJANUARY")
        has_through = bool(re.search(r"THROUGH", flat))
        return has_chase and has_through

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        credits = cls._grab_amount(
            r"Deposits\s+and\s+Additions\s+\$?([\d,]+\.\d{2})",
            flat,
        )

        debit_patterns = [
            r"ATM\s*&?\s*Debit\s+Card\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Checks\s*Paid\s+\$?([\d,]+\.\d{2})",
            r"Service\s+Fees?\s+\$?([\d,]+\.\d{2})",
            r"Other\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
        ]

        debit_seen = set()
        debits = 0.0

        for pattern in debit_patterns:
            for m in re.finditer(pattern, flat, re.IGNORECASE):
                amount = abs(clean_money(m.group(1)))
                key = (pattern, round(amount, 2))

                if key in debit_seen:
                    continue

                debit_seen.add(key)
                debits += amount

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }

    @classmethod
    def parse_transactions(cls, text: str) -> pd.DataFrame:
        """
        Chase-specific transaction parser.

        This assigns transaction rows into Debit/Credit based on Chase sections:
        - Deposits and Additions => Credit
        - Electronic Withdrawals => Debit
        - ATM & Debit Card Withdrawals => Debit
        - Checks Paid => Debit
        - Service Fees => Debit

        Lender detection then reads:
        - Debit column for lender debits
        - Credit column for lender credits
        """
        rows = []
        current_section = ""

        section_map = {
            "DEPOSITS AND ADDITIONS": "Credit",
            "ELECTRONIC WITHDRAWALS": "Debit",
            "ATM & DEBIT CARD WITHDRAWALS": "Debit",
            "ATM AND DEBIT CARD WITHDRAWALS": "Debit",
            "CHECKS PAID": "Debit",
            "SERVICE FEES": "Debit",
            "OTHER WITHDRAWALS": "Debit",
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

            # If Chase line has transaction amount + balance, use transaction amount.
            # Otherwise use the only/last amount.
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

    @classmethod
    def count_nsf(cls, text: str) -> int:
        section_match = re.search(
            r"Items\s+returned\s+unpaid(.*?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not section_match:
            return 0

        section_text = section_match.group(1)
        return len(re.findall(r"^\s*\d{1,2}/\d{1,2}", section_text, re.MULTILINE))