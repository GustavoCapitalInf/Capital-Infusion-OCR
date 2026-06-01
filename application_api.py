"""
application_api.py
------------------
Flask API with two endpoints:

POST /parse-application
    Receives a completed Capital Infusion funding application PDF and returns
    parsed fields as JSON.

    Content-Type: multipart/form-data
    Body:         file=<pdf>  [client_id=<str>]

POST /parse-bank-statement
    Receives one or more bank statement files (PDF / PNG / JPG / CSV / XLSX)
    and returns OCR-extracted financial metrics per statement plus aggregated
    totals and monthly averages.

    Content-Type: multipart/form-data
    Body:         files[]=<file> ...  [client_id=<str>]

GET /health
    Returns {"status": "ok"}
"""

import io
import json
import os

import pandas as pd
import requests as _requests

from flask import Flask, jsonify, request

from utils.application_ocr import parse_signed_application
from utils.ocr_headless import extract_text_from_pdf, extract_text_from_image
from utils.cleaning import normalize_transaction_text, clean_money, fix_spaced_ocr_text
from utils.ocr import translate_to_english
from banks.router import route_and_extract
from banks.base import parse_universal_bank_rows, parse_ocr_transactions, fix_lender_direction
from utils.calculations import prepare_dataframe
from utils.lender_detection import get_lender_debits, get_lender_credits
from utils.metrics import count_nsf, count_pos, extract_charges_only
from utils.balance import extract_average_balance, extract_daily_balances_from_text
from utils.dates import extract_statement_date

_LENDER_APP_URL = "https://lendersuggestion.onrender.com"

_ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".xls"}

app = Flask(__name__)


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
        raw_df.loc[neg, "Debit"]  = raw_df["Amount"].abs()
        raw_df.loc[pos, "Credit"] = raw_df["Amount"].abs()
    return fix_lender_direction(raw_df)


def _process_statement(raw_bytes: bytes, filename: str, all_filenames: list[str]) -> dict:
    """Run the full bank statement pipeline on raw file bytes. Returns a metrics dict."""
    ext = os.path.splitext(filename.lower())[1]
    original_text = ""
    translated_text = ""
    charges_only_total = 0.0
    raw_df = pd.DataFrame()

    if ext == ".csv":
        raw_df = pd.read_csv(io.BytesIO(raw_bytes))
    elif ext in (".xlsx", ".xls"):
        raw_df = pd.read_excel(io.BytesIO(raw_bytes))
    elif ext == ".pdf":
        original_text   = extract_text_from_pdf(raw_bytes)
        translated_text = normalize_transaction_text(translate_to_english(original_text))
        _, charges_only_total = extract_charges_only(translated_text)
        raw_df = parse_universal_bank_rows(translated_text)
        if raw_df.empty:
            raw_df = parse_ocr_transactions(translated_text)
    else:  # image
        original_text   = extract_text_from_image(raw_bytes)
        translated_text = normalize_transaction_text(translate_to_english(original_text))
        raw_df = parse_universal_bank_rows(translated_text)
        if raw_df.empty:
            raw_df = parse_ocr_transactions(translated_text)

    # Bank-specific summary extraction
    file_bytes_io = io.BytesIO(raw_bytes) if ext == ".pdf" else None
    file_summary = route_and_extract(original_text, translated_text, file_bytes_io)

    raw_df  = _prep_raw_df(raw_df) if not raw_df.empty else pd.DataFrame()
    temp_df = prepare_dataframe(raw_df) if not raw_df.empty else pd.DataFrame()

    if file_summary["credits_amount"] > 0 or file_summary["debits_amount"] > 0:
        file_credits = file_summary["credits_amount"]
        file_debits  = file_summary["debits_amount"]
    else:
        file_credits = temp_df["Credit"].sum() if not temp_df.empty and "Credit" in temp_df.columns else 0.0
        file_debits  = temp_df["Debit"].sum()  if not temp_df.empty and "Debit"  in temp_df.columns else 0.0

    if not raw_df.empty:
        _,    lender_debit_total,  _ = get_lender_debits(raw_df, file_credits)
        _, lender_credit_total    = get_lender_credits(raw_df)
    else:
        lender_debit_total = lender_credit_total = 0.0

    withholding_rate = (lender_debit_total / file_credits * 100) if file_credits > 0 else 0.0
    nsf_count        = count_nsf(temp_df, original_text)
    pos_count        = count_pos(temp_df)

    avg_bal = extract_average_balance(original_text) if original_text else None
    if avg_bal is None:
        daily = extract_daily_balances_from_text(original_text) if original_text else []
        if not daily and not temp_df.empty and "Balance" in temp_df.columns:
            daily = temp_df["Balance"].dropna().tolist()
        avg_bal = float(sum(daily) / len(daily)) if daily else 0.0

    statement_date = extract_statement_date(original_text, filename, all_filenames)

    return {
        "filename":          filename,
        "statement_date":    statement_date.isoformat() if statement_date else None,
        "credits":           round(file_credits, 2),
        "debits":            round(file_debits, 2),
        "cash_flow":         round(file_credits - file_debits, 2),
        "lender_debits":     round(lender_debit_total, 2),
        "lender_credits":    round(lender_credit_total, 2),
        "withholding_rate":  round(withholding_rate, 4),
        "nsf_count":         nsf_count,
        "pos_count":         pos_count,
        "avg_daily_balance": round(avg_bal, 2),
        "charges_only":      round(charges_only_total, 2),
    }



@app.route("/parse-bank-statement", methods=["POST"])
def parse_bank_statement():
    files = (
        request.files.getlist("files[]")
        or request.files.getlist("files")
        or [f for key in request.files for f in request.files.getlist(key)]
    )
    if not files or all(f.filename == "" for f in files):
        return jsonify({"error": "No files provided. Send bank statements as 'files' in multipart/form-data."}), 400

    for f in files:
        ext = os.path.splitext(f.filename.lower())[1]
        if ext not in _ALLOWED_EXTENSIONS:
            return jsonify({"error": f"Unsupported file type '{ext}' in {f.filename}."}), 400

    client_id    = request.form.get("client_id", "")
    all_filenames = [f.filename for f in files]
    statements   = []

    for uploaded in files:
        try:
            raw_bytes = uploaded.read()
            result    = _process_statement(raw_bytes, uploaded.filename, all_filenames)
            statements.append(result)
        except Exception as exc:
            statements.append({"filename": uploaded.filename, "error": str(exc)})

    good = [s for s in statements if "error" not in s]
    n    = len(good) or 1

    totals = {
        "credits":           round(sum(s["credits"]        for s in good), 2),
        "debits":            round(sum(s["debits"]         for s in good), 2),
        "cash_flow":         round(sum(s["cash_flow"]      for s in good), 2),
        "lender_debits":     round(sum(s["lender_debits"]  for s in good), 2),
        "lender_credits":    round(sum(s["lender_credits"] for s in good), 2),
        "nsf_count":         sum(s["nsf_count"]            for s in good),
        "pos_count":         sum(s["pos_count"]            for s in good),
        "avg_daily_balance": round(sum(s["avg_daily_balance"] for s in good) / n, 2),
        "withholding_rate":  round(
            sum(s["lender_debits"] for s in good) / sum(s["credits"] for s in good) * 100
            if sum(s["credits"] for s in good) > 0 else 0.0, 4
        ),
    }

    averages = {
        "credits":           round(totals["credits"]           / n, 2),
        "debits":            round(totals["debits"]            / n, 2),
        "cash_flow":         round(totals["cash_flow"]         / n, 2),
        "lender_debits":     round(totals["lender_debits"]     / n, 2),
        "lender_credits":    round(totals["lender_credits"]    / n, 2),
        "nsf_count":         round(totals["nsf_count"]         / n, 2),
        "pos_count":         round(totals["pos_count"]         / n, 2),
        "avg_daily_balance": totals["avg_daily_balance"],
        "withholding_rate":  totals["withholding_rate"],
    }

    # Forward to lender app if client_id provided
    lender_result = {}
    if client_id:
        try:
            resp = _requests.post(
                f"{_LENDER_APP_URL}/bank-statement",
                json={
                    "client_id": client_id,
                    "summary_metrics": {
                        "nsf_count":         totals["nsf_count"],
                        "pos_count":         totals["pos_count"],
                        "total_deposits":    averages["credits"],
                        "total_revenue":     averages["credits"],
                        "avg_daily_balance": averages["avg_daily_balance"],
                    },
                },
                timeout=10,
            )
            lender_result["lender_app_notified"] = resp.ok
            lender_result["lender_app_status"]   = resp.status_code
            if resp.ok:
                cid = resp.json().get("client_id") or client_id
                jr  = _requests.get(f"{_LENDER_APP_URL}/job/{cid}", timeout=10)
                lender_result["lender_suggestion"] = jr.json() if jr.ok else {"error": jr.status_code}
        except Exception as exc:
            lender_result["lender_app_notified"] = False
            lender_result["lender_app_status"]   = str(exc)

    return jsonify({
        "statements": statements,
        "totals":     totals,
        "averages":   averages,
        **lender_result,
    }), 200


@app.route("/parse-application", methods=["POST"])
def parse_application():
    if "file" not in request.files:
        return jsonify({"error": "No file provided. Send the PDF as 'file' in multipart/form-data."}), 400

    uploaded = request.files["file"]
    if not uploaded.filename.lower().endswith(".pdf"):
        return jsonify({"error": "Only PDF files are accepted."}), 400

    client_id = request.form.get("client_id", "")
    pdf_bytes = uploaded.read()
    ocr = parse_signed_application(pdf_bytes)

    payload = {
        "clientCode":                   client_id,
        # business
        "Business_Legal_Name":         ocr.get("Business_Legal_Name"),
        "Doing_Business_As_DBA":       ocr.get("Doing_Business_As_DBA"),
        "Federal_Tax_ID":              ocr.get("Federal_Tax_ID"),
        "Entity_Type1":                ocr.get("Entity_Type1"),
        "Business_Address":            ocr.get("Business_Address"),
        "Business_City":               ocr.get("Business_City"),
        "Business_State":              ocr.get("Business_State"),
        "Business_Zip":                ocr.get("Business_Zip"),
        "Business_Phone":              ocr.get("Business_Phone"),
        "Business_Email":              ocr.get("Business_Email"),
        "Date_Current_Ownership_Started": ocr.get("Date_Current_Ownership_Started"),
        "Industry_App":                ocr.get("Industry_App"),
        "Time_in_Business":            ocr.get("Time_in_Business"),
        # principle owner
        "Principle_Owner_Name":        ocr.get("Principle_Owner_Name"),
        "Principle_SSN":               ocr.get("Principle_SSN"),
        "Principle_DOB":               ocr.get("Principle_DOB"),
        "Principle_Ownership":         ocr.get("Principle_Ownership"),
        "Principle_Email":             ocr.get("Principle_Email"),
        "Principle_Phone":             ocr.get("Principle_Phone"),
        "Principle_Address":           ocr.get("Principle_Address"),
        "Principle_City":              ocr.get("Principle_City"),
        "Principle_State":             ocr.get("Principle_State"),
        "Principle_Zip":               ocr.get("Principle_Zip"),
        # secondary owner
        "Secondary_Owner_Name":        ocr.get("Secondary_Owner_Name"),
        "Secondary_SSN":               ocr.get("Secondary_SSN"),
        "Secondary_DOB":               ocr.get("Secondary_DOB"),
        "Secondary_Ownership":         ocr.get("Secondary_Ownership"),
        "Secondary_Email1":            ocr.get("Secondary_Email1"),
        "Secondary_Phone":             ocr.get("Secondary_Phone"),
        "Secondary_Address":           ocr.get("Secondary_Address"),
        "Secondary_City":              ocr.get("Secondary_City"),
        "Secondary_State":             ocr.get("Secondary_State"),
        "Secondary_Zip":               ocr.get("Secondary_Zip"),
        # funding
        "Requested_Funding_Amount":    ocr.get("Requested_Funding_Amount"),
        "Portal_Monthly_Rev":          ocr.get("Portal_Monthly_Rev"),
        "Average_Monthly_Deposits":    ocr.get("Average_Monthly_Deposits"),
        "Percent_Ownership":           ocr.get("Percent_Ownership"),
        # portal
        "Portal_Email":                ocr.get("Portal_Email"),
        "Portal_Mobile":               ocr.get("Portal_Mobile"),
        # legacy
        "estimated_fico_score":        ocr.get("estimated_fico_score"),
        "business_description":        ocr.get("business_description"),
        "ownership_percentage":        ocr.get("ownership_percentage"),
        "time_in_business_years":      ocr.get("time_in_business_years"),
        "state":                       ocr.get("Business_State"),
        "zip":                         ocr.get("Business_Zip"),
    }

    result = {**ocr}
    try:
        resp = _requests.post(f"{_LENDER_APP_URL}/application", json=payload, timeout=10)
        result["lender_app_notified"] = resp.ok
        result["lender_app_status"] = resp.status_code
        result["lender_app_response"] = resp.text
        if resp.ok:
            post_client_id = resp.json().get("client_id") or client_id
            if post_client_id:
                job_resp = _requests.get(
                    f"{_LENDER_APP_URL}/job/{post_client_id}", timeout=10
                )
                result["lender_suggestion"] = job_resp.json() if job_resp.ok else {"error": job_resp.status_code}
    except Exception as e:
        result["lender_app_notified"] = False
        result["lender_app_status"] = str(e)

    return jsonify(result), 200


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"}), 200


# ── Persistent custom lender keywords ────────────────────────────────────────
_KEYWORDS_FILE = os.path.join(os.path.dirname(__file__), "lender_keywords.json")

def _load_keywords():
    if not os.path.exists(_KEYWORDS_FILE):
        return []
    try:
        with open(_KEYWORDS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return []

def _save_keywords(keywords):
    with open(_KEYWORDS_FILE, "w") as f:
        json.dump(keywords, f, indent=2)

@app.route("/lender-keywords", methods=["GET"])
def get_lender_keywords():
    return jsonify(_load_keywords()), 200

@app.route("/lender-keywords", methods=["POST"])
def add_lender_keyword():
    body  = request.get_json(silent=True) or {}
    name  = (body.get("name") or "").strip()
    type_ = body.get("type", "debit")
    if not name:
        return jsonify({"error": "name is required"}), 400
    keywords = _load_keywords()
    if not any(k["name"].lower() == name.lower() and k["type"] == type_ for k in keywords):
        keywords.append({"name": name, "type": type_})
        _save_keywords(keywords)
    return jsonify(keywords), 200

@app.route("/lender-keywords", methods=["DELETE"])
def remove_lender_keyword():
    body  = request.get_json(silent=True) or {}
    name  = (body.get("name") or "").strip()
    type_ = body.get("type", "debit")
    keywords = _load_keywords()
    keywords = [k for k in keywords
                if not (k["name"].lower() == name.lower() and k["type"] == type_)]
    _save_keywords(keywords)
    return jsonify(keywords), 200


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
