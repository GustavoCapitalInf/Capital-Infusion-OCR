"""
utils/calculations.py
---------------------
DataFrame preparation (column normalisation, type coercion, derived fields)
and monthly summary aggregation.
"""

from __future__ import annotations

import pandas as pd

from utils.risk_detection import detect_nsf


# ---------------------------------------------------------------------------
# Amount cleaning
# ---------------------------------------------------------------------------

def _clean_amount(value) -> float:
    if pd.isna(value) or value == "":
        return 0.0
    value = str(value).strip()
    for ch in "$,() ":
        value = value.replace(ch, "")
    try:
        return float(value)
    except (ValueError, TypeError):
        return 0.0


# ---------------------------------------------------------------------------
# Description-based heuristics
# ---------------------------------------------------------------------------

_DEBIT_WORDS = [
    "debit", "withdrawal", "withdraw", "purchase", "pos", "atm", "check",
    "payment", "ach debit", "fee", "charge", "payroll", "transfer out",
    "zelle payment", "cash app", "square capital", "loan payment", "mca",
    "funding payment", "returned item", "overdraft",
]

_CREDIT_WORDS = [
    "deposit", "credit", "ach credit", "merchant deposit", "stripe",
    "square deposit", "paypal deposit", "transfer in", "zelle deposit",
]


def _is_debit(description: str) -> bool:
    desc = str(description).lower()
    return any(w in desc for w in _DEBIT_WORDS)


def _is_credit(description: str) -> bool:
    desc = str(description).lower()
    return any(w in desc for w in _CREDIT_WORDS)


# ---------------------------------------------------------------------------
# Column aliases
# ---------------------------------------------------------------------------

_DATE_ALIASES = ["date", "transaction date", "posted date"]
_DESC_ALIASES = ["description", "details", "transaction", "memo"]
_AMOUNT_ALIASES = ["amount", "transaction amount"]
_DEBIT_ALIASES = ["debit", "debits", "withdrawal", "withdrawals", "money out"]
_CREDIT_ALIASES = ["credit", "credits", "deposit", "deposits", "money in"]


def _find_col(columns: list[str], aliases: list[str]) -> str | None:
    lower_map = {c.lower(): c for c in columns}
    for alias in aliases:
        if alias in lower_map:
            return lower_map[alias]
    return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def prepare_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalise any raw bank DataFrame (CSV, Excel, or parsed OCR rows) into
    a standard schema:

      Date | Description | Debit | Credit | Amount | Month | Type |
      NSF Flag | Funding Detected | Funded By
    """
    if df.empty:
        return pd.DataFrame()

    # Lower-case columns for alias matching
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    lower_cols = [c.lower() for c in df.columns]
    col_map = dict(zip(lower_cols, df.columns))

    def find(aliases: list[str]) -> str | None:
        for a in aliases:
            if a in col_map:
                return col_map[a]
        return None

    date_col = find(_DATE_ALIASES)
    desc_col = find(_DESC_ALIASES)
    amount_col = find(_AMOUNT_ALIASES)
    debit_col = find(_DEBIT_ALIASES)
    credit_col = find(_CREDIT_ALIASES)

    if not date_col:
        return pd.DataFrame()

    if not desc_col:
        df["description"] = ""
        desc_col = "description"

    clean_df = pd.DataFrame()
    clean_df["Date"] = pd.to_datetime(df[date_col], errors="coerce")
    clean_df["Description"] = df[desc_col].astype(str)

    if debit_col or credit_col:
        clean_df["Debit"] = df[debit_col].apply(_clean_amount).abs() if debit_col else 0.0
        clean_df["Credit"] = df[credit_col].apply(_clean_amount).abs() if credit_col else 0.0
        clean_df["Amount"] = clean_df["Credit"] - clean_df["Debit"]

    elif amount_col:
        clean_df["Amount"] = df[amount_col].apply(_clean_amount).abs()
        clean_df["Debit"] = 0.0
        clean_df["Credit"] = 0.0
        for idx, row in clean_df.iterrows():
            amt = abs(row["Amount"])
            desc = row["Description"]
            if _is_debit(desc):
                clean_df.at[idx, "Debit"] = amt
            elif _is_credit(desc):
                clean_df.at[idx, "Credit"] = amt
            else:
                clean_df.at[idx, "Debit"] = amt  # default unknown → debit
        clean_df["Amount"] = clean_df["Credit"] - clean_df["Debit"]

    else:
        return pd.DataFrame()

    # Pass Balance through if present (used for avg daily balance calculation)
    if "Balance" in df.columns:
        clean_df["Balance"] = df["Balance"].apply(_clean_amount)

    clean_df = clean_df.dropna(subset=["Date"])
    clean_df["Month"] = clean_df["Date"].dt.strftime("%B %Y")
    clean_df["Type"] = clean_df.apply(
        lambda r: "Debit" if r["Debit"] > 0 else "Credit", axis=1
    )
    clean_df["NSF Flag"] = clean_df["Description"].apply(detect_nsf)

    # Funding detection (lazy import to avoid circular dependency)
    try:
        from utils.funding_detection import detect_existing_funding
        funding = clean_df["Description"].apply(detect_existing_funding)
        clean_df["Funding Detected"] = funding.apply(lambda x: x[0])
        clean_df["Funded By"] = funding.apply(lambda x: x[1])
    except ImportError:
        clean_df["Funding Detected"] = False
        clean_df["Funded By"] = ""

    return clean_df


def create_monthly_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Aggregate prepared transactions into a per-month summary table."""
    if df.empty:
        return pd.DataFrame()

    monthly = (
        df.groupby("Month")
        .agg(
            Monthly_Revenue=("Credit", "sum"),
            Monthly_Debits=("Debit", "sum"),
            Transaction_Count=("Amount", "count"),
            NSF_Count=("NSF Flag", "sum"),
        )
        .reset_index()
    )
    monthly["Monthly_Cash_Flow"] = monthly["Monthly_Revenue"] - monthly["Monthly_Debits"]
    monthly["Withholding_Rate"] = monthly.apply(
        lambda r: (r["Monthly_Debits"] / r["Monthly_Revenue"] * 100)
        if r["Monthly_Revenue"] > 0 else 0,
        axis=1,
    )
    return monthly
