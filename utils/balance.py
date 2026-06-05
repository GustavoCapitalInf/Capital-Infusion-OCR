"""
utils/balance.py
----------------
Average daily balance extraction.

Level 0  — Bank-printed average from the monthly service-fee block.
Level 1  — Date-weighted calculation from a Daily Balance Summary section.
Level 2  — Date-weighted calculation from sparse "Ending daily balance" column.
Level 3  — Return None (caller decides on a fallback).
"""

import re
from datetime import date as _date

import pandas as pd

from utils.cleaning import safe_money_balance


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_mmdd(month_day_str: str, ref_year: int) -> _date | None:
    parts = month_day_str.split("/")
    try:
        m, d = int(parts[0]), int(parts[1])
        if len(parts) == 3:
            y = int(parts[2])
            y = y + 2000 if y < 100 else y
        else:
            y = ref_year
        return _date(y, m, d)
    except Exception:
        return None


_SECTION_HEADERS = [
    r"DAILY\s+ENDING\s+BALANCE",
    r"DAILY\s*BALANCE\s*SUMMARY",
    r"Daily\s*ledger\s*balances",
    r"END(?:ING)?\s+BALANCE\s+SUMMARY",
    r"SOLDE\s+DE\s+FIN\s+DE\s+JOURN[EÉ]E",
]

_STOP_PAT = (
    r"SERVICE\s+CHARGE\s+(?:SUMMARY|DETAIL)"
    r"|SERVICE\s+FEE\s+SUMMARY"
    r"|FRAIS"
    r"|INTEREST\s+CHARGE"
    r"|ACCOUNT\s+SUMMARY"
    r"|SAVINGS\s+SUMMARY"
    r"|#\d{3,}"
)

_INVALID_CONTEXT = [
    "TRACE", "REFERENCE", "ACCOUNT", "ROUTING",
    "CHECK #", "CARD", "ID #", "PHONE", "AUTHORIZED",
]

_LEVEL0_PATTERNS = [
    # \s* instead of \s+ so compressed PDFs ("AverageCollectedBalance") also match
    # Wells Fargo — threshold then actual
    r"Average\s*[Ll]edger\s*[Bb]alance\s+\$?[\d,]+\.?\d*\s+(-?\$?[\d,]+\.?\d+)",
    r"Average\s*[Ll]edger\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d+)",
    r"Average\s*[Dd]aily\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d*)",
    r"Average\s*[Cc]ollected\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d*)",
    r"Average\s*[Aa]vailable\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d*)",
    r"Average\s*[Cc]losing\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d*)",
    r"Solde\s*moyen\s*\$?\s*(-?[\d,]+\.?\d*)",
    r"Average\s*\w+\s*[Bb]alance\s*\$?\s*(-?[\d,]+\.?\d*)",
    # TD Canada Trust: "MONTHLY AVER. CR. BAL. $294.88"
    r"MONTHLY\s+AVER\w*\.?\s+CR\.?\s+BAL\.?\s+\$?\s*(-?[\d,]+\.?\d*)",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_average_balance(text: str) -> float | None:
    """Return the average daily balance, or None when unavailable."""
    if not text:
        return None

    flat = re.sub(r"\s+", " ", text)
    year_m = re.search(r"\b(20\d{2})\b", text)
    ref_year = int(year_m.group(1)) if year_m else _date.today().year

    # ── Level 0 — Bank-printed average (checked FIRST; most authoritative) ──
    # TD Bank prints "Average Collected Balance"; Wells Fargo prints
    # "Average Ledger Balance"; Chase prints "Average Daily Balance".
    # Prefer the bank's own stated figure over any computed average.
    for pattern in _LEVEL0_PATTERNS:
        m = re.search(pattern, flat, re.IGNORECASE)
        if not m:
            continue
        # Use a 30-char lookback so section headers like "ACCOUNT SUMMARY"
        # that appear 40+ chars earlier don't falsely trigger the ACCOUNT filter.
        context = flat[max(0, m.start() - 30): m.end()].upper()
        if any(kw in context for kw in _INVALID_CONTEXT):
            continue
        val = safe_money_balance(m.group(1).replace("$", "").strip())
        if val is not None:
            return val

    # ── Level 1 — Structured Daily Balance section ────────────────────────
    cleaned = re.sub(r"\*(?:start|end)\*[^\n]*\n?", "\n", text, flags=re.IGNORECASE)

    # Detect period-end date for Chase-style statements
    period_end_l1 = None
    pe_m = re.search(
        r"through\s+((?:January|February|March|April|May|June|July|August|"
        r"September|October|November|December)\s+\d{1,2},?\s+\d{4})",
        flat, re.IGNORECASE,
    )
    if pe_m:
        try:
            period_end_l1 = pd.to_datetime(pe_m.group(1)).date()
        except Exception:
            pass

    section_pat = "|".join(f"(?:{p})" for p in _SECTION_HEADERS)
    sections = re.findall(
        rf"(?:{section_pat}).*?(?={_STOP_PAT}|\Z)",
        cleaned, re.IGNORECASE | re.DOTALL,
    )

    if sections:
        raw_pairs = re.findall(
            r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+\$?(-?[\d,]+\.\d{2})",
            sections[0],
        )
        # Chase corrupt-tag recovery
        for line in text.split("\n"):
            if (line.strip().startswith("*end*")
                    and "balance" in line.lower()
                    and "ending" in line.lower()):
                for amt in re.findall(r"-?[\d,]{4,}\.\d{2}", line):
                    raw_pairs.append(("corrupt", amt))

        date_balance_pairs = [
            (ds, v)
            for ds, amt in raw_pairs
            if (v := safe_money_balance(amt)) is not None
        ]

        if date_balance_pairs:
            dated = [
                (_parse_mmdd(ds, ref_year), v)
                for ds, v in date_balance_pairs
                if ds != "corrupt"
            ]
            dated = [(d, v) for d, v in dated if d is not None]
            if period_end_l1:
                dated = [(d, v) for d, v in dated if d <= period_end_l1]

            all_vals = [v for _, v in date_balance_pairs]
            return sum(all_vals) / len(all_vals)

    # ── Level 2 — Sparse "Ending daily balance" column ───────────────────
    begin_m = re.search(
        r"Beginning\s+balance\s+on\s+(\d{1,2}/\d{1,2})\s+(-?\$?[\d,]+\.?\d+)",
        flat, re.IGNORECASE,
    )
    beginning_balance = None
    start_date = None
    if begin_m:
        beginning_balance = safe_money_balance(begin_m.group(2).replace("$", ""))
        start_date = _parse_mmdd(begin_m.group(1), ref_year)

    end_m = re.search(
        r"Ending\s+balance\s+on\s+(\d{1,2}/\d{1,2})",
        flat, re.IGNORECASE,
    )
    period_end = _parse_mmdd(end_m.group(1), ref_year) if end_m else None

    has_balance_col = bool(
        re.search(r"Ending\s+daily\s+balance", text, re.IGNORECASE)
        or re.search(r"Ending\s+balance", text, re.IGNORECASE)
        or re.search(r"Running\s+balance", text, re.IGNORECASE)
    )

    sparse_pairs: list[tuple[_date, float]] = []
    if has_balance_col:
        SKIP = [
            "TOTAL", "BALANCE FORWARD", "OPENING", "CLOSING", "BEGINNING",
            "SERVICE FEE", "ITEMS RETURNED", "AVERAGE", "MINIMUM",
        ]
        tx_pat = re.compile(
            r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?).*?(-?\$?[\d,]+\.\d{2})\s*$",
            re.MULTILINE,
        )
        for m in tx_pat.finditer(text):
            if any(kw in m.group(0).upper() for kw in SKIP):
                continue
            if len(re.findall(r"-?\$?[\d,]+\.\d{2}", m.group(0))) < 2:
                continue
            d = _parse_mmdd("/".join(m.group(1).split("/")[:2]), ref_year)
            if d is None:
                continue
            val = safe_money_balance(m.group(2).replace("$", ""))
            if val is not None:
                sparse_pairs.append((d, val))

    all_points: list[tuple[_date, float]] = []
    if beginning_balance is not None and start_date is not None:
        all_points.append((start_date, beginning_balance))
    all_points.extend(sparse_pairs)

    if all_points:
        seen: dict[_date, float] = {}
        for d, v in all_points:
            seen[d] = v
        all_points = sorted(seen.items())

        if len(all_points) >= 2:
            if period_end is None:
                period_end = all_points[-1][0]
            total_weighted = total_days = 0.0
            for i, (d, v) in enumerate(all_points):
                next_d = all_points[i + 1][0] if i + 1 < len(all_points) else (
                    period_end if period_end and period_end > d else d
                )
                days = (next_d - d).days
                if days > 0:
                    total_weighted += v * days
                    total_days += days
            if total_days > 0:
                return total_weighted / total_days

    # ── Level 3 ───────────────────────────────────────────────────────────
    return None


def extract_daily_balances_from_text(text: str) -> list[float]:
    """
    Lightweight helper: return a list of balance values found in the
    daily-balance section (used as a quick fallback when Level 0–2 fail).
    """
    if not text:
        return []

    cleaned = re.sub(r"\*(?:start|end)\*[^\n]*\n?", "\n", text, flags=re.IGNORECASE)
    section_pat = "|".join(f"(?:{p})" for p in _SECTION_HEADERS)
    stop_pat = r"SERVICE\s+CHARGE|SERVICE\s+FEE|FRAIS|INTEREST\s+CHARGE|ACCOUNT\s+SUMMARY"

    sections = re.findall(
        rf"(?:{section_pat}).*?(?={stop_pat}|\Z)",
        cleaned, re.IGNORECASE | re.DOTALL,
    )

    balances: list[float] = []
    if sections:
        raw = re.findall(
            r"(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+\$?(-?[\d,]+\.\d{2})",
            sections[0],
        )
        for _, amt in raw:
            v = safe_money_balance(amt)
            if v is not None:
                balances.append(v)

    if not balances:
        for line in cleaned.split("\n"):
            line = line.strip()
            if not line or len(line) < 10:
                continue
            if re.match(r"^\d{1,2}[/\-]\d{1,2}", line):
                amts = re.findall(r"-?[\d,]+\.\d{2}", line)
                if amts:
                    v = safe_money_balance(amts[-1])
                    if v is not None:
                        balances.append(v)

    return balances
