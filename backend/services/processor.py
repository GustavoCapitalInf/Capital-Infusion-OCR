"""
backend/services/processor.py
------------------------------
Pure business logic — no Streamlit, no FastAPI concerns.
Wraps the existing banks/ and utils/ modules.
"""
from __future__ import annotations

import io
import os
import re
import sys

import pandas as pd

# Make banks/ and utils/ importable from the project root
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from banks.base import parse_universal_bank_rows, parse_ocr_transactions, fix_lender_direction
from banks.router import route_and_extract
from utils.balance import extract_average_balance, extract_daily_balances_from_text
from utils.calculations import prepare_dataframe
from utils.cleaning import normalize_transaction_text, clean_money
from utils.dates import extract_statement_date, extract_statement_period
from utils.lender_detection import get_lender_debits, get_lender_credits
from utils.metrics import count_nsf, count_loan, extract_charges_only
from utils.ocr_headless import (
    extract_columnar_transactions_from_pdf,
    extract_text_from_pdf,
    extract_text_from_image,
    translate_to_english,
)
from utils.risk_detection import calculate_risk_level, generate_notes


# ---------------------------------------------------------------------------
# DataFrame helpers (extracted from app.py — UI-free)
# ---------------------------------------------------------------------------

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    keep = []
    for col in df.columns:
        try:
            sample = df[col].dropna()
            if sample.empty or isinstance(sample.iloc[0], (str, int, float, bool, type(None))):
                keep.append(col)
        except Exception:
            pass
    return df[keep] if keep else df


def _prep_raw_df(raw_df: pd.DataFrame) -> pd.DataFrame:
    raw_df = raw_df.copy()
    raw_df.columns = [str(c).strip() for c in raw_df.columns]
    col_map: dict[str, str] = {}
    for col in raw_df.columns:
        lower = col.lower()
        if "date" in lower:
            col_map[col] = "Date"
        elif "description" in lower or "memo" in lower or "details" in lower:
            col_map[col] = "Description"
        elif "withdrawal" in lower or "debit" in lower:
            col_map[col] = "Debit"
        elif "deposit" in lower or "credit" in lower:
            col_map[col] = "Credit"
        elif "amount" in lower:
            col_map[col] = "Amount"
    raw_df.rename(columns=col_map, inplace=True)
    for col in ["Date", "Description", "Debit", "Credit", "Amount"]:
        if col not in raw_df.columns:
            raw_df[col] = "" if col in ("Date", "Description") else 0.0
    for col in ["Debit", "Credit", "Amount", "Balance"]:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].apply(clean_money)
    if all(c in raw_df.columns for c in ["Amount", "Debit", "Credit"]):
        neg = (raw_df["Debit"] == 0) & (raw_df["Credit"] == 0) & (raw_df["Amount"] < 0)
        pos = (raw_df["Debit"] == 0) & (raw_df["Credit"] == 0) & (raw_df["Amount"] > 0)
        raw_df.loc[neg, "Debit"] = raw_df["Amount"].abs()
        raw_df.loc[pos, "Credit"] = raw_df["Amount"].abs()
    raw_df = _sanitize_df(raw_df)
    return fix_lender_direction(raw_df)


# ---------------------------------------------------------------------------
# Single-file processor
# ---------------------------------------------------------------------------

_SUSPICIOUS_KEYWORDS = ["SQ", "SQUARE", "PAYPAL", "PAY PAL", "STRIPE",
                        "SHOPIFY", "INTUIT", "CLOVER", "TOAST"]


def process_file(raw_bytes: bytes, filename: str, all_filenames: list[str]) -> dict:
    """
    Process one bank statement file and return a metrics dict + raw dataframes.
    Identical logic to app.process_file() — no Streamlit dependencies.
    """
    ext = os.path.splitext(filename.lower())[1]
    original_text = translated_text = ""
    charges_only_total = 0.0
    raw_df = pd.DataFrame()

    if ext == ".csv":
        raw_df = pd.read_csv(io.BytesIO(raw_bytes))
    elif ext in (".xlsx", ".xls"):
        raw_df = pd.read_excel(io.BytesIO(raw_bytes))
    elif ext == ".pdf":
        original_text = extract_text_from_pdf(raw_bytes)
        translated_text = normalize_transaction_text(translate_to_english(original_text))
        _, charges_only_total = extract_charges_only(translated_text)

        # RBC uses a multi-column layout with a "DD Mon" date format that the
        # universal parser can't handle — use the dedicated columnar extractor.
        from banks.rbc import RBCParser
        if RBCParser.is_this_bank(original_text):
            raw_df = RBCParser.parse_transactions(raw_bytes)
            if not raw_df.empty:
                print(f"[process_file] RBC columnar parser: {len(raw_df)} rows")

        # TD Bank uses a section-based layout (Deposits / Electronic Deposits /
        # Other Credits / Electronic Payments …) that the generic parser
        # misclassifies because "DEBIT CARD CREDIT" descriptions trigger the
        # debit-section heuristic.  Use the dedicated section-aware extractor.
        from banks.td import TDParser
        if raw_df.empty and TDParser.is_this_bank(original_text):
            raw_df = TDParser.parse_transactions(raw_bytes)
            if not raw_df.empty:
                print(f"[process_file] TD section parser: {len(raw_df)} rows")

        # Chase PDF layout places section headers AFTER their transactions, so
        # the generic parser can't detect sections before classifying rows.
        # ChaseParser.parse_transactions buffers rows and retroactively tags them
        # once the trailing section header is seen — fixing the Paymentech/PAYMENT
        # substring false-positive that marks all ACH deposits as debits.
        from banks.chase import ChaseParser
        if raw_df.empty and ChaseParser.is_this_bank(original_text):
            raw_df = ChaseParser.parse_transactions(original_text)
            if not raw_df.empty:
                print(f"[process_file] Chase section parser: {len(raw_df)} rows")

        # Capital One uses a Date | Description | Credits | Debits | Balance
        # column layout. Direction is determined by description keywords since
        # both credit and debit rows have the same two-amount structure.
        from banks.capital_one import CapitalOneParser
        if raw_df.empty and CapitalOneParser.is_this_bank(original_text):
            raw_df = CapitalOneParser.parse_transactions(original_text)
            if not raw_df.empty:
                print(f"[process_file] Capital One parser: {len(raw_df)} rows")

        # Generic fallback parsers
        if raw_df.empty:
            raw_df = parse_universal_bank_rows(translated_text)
        if raw_df.empty:
            raw_df = parse_ocr_transactions(translated_text)

        # If still no credits, try the generic columnar extractor
        credits_found = raw_df["Credit"].sum() if not raw_df.empty and "Credit" in raw_df.columns else 0
        if credits_found == 0:
            col_df = extract_columnar_transactions_from_pdf(raw_bytes)
            if not col_df.empty and col_df["Credit"].sum() > 0:
                raw_df = col_df
    else:
        original_text = extract_text_from_image(raw_bytes)
        translated_text = normalize_transaction_text(translate_to_english(original_text))
        raw_df = parse_universal_bank_rows(translated_text)
        if raw_df.empty:
            raw_df = parse_ocr_transactions(translated_text)

    file_bytes_io = io.BytesIO(raw_bytes) if ext == ".pdf" else None
    file_summary = route_and_extract(original_text, translated_text, file_bytes_io)

    print(f"[process_file] '{filename}' file_summary={file_summary}")

    raw_df = _prep_raw_df(raw_df) if not raw_df.empty else pd.DataFrame()
    temp_df = prepare_dataframe(raw_df) if not raw_df.empty else pd.DataFrame()

    print(f"[process_file] raw_df rows={len(raw_df)}, temp_df rows={len(temp_df)}")

    if file_summary["credits_amount"] > 0 or file_summary["debits_amount"] > 0:
        file_credits = file_summary["credits_amount"]
        file_debits  = file_summary["debits_amount"]
    else:
        file_credits = temp_df["Credit"].sum() if not temp_df.empty and "Credit" in temp_df.columns else 0.0
        file_debits  = temp_df["Debit"].sum()  if not temp_df.empty and "Debit"  in temp_df.columns else 0.0
        # raw_df is more complete than temp_df when prepare_dataframe drops rows
        # (e.g. date parsing issues).  Take the max so the higher value wins.
        if not raw_df.empty:
            rc = raw_df["Credit"].sum() if "Credit" in raw_df.columns else 0.0
            rd = raw_df["Debit"].sum()  if "Debit"  in raw_df.columns else 0.0
            if rc > file_credits:
                file_credits = round(rc, 2)
            if rd > file_debits:
                file_debits = round(rd, 2)

    print(f"[process_file] '{filename}' file_credits={file_credits}, file_debits={file_debits}")

    if not raw_df.empty:
        lender_rows, lender_debit_total, _ = get_lender_debits(raw_df, file_credits)
        lender_credit_rows, lender_credit_total = get_lender_credits(raw_df)
    else:
        lender_rows = lender_credit_rows = pd.DataFrame()
        lender_debit_total = lender_credit_total = 0.0

    file_true_revenue = file_credits - lender_credit_total
    withholding_rate = (lender_debit_total / file_true_revenue * 100) if file_true_revenue > 0 else 0.0
    nsf_count = count_nsf(temp_df, original_text)
    loan_count = count_loan(temp_df)

    avg_bal = extract_average_balance(original_text) if original_text else None
    if avg_bal is None:
        daily = extract_daily_balances_from_text(original_text) if original_text else []
        if not daily and not temp_df.empty and "Balance" in temp_df.columns:
            daily = [b for b in temp_df["Balance"].dropna().tolist() if b > 0]
        avg_bal = float(sum(daily) / len(daily)) if daily else 0.0

    flagged = []
    for line in translated_text.split("\n"):
        upper = str(line).upper()
        for kw in _SUSPICIOUS_KEYWORDS:
            if re.search(r"\b" + re.escape(kw) + r"\b", upper):
                amounts = re.findall(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}", line)
                flagged.append({
                    "keyword": kw,
                    "line": line.strip(),
                    "amount": abs(clean_money(amounts[0])) if amounts else 0.0,
                    "statement": filename,
                })
                break

    statement_date = extract_statement_date(original_text, filename, all_filenames)
    period_start, period_end = extract_statement_period(original_text) if original_text else (None, None)

    metrics = {
        "filename":          filename,
        "statement_date":    statement_date.isoformat() if statement_date else None,
        "period_start":      period_start.isoformat() if period_start else None,
        "period_end":        period_end.isoformat() if period_end else None,
        "credits":           round(file_credits, 2),
        "debits":            round(file_debits, 2),
        "cash_flow":         round(file_credits - file_debits, 2),
        "lender_debits":     round(lender_debit_total, 2),
        "lender_credits":    round(lender_credit_total, 2),
        "true_revenue":      round(file_credits - lender_credit_total, 2),
        "withholding_rate":  round(withholding_rate, 4),
        "nsf_count":         nsf_count,
        "loan_count":         loan_count,
        "avg_daily_balance": round(float(avg_bal), 2),
        "charges_only":      round(charges_only_total, 2),
    }

    return {
        "metrics":      metrics,
        "temp_df":      temp_df,
        "lender_rows":  lender_rows,
        "lender_credit_rows": lender_credit_rows,
        "flagged":      flagged,
    }


# ---------------------------------------------------------------------------
# Multi-file aggregator
# ---------------------------------------------------------------------------

def process_files(files: list[tuple[bytes, str]]) -> dict:
    """
    Process a list of (bytes, filename) tuples.
    Returns fully aggregated dashboard data.
    """
    all_filenames = [f[1] for f in files]
    statements = []
    all_lender_rows: list[pd.DataFrame] = []
    all_flagged: list[dict] = []
    all_transactions: list[dict] = []

    for raw_bytes, filename in files:
        result = process_file(raw_bytes, filename, all_filenames)
        m = result["metrics"]
        statements.append(m)

        if not result["lender_rows"].empty:
            lr = result["lender_rows"].copy()
            lr["statement"] = filename
            all_lender_rows.append(lr)

        all_flagged.extend(result["flagged"])

        if not result["temp_df"].empty:
            df = result["temp_df"].copy()
            df["statement"] = filename
            all_transactions.extend(df.to_dict("records"))

    n = max(len(statements), 1)
    total_credits  = sum(s["credits"]        for s in statements)
    total_debits   = sum(s["debits"]         for s in statements)
    total_ldr_deb  = sum(s["lender_debits"]  for s in statements)
    total_ldr_crd  = sum(s["lender_credits"] for s in statements)
    total_nsf      = sum(s["nsf_count"]      for s in statements)
    total_pos      = sum(s["loan_count"]      for s in statements)
    avg_bal        = sum(s["avg_daily_balance"] for s in statements) / n
    true_revenue   = total_credits - total_ldr_crd
    wh_rate        = (total_ldr_deb / true_revenue * 100) if true_revenue > 0 else 0.0

    totals = {
        "credits":           round(total_credits, 2),
        "debits":            round(total_debits, 2),
        "cash_flow":         round(total_credits - total_debits, 2),
        "lender_debits":     round(total_ldr_deb, 2),
        "lender_credits":    round(total_ldr_crd, 2),
        "true_revenue":      round(true_revenue, 2),
        "nsf_count":         total_nsf,
        "loan_count":         total_pos,
        "avg_daily_balance": round(avg_bal, 2),
        "withholding_rate":  round(wh_rate, 4),
    }

    averages = {
        "credits":           round(total_credits / n, 2),
        "debits":            round(total_debits / n, 2),
        "cash_flow":         round((total_credits - total_debits) / n, 2),
        "lender_debits":     round(total_ldr_deb / n, 2),
        "lender_credits":    round(total_ldr_crd / n, 2),
        "true_revenue":      round(true_revenue / n, 2),
        "nsf_count":         round(total_nsf / n, 2),
        "loan_count":         round(total_pos / n, 2),
        "avg_daily_balance": round(avg_bal, 2),
        "withholding_rate":  round(wh_rate, 4),
    }

    # Lender rows → serialisable list
    lenders = []
    if all_lender_rows:
        combined_lr = pd.concat(all_lender_rows, ignore_index=True)
        for _, row in combined_lr.iterrows():
            lenders.append({
                "lender":    str(row.get("Detected Lender", "")),
                "keyword":   str(row.get("Matched Keyword", "")),
                "amount":    float(row.get("Lender Debit Amount", 0.0)),
                "statement": str(row.get("statement", "")),
            })

    # Risk
    funding_detected = total_ldr_deb > 0
    risk_score, risk_level = calculate_risk_level(
        total_credits / n, total_debits / n, total_nsf, funding_detected
    )
    funders = list({r["lender"] for r in lenders if r["lender"]})
    notes = generate_notes(
        total_credits / n, total_debits / n,
        (total_credits - total_debits) / n,
        total_nsf, funding_detected, funders, wh_rate
    )

    # Transactions — make JSON-safe
    safe_txns = []
    for row in all_transactions:
        safe_row = {}
        for k, v in row.items():
            try:
                import math
                if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                    safe_row[k] = None
                elif hasattr(v, "item"):
                    safe_row[k] = v.item()
                elif hasattr(v, "isoformat"):
                    safe_row[k] = v.isoformat()
                else:
                    safe_row[k] = v
            except Exception:
                safe_row[k] = str(v)
        safe_txns.append(safe_row)

    return {
        "statements":   statements,
        "totals":       totals,
        "averages":     averages,
        "lenders":      lenders,
        "flagged":      all_flagged,
        "risk":         {"score": risk_score, "level": risk_level, "notes": notes},
        "transactions": safe_txns,
    }
