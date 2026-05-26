"""
utils/metrics.py
----------------
Per-statement metric helpers:
  - NSF count  (from transaction DataFrame + raw OCR text section)
  - POS count  (from transaction DataFrame)
  - Charges-only extraction  (checks-and-charges section)
"""

from __future__ import annotations

import re

import pandas as pd

from utils.cleaning import clean_money


# ---------------------------------------------------------------------------
# NSF keywords — only match actual NSF/overdraft events, not boilerplate
# ---------------------------------------------------------------------------

_NSF_DESCRIPTION_KEYWORDS = [
    r"\bNSF\b",
    r"\bNSF\s+FEE\b",
    r"NON.SUFFICIENT\s+FUNDS",
    r"INSUFFICIENT\s+FUNDS",
    r"OVERDRAFT\s+FEE",          # Wells Fargo: "Overdraft Fee for a Transaction"
    r"RETURNED\s+ITEM\s+FEE",
    r"RETURN\s+FEE",
    r"ITEMS?\s+RETURNED\s+UNPAID",
]

_NSF_PATTERN = re.compile(
    "|".join(_NSF_DESCRIPTION_KEYWORDS),
    re.IGNORECASE,
)


# ---------------------------------------------------------------------------
# NSF count
# ---------------------------------------------------------------------------

def count_nsf(temp_df: pd.DataFrame, original_text: str = "") -> int:
    """
    Return total NSF / overdraft event count.

    Two sources — takes the higher:

    1. Description column of the parsed DataFrame, matched with strict
       keyword patterns (word-boundary aware, no substring false positives).

    2. "Items returned unpaid" section in raw OCR text — each dated line
       is one returned item.

    Wells Fargo labels overdrafts as "Overdraft Fee for a Transaction
    Posted on MM/DD …" which is caught by the OVERDRAFT_FEE pattern above.
    The phrase "OD/NSF" in page headers is NOT matched because it lacks the
    surrounding context words.
    """
    # Source 1 — DataFrame descriptions
    df_nsf = 0
    if not temp_df.empty and "Description" in temp_df.columns:
        df_nsf = int(
            temp_df["Description"]
            .astype(str)
            .apply(lambda d: bool(_NSF_PATTERN.search(d)))
            .sum()
        )

    # Source 2 — "Items returned unpaid" section in raw text
    text_nsf = 0
    if original_text:
        section_m = re.search(
            r"Items\s+returned\s+unpaid(.*?)(?:\n\n|\Z)",
            original_text, re.IGNORECASE | re.DOTALL,
        )
        if section_m:
            text_nsf = len(
                re.findall(
                    r"^\s*\d{1,2}/\d{1,2}",
                    section_m.group(1),
                    re.MULTILINE,
                )
            )

    return max(df_nsf, text_nsf)


# ---------------------------------------------------------------------------
# POS count
# ---------------------------------------------------------------------------

def count_pos(temp_df: pd.DataFrame) -> int:
    """
    Count POS / point-of-sale transactions in the parsed DataFrame.

    Uses a strict word-boundary regex \\bPOS\\b so that the substring
    "POS" inside words like "DEPOSIT", "COMPOSE", "EXPOSURE" etc. is
    NOT counted as a POS transaction.
    """
    if temp_df.empty or "Description" not in temp_df.columns:
        return 0
    return int(
        temp_df["Description"]
        .astype(str)
        .str.upper()
        .str.contains(r"\bPOS\b", regex=True)
        .sum()
    )


# ---------------------------------------------------------------------------
# Charges-only extraction (e.g. checks-and-charges section)
# ---------------------------------------------------------------------------

def extract_charges_only(text: str) -> tuple[pd.DataFrame, float]:
    """
    Extract transactions from a dedicated "Checks and Charges" section.

    Returns (charges_df, total_amount).
    """
    charges: list[dict] = []
    in_section = False

    for line in str(text).split("\n"):
        clean = re.sub(r"\s+", " ", line).strip()
        upper = clean.upper()

        if "CHECKS AND CHARGES" in upper:
            in_section = True
            continue
        if "SUMMARY BY CHECK NUMBER" in upper:
            in_section = False
            continue
        if not in_section or "CHECK #" in upper:
            continue

        m = re.search(
            r"^(\d{1,2}/\d{1,2})\s+(.+?)\s+(-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2})",
            clean,
        )
        if m:
            charges.append({
                "Date":          m.group(1),
                "Description":   m.group(2),
                "Charge Amount": abs(clean_money(m.group(3))),
                "Raw Line":      clean,
            })

    df = pd.DataFrame(charges)
    total = df["Charge Amount"].sum() if not df.empty else 0.0
    return df, total
