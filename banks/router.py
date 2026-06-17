"""
banks/router.py
---------------
Auto-detects which bank a statement belongs to and routes it to the
correct parser.  Falls back to the generic multi-pattern extractor when
no bank-specific parser matches.
"""

from __future__ import annotations

import re

import pdfplumber

from banks.base import BankParser
from banks.chase import ChaseParser
from banks.bofa import BofAParser
from banks.td import TDParser
from banks.wells_fargo import WellsFargoParser
from banks.rbc import RBCParser
from banks.usbank import USBankParser
from banks.pnc import PNCParser
from banks.capital_one import CapitalOneParser
from banks.regions import RegionsParser
from utils.cleaning import clean_money, fix_spaced_ocr_text


# ── Ordered list of parsers (most-specific first) ──────────────────────────
PARSERS: list[type[BankParser]] = [
    ChaseParser,
    BofAParser,
    TDParser,
    WellsFargoParser,
    RBCParser,
    USBankParser,
    PNCParser,
    CapitalOneParser,
    RegionsParser,
]


# ── Generic fallback patterns ───────────────────────────────────────────────
_GENERIC_PATTERNS: list[tuple[str, str]] = [
    ("credit", r"(\d+)\s+Deposits/Credits\s+([\d,]+\.\d{2})"),
    ("debit",  r"(\d+)\s+Checks/Debits\s+([\d,]+\.\d{2})"),
    ("credit", r"Deposits\s+and\s+other\s+credits\s+([\d,]+\.\d{2})"),
    ("debit",  r"Withdrawals\s+and\s+other\s+debits\s+([\d,]+\.\d{2})"),
    ("credit", r"(\d+)\s+Credit\(s\)\s+This\s+Period\s+\$?([\d,]+\.\d{2})"),
    ("debit",  r"(\d+)\s+Debit\(s\)\s+This\s+Period\s+\$?([\d,]+\.\d{2})"),
    ("credit", r"Deposits/Credits\s+\$?\s*([\d,]+\.\d{2})"),
    ("debit",  r"Withdrawals/Debits\s*-?\s*\$?\s*([\d,]+\.\d{2})"),
    ("both",   r"Totals\s+\$?([\d,]+\.\d{2})\s+\$?([\d,]+\.\d{2})"),
    ("credit", r"Deposits\s+and\s+Additions\s+\$?([\d,]+\.\d{2})"),
    ("debit",  r"ATM\s*&?\s*DEBIT CARD WITHDRAWALS\s+\$?([\d,]+\.\d{2})"),
    ("debit",  r"ELECTRONIC WITHDRAWALS\s+\$?([\d,]+\.\d{2})"),
    ("debit",  r"OTHER WITHDRAWALS\s+\$?([\d,]+\.\d{2})"),
    ("debit",  r"SERVICE FEES\s+\$?([\d,]+\.\d{2})"),
    # French
    ("credit", r"Total\s+des\s+d[ée]p[oô]ts.*?\+?\s*([\d\s]+,\d{2})"),
    ("debit",  r"Total\s+des\s+retraits.*?-?\s*([\d\s]+,\d{2})"),
    # Spanish
    ("credit", r"Total\s+de\s+dep[oó]sitos.*?\+?\s*\$?([\d,\s]+\.\d{2}|[\d\s]+,\d{2})"),
    ("debit",  r"Total\s+de\s+retiros.*?-?\s*\$?([\d,\s]+\.\d{2}|[\d\s]+,\d{2})"),
]


def _generic_extract(text: str) -> dict:
    """
    Multi-pattern summary extractor used when no bank-specific parser matches.
    Takes the highest matched value for credits and debits.
    """
    flat = str(text).replace("\n", " ").replace("|", " ").replace("\t", " ")
    flat = re.sub(r"\s+", " ", flat)

    credits_amount = 0.0
    debits_amount = 0.0
    credit_count = 0
    debit_count = 0

    for kind, pattern in _GENERIC_PATTERNS:
        for match in re.finditer(pattern, flat, re.IGNORECASE):
            if kind == "both":
                c = abs(clean_money(match.group(1)))
                d = abs(clean_money(match.group(2)))
                if c > credits_amount:
                    credits_amount = c
                if d > debits_amount:
                    debits_amount = d
                continue

            groups = match.groups()
            if len(groups) == 2:
                count = int(groups[0]) if str(groups[0]).isdigit() else 0
                amount = abs(clean_money(groups[1]))
            else:
                count = 0
                amount = abs(clean_money(groups[-1]))

            if kind == "credit" and amount > credits_amount:
                credits_amount = amount
                credit_count = count
            if kind == "debit" and amount > debits_amount:
                debits_amount = amount
                debit_count = count

    # Special-layout override (Chase-style multi-category debit block)
    special = (
        re.search(r"Deposits\s+and\s+Additions", flat, re.IGNORECASE)
        and (
            re.search(r"ATM\s*&?\s*Debit\s+Card\s+Withdrawals", flat, re.IGNORECASE)
            or re.search(r"Electronic\s+Withdrawals", flat, re.IGNORECASE)
            or re.search(r"Checks\s+Paid", flat, re.IGNORECASE)
        )
    )

    if special:
        sc_patterns = [
            r"Deposits\s+and\s+Additions\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s*Deposits\s+\$?([\d,]+\.\d{2})",
            r"Other\s*Credits\s+\$?([\d,]+\.\d{2})",
            # TD Bank plain "Deposits" line (not preceded by "Electronic" or "Other")
            r"(?<!Electronic )(?<!Other )(?<!\w)Deposits\s+\$?([\d,]+\.\d{2})",
        ]
        sd_patterns = [
            r"ATM\s*&?\s*Debit\s+Card\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Checks\s*Paid\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s*Payments\s+\$?([\d,]+\.\d{2})",
            r"Other\s*Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Service\s+Fees?\s+\$?([\d,]+\.\d{2})",
        ]
        sc = sum(
            abs(clean_money(m.group(1)))
            for p in sc_patterns
            for m in re.finditer(p, flat, re.IGNORECASE)
        )
        sd = sum(
            abs(clean_money(m.group(1)))
            for p in sd_patterns
            for m in re.finditer(p, flat, re.IGNORECASE)
        )
        if sc > 0:
            credits_amount = sc
        if sd > 0:
            debits_amount = sd

    return {
        "credits_amount": round(credits_amount, 2),
        "debits_amount": round(debits_amount, 2),
        "credit_count": credit_count,
        "debit_count": debit_count,
    }


def _pdf_direct_extract(uploaded_file) -> dict:
    """
    Line-by-line PDF extraction (fallback when OCR text parsing yields zeros).
    """
    credits_amount = debits_amount = credit_count = debit_count = 0.0
    td_debit = td_credit = 0.0
    td_cats = 0

    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                raw = page.extract_text() or ""
                for line in fix_spaced_ocr_text(raw).split("\n"):
                    clean_line = re.sub(r"\s+", " ", line).strip()
                    upper = clean_line.upper()
                    amounts = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2}", clean_line)
                    count_m = re.match(r"^(\d+)", clean_line)

                    if not amounts:
                        continue

                    def _take(col):
                        return abs(clean_money(amounts[0]))

                    if "DEPOSITS/CREDITS" in upper:
                        credits_amount = _take(0)
                        credit_count = int(count_m.group(1)) if count_m else 0
                    elif "CHECKS/DEBITS" in upper:
                        debits_amount = _take(0)
                        debit_count = int(count_m.group(1)) if count_m else 0
                    elif "DEPOSITS AND OTHER CREDITS" in upper:
                        credits_amount = _take(0)
                    elif "WITHDRAWALS AND OTHER DEBITS" in upper:
                        debits_amount = _take(0)
                    # ── RBC format ──────────────────────────────────────────
                    # "Total deposits & credits (44) + 68,770.44"
                    elif "DEPOSITS" in upper and "CREDITS" in upper and "&" in clean_line:
                        cnt_m = re.search(r"\((\d+)\)", clean_line)
                        if amounts:
                            credits_amount = abs(clean_money(amounts[-1]))
                            credit_count = int(cnt_m.group(1)) if cnt_m else 0
                            print(f"[PDF direct RBC] credits={credits_amount}, count={credit_count}")
                    # "Total cheques & debits (144) - 74,947.80"
                    elif "CHEQUES" in upper and "DEBITS" in upper:
                        cnt_m = re.search(r"\((\d+)\)", clean_line)
                        if amounts:
                            debits_amount = abs(clean_money(amounts[-1]))
                            debit_count = int(cnt_m.group(1)) if cnt_m else 0
                            print(f"[PDF direct RBC] debits={debits_amount}, count={debit_count}")

                    # TD-style accumulated debits
                    amt = abs(clean_money(amounts[-1]))
                    if "CHECKS PAID" in upper and "NO." not in upper:
                        td_debit += amt; td_cats += 1
                    elif "ELECTRONIC PAYMENTS" in upper:
                        td_debit += amt; td_cats += 1
                    elif "OTHER WITHDRAWALS" in upper:
                        td_debit += amt; td_cats += 1
                    elif "SERVICE CHARGES" in upper and "SUMMARY" not in upper:
                        td_debit += amt; td_cats += 1
                    if "ELECTRONIC DEPOSITS" in upper:
                        td_credit += amt
                    elif "OTHER CREDITS" in upper:
                        td_credit += amt
                    elif ("DEPOSITS" in upper
                          and "ELECTRONIC" not in upper
                          and "OTHER" not in upper
                          and "SUBTOTAL" not in upper
                          and "POSTING" not in upper):
                        td_credit += amt

    except Exception as exc:
        print(f"[PDF direct extract] {exc}")

    if td_cats >= 2:
        if td_debit > debits_amount:
            debits_amount = td_debit
        if td_credit > credits_amount:
            credits_amount = td_credit

    return {
        "credits_amount": round(credits_amount, 2),
        "debits_amount": round(debits_amount, 2),
        "credit_count": int(credit_count),
        "debit_count": int(debit_count),
    }


# ---------------------------------------------------------------------------
# Main router
# ---------------------------------------------------------------------------

def route_and_extract(
    original_text: str,
    translated_text: str,
    uploaded_file=None,
) -> dict:
    """
    Detect the bank from *original_text* and extract the summary.

    Falls back through:
      1. Bank-specific parser on original text
      2. Bank-specific parser on translated text
      3. Generic multi-pattern extractor
      4. Direct PDF line extraction (if uploaded_file provided)
    """
    print(f"[route_and_extract] original_len={len(original_text)}, translated_len={len(translated_text)}")

    # Try each bank-specific parser
    for parser_cls in PARSERS:
        matched = parser_cls.is_this_bank(original_text)
        if matched:
            print(f"[route_and_extract] matched parser: {parser_cls.NAME}")
            result = parser_cls.extract_summary(original_text)
            print(f"[route_and_extract] {parser_cls.NAME}(original) -> {result}")
            if result["credits_amount"] > 0 or result["debits_amount"] > 0:
                return result
            # Try translated text with the same parser
            result = parser_cls.extract_summary(translated_text)
            print(f"[route_and_extract] {parser_cls.NAME}(translated) -> {result}")
            if result["credits_amount"] > 0 or result["debits_amount"] > 0:
                return result

    print("[route_and_extract] no bank-specific parser returned non-zero; trying generic")

    # Generic fallback on original
    result = _generic_extract(original_text)
    print(f"[route_and_extract] generic(original) -> {result}")
    if result["credits_amount"] > 0 or result["debits_amount"] > 0:
        return result

    # Generic fallback on translated
    result = _generic_extract(translated_text)
    print(f"[route_and_extract] generic(translated) -> {result}")
    if result["credits_amount"] > 0 or result["debits_amount"] > 0:
        return result

    # Last resort — parse the raw PDF pages directly
    if uploaded_file is not None:
        print("[route_and_extract] trying _pdf_direct_extract")
        result = _pdf_direct_extract(uploaded_file)
        print(f"[route_and_extract] _pdf_direct_extract -> {result}")
        return result

    print("[route_and_extract] all methods exhausted — returning zeros")
    return {
        "credits_amount": 0.0,
        "debits_amount": 0.0,
        "credit_count": 0,
        "debit_count": 0,
    }
