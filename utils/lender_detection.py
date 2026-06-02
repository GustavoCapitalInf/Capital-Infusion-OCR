"""
utils/lender_detection.py
-------------------------
MCA / lender keyword dictionary and detection functions.
"""

from __future__ import annotations

import re
import pandas as pd

from utils.cleaning import clean_text, clean_money, keyword_matches


# ---------------------------------------------------------------------------
# Known credit-only lender name fragments
# If ANY of these appear in a description, it is ALWAYS an inbound credit
# regardless of which column it landed in.
# ---------------------------------------------------------------------------

ALWAYS_CREDIT_SUBSTRINGS: list[str] = [
    "EXPANSION CAPITA",
    "EXPANSION CAPITAL FUND",
    "RETRO ADVANCE INC",
    "J & A MARKETING",
    "J&A MARKETING",
    "CDC SMALL BUS",
    "BLACKBULL ENTERP",
    "00SAPP010",
]

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
    r"PY\d{2}/\d{2}/\d{2}",
    r"00SAPP010",
    r"CAPITA\s+FUNDING",
    r"CAPITAL\s+FUNDING",
    r"FUNDING\s+\d{5,}",
    r"ADVANCE\s+INC",
    r"SALE\s+\d{6}",
    r"EXPANSION\s+CAPITA",
]

DEBIT_ONLY_PATTERNS: list[str] = [
    r"\bBILLPAY\b",
    r"\bBILL\s*PAY\b",
    r"\bPAYMENT\b",
    r"\bPMT\b",
    r"\bREPAY\b",
    r"CCD\s+DEBIT",
    r"ACH\s+DEBIT",
    r"PURCHASE\s+AUTH",
    r"\bCHECKCARD\b",     # BofA debit card transaction — always a debit
    r"SHOPIFY\s+CAPITAL\s+DES",  # Shopify Capital repayment ACH
    r"SHOPIFY\s+CREDIT\s+DES",   # Shopify Credit repayment ACH (misleading name — it's a debit)
    r"\bDES:",            # ACH debit descriptor field (OnDeck, Forward Financing)
    r"\bINDN:",           # ACH individual name field
    r"\bID:RPP",          # Forward Financing ACH ID
    r"\bID:XXXXXXXXX",    # OnDeck masked ACH ID
    r"\bCO\s+ID:",       # ACH company ID field
    r"\s+CCD$",           # CCD at end of line = ACH debit entry
]


def _is_always_credit(description: str) -> bool:
    """Check if description contains a known credit-only lender fragment."""
    upper = description.upper()
    return any(s in upper for s in ALWAYS_CREDIT_SUBSTRINGS)


# Descriptions containing these are returned/unpaid items — skip entirely from lender detection
SKIP_LENDER_SUBSTRINGS: list[str] = [
    "REFERENCE #",        # Wells Fargo "Items returned unpaid" — bounced, not real transactions
]

def _should_skip_lender(description: str) -> bool:
    upper = description.upper()
    return any(s in upper for s in SKIP_LENDER_SUBSTRINGS)


ALWAYS_DEBIT_SUBSTRINGS: list[str] = [
    "SHOPIFY CAPITAL DES",
    "SHOPIFY CREDIT DES",
    "CHECKCARD",
    "ORIG CO NAME:",      # Chase ACH debit format — always outgoing repayment
    "REFERENCE #",        # Wells Fargo returned/unpaid item — attempted debit that bounced
]

def _is_always_debit(description: str) -> bool:
    upper = description.upper()
    return any(s in upper for s in ALWAYS_DEBIT_SUBSTRINGS)

def _is_funding_deposit(description: str) -> bool:
    upper = description.upper()
    return any(re.search(p, upper) for p in FUNDING_DEPOSIT_PATTERNS)


def _is_debit_only(description: str) -> bool:
    upper = description.upper()
    return any(re.search(p, upper) for p in DEBIT_ONLY_PATTERNS)


def _looks_like_funding(description: str, matched_keyword: str) -> bool:
    if _is_debit_only(description):
        return False
    upper = description.upper()
    kw_upper = clean_text(matched_keyword)
    keyword_at_start = upper.lstrip().startswith(kw_upper)
    has_batch_id = bool(re.search(r"\d{5,}", description))
    has_date = bool(re.search(r"\d{2}/\d{2}/\d{2,4}", description))
    return keyword_at_start and (has_batch_id or has_date)


# ---------------------------------------------------------------------------
# MCA / Lender keyword dictionary
# ---------------------------------------------------------------------------

LENDER_KEYWORDS: dict[str, list[str]] = {
    "ACH CAPITAL": ["ACH CAPITAL"],
    "AFFIRM": ["AFFIRM", "AFFIRM PAY", "AFFIRM COM", "AFFIRM COM PAYME"],
    "BALBOA CAPITAL": ["BALBOA", "BALBOA CAPITAL"],
    "BITTY ADVANCE": ["BITTY", "BITTY ADVANCE", "MCA SAVINGS"],
    "BIZFUND": ["BIZFUND", "BIZFUND ACHDEBIT"],
    "BLUEVINE": ["BLUEVINE"],
    "BLACKBULL": ["BLACKBULL", "BLACKBULL ENTERP", "BLACKBULL WCTA"],
    "BREAKOUT CAPITAL": ["BREAKOUT", "BREAKOUT CAPITAL"],
    "CAN CAPITAL": ["CAN CAPITAL", "CANCAP", "CANACAP"],
    "CAPITAL INFUSION": ["CAP INFUSION", "CAPITAL INFUSION"],
    "CDC SMALL BUSINESS": ["CDC SMALL BUS", "CDC SMALL BUSINESS"],
    "CFGMS": ["CFGMS", "LCM", "LCM 1823095", "MC 844 662 3467"],
    "CHANNEL PARTNERS": ["CHANNEL PARTNERS", "LENDING SERVICES"],
    "CLEARCO": ["CLEARCO"],
    "CREDIBLY": ["CREDIBLY", "RETAIL CAPITAL"],
    "DAILY FUNDING": ["DAILY FUNDING", "DAILYFUNDING"],
    "DE LAGE LANDEN": ["DE LAGE LANDEN", "DELAGELANDEN", "DIRECT DEB DELAGELANDEN"],
    "DELTA": ["DELTA", "FUNDRY"],
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
    "FORA FINANCIAL": ["FORA", "FORA FINANCIAL"],
    "FORWARD FINANCING": ["FORWARD FINANCIN", "FORWARD FINANCING", "FORWARDFINANCIN", "FORWARD FINANCINFF"],
    "FUNDBOX": ["FUNDBOX"],
    "FUNDATION": ["FUNDATION"],
    "FUNDIFI": ["FUNDIFI", "FUNDFI"],
    "FUNDWORKS": [
        "FW CAPITAL", "FWCAPITAL", "FUNDWORKS", "FUND WORKS",
        "THE FUNDWORKS", "THE FUND WORKS", "FUNDWORK", "FUND WORK",
        "FUNDOWRK", "FUNDOWRKS", "FUND WRKS", "FUNDWK",
        "ACH FUNDWORKS", "FUNDWORKS LLC", "THE FUNDWORKS LLC",
    ],
    "GLOBAL MERCHANT": ["EDI PYMNTS", "GBL MERCHANT", "GLOBAL MER", "GLOBAL MER EDI", "GLOBAL MERCHANT", "WALL"],
    "GREENBOX CAPITAL": ["GREENBOX", "GREENBOX CAPITAL"],
    "GFE": ["GFE", "UFCE", "UNITED FIRST", "GLOBAL FUNDING"],
    "HEADWAY CAPITAL": ["HEADWAY", "HEADWAY CAPITAL"],
    "HOUSE": ["HOUSE", "MRBIZCAP"],
    "IDEA FINANCIAL": ["IDEAFINANCIAL", "IDEA FINANCIAL"],
    "IOU FINANCIAL": ["IOU", "IOU FINANCIAL"],
    "IRUKA": ["IRUKA", "J&G", "ICG"],
    "J & A MARKETING": ["J & A MARKETING", "J A MARKETING", "J&A MARKETING"],
    "JRW CAPITAL": ["JRW CAPITAL", "JR CAPITAL LLC"],
    "KABBAGE": ["KABBAGE"],
    "KAPITUS": ["KAPITUS", "STRATEGIC FUNDING"],
    "LENDINI": ["LENDINI", "FUNDING METRICS"],
    "LENTEGRITY": ["LENTEGRITY", "LENTEGRITY BILLPAY"],
    "LG FUNDING": ["LG FUNDING", "LG FUNDING LLC"],
    "LIBERTAS FUNDING": ["LIBERTAS", "LIBERTAS FUNDING"],
    "LOANME": ["LOAN ME", "LOANME"],
    "MUDFLAP": ["MUDFLAP"],
    "NATIONAL FUNDING": ["NATIONAL FUNDING"],
    "NMEF": ["NMEF", "NMEF 2023 A"],
    "ONDECK": ["ON DECK", "ONDECK", "ENOVA"],
    "PAR FUNDING": ["PAR", "PAR FUNDING"],
    "PAYABILITY": ["PAYABILITY"],
    "PAYPAL WORKING CAPITAL": ["PAYPAL CAPITAL", "PAYPAL WORKING CAPITAL"],
    "QUARTERSPOT": ["QUARTER SPOT", "QUARTERSPOT"],
    "RAPID FINANCE": ["RAPIDFINANCE", "RAPID FINANCE", "RAPID", "SBFS"],
    "RELIANT FUNDING": ["RELIANT", "RELIANT FUNDING"],
    "RETRO ADVANCE": ["RETRO ADVANCE", "RETROADVANCE", "RETROADVANCEINC", "RETRO ADVANCE INC"],
    "SHEAVES": ["SHEAVES", "3201961 ONTARRIO INC", "11302078 CANADA LTD"],
    "SMARTPAY": ["SMARTPAY", "SMARTPAY SOL"],
    "SPECIALTY": ["SPECIALTY", "ASCENTRA VENTURE"],
    "SHOPIFY CAPITAL": ["SHOPIFY CAPITAL", "SHOPIFY CREDIT"],
    "SQUARE CAPITAL": ["SQ CAPITAL", "SQUARE CAPITAL"],
    "TORRO": ["TORRO"],
    "VELOCITY CAPITAL": ["VELOCITY", "VELOCITY CAPITAL"],
    "YELLOWSTONE CAPITAL": ["YELLOWSTONE", "YELLOWSTONE CAPITAL"],
    "2M7": ["2M7", "URAL LINK"],
}

FALSE_LENDER_KEYWORDS: list[str] = [
    "SQ", "SQUARE", "PAYPAL", "PAY PAL", "STRIPE", "SNAP",
    "VENMO", "ZELLE", "CASHAPP", "INTUIT", "SHOPIFY",
    "CARD PURCHASE", "POS", "DEBIT CARD", "PURCHASE AUTHORIZED",
    "CLOVER", "TOAST",
]


def detect_company(description: str, keyword_dict: dict) -> tuple[str, str]:
    clean_desc = clean_text(description)
    # Also try stripping common ACH prefixes (squished OCR: "CCDDEBIT,FORWARDFINANCIN")
    stripped = re.sub(r"^(CCD\s*DEBIT[,\s]*|ACH\s*DEBIT[,\s]*|ACH\s*PMT[,\s]*|WIRE\s*TRANSFER\s*INCOMING[,\s]*|TRANSFER\s*INCOMING[,\s]*)", "", clean_desc, flags=re.IGNORECASE).strip()

    for desc_variant in [clean_desc, stripped]:
        for lender_name, keywords in keyword_dict.items():
            for kw in keywords:
                ck = clean_text(kw)
                if keyword_matches(desc_variant, ck):
                    return lender_name, ck
                # Handle squished format: "RETROADVANCE9547435581..." starts with keyword
                if desc_variant.startswith(ck) or desc_variant.startswith(ck.replace(" ", "")):
                    return lender_name, ck
    return "", ""


def is_false_lender(description: str) -> tuple[bool, str]:
    clean_desc = clean_text(description)
    for kw in FALSE_LENDER_KEYWORDS:
        if keyword_matches(clean_desc, clean_text(kw)):
            return True, kw
    return False, ""


def get_lender_debits(
    df: pd.DataFrame,
    total_revenue: float,
) -> tuple[pd.DataFrame, float, float]:
    rows: list[dict] = []
    for _, row in df.iterrows():
        desc = str(row.get("Description", "")).strip()
        if not desc:
            desc = " ".join(str(v) for v in row.values if pd.notna(v))
        # Skip garbage rows (very long descriptions = OCR boilerplate garbage)
        if len(desc) > 400:
            continue
        lender, kw = detect_company(desc, LENDER_KEYWORDS)
        if not lender:
            continue
        # _is_always_debit takes priority — even known credit lenders can have returned items
        # Exception: REFERENCE # + ACH ITEMS/ACH DEBIT = lender tried to collect and bounced
        # = money never left, skip from debits (not Blackbull "SALE" which is a customer payment)
        if _is_always_debit(desc):
            upper_desc = desc.upper()
            is_bounced_collection = (
                "REFERENCE #" in upper_desc
                and ("ACH ITEMS" in upper_desc or "ACH DEBIT" in upper_desc)
            )
            if is_bounced_collection:
                continue  # bounced lender collection, money never left
        else:
            if _is_always_credit(desc) or _is_funding_deposit(desc) or _looks_like_funding(desc, kw):
                continue
        debit = clean_money(row.get("Debit", 0))
        # For always-debit rows, also check Credit column (misclassified by parser)
        if debit <= 0 and _is_always_debit(desc):
            debit = clean_money(row.get("Credit", 0))
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
    total = result["Lender Debit Amount"].sum() if not result.empty else 0.0
    rate = (total / total_revenue * 100) if total_revenue > 0 else 0.0
    return result, total, rate


def get_lender_credits(df: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    rows: list[dict] = []
    seen: set[tuple] = set()
    for _, row in df.iterrows():
        desc = str(row.get("Description", "")).strip()
        if not desc:
            desc = " ".join(str(v) for v in row.values if pd.notna(v))
        lender, kw = detect_company(desc, LENDER_KEYWORDS)
        if not lender:
            continue
        # Skip garbage rows and returned/unpaid items
        if len(desc) > 400 or _should_skip_lender(desc):
            continue
        # Skip known outgoing repayments regardless of which column they landed in
        if _is_always_debit(desc):
            continue
        credit = clean_money(row.get("Credit", 0))
        debit  = clean_money(row.get("Debit", 0))
        # Use whichever column has a value
        raw_amount = credit if credit > 0 else debit

        # Pass 0 — ALWAYS_CREDIT description: use whichever column has value
        if _is_always_credit(desc) and raw_amount > 0:
            amount = raw_amount
        # Pass 1 — Credit column
        elif credit > 0:
            amount = credit
        # Pass 2 — known credit substrings with debit column
        elif debit > 0 and _is_always_credit(desc):
            amount = debit
        # Pass 3 — funding deposit patterns
        elif debit > 0 and _is_funding_deposit(desc):
            amount = debit
        # Pass 4 — heuristic
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
    total = result["Lender Credit Amount"].sum() if not result.empty else 0.0
    return result, total
