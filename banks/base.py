"""
banks/base.py
-------------
Abstract base class for all bank-specific statement parsers.

Each bank subclass implements:
  - extract_summary(text) → dict with credits_amount, debits_amount, etc.
  - is_this_bank(text)    → bool  (quick heuristic to identify the bank)

The universal row parser and lender-direction fixer live here so all
subclasses share the same logic.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

import pandas as pd

from utils.cleaning import clean_money, fix_spaced_ocr_text


# ---------------------------------------------------------------------------
# Section-header keyword lists  (shared across parsers)
# ---------------------------------------------------------------------------

CHECKING_SECTION_KEYWORDS = [
    "checking", "checking account",
    "business plus ckg", "business plus ckf",
    "business plus checking", "business plus", "ckg",
]

SAVINGS_SECTION_KEYWORDS = ["savings", "business savings"]

EXCLUDED_REVENUE_WORDS = ["transfer from shares", "refund", "reversal"]

CREDIT_SECTION_WORDS = [
    "DEPOSITS AND ADDITIONS",
    "DEPOSITS AND OTHER CREDITS",
    "DEPOSITS/CREDITS",
    "DEPOSITS AND CREDITS",
    "CREDITS TO YOUR ACCOUNT",
    "OTHER CREDITS",
    "CREDIT",
]

DEBIT_SECTION_WORDS = [
    "ELECTRONIC WITHDRAWALS",
    "WITHDRAWALS AND OTHER DEBITS",
    "ATM & DEBIT CARD WITHDRAWALS",
    "ATM AND DEBIT CARD WITHDRAWALS",
    "CHECKS PAID",
    "CHECKS/DEBITS",
    "DEBITS TO YOUR ACCOUNT",
    "OTHER WITHDRAWALS",
    "SERVICE FEES",
    "SERVICE CHARGES",
    "DEBIT",
    "WITHDRAWAL",
]

SKIP_LINE_KEYWORDS = [
    "BEGINNING BALANCE", "ENDING BALANCE", "ENDING DAILY BALANCE",
    "ACCOUNT NUMBER", "ROUTING NUMBER", "STATEMENT PERIOD", "PAGE ",
    "SUMMARY OF CHECKS", "MONTHLY SERVICE FEE",
    "SERVICE CHARGE DESCRIPTION", "TOTAL DEPOSITS", "TOTAL WITHDRAWALS",
    "TOTAL ELECTRONIC WITHDRAWALS", "TOTAL ATM", "TOTAL CHECKS", "TOTAL FEES",
]


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

class BankParser(ABC):
    """Base class for bank-specific statement parsers."""

    NAME: str = "Generic"

    @classmethod
    @abstractmethod
    def is_this_bank(cls, text: str) -> bool:
        """Return True if *text* looks like a statement from this bank."""

    @classmethod
    @abstractmethod
    def extract_summary(cls, text: str) -> dict:
        """
        Parse the statement-level summary block.

        Returns a dict with keys:
          credits_amount, debits_amount, credit_count, debit_count
        """

    # -----------------------------------------------------------------------
    # Shared helpers used by most subclasses
    # -----------------------------------------------------------------------

    @staticmethod
    def _empty_summary() -> dict:
        return {
            "credits_amount": 0.0,
            "debits_amount": 0.0,
            "credit_count": 0,
            "debit_count": 0,
        }

    @staticmethod
    def _flatten(text: str) -> str:
        """Collapse newlines + tabs into a single space for regex scanning."""
        text = str(text).replace("\n", " ").replace("|", " ").replace("\t", " ")
        return re.sub(r"\s+", " ", text)

    @staticmethod
    def _grab_amount(pattern: str, text: str) -> float:
        """Return the first captured amount matching *pattern*, or 0.0."""
        m = re.search(pattern, text, re.IGNORECASE)
        return abs(clean_money(m.group(1))) if m else 0.0


# ---------------------------------------------------------------------------
# Universal row parser  (bank-agnostic, used as a fallback)
# ---------------------------------------------------------------------------

_DATE_START = re.compile(
    r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{1,2}\s+[A-ZÉÈÊÀÂÎÏÔÛÙÇÓÍÚÑ]{3,})\b",
    re.IGNORECASE,
)

_MONEY_RE = re.compile(
    r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}|-?\d[\d\s]*,\d{2}",
    re.IGNORECASE,
)


def parse_universal_bank_rows(text: str) -> pd.DataFrame:
    """
    Generic line-by-line transaction parser.

    Works on any bank where transactions start with a date followed by
    a description and one or more dollar amounts.
    """
    if not text:
        return pd.DataFrame()

    raw_lines = [l.strip() for l in str(text).split("\n") if l.strip()]
    current_account_type = "checking"
    current_section = ""

    # ── Pass 1: join continuation lines into logical transaction lines ──
    logical: list[tuple[str, str]] = []
    current_line = ""
    current_section_snapshot = ""

    for line in raw_lines:
        lower = line.lower()
        upper = line.upper()

        # Account type routing
        if any(kw in lower for kw in CHECKING_SECTION_KEYWORDS):
            current_account_type = "checking"
        if any(kw in lower for kw in SAVINGS_SECTION_KEYWORDS):
            current_account_type = "savings"
            continue
        if current_account_type == "savings":
            continue

        # Section classification
        if any(w in upper for w in CREDIT_SECTION_WORDS):
            current_section = "Credit"
        if any(w in upper for w in DEBIT_SECTION_WORDS):
            current_section = "Debit"
        if any(skip in upper for skip in SKIP_LINE_KEYWORDS):
            continue

        if _DATE_START.match(line):
            if current_line:
                logical.append((current_line.strip(), current_section_snapshot))
            current_line = line
            current_section_snapshot = current_section
        else:
            if current_line:
                current_line += " " + line

    if current_line:
        logical.append((current_line.strip(), current_section_snapshot))

    # ── Pass 2: parse each logical line ─────────────────────────────────
    rows: list[dict] = []

    for line, section in logical:
        m = _DATE_START.match(line)
        if not m:
            continue

        date = m.group(1)
        rest = line[m.end():].strip()
        money_matches = list(_MONEY_RE.finditer(rest))
        if not money_matches:
            continue

        amounts = [clean_money(x.group(0)) for x in money_matches]
        amounts = [a for a in amounts if a != 0]
        if not amounts:
            continue

        first_pos = money_matches[0].start()
        description = re.sub(r"\s+", " ", rest[:first_pos]).strip()

        transaction_amount = amounts[-2] if len(amounts) >= 2 else amounts[-1]
        balance = amounts[-1] if len(amounts) >= 2 else 0.0

        if section == "Debit":
            debit, credit = abs(transaction_amount), 0.0
        elif section == "Credit":
            debit, credit = 0.0, abs(transaction_amount)
        elif transaction_amount < 0:
            debit, credit = abs(transaction_amount), 0.0
        else:
            debit, credit = 0.0, abs(transaction_amount)

        rows.append({
            "Date": date,
            "Description": description,
            "Debit": round(debit, 2),
            "Credit": round(credit, 2),
            "Amount": round(credit - debit, 2),
            "Balance": round(balance, 2),
            "Section": section,
            "Raw Line": line,
        })

    return pd.DataFrame(rows)


def parse_ocr_transactions(text: str) -> pd.DataFrame:
    """
    Simple regex-based transaction parser used when the universal
    row parser returns an empty DataFrame.
    """
    lines = text.split("\n")
    transactions: list[dict] = []
    current_section = ""
    current_account_type = "checking"

    tx_pat = re.compile(
        r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d{1,2}\s+[A-ZÉÈÊÀÂÎÏÔÛÙÇÓÍÚÑ]{3,})\s+"
        r"(.*?)\s+\$?(-?[\d,\s]+\.\d{2}|-?[\d\s]+,\d{2})",
        re.IGNORECASE,
    )

    for line in lines:
        line = line.strip()
        if not line:
            continue
        lower, upper = line.lower(), line.upper()

        if any(kw in lower for kw in CHECKING_SECTION_KEYWORDS):
            current_account_type = "checking"
            continue
        if any(kw in lower for kw in SAVINGS_SECTION_KEYWORDS):
            current_account_type = "savings"
            continue
        if current_account_type == "savings":
            continue

        if any(w in upper for w in ["DEPOSITS AND CREDITS", "OTHER CREDITS", "CREDITS", "CREDIT"]):
            current_section = "Credit"
        if any(w in upper for w in ["CHECKS AND CHARGES", "ELECTRONIC DEBITS", "OTHER DEBITS",
                                     "CHECKS/DEBITS", "DEBITS", "DEBIT", "WITHDRAWALS",
                                     "WITHDRAWAL", "PAYMENT"]):
            current_section = "Debit"

        match = tx_pat.search(line)
        if match:
            amount = clean_money(match.group(3))
            amount = -abs(amount) if current_section == "Debit" else abs(amount)

            if any(w in lower for w in EXCLUDED_REVENUE_WORDS) and amount > 0:
                amount = 0.0

            transactions.append({
                "Date": match.group(1),
                "Description": match.group(2).strip(),
                "Amount": amount,
                "Debit": abs(amount) if amount < 0 else 0.0,
                "Credit": amount if amount > 0 else 0.0,
                "Raw Line": line,
            })

    return pd.DataFrame(transactions)


# ---------------------------------------------------------------------------
# Lender debit/credit direction corrector
# ---------------------------------------------------------------------------

def fix_lender_direction(raw_df: pd.DataFrame) -> pd.DataFrame:
    """
    When a lender transaction lands in the wrong column due to OCR/parser
    ambiguity, correct Debit↔Credit based on section context.
    """
    if raw_df.empty:
        return raw_df

    from utils.lender_detection import detect_company, LENDER_KEYWORDS

    df = raw_df.copy()

    for col in ["Debit", "Credit", "Amount"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].apply(clean_money)

    for col in ["Description", "Raw Line", "Section"]:
        if col not in df.columns:
            df[col] = ""

    for idx, row in df.iterrows():
        text = f"{row['Description']} {row['Raw Line']}"
        section = str(row["Section"]).upper()
        lender, _ = detect_company(text, LENDER_KEYWORDS)
        if not lender:
            continue

        debit = abs(clean_money(row.get("Debit", 0)))
        credit = abs(clean_money(row.get("Credit", 0)))
        amount = clean_money(row.get("Amount", 0))

        if section == "DEBIT" and credit > 0 and debit == 0:
            df.at[idx, "Debit"] = credit
            df.at[idx, "Credit"] = 0.0
            df.at[idx, "Amount"] = -credit
        elif section == "CREDIT" and debit > 0 and credit == 0:
            df.at[idx, "Credit"] = debit
            df.at[idx, "Debit"] = 0.0
            df.at[idx, "Amount"] = debit
        elif amount < 0 and credit > 0 and debit == 0:
            df.at[idx, "Debit"] = credit
            df.at[idx, "Credit"] = 0.0
            df.at[idx, "Amount"] = -credit

    return df
