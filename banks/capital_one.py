"""
banks/capital_one.py
--------------------
Capital One statement parser.

Detected by: "CAPITAL ONE" in header.

Summary format (business checking):
  "19 Deposits/Credits  $9,230.78"
  "30 Checks/Debits    ($8,968.79)"
  "Service Charges      ($15.00)"

Transaction rows in ACCOUNT DETAIL section:
  Date | Description | Deposits/Credits | Withdrawals/Debits | Resulting Balance

Credits:  "TRANSFER DEPOSIT ...", "DEBIT CARD MONEY RECEIVED ..."
Debits:   "Debit Card Purchase ...", "Recur Debit Card Purchase ...",
          "ACH Withdrawal ...", "TRANSFER WITHDRAWAL ...",
          "NSF charge ...", "Maintenance charge ..."

NSF: "NSF charge" in description.
"""

from __future__ import annotations

import re

import pandas as pd

from banks.base import BankParser
from utils.cleaning import clean_money


# ── Transaction classification ───────────────────────────────────────────────

_CREDIT_RE = re.compile(
    r"TRANSFER\s+DEPOSIT|DEBIT\s+CARD\s+MONEY\s+RECEIVED|\bDEPOSIT\b",
    re.IGNORECASE,
)

_DEBIT_RE = re.compile(
    r"Debit\s+Card\s+Purchase|Recur\s+Debit\s+Card\s+Purchase|"
    r"ACH\s+Withdrawal|TRANSFER\s+WITHDRAWAL|NSF\s+charge|"
    r"Maintenance\s+charge|Service\s+charge|\bPURCHASE\b",
    re.IGNORECASE,
)

# Matches dollar amounts including parenthetical negatives like ($20.71)
_AMOUNT_RE = re.compile(r"\(?\$?([\d,]+\.\d{2})\)?")

# Lines that are structural noise, not transactions
_SKIP_RE = re.compile(
    r"DEPOSITS/CREDITS|WITHDRAWALS/DEBITS|RESULTING\s+BALANCE|"
    r"SERVICE\s+CHARGE|TOTAL\s+NSF|TOTAL\s+OVERDRAFT|"
    r"THANK\s+YOU|MEMBER\s+FDIC|CAPITAL\s+ONE|MANAGE\s+YOUR\s+CASH|"
    r"CASH\s+MANAGEMENT|PAGE\s+\d+\s+OF\s+\d+|"
    r"CONTINUED\s+FOR\s+PERIOD|PSI:\s*\d",
    re.IGNORECASE,
)

_DATE_RE = re.compile(r"^(\d{2}/\d{2})\s+(.+)$")

# Stop parsing transactions when the totals row is reached
_TOTAL_ROW_RE = re.compile(r"^Total\s+\$[\d,]+\.\d{2}", re.IGNORECASE)


class CapitalOneParser(BankParser):

    NAME = "Capital One"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        return bool(re.search(r"CAPITAL\s+ONE", text, re.IGNORECASE))

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        # "19 Deposits/Credits $9,230.78"
        credits = cls._grab_amount(
            r"\d+\s+Deposits/Credits\s+\$?\s*([\d,]+\.\d{2})", flat
        )
        if credits == 0.0:
            credits = cls._grab_amount(
                r"Deposits\s*(?:/|and\s+(?:Other\s+)?)Credits\s+\$?\s*([\d,]+\.\d{2})",
                flat,
            )

        # "30 Checks/Debits ($8,968.79)"  — parentheses indicate negative
        withdrawals = cls._grab_amount(
            r"\d+\s+Checks/Debits\s+\(?\$?\s*([\d,]+\.\d{2})\)?", flat
        )
        if withdrawals == 0.0:
            withdrawals = cls._grab_amount(
                r"Checks/Debits\s+\(?\$?\s*([\d,]+\.\d{2})\)?", flat
            )

        # Service charges are debits ("Service Charges ($15.00)")
        fees = cls._grab_amount(
            r"Service\s+Charges?\s+\(?\$?\s*([\d,]+\.\d{2})\)?", flat
        )
        debits = withdrawals + fees

        # Totals row fallback: "Total $9,230.78 $8,983.79"
        if credits == 0.0 and debits == 0.0:
            m = re.search(
                r"Totals?\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if m:
                credits = abs(clean_money(m.group(1)))
                debits  = abs(clean_money(m.group(2)))

        return {
            "credits_amount": round(credits, 2),
            "debits_amount":  round(debits, 2),
            "credit_count":   0,
            "debit_count":    0,
        }

    @classmethod
    def parse_transactions(cls, text: str) -> pd.DataFrame:
        """
        Parse Capital One ACCOUNT DETAIL transactions.

        Each transaction row starts with MM/DD and has one or two dollar
        amounts at the end: [transaction_amount, resulting_balance].
        Direction (Credit/Debit) is determined by description keywords.
        """
        lines = [
            re.sub(r"\s+", " ", ln).strip()
            for ln in str(text).splitlines()
            if ln.strip()
        ]

        in_detail   = False
        pending_date  = ""
        pending_text  = ""
        logical: list[tuple[str, str]] = []

        def _flush() -> None:
            if pending_date and pending_text.strip():
                logical.append((pending_date, pending_text.strip()))

        for line in lines:
            upper = line.upper()

            if "ACCOUNT DETAIL" in upper:
                _flush()
                pending_date = pending_text = ""
                in_detail = True
                continue

            if not in_detail:
                continue

            # Stop at the totals row at the bottom of the last page
            if _TOTAL_ROW_RE.match(line):
                _flush()
                pending_date = pending_text = ""
                break

            # Skip structural / header noise
            if _SKIP_RE.search(line):
                continue

            dm = _DATE_RE.match(line)
            if dm:
                _flush()
                pending_date = dm.group(1)
                pending_text = dm.group(2)
            elif pending_date:
                pending_text += " " + line

        _flush()

        # ── Classify and build rows ──────────────────────────────────────────
        rows: list[dict] = []
        for date, full_text in logical:
            raw_vals = [
                abs(clean_money(m.group(0).replace("(", "-").replace(")", "")))
                for m in _AMOUNT_RE.finditer(full_text)
            ]
            raw_vals = [v for v in raw_vals if v > 0]
            if not raw_vals:
                continue

            # Second-to-last = transaction amount; last = resulting balance
            if len(raw_vals) >= 2:
                txn_amt = raw_vals[-2]
                balance = raw_vals[-1]
            else:
                txn_amt = raw_vals[-1]
                balance = 0.0

            # Strip all money tokens from description
            desc = _AMOUNT_RE.sub("", full_text)
            desc = re.sub(r"\s{2,}", " ", desc).strip()

            # Classify direction — credit check runs first so "DEBIT CARD
            # MONEY RECEIVED" (a Square deposit) is correctly read as credit
            if _CREDIT_RE.search(full_text):
                debit, credit = 0.0, txn_amt
            elif _DEBIT_RE.search(full_text):
                debit, credit = txn_amt, 0.0
            else:
                # Unknown: default to debit (conservative for underwriting)
                debit, credit = txn_amt, 0.0

            rows.append({
                "Date":        date,
                "Description": desc,
                "Debit":       round(debit, 2),
                "Credit":      round(credit, 2),
                "Amount":      round(credit - debit, 2),
                "Balance":     round(balance, 2),
                "Section":     "Credit" if credit > 0 else "Debit",
            })

        return pd.DataFrame(rows)

    @classmethod
    def count_nsf(cls, text: str) -> int:
        return len(re.findall(r"NSF\s+(?:charge|fee)", text, re.IGNORECASE))
