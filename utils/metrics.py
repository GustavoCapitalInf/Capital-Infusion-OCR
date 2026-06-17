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
# Loan count
# ---------------------------------------------------------------------------

def count_loan(temp_df: pd.DataFrame) -> int:
    """
    Count loan-related transactions in the parsed DataFrame.

    Matches traditional bank loans, SBA loans, lines of credit, and
    mortgage payments. Retail / POS purchases (Whole Foods, card swipes,
    etc.) are naturally excluded because they contain none of these keywords.
    """
    if temp_df.empty or "Description" not in temp_df.columns:
        return 0

    desc = temp_df["Description"].astype(str).str.upper()

    loan_pattern = (
        r"\bLOAN\b"                      # AUTO LOAN, LOAN PMT, BUSINESS LOAN …
        r"|\bMORTGAGE\b|\bMORTG\b"     # mortgage payments
        r"|\bLINE\s+OF\s+CREDIT\b"     # line of credit draws / payments
        r"|\bLOC\s+(?:PMT|PYMT|PAY)\b" # LOC payment abbreviations
        r"|\bSBA\b"                      # Small Business Administration loan
    )

    return int(desc.str.contains(loan_pattern, regex=True, na=False).sum())
 
 
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
 
 
 
# ---------------------------------------------------------------------------
# Transaction count
# ---------------------------------------------------------------------------
 
# ---------------------------------------------------------------------------
# Transaction count
# ---------------------------------------------------------------------------
 
def count_transactions(temp_df: pd.DataFrame, original_text: str = "") -> tuple[int, int, int]:
    """
    Returns:
        credit_count, debit_count, total_count
    """
 
    text = str(original_text or "")
    upper_text = text.upper()
 
    # -----------------------------
    # Bank of America
    # -----------------------------
    bofa_credits = re.search(r"#\s*of\s*deposits/credits:\s*(\d+)", text, re.I)
    bofa_debits = re.search(r"#\s*of\s*withdrawals/debits:\s*(\d+)", text, re.I)
    bofa_checks = re.search(r"Total\s+#\s*of\s*checks\s+(\d+)", text, re.I)
 
    if bofa_credits or bofa_debits or bofa_checks:
        credit_count = int(bofa_credits.group(1)) if bofa_credits else 0
        debit_count = int(bofa_debits.group(1)) if bofa_debits else 0
        check_count = int(bofa_checks.group(1)) if bofa_checks else 0
 
        debit_count += check_count
        return credit_count, debit_count, credit_count + debit_count
 
    # -----------------------------
    # Chase
    # -----------------------------
    if "CHASE" in upper_text or "JPMORGAN" in upper_text:
        deposits = _extract_count(text, r"Deposits\s+and\s+Additions\s+(\d+)\s+[\d,]+\.\d{2}")
        checks = _extract_count(text, r"Checks\s+Paid\s+(\d+)\s+-?[\d,]+\.\d{2}")
        atm_debit = _extract_count(text, r"ATM\s*&\s*Debit\s+Card\s+Withdrawals\s+(\d+)\s+-?[\d,]+\.\d{2}")
        electronic = _extract_count(text, r"Electronic\s+Withdrawals\s+(\d+)\s+-?[\d,]+\.\d{2}")
        fees = _extract_count(text, r"Fees\s+(\d+)\s+-?[\d,]+\.\d{2}")
 
        credit_count = deposits
        debit_count = checks + atm_debit + electronic + fees
        total_count = credit_count + debit_count
 
        if total_count > 0:
            return credit_count, debit_count, total_count
 
    # -----------------------------
    # TD Bank
    # -----------------------------
    if "TD BANK" in upper_text or "TD BUSINESS" in upper_text:
        deposits = _extract_td_summary_count(text, "Deposits")
        electronic_deposits = _extract_td_summary_count(text, "Electronic Deposits")
        other_credits = _extract_td_summary_count(text, "Other Credits")
 
        checks = _extract_count(text, r"Checks\s+Paid\s+No\.\s+Checks:\s*(\d+)")
 
        if checks == 0:
            checks = _count_td_checks_paid(text)
 
        electronic_payments = _count_section_rows(text, "Electronic Payments", "Other Withdrawals")
        other_withdrawals = _count_section_rows(text, "Other Withdrawals", "Service Charges")
        service_charges = _count_section_rows(text, "Service Charges", "DAILY BALANCE")
 
        credit_count = deposits + electronic_deposits + other_credits
        debit_count = checks + electronic_payments + other_withdrawals + service_charges
        total_count = credit_count + debit_count
 
        if total_count > 0:
            return credit_count, debit_count, total_count
 
    # -----------------------------
    # Wells Fargo
    # -----------------------------
    if "WELLS FARGO" in upper_text:
        credit_count = _count_wf_credits_from_text(text)
        debit_count = _count_wf_debits_from_text(text)
        total_count = credit_count + debit_count
 
        if total_count > 0:
            return credit_count, debit_count, total_count
 
    # -----------------------------
    # Generic fallback
    # -----------------------------
    if temp_df.empty:
        return 0, 0, 0
 
    df = temp_df.copy()
 
    for col in ["Date", "Description"]:
        if col not in df.columns:
            df[col] = ""
 
    for col in ["Debit", "Credit"]:
        if col not in df.columns:
            df[col] = 0.0
        df[col] = df[col].apply(clean_money).fillna(0.0)
 
    df["Date"] = df["Date"].astype(str).str.strip()
    df["Description"] = (
        df["Description"]
        .astype(str)
        .str.upper()
        .str.replace(r"\s+", " ", regex=True)
        .str.strip()
    )
 
    df = df[
        (df["Date"].str.match(r"^\d{1,2}/\d{1,2}", na=False))
        & (df["Description"] != "")
        & ((df["Debit"] > 0) | (df["Credit"] > 0))
    ]
 
    df = df.drop_duplicates(
        subset=["Date", "Description", "Debit", "Credit"],
        keep="first",
    )
 
    credit_count = int((df["Credit"] > 0).sum())
    debit_count = int((df["Debit"] > 0).sum())
 
    return credit_count, debit_count, credit_count + debit_count
 
 
def _extract_count(text: str, pattern: str) -> int:
    m = re.search(pattern, text or "", re.I)
    return int(m.group(1).replace(",", "")) if m else 0
 
 
def _extract_td_summary_count(text: str, label: str) -> int:
    """
    TD summary gives amount only, not count.
    So we count actual rows inside that section.
    """
    end_map = {
        "Deposits": "Electronic Deposits",
        "Electronic Deposits": "Other Credits",
        "Other Credits": "Checks Paid",
    }
 
    return _count_section_rows(text, label, end_map.get(label, ""))
 
 
def _count_td_checks_paid(text: str) -> int:
    m = re.search(
        r"Checks\s+Paid.*?(?:Electronic\s+Payments|Subtotal:)",
        text,
        re.I | re.S,
    )
    if not m:
        return 0
 
    section = m.group(0)
 
    return len(
        re.findall(
            r"\d{2}/\d{2}\s+\d+\*?\s+[\d,]+\.\d{2}",
            section,
            re.I,
        )
    )
 
 
def _count_section_rows(text: str, start_label: str, end_label: str) -> int:
    if not start_label:
        return 0
 
    if end_label:
        m = re.search(
            rf"{re.escape(start_label)}(.*?){re.escape(end_label)}",
            text,
            re.I | re.S,
        )
    else:
        m = re.search(
            rf"{re.escape(start_label)}(.*)",
            text,
            re.I | re.S,
        )
 
    if not m:
        return 0
 
    section = m.group(1)
 
    blocks = []
    current = ""
 
    for raw_line in section.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
 
        if not line:
            continue
 
        if re.match(r"^\d{1,2}/\d{1,2}\b", line):
            if current:
                blocks.append(current)
            current = line
        else:
            current += " " + line
 
    if current:
        blocks.append(current)
 
    money_re = re.compile(r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b")
 
    cleaned = [
        b for b in blocks
        if money_re.search(b)
        and not re.search(r"Subtotal|Total|Beginning Balance|Ending Balance", b, re.I)
    ]
 
    return len(cleaned)
 
 
def _get_wf_transaction_blocks(text: str) -> list[str]:
    """
    Extract ALL Wells Fargo transaction rows.
    """
 
    section_match = re.search(
        r"Transaction history(.*)",
        text,
        re.I | re.S,
    )
 
    section = section_match.group(1) if section_match else text
 
    blocks = []
    current = ""
 
    for raw_line in section.splitlines():
 
        line = re.sub(r"\s+", " ", raw_line).strip()
 
        if not line:
            continue
 
        # New transaction row starts with date
        if re.match(r"^\d{1,2}/\d{1,2}\b", line):
 
            if current:
                blocks.append(current)
 
            current = line
 
        else:
            current += " " + line
 
    if current:
        blocks.append(current)
 
    money_re = re.compile(
        r"\b\d{1,3}(?:,\d{3})*\.\d{2}\b|\b\d+\.\d{2}\b"
    )
 
    cleaned = []
 
    for block in blocks:
 
        upper = block.upper()
 
        # Skip statement junk
        if any(skip in upper for skip in [
            "BEGINNING BALANCE",
            "ENDING BALANCE",
            "DAILY BALANCE",
            "STATEMENT PERIOD",
            "TOTALS",
            "PAGE ",
        ]):
            continue
 
        # Must contain money
        if not money_re.search(block):
            continue
 
        cleaned.append(block)
 
    return cleaned
 
 
def _count_wf_credits_from_text(text: str) -> int:
 
    blocks = _get_wf_transaction_blocks(text)
 
    credit_keywords = [
        "DEPOSIT",
        "ZELLE FROM",
        "PURCHASE RETURN",
        "REFUNDED",
        "ACH CREDIT",
        "CREDIT",
        "SALE",
        "DEPOSIT MADE",
        "INSTANT PMT FROM",
    ]
 
    count = 0
 
    for block in blocks:
 
        upper = block.upper()
 
        if any(k in upper for k in credit_keywords):
            count += 1
 
    return count
 
 
def _count_wf_debits_from_text(text: str) -> int:
 
    blocks = _get_wf_transaction_blocks(text)
 
    debit_keywords = [
        "PURCHASE AUTHORIZED",
        "RECURRING PAYMENT",
        "ZELLE TO",
        "PAYMENT",
        "ACH DEBIT",
        "TRANSFER",
        "CHECK",
        "FEE",
        "WITHDRAWAL",
        "ACORNS",
        "VENMO",
        "PURCHASE",
    ]
 
    count = 0
 
    for block in blocks:
 
        upper = block.upper()
 
        if any(k in upper for k in debit_keywords):
            count += 1
 
    return count