"""
utils/lender_detection.py
-------------------------
MCA / lender keyword dictionary and detection functions.
Detects lender debits (loan repayments) and lender credits (fundings).

Credit detection uses a 3-pass strategy:
  Pass 1 — Credit column (standard banks with section headers)
  Pass 2 — Debit column + FUNDING_DEPOSIT_PATTERNS (Wells Fargo sectionless)
  Pass 3 — Debit column + heuristic: lender name at description start
            with no debit-only words → almost certainly an inbound advance
"""

from __future__ import annotations

import re
import pandas as pd

from utils.cleaning import clean_text, clean_money, keyword_matches


# ---------------------------------------------------------------------------
# Patterns indicating an INBOUND funding deposit
# ---------------------------------------------------------------------------

FUNDING_DEPOSIT_PATTERNS: list[str] = [
    r"ACH\s*PAYMEN",
    r"ACH\s*ITEMS",
    r"ACH\s*DEPOSIT",
    r"ACH\s*CREDIT",
    r"FUNDING\s*DEPOSIT",
    r"LOAN\s*PROCEED",
    r"LOAN\s*DEPOSIT",
    r"MCA\s*FUND",
    r"ADVANCE\s*DEPOSIT",
    r"FUNDED",
    r"WIRE\s*IN",
    r"INCOMING\s*WIRE",
    r"WIRE\s*TRANSFER\s*INCOMING",
    r"PY\d{2}/\d{2}/\d{2}",        # J&A Marketing: PY04/23/26
    r"00SAPP010",                   # J&A Marketing batch ID
    r"CAPITA\s+FUNDING",            # Expansion Capita Funding
    r"CAPITAL\s+FUNDING",           # Expansion Capital Funding
    r"FUNDING\s+\d{5,}",           # Lender + numeric batch: "Funding 5769267"
    r"ADVANCE\s+INC",              # Retro Advance Inc
    r"SALE\s+\d{6}",               # CDC: "Sale 260301"
]

# Patterns that unambiguously indicate an OUTGOING payment (never a credit)
DEBIT_ONLY_PATTERNS: list[str] = [
    r"\bBILLPAY\b",
    r"\bBILL\s*PAY\b",
    r"\bPAYMENT\b",
    r"\bPMT\b",
    r"\bREPAY\b",
    r"CCD\s+DEBIT",
    r"ACH\s+DEBIT",
    r"PURCHASE\s+AUTH",
]


def _is_funding_deposit(description: str) -> bool:
    upper = description.upper()
    return any(re.search(p, upper) for p in FUNDING_DEPOSIT_PATTERNS)


def _is_debit_only(description: str) -> bool:
    upper = description.upper()
    return any(re.search(p, upper) for p in DEBIT_ONLY_PATTERNS)


def _looks_like_funding(description: str, matched_keyword: str) -> bool:
    """
    Heuristic for sectionless banks (Wells Fargo etc.):
    If the description STARTS with the lender keyword and contains a
    numeric batch ID or date — and has no debit-only words — it's almost
    certainly an inbound advance deposit.

    True  → "Expansion Capita Funding 5769267 Lady Luck Print CO"
    True  → "J & A Marketing PY04/23/26 00Sapp010 Lady Luck Print CO."
    False → "CCD DEBIT, FORWARD FINANCIN FF"
    False → "Lentegrity BILLPAY xxxxx5464"
    """
    if _is_debit_only(description):
        return False

    upper = description.upper()
    kw_upper = clean_text(matched_keyword)

    # Keyword appears at the very start of the description
    keyword_at_start = upper.lstrip().startswith(kw_upper)

    # Description contains a batch ID (5+ digits) or date
    has_batch_id = bool(re.search(r"\d{5,}", description))
    has_date     = bool(re.search(r"\d{2}/\d{2}/\d{2,4}", description))

    return keyword_at_start and (has_batch_id or has_date)


# ---------------------------------------------------------------------------
# MCA / Lender keyword dictionary
# ---------------------------------------------------------------------------

LENDER_KEYWORDS: dict[str, list[str]] = {
    # A
    "ACH CAPITAL": ["ACH CAPITAL"],
    "AFFIRM": ["AFFIRM", "AFFIRM PAY", "AFFIRM COM", "AFFIRM COM PAYME"],

    # B
    "BALBOA CAPITAL": ["BALBOA", "BALBOA CAPITAL"],
    "BITTY ADVANCE": ["BITTY", "BITTY ADVANCE", "MCA SAVINGS"],
    "BIZFUND": ["BIZFUND", "BIZFUND ACHDEBIT"],
    "BLUEVINE": ["BLUEVINE"],
    "BLACKBULL": ["BLACKBULL", "BLACKBULL ENTERP", "BLACKBULL WCTA"],
    "BREAKOUT CAPITAL": ["BREAKOUT", "BREAKOUT CAPITAL"],

    # C
    "CAN CAPITAL": ["CAN CAPITAL", "CANCAP", "CANACAP"],
    "CAPITAL INFUSION": ["CAP INFUSION", "CAPITAL INFUSION"],
    "CDC SMALL BUSINESS": ["CDC SMALL BUS", "CDC SMALL BUSINESS"],
    "CFGMS": ["CFGMS", "LCM", "LCM 1823095", "MC 844 662 3467"],
    "CHANNEL PARTNERS": ["CHANNEL PARTNERS", "LENDING SERVICES"],
    "CLEARCO": ["CLEARCO"],
    "CREDIBLY": ["CREDIBLY", "RETAIL CAPITAL"],

    # D
    "DAILY FUNDING": ["DAILY FUNDING", "DAILYFUNDING"],
    "DE LAGE LANDEN": ["DE LAGE LANDEN", "DELAGELANDEN", "DIRECT DEB DELAGELANDEN"],
    "DELTA": ["DELTA", "FUNDRY"],

    # E
    "EBF HOLDINGS": ["EBF", "EBF DEBIT", "EBF HOLDINGS", "HOLDINGS EBF"],
    "ELEVATED FUNDING": ["ELEVATED", "ELEVATED FUNDING"],
    "EMINENT FUNDING": ["EMINENT", "3329001101", "EMINENT FUNDING"],
    "EMS HOLDINGS": ["EMS", "EMS HOLDINGS"],
    "EVEREST BUSINESS FUNDING": ["EVEREST", "EBFUNDING", "EVEREST BUSINESS FUNDING"],
    "EXPANSION CAPITAL": [
        "EXP CAPITAL", "EXPANSION CAPITA", "EXPANSION CAPITAL",
        "EXPANSION CAPITA FUNDING", "EXPANSION CAPITAL FUNDING",
        "Expansion Capita Funding 5769267", "ECG LLC",
    ],

    # F
    "FORA FINANCIAL": ["FORA", "FORA FINANCIAL"],
    "FORWARD FINANCING": ["FORWARD FINANCIN", "FORWARD FINANCING"],
    "FUNDBOX": ["FUNDBOX"],
    "FUNDATION": ["FUNDATION"],
    "FUNDIFI": ["FUNDIFI", "FUNDFI"],
    "FUNDWORKS": [
        "FW CAPITAL", "FWCAPITAL", "FUNDWORKS", "FUND WORKS",
        "THE FUNDWORKS", "THE FUND WORKS", "FUNDWORK", "FUND WORK",
        "FUNDOWRK", "FUNDOWRKS", "FUND WRKS", "FUNDWK",
        "ACH FUNDWORKS", "FUNDWORKS LLC", "THE FUNDWORKS LLC",
    ],

    # G
    "GLOBAL MERCHANT": [
        "EDI PYMNTS", "GBL MERCHANT", "GLOBAL MER",
        "GLOBAL MER EDI", "GLOBAL MERCHANT", "WALL",
    ],
    "GREENBOX CAPITAL": ["GREENBOX", "GREENBOX CAPITAL"],
    "GFE": ["GFE", "UFCE", "UNITED FIRST", "GLOBAL FUNDING"],

    # H
    "HEADWAY CAPITAL": ["HEADWAY", "HEADWAY CAPITAL"],
    "HOUSE": ["HOUSE", "MRBIZCAP"],

    # I
    "IDEA FINANCIAL": ["IDEAFINANCIAL", "IDEA FINANCIAL"],
    "IOU FINANCIAL": ["IOU", "IOU FINANCIAL"],
    "IRUKA": ["IRUKA", "J&G", "ICG"],

    # J
    "J & A MARKETING": ["J & A MARKETING", "J A MARKETING", "J&A MARKETING"],
    "JRW CAPITAL": ["JRW CAPITAL", "JR CAPITAL LLC"],

    # K
    "KABBAGE": ["KABBAGE"],
    "KAPITUS": ["KAPITUS", "STRATEGIC FUNDING"],

    # L
    "LENDINI": ["LENDINI", "FUNDING METRICS"],
    "LENTEGRITY": ["LENTEGRITY", "LENTEGRITY BILLPAY"],
    "LG FUNDING": ["LG FUNDING", "LG FUNDING LLC"],
    "LIBERTAS FUNDING": ["LIBERTAS", "LIBERTAS FUNDING"],
    "LOANME": ["LOAN ME", "LOANME"],

    # M
    "MUDFLAP": ["MUDFLAP"],

    # N
    "NATIONAL FUNDING": ["NATIONAL FUNDING"],
    "NMEF": ["NMEF", "NMEF 2023 A"],

    # O
    "ONDECK": ["ON DECK", "ONDECK", "ENOVA"],

    # P
    "PAR FUNDING": ["PAR", "PAR FUNDING"],
    "PAYABILITY": ["PAYABILITY"],
    "PAYPAL WORKING CAPITAL": ["PAYPAL CAPITAL", "PAYPAL WORKING CAPITAL"],

    # Q
    "QUARTERSPOT": ["QUARTER SPOT", "QUARTERSPOT"],

    # R
    "RAPID FINANCE": ["RAPIDFINANCE", "RAPID FINANCE", "RAPID", "SBFS"],
    "RELIANT FUNDING": ["RELIANT", "RELIANT FUNDING"],
    "RETRO ADVANCE": ["RETRO ADVANCE", "RETROADVANCE"],

    # S
    "SHEAVES": ["SHEAVES", "3201961 ONTARRIO INC", "11302078 CANADA LTD"],
    "SMARTPAY": ["SMARTPAY", "SMARTPAY SOL"],
    "SPECIALTY": ["SPECIALTY", "ASCENTRA VENTURE"],
    "SQUARE CAPITAL": ["SQ CAPITAL", "SQUARE CAPITAL"],

    # T
    "TORRO": ["TORRO"],

    # V
    "VELOCITY CAPITAL": ["VELOCITY", "VELOCITY CAPITAL"],

    # Y
    "YELLOWSTONE CAPITAL": ["YELLOWSTONE", "YELLOWSTONE CAPITAL"],

    # Numeric / Other
    "2M7": ["2M7", "URAL LINK"],
}

# Keywords indicating a payment processor — NOT a lender
FALSE_LENDER_KEYWORDS: list[str] = [
    "SQ", "SQUARE", "PAYPAL", "PAY PAL", "STRIPE", "SNAP",
    "VENMO", "ZELLE", "CASHAPP", "INTUIT", "SHOPIFY",
    "CARD PURCHASE", "POS", "DEBIT CARD", "PURCHASE AUTHORIZED",
    "CLOVER", "TOAST",
]


# ---------------------------------------------------------------------------
# Core detection helpers
# ---------------------------------------------------------------------------

def detect_company(description: str, keyword_dict: dict) -> tuple[str, str]:
    clean_desc = clean_text(description)
    for lender_name, keywords in keyword_dict.items():
        for kw in keywords:
            if keyword_matches(clean_desc, clean_text(kw)):
                return lender_name, clean_text(kw)
    return "", ""


def is_false_lender(description: str) -> tuple[bool, str]:
    clean_desc = clean_text(description)
    for kw in FALSE_LENDER_KEYWORDS:
        if keyword_matches(clean_desc, clean_text(kw)):
            return True, kw
    return False, ""


# ---------------------------------------------------------------------------
# Lender debit extraction
# ---------------------------------------------------------------------------

def get_lender_debits(
    df: pd.DataFrame,
    total_revenue: float,
) -> tuple[pd.DataFrame, float, float]:
    """
    Scan the Debit column for MCA repayments.
    Skips rows that look like inbound funding deposits.
    """
    rows: list[dict] = []

    for _, row in df.iterrows():
        desc = str(row.get("Description", "")).strip()
        if not desc:
            desc = " ".join(str(v) for v in row.values if pd.notna(v))

        lender, kw = detect_company(desc, LENDER_KEYWORDS)
        if not lender:
            continue

        # Skip inbound funding
        if _is_funding_deposit(desc) or _looks_like_funding(desc, kw):
            continue

        debit = clean_money(row.get("Debit", 0))
        if debit <= 0:
            continue

        rows.append({
            "Date":                str(row.get("Date", "")),
            "Description":         desc,
            "Debit":               round(debit, 2),
            "Detected Lender":     lender,
            "Matched Keyword":     kw,
            "Lender Debit Amount": round(debit, 2),
        })

    result = pd.DataFrame(rows)
    total  = result["Lender Debit Amount"].sum() if not result.empty else 0.0
    rate   = (total / total_revenue * 100) if total_revenue > 0 else 0.0
    return result, total, rate


# ---------------------------------------------------------------------------
# Lender credit extraction
# ---------------------------------------------------------------------------

def get_lender_credits(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    """
    Scan for MCA / loan funding deposits using a 3-pass strategy.

    Pass 1 — Credit > 0  (standard banks with section headers)
    Pass 2 — Debit > 0 + FUNDING_DEPOSIT_PATTERNS match
              (sectionless banks: ACH PAYMEN, ACH ITEMS, etc.)
    Pass 3 — Debit > 0 + heuristic: lender keyword at description start
              + numeric batch ID or date + no debit-only words
              (catches "Expansion Capita Funding 5769267 …")
    """
    rows: list[dict] = []
    seen: set[tuple] = set()

    for _, row in df.iterrows():
        desc = str(row.get("Description", "")).strip()
        if not desc:
            desc = " ".join(str(v) for v in row.values if pd.notna(v))

        lender, kw = detect_company(desc, LENDER_KEYWORDS)
        if not lender:
            continue

        credit = clean_money(row.get("Credit", 0))
        debit  = clean_money(row.get("Debit",  0))

        # Pass 1 — correctly in Credit column
        if credit > 0:
            amount = credit

        # Pass 2 — funding pattern in description
        elif debit > 0 and _is_funding_deposit(desc):
            amount = debit

        # Pass 3 — heuristic: lender name at start + batch ID, no debit words
        elif debit > 0 and _looks_like_funding(desc, kw):
            amount = debit

        else:
            continue

        key = (str(row.get("Date", "")), desc, round(amount, 2))
        if key in seen:
            continue
        seen.add(key)

        rows.append({
            "Date":                 str(row.get("Date", "")),
            "Description":          desc,
            "Detected Lender":      lender,
            "Matched Keyword":      kw,
            "Lender Credit Amount": round(amount, 2),
        })

    result = pd.DataFrame(rows)
    total  = result["Lender Credit Amount"].sum() if not result.empty else 0.0
    return result, total