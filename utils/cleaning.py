"""
utils/cleaning.py
-----------------
Shared text and money cleaning utilities used across all bank parsers
and extraction modules.
"""

import re
import pandas as pd


# ---------------------------------------------------------------------------
# Money
# ---------------------------------------------------------------------------

def clean_money(value) -> float:
    """
    Convert any raw string/float representation of a dollar amount
    to a Python float.  Handles:
      - Parenthetical negatives  (1,234.56)
      - Trailing minus           1,234.56-
      - Leading minus            -1,234.56
      - European comma decimals  1.234,56 → 1234.56
      - Dollar signs, spaces, plus signs
    Returns 0.0 on parse failure.
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return 0.0

    value = str(value).strip()
    value = value.replace("$", "").replace("+", "").replace(" ", "")

    negative = False

    if value.startswith("(") and value.endswith(")"):
        negative = True
        value = value[1:-1]

    if value.endswith("-"):
        negative = True
        value = value[:-1]

    if value.startswith("-"):
        negative = True
        value = value[1:]

    # European format: 1.234,56
    if "," in value and "." not in value:
        value = value.replace(",", ".")
    else:
        value = value.replace(",", "")

    try:
        amount = float(value)
        return -amount if negative else amount
    except (ValueError, TypeError):
        return 0.0


def safe_money_balance(raw) -> float | None:
    """
    Parse a balance value and reject obviously garbage OCR numbers
    (> $10 million or more than 8 integer digits).
    Returns None when the value looks invalid.
    """
    v = clean_money(raw)
    if abs(v) > 10_000_000:
        return None
    if len(str(int(abs(v)))) > 8:
        return None
    return v


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """
    Uppercase, strip punctuation/special chars, and collapse whitespace.
    Used by the lender-keyword matcher.
    """
    text = str(text).upper().strip()
    for ch in "-_.,*#/\\":
        text = text.replace(ch, " ")
    return " ".join(text.split())


def fix_spaced_ocr_text(text: str) -> str:
    """
    Collapse lines where every token is ≤ 2 characters (common OCR artefact
    where characters are space-separated rather than joined).
    """
    lines = text.split("\n")
    fixed = []
    for line in lines:
        tokens = line.split(" ")
        if len(tokens) > 4 and all(len(t) <= 2 for t in tokens if t):
            fixed.append("".join(tokens))
        else:
            fixed.append(line)
    return "\n".join(fixed)


def normalize_transaction_text(text: str) -> str:
    """
    Replace verbose transaction type labels with standardized short forms.
    """
    NORMALIZATION_MAP = {
        "DIRECT DEPOSIT": "DEPOSIT",
        "INTERAC TRANSFER": "TRANSFER",
        "WIRE IN": "TRANSFER",
        "POS PURCHASE": "PURCHASE",
        "ATM WITHDRAWAL": "WITHDRAWAL",
        "PREAUTHORIZED DEBIT": "PREAUTHORIZED DEBIT",
        "SERVICE FEE": "FEE",
        "NSF FEE": "NSF",
        "ONLINE TRANSFER": "TRANSFER",
        "WIRE TRANSFER": "TRANSFER",
        "OVERDRAFT": "OVERDRAFT",
        "INTEREST": "INTEREST",
    }
    normalized = str(text).upper()
    for old, new in NORMALIZATION_MAP.items():
        normalized = normalized.replace(old, new)
    return normalized


def keyword_matches(clean_description: str, clean_keyword: str) -> bool:
    """Strict word-boundary keyword match (prevents PAR → PARKING)."""
    pattern = r"\b" + re.escape(clean_keyword) + r"\b"
    return bool(re.search(pattern, clean_description))
