"""
utils/dates.py
--------------
Statement date extraction from OCR text and filenames.
"""

import re
from collections import Counter
from datetime import datetime

import pandas as pd


MONTH_MAP = {
    "january": 1, "jan": 1,
    "february": 2, "feb": 2,
    "march": 3, "mar": 3,
    "april": 4, "apr": 4,
    "may": 5,
    "june": 6, "jun": 6,
    "july": 7, "jul": 7,
    "august": 8, "aug": 8,
    "september": 9, "sep": 9,
    "october": 10, "oct": 10,
    "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}

_MONTH_NAMES = (
    "January|February|March|April|May|June|July|August|"
    "September|October|November|December"
)


def extract_statement_date(
    text: str,
    filename: str = "",
    all_filenames: list[str] | None = None,
) -> pd.Timestamp | None:
    """
    Extract the end date of a statement period.

    Priority:
      1. Chase "X through Y" pattern  → uses end date
      2. Generic date patterns in text
      3. Month name in filename  + year from filename / sibling files / system
    """

    # 1 — Chase "through" format
    chase = re.search(
        rf"(?:{_MONTH_NAMES})\s+\d{{1,2}},?\s+\d{{4}}\s+through\s+"
        rf"((?:{_MONTH_NAMES})\s+\d{{1,2}},?\s+\d{{4}})",
        text, re.IGNORECASE,
    )
    if chase:
        try:
            return pd.to_datetime(chase.group(1))
        except Exception:
            pass

    # 2 — Generic patterns
    for pattern in [
        r"statement\s+(?:period|date)[:\s]+([A-Za-z]+\s+\d{1,2}[\s,]+\d{4})",
        r"period\s+ending\s+([A-Za-z]+\s+\d{1,2},?\s+\d{4})",
        r"\b(\d{1,2}/\d{1,2}/\d{4})\b",
        r"\b(\d{4}-\d{2}-\d{2})\b",
    ]:
        m = re.search(pattern, text, re.IGNORECASE)
        if m:
            try:
                return pd.to_datetime(m.group(1))
            except Exception:
                continue

    # 3 — Filename fallback
    name = filename.lower()
    year_m = re.search(r"\b(20\d{2})\b", name)
    if year_m:
        year = int(year_m.group(1))
    elif all_filenames:
        years = re.findall(r"\b(20\d{2})\b", " ".join(all_filenames).lower())
        year = int(Counter(years).most_common(1)[0][0]) if years else datetime.now().year
    else:
        year = datetime.now().year

    for month_name, month_num in MONTH_MAP.items():
        if month_name in name:
            return pd.Timestamp(year=year, month=month_num, day=1)

    return None
