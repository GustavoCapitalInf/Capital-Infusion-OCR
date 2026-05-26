"""
app.py
------
Orbit Optix — Financial Intelligence & Bank Statement Analysis
Main Streamlit application entry point.
"""

import re
import threading

import requests as _requests

_LENDER_APP_URL = "https://lendersuggestion.onrender.com"

import pandas as pd
import plotly.express as px
import streamlit as st

from banks.base import parse_universal_bank_rows, parse_ocr_transactions, fix_lender_direction
from banks.router import route_and_extract
from utils.balance import extract_average_balance, extract_daily_balances_from_text
from utils.calculations import prepare_dataframe
from utils.cleaning import normalize_transaction_text, clean_money, fix_spaced_ocr_text
from utils.dates import extract_statement_date
from utils.lender_detection import get_lender_debits, get_lender_credits
from utils.metrics import count_nsf, count_pos, extract_charges_only
from utils.ocr import extract_text_from_pdf, extract_text_from_image, translate_to_english
from utils.risk_detection import calculate_risk_level, generate_notes
from utils.teams_notify import notify_teams


# ============================================================================
# APPLICATION API — start Flask server once in a background daemon thread
# ============================================================================

def _start_application_api():
    from application_api import app as flask_app
    flask_app.run(host="0.0.0.0", port=5001, debug=False, use_reloader=False)

_api_thread = None

def _ensure_api_running():
    global _api_thread
    if _api_thread is None or not _api_thread.is_alive():
        _api_thread = threading.Thread(target=_start_application_api, daemon=True)
        _api_thread.start()

_ensure_api_running()


# ============================================================================
# PAGE CONFIG & THEME
# ============================================================================

st.set_page_config(
    page_title="Orbit Optix - Financial Intelligence",
    layout="wide",
    initial_sidebar_state="expanded",
    menu_items={"About": "Orbit Optix v2.0 — Enterprise Bank Statement Analysis"},
)

DARK_THEME_CSS = """
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    :root {
        --bg-base:#f4f8ff; --bg-card:#ffffff; --bg-hover:#eaf2ff;
        --border:#c9d8f0; --border-dim:#dfe8f7;
        --text-primary:#0f172a; --text-secondary:#4b5b7a; --text-dim:#94a3b8;
        --orange:#f59e0b; --green:#22c55e; --blue:#2563eb;
        --red:#ef4444; --amber:#fbbf24;
    }
    html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"],.main {
        background-color:var(--bg-base)!important;
        color:var(--text-primary)!important;
        font-family:'Inter',sans-serif!important;
    }
    [data-testid="stSidebar"]{background-color:#111!important;}
    [data-testid="stSidebar"] p,[data-testid="stSidebar"] span,
    [data-testid="stSidebar"] label{color:var(--text-secondary)!important;font-size:12px!important;}
    [data-testid="stSidebar"] h3{color:var(--text-secondary)!important;font-size:10px!important;
        font-weight:600!important;letter-spacing:1.5px!important;text-transform:uppercase!important;}
    h1{font-size:16px!important;font-weight:500!important;color:var(--text-primary)!important;}
    h2,h3{font-size:11px!important;font-weight:600!important;letter-spacing:1px!important;
        text-transform:uppercase!important;color:var(--text-secondary)!important;
        border-bottom:none!important;margin-bottom:12px!important;}
    p,span,.stMarkdown,li{color:var(--text-secondary)!important;font-size:13px!important;}
    [data-testid="metric-container"]{background-color:var(--bg-card)!important;
        border:1px solid var(--border)!important;border-radius:8px!important;padding:18px 20px!important;}
    [data-testid="stMetricValue"]{font-size:28px!important;font-weight:600!important;
        color:var(--text-primary)!important;}
    [data-testid="stMetricLabel"]{font-size:10px!important;font-weight:600!important;
        letter-spacing:1px!important;text-transform:uppercase!important;color:var(--text-secondary)!important;}
    .stTabs [data-baseweb="tab"]{font-size:11px!important;font-weight:500!important;
        padding:10px 18px!important;color:var(--text-dim)!important;}
    .stTabs [aria-selected="true"]{color:var(--text-primary)!important;
        border-bottom:2px solid var(--orange)!important;}
    .stButton>button{background-color:#252525!important;color:#eee!important;
        border:1px solid var(--border)!important;border-radius:6px!important;font-size:12px!important;}
    ::-webkit-scrollbar{width:5px;height:5px;}
    ::-webkit-scrollbar-thumb{background:#333;border-radius:2px;}
</style>
"""


# ============================================================================
# SAFE DATAFRAME DISPLAY
# Strips any non-scalar objects (e.g. Streamlit DeltaGenerator) before
# passing a DataFrame to st.dataframe().  Selects only named columns when
# provided so the table always shows clean, relevant data.
# ============================================================================

def _safe_show(df: pd.DataFrame, cols: list[str] | None = None) -> None:
    """
    Display a DataFrame safely — no DeltaGenerator leakage, no crashes.

    Parameters
    ----------
    df   : DataFrame to display
    cols : Optional explicit list of columns to show (in order).
           Only columns that actually exist in df are kept.
    """
    if df is None or df.empty:
        return

    # Select columns
    if cols:
        present = [c for c in cols if c in df.columns]
        df = df[present].copy() if present else df.copy()
    else:
        df = df.copy()

    # Cast every column to a safe type
    for col in df.columns:
        try:
            numeric = pd.to_numeric(df[col], errors="coerce")
            if numeric.notna().sum() > 0 and df[col].dtype != object:
                df[col] = numeric
            else:
                df[col] = df[col].astype(str)
        except Exception:
            df[col] = df[col].astype(str)

    st.dataframe(df, use_container_width=True, hide_index=True)


# ============================================================================
# UI HELPERS
# ============================================================================

def render_header():
    st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)
    col1, col2 = st.columns([1, 8])
    with col1:
        try:
            st.image("CapInfBack.png", width=120)
        except Exception:
            pass
    with col2:
        st.markdown("""
        <div style="padding-top:18px;">
            <div style="font-family:'Inter',sans-serif;font-size:15px;font-weight:500;color:#e8e8e8;">
                Orbit Optix
            </div>
            <div style="font-family:'Inter',sans-serif;font-size:11px;color:#555;margin-top:2px;">
                Financial Intelligence &amp; Bank Statement Analysis
            </div>
        </div>""", unsafe_allow_html=True)


def render_sidebar() -> tuple[bool, str]:
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        debug_mode = st.toggle("Debug Mode", value=False,
                               help="Show OCR text and detailed parser output")
        st.divider()
        st.markdown("### 🔑 Client ID")
        client_id = st.text_input("Client ID", placeholder="e.g. SMITH-001")
        st.divider()
        st.markdown("### 📄 Supported Formats")
        st.caption("• PDF (digital & scanned)\n• Images (PNG, JPG)\n• Spreadsheets (CSV, XLSX)")
        st.divider()
        st.markdown("### 🌍 Languages")
        st.caption("• English\n• French\n• Spanish\n(Auto-detected & translated)")
    return debug_mode, client_id


def render_empty_state():
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h2 style='text-align:center;margin-top:40px;'>Welcome to Orbit Optix</h2>",
                    unsafe_allow_html=True)
        st.markdown(
            "<p style='text-align:center;font-size:16px;color:#86868b;'>"
            "Upload bank statements to begin analysis</p>",
            unsafe_allow_html=True,
        )
        st.markdown("---")
        ca, cb = st.columns(2)
        with ca:
            st.markdown("#### ✨ Features")
            st.markdown("• Multi-format OCR\n• Multi-bank detection\n• Risk Analysis\n• Export Reports")
        with cb:
            st.markdown("#### 🔒 Security")
            st.markdown("• Local Processing\n• No Cloud Upload\n• HIPAA Ready\n• Enterprise Grade")


def render_kpis(
    total_revenue, total_credits, total_debits,
    total_lender_debits, total_lender_credits, total_cash_flow,
    withholding_rate, nsf_count=0, avg_daily_balance=0.0, pos_count=0,
):
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Monthly Revenue", f"${total_revenue:,.2f}")
    c2.metric("Total Credits",         f"${total_credits:,.2f}")
    c3.metric("Total Debits",          f"${total_debits:,.2f}")
    c4.metric("Cash Flow",             f"${total_cash_flow:,.2f}")

    c5, c6, c7, c8, c9, c10 = st.columns(6)
    c5.metric("Lender Debits",    f"${total_lender_debits:,.2f}")
    c6.metric("Lender Credits",   f"${total_lender_credits:,.2f}")
    c7.metric("Withholding Rate", f"{withholding_rate:.2f}%")
    c8.metric("NSF Count",        nsf_count)
    c9.metric("Avg Daily Balance",f"${avg_daily_balance:,.2f}")
    c10.metric("POS Count",       pos_count)


def render_chart(results_df: pd.DataFrame):
    st.markdown("### 📈 Financial Overview")
    chart_df = results_df.melt(
        id_vars="Statement",
        value_vars=["Total Credits", "Total Debits",
                    "Total Lender Debits", "Total Lender Credits"],
        var_name="Metric", value_name="Amount",
    )
    fig = px.bar(
        chart_df, x="Statement", y="Amount", color="Metric",
        barmode="group",
        color_discrete_map={
            "Total Credits":       "#4a9eff",
            "Total Debits":        "#e87c2a",
            "Total Lender Debits": "#9b6dff",
            "Total Lender Credits":"#34c759",
        },
        template="plotly_dark",
    )
    fig.update_layout(
        height=420, hovermode="x unified",
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="#111111",
        font=dict(color="#666", family="Inter", size=11),
        xaxis=dict(showgrid=False, tickangle=-20, linecolor="#2a2a2a"),
        yaxis=dict(showgrid=True, gridcolor="#1e1e1e", linecolor="#2a2a2a"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02,
                    xanchor="left", x=0, bgcolor="rgba(0,0,0,0)"),
        margin=dict(t=40, b=20, l=10, r=10),
    )
    st.plotly_chart(fig, use_container_width=True)


# ============================================================================
# DATA PREPARATION
# ============================================================================

def _sanitize_df(df: pd.DataFrame) -> pd.DataFrame:
    """
    Drop any column whose first non-null value is not a plain Python scalar.
    Prevents Streamlit DeltaGenerator objects from surviving into lender
    detection or display.
    """
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
    """
    Normalise a raw parsed DataFrame:
      - Rename common column aliases → Date / Description / Debit / Credit / Amount
      - Force numeric types on money columns
      - Split a single Amount column into Debit / Credit where missing
      - Strip any non-scalar columns (DeltaGenerator safety net)
      - Run fix_lender_direction to correct misclassified lender rows
    """
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

    # Ensure required columns exist
    for col in ["Date", "Description", "Debit", "Credit", "Amount"]:
        if col not in raw_df.columns:
            raw_df[col] = "" if col in ("Date", "Description") else 0.0

    # Force numeric money columns
    for col in ["Debit", "Credit", "Amount", "Balance"]:
        if col in raw_df.columns:
            raw_df[col] = raw_df[col].apply(clean_money)

    # Split Amount → Debit / Credit when both are zero
    if all(c in raw_df.columns for c in ["Amount", "Debit", "Credit"]):
        neg = (raw_df["Debit"] == 0) & (raw_df["Credit"] == 0) & (raw_df["Amount"] < 0)
        pos = (raw_df["Debit"] == 0) & (raw_df["Credit"] == 0) & (raw_df["Amount"] > 0)
        raw_df.loc[neg, "Debit"]  = raw_df["Amount"].abs()
        raw_df.loc[pos, "Credit"] = raw_df["Amount"].abs()

    # Safety: strip non-scalar columns
    raw_df = _sanitize_df(raw_df)

    return fix_lender_direction(raw_df)


# ============================================================================
# SINGLE-FILE PROCESSING
# ============================================================================

def process_file(
    uploaded_file,
    all_filenames: list[str],
    debug_mode: bool,
) -> tuple[dict, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Process one uploaded file.

    Returns
    -------
    (statement_result_dict, temp_df, lender_rows, lender_credit_rows, flagged_df)
    """
    name = uploaded_file.name.lower()
    raw_df = pd.DataFrame()
    original_text = translated_text = ""
    charges_only_total = 0.0

    with st.status(f"Processing {uploaded_file.name}…", expanded=False) as status:

        # ── Load & extract text ──────────────────────────────────────────
        if name.endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)

        elif name.endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(uploaded_file)

        elif name.endswith(".pdf"):
            status.update(label="Extracting PDF…", state="running")
            original_text  = extract_text_from_pdf(uploaded_file, debug_mode)
            translated_text = normalize_transaction_text(
                translate_to_english(original_text)
            )
            _, charges_only_total = extract_charges_only(translated_text)
            raw_df = parse_universal_bank_rows(translated_text)
            if raw_df.empty:
                raw_df = parse_ocr_transactions(translated_text)

        else:  # image (PNG / JPG)
            status.update(label="Processing image…", state="running")
            original_text  = extract_text_from_image(uploaded_file)
            translated_text = normalize_transaction_text(
                translate_to_english(original_text)
            )
            raw_df = parse_universal_bank_rows(translated_text)
            if raw_df.empty:
                raw_df = parse_ocr_transactions(translated_text)

        # ── Debug: show OCR output ───────────────────────────────────────
        if debug_mode and translated_text:
            with st.expander("Debug: OCR Output"):
                st.text_area("Extracted Text", translated_text, height=200, disabled=True)

        # ── Bank router: extract summary totals ──────────────────────────
        file_summary = route_and_extract(original_text, translated_text, uploaded_file)

        # ── Normalise raw DataFrame ──────────────────────────────────────
        raw_df  = _prep_raw_df(raw_df) if not raw_df.empty else pd.DataFrame()
        temp_df = prepare_dataframe(raw_df) if not raw_df.empty else pd.DataFrame()

        if debug_mode and not raw_df.empty:
            debug_cols = [c for c in ["Date", "Description", "Debit", "Credit",
                                      "Amount", "Balance"] if c in raw_df.columns]
            st.dataframe(raw_df[debug_cols], use_container_width=True)

        # ── Revenue / credits / debits ───────────────────────────────────
        if file_summary["credits_amount"] > 0 or file_summary["debits_amount"] > 0:
            file_revenue      = file_summary["credits_amount"]
            file_credits      = file_summary["credits_amount"]
            file_debits       = file_summary["debits_amount"]
            file_credit_count = file_summary["credit_count"]
            file_debit_count  = file_summary["debit_count"]
        else:
            file_revenue      = temp_df["Credit"].sum() if not temp_df.empty and "Credit" in temp_df.columns else 0.0
            file_credits      = file_revenue
            file_debits       = temp_df["Debit"].sum()  if not temp_df.empty and "Debit"  in temp_df.columns else 0.0
            file_credit_count = int(len(temp_df[temp_df["Credit"] > 0])) if not temp_df.empty and "Credit" in temp_df.columns else 0
            file_debit_count  = int(len(temp_df[temp_df["Debit"]  > 0])) if not temp_df.empty and "Debit"  in temp_df.columns else 0

        # ── Lender detection ─────────────────────────────────────────────
        # Sanitize first so no DeltaGenerator survives into detection
        if not raw_df.empty:
            clean_df = _sanitize_df(raw_df)
            lender_rows,       lender_debit_total,  _ = get_lender_debits(clean_df, file_revenue)
            lender_credit_rows, lender_credit_total    = get_lender_credits(clean_df)
        else:
            lender_rows = lender_credit_rows = pd.DataFrame()
            lender_debit_total = lender_credit_total = 0.0

        withholding_rate = (lender_debit_total / file_revenue * 100) if file_revenue > 0 else 0.0

        # ── Flagged / suspicious transactions ────────────────────────────
        SUSPICIOUS_KEYWORDS = [
            "SQ", "SQUARE", "PAYPAL", "PAY PAL", "STRIPE",
            "SHOPIFY", "INTUIT", "CLOVER", "TOAST",
        ]
        flagged: list[dict] = []
        if translated_text:
            for line in translated_text.split("\n"):
                upper = str(line).upper()
                for kw in SUSPICIOUS_KEYWORDS:
                    if re.search(r"\b" + re.escape(kw) + r"\b", upper):
                        amounts = re.findall(
                            r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}", line
                        )
                        flagged.append({
                            "Matched Keyword": kw,
                            "Flagged Line":    line,
                            "Detected Amount": abs(clean_money(amounts[0])) if amounts else 0.0,
                        })
                        break
        flagged_df = pd.DataFrame(flagged)

        # ── Per-statement metrics ────────────────────────────────────────
        stmt_nsf = count_nsf(temp_df, original_text)
        stmt_pos = count_pos(temp_df)

        avg_bal_result = extract_average_balance(original_text) if original_text else None
        if avg_bal_result is None:
            daily = extract_daily_balances_from_text(original_text) if original_text else []
            if not daily and not temp_df.empty and "Balance" in temp_df.columns:
                daily = temp_df["Balance"].dropna().tolist()
            stmt_avg_balance = float(sum(daily) / len(daily)) if daily else 0.0
        else:
            stmt_avg_balance = float(avg_bal_result)

        statement_date = extract_statement_date(
            original_text, uploaded_file.name, all_filenames
        )

        status.update(label="Complete", state="complete")

    result = {
        "Statement":            uploaded_file.name,
        "Statement Date":       statement_date,
        "Total Monthly Revenue":file_revenue,
        "Total Credits":        file_credits,
        "Total Debits":         file_debits,
        "Total Charges Only":   charges_only_total,
        "Total Lender Debits":  lender_debit_total,
        "Total Lender Credits": lender_credit_total,
        "Withholding Rate":     withholding_rate,
        "Credit Transactions":  file_credit_count,
        "Debit Transactions":   file_debit_count,
        "Lender Transactions":  len(lender_rows),
        "NSF Count":            stmt_nsf,
        "Avg Daily Balance":    stmt_avg_balance,
        "POS Count":            stmt_pos,
    }

    return result, temp_df, lender_rows, lender_credit_rows, flagged_df


# ============================================================================
# MAIN APPLICATION
# ============================================================================

def main():
    render_header()
    debug_mode, client_id = render_sidebar()

    st.markdown("### 📁 Upload Bank Statements")
    uploaded_files = st.file_uploader(
        "Select bank statement files",
        type=["csv", "xlsx", "xls", "pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded_files:
        render_empty_state()
        return

    try:
        all_filenames         = [f.name for f in uploaded_files]
        statement_results:    list[dict]                  = []
        all_dataframes:       list[pd.DataFrame]          = []
        all_lender_data:      dict[str, pd.DataFrame]     = {}
        all_lender_credit_data: dict[str, pd.DataFrame]   = {}
        all_flagged_data:     dict[str, pd.DataFrame]     = {}

        for uploaded_file in uploaded_files:
            result, temp_df, lender_rows, lender_credit_rows, flagged_df = process_file(
                uploaded_file, all_filenames, debug_mode
            )
            statement_results.append(result)
            if not temp_df.empty:
                temp_df["Statement"] = uploaded_file.name
                all_dataframes.append(temp_df)
            all_lender_data[uploaded_file.name]        = lender_rows
            all_lender_credit_data[uploaded_file.name] = lender_credit_rows
            all_flagged_data[uploaded_file.name]       = flagged_df

        # ── Build results_df, sort by statement date ─────────────────────
        results_df = pd.DataFrame(statement_results)
        if "Total Lender Credits" not in results_df.columns:
            results_df["Total Lender Credits"] = 0.0
        results_df["Statement Date"] = pd.to_datetime(
            results_df["Statement Date"], errors="coerce"
        )
        results_df = results_df.sort_values(
            "Statement Date", na_position="last"
        ).reset_index(drop=True)

        # Fix wrong-year assignments (gap > 6 months → subtract a year)
        for i in range(1, len(results_df)):
            curr = results_df.at[i,     "Statement Date"]
            prev = results_df.at[i - 1, "Statement Date"]
            if pd.isna(curr) or pd.isna(prev):
                continue
            gap = (curr.year - prev.year) * 12 + (curr.month - prev.month)
            if gap > 6:
                results_df.at[i, "Statement Date"] = curr - pd.DateOffset(years=1)
        results_df = results_df.sort_values(
            "Statement Date", na_position="last"
        ).reset_index(drop=True)

        if results_df.empty:
            st.error("No statement data detected.")
            return

        st.success("✅ All statements processed successfully")
        st.divider()

        # ── Aggregate totals ─────────────────────────────────────────────
        total_revenue       = results_df["Total Monthly Revenue"].sum()
        total_credits       = results_df["Total Credits"].sum()
        total_debits        = results_df["Total Debits"].sum()
        total_lender_debits = results_df["Total Lender Debits"].sum()
        total_lender_credits= results_df["Total Lender Credits"].sum()
        total_cash_flow     = total_credits - total_debits
        withholding_rate    = (total_lender_debits / total_revenue * 100) if total_revenue > 0 else 0.0
        avg_daily_balance   = float(results_df["Avg Daily Balance"].mean())

        combined_df = (
            pd.concat(all_dataframes, ignore_index=True)
            if all_dataframes else pd.DataFrame()
        )
        # NSF — uses fixed detect_nsf() with strict patterns (no boilerplate hits)
        nsf_count = (
            int(combined_df["NSF Flag"].sum())
            if not combined_df.empty and "NSF Flag" in combined_df.columns else 0
        )
        # POS — word-boundary match; avoids hitting POS inside DEPOSIT etc.
        pos_count = (
            int(
                combined_df["Description"]
                .astype(str).str.upper()
                .str.contains(r"POS", regex=True)
                .sum()
            )
            if not combined_df.empty and "Description" in combined_df.columns else 0
        )

        # ── Forward metrics to lender suggestion app ─────────────────────
        try:
            resp = _requests.post(
                f"{_LENDER_APP_URL}/bank-statement",
                json={
                    "client_id": client_id,
                    "summary_metrics": {
                        "nsf_count":         nsf_count,
                        "pos_count":         pos_count,
                        "total_deposits":    round(total_credits, 2),
                        "total_revenue":     round(total_revenue, 2),
                        "avg_daily_balance": round(avg_daily_balance, 2),
                    },
                },
                timeout=10,
            )
            if resp.ok:
                st.toast("Bank statement data sent to lender app", icon="✅")
                client_id = resp.json().get("client_id")
                if client_id:
                    job_resp = _requests.get(
                        f"{_LENDER_APP_URL}/job/{client_id}", timeout=10
                    )
                    if job_resp.ok:
                        st.toast("Lender suggestion received", icon="✅")
                    else:
                        st.toast(f"Job poll returned {job_resp.status_code}", icon="⚠️")
            else:
                st.toast(f"Lender app {resp.status_code}: {resp.text[:200]}", icon="⚠️")
        except Exception as e:
            st.toast(f"Could not reach lender app: {e}", icon="❌")

        # ── Tabs ─────────────────────────────────────────────────────────
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📊 Dashboard", "📑 Statements",
            "🏢 Lenders",   "📈 Analysis", "⬇️ Export",
        ])

        # ── TAB 1: Dashboard ──────────────────────────────────────────────
        with tab1:
            st.markdown("### 📊 Overall Totals")
            render_kpis(
                total_revenue, total_credits, total_debits,
                total_lender_debits, total_lender_credits,
                total_cash_flow, withholding_rate,
                nsf_count, avg_daily_balance, pos_count,
            )
            st.divider()

            st.markdown("### 📅 Average Monthly")
            n = len(results_df)
            render_kpis(
                total_revenue / n,        total_credits / n,
                total_debits / n,         total_lender_debits / n,
                total_lender_credits / n, total_cash_flow / n,
                withholding_rate,
                int(results_df["NSF Count"].mean()),
                float(results_df["Avg Daily Balance"].mean()),
                int(results_df["POS Count"].mean()),
            )
            st.divider()

            st.markdown("### 🔄 Latest Statement")
            lr = results_df.iloc[-1]
            render_kpis(
                lr["Total Monthly Revenue"],
                lr["Total Credits"],
                lr["Total Debits"],
                lr["Total Lender Debits"],
                lr.get("Total Lender Credits", 0.0),
                lr["Total Credits"] - lr["Total Debits"],
                lr["Withholding Rate"],
                int(lr.get("NSF Count", 0)),
                float(lr.get("Avg Daily Balance", 0.0)),
                int(lr.get("POS Count", 0)),
            )
            st.divider()
            render_chart(results_df)

        # ── TAB 2: Statements ─────────────────────────────────────────────
        with tab2:
            st.markdown("### 📋 Statement Summary")
            display = results_df.copy()
            for col in ["Total Monthly Revenue", "Total Credits", "Total Debits",
                        "Total Lender Debits", "Total Lender Credits"]:
                if col in display.columns:
                    display[col] = display[col].apply(lambda x: f"${x:,.2f}")
            if "Withholding Rate" in display.columns:
                display["Withholding Rate"] = display["Withholding Rate"].apply(
                    lambda x: f"{x:.2f}%"
                )
            st.dataframe(display, use_container_width=True, hide_index=True)

        # ── TAB 3: Lenders ────────────────────────────────────────────────
        with tab3:
            # Combine all lender rows across statements
            all_lender_rows = pd.concat(
                [df for df in all_lender_data.values() if not df.empty],
                ignore_index=True,
            ) if any(not df.empty for df in all_lender_data.values()) else pd.DataFrame()

            all_credit_rows = pd.concat(
                [df for df in all_lender_credit_data.values() if not df.empty],
                ignore_index=True,
            ) if any(not df.empty for df in all_lender_credit_data.values()) else pd.DataFrame()

            # Summary metrics
            st.markdown("### 💰 Lender Summary")
            c1, c2 = st.columns(2)
            c1.metric(
                "Total Lender Debits",
                f"${all_lender_rows['Lender Debit Amount'].sum():,.2f}"
                if not all_lender_rows.empty else "$0.00",
            )
            c2.metric(
                "Total Lender Credits",
                f"${all_credit_rows['Lender Credit Amount'].sum():,.2f}"
                if not all_credit_rows.empty else "$0.00",
            )
            st.divider()

            # Debit totals table
            if not all_lender_rows.empty:
                st.markdown("### 📋 Lender Debit Totals")
                tbl = (
                    all_lender_rows
                    .groupby("Detected Lender")["Lender Debit Amount"]
                    .sum().reset_index()
                    .rename(columns={
                        "Detected Lender":    "Lender",
                        "Lender Debit Amount":"Total Debited",
                    })
                    .sort_values("Total Debited", ascending=False)
                    .reset_index(drop=True)
                )
                tbl["Total Debited"] = tbl["Total Debited"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                st.divider()

            # Credit totals table
            if not all_credit_rows.empty:
                st.markdown("### 📋 Lender Credit Totals")
                tbl = (
                    all_credit_rows
                    .groupby("Detected Lender")["Lender Credit Amount"]
                    .sum().reset_index()
                    .rename(columns={
                        "Detected Lender":      "Lender",
                        "Lender Credit Amount": "Total Credited",
                    })
                    .sort_values("Total Credited", ascending=False)
                    .reset_index(drop=True)
                )
                tbl["Total Credited"] = tbl["Total Credited"].apply(lambda x: f"${x:,.2f}")
                st.dataframe(tbl, use_container_width=True, hide_index=True)
                st.divider()

            # Per-statement expanders
            for fname, lender_data in all_lender_data.items():
                with st.expander(f"📊 {fname}", expanded=True):
                    lc_data     = all_lender_credit_data.get(fname, pd.DataFrame())
                    flagged_data= all_flagged_data.get(fname, pd.DataFrame())

                    c1, c2 = st.columns(2)

                    with c1:
                        st.markdown("#### 🔻 Lender Debits")
                        if not lender_data.empty:
                            _safe_show(lender_data, [
                                "Date", "Description",
                                "Detected Lender", "Matched Keyword",
                                "Lender Debit Amount",
                            ])
                            st.metric(
                                "Total",
                                f"${lender_data['Lender Debit Amount'].sum():,.2f}"
                                if "Lender Debit Amount" in lender_data.columns else "$0.00",
                            )
                        else:
                            st.info("No lender debits detected")

                    with c2:
                        st.markdown("#### 🟢 Lender Credits")
                        if not lc_data.empty:
                            _safe_show(lc_data, [
                                "Date", "Description",
                                "Detected Lender", "Matched Keyword",
                                "Lender Credit Amount",
                            ])
                            st.metric(
                                "Total",
                                f"${lc_data['Lender Credit Amount'].sum():,.2f}"
                                if "Lender Credit Amount" in lc_data.columns else "$0.00",
                            )
                        else:
                            st.info("No lender credits detected")

                    st.markdown("#### ⚠️ Flagged Transactions")
                    if flagged_data.empty:
                        st.success("No suspicious transactions detected")
                    else:
                        _safe_show(flagged_data, [
                            "Matched Keyword", "Flagged Line", "Detected Amount"
                        ])

        # ── TAB 4: Analysis ───────────────────────────────────────────────
        with tab4:
            if not combined_df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Total Rows",   len(combined_df))
                c2.metric("Credit Rows",
                          len(combined_df[combined_df["Credit"] > 0])
                          if "Credit" in combined_df.columns else 0)
                c3.metric("Debit Rows",
                          len(combined_df[combined_df["Debit"] > 0])
                          if "Debit"  in combined_df.columns else 0)
                st.divider()
                st.markdown("### 💳 Transaction Details")
                _safe_show(combined_df)

                funding_detected = (
                    bool(combined_df["Funding Detected"].any())
                    if "Funding Detected" in combined_df.columns else False
                )
                funders = (
                    sorted(set(
                        combined_df.loc[
                            combined_df["Funded By"] != "", "Funded By"
                        ].tolist()
                    ))
                    if "Funded By" in combined_df.columns else []
                )
                risk_score, risk_level = calculate_risk_level(
                    total_revenue, total_debits, nsf_count, funding_detected
                )
                st.divider()
                st.markdown("### 🎯 Risk Assessment")
                rc1, rc2 = st.columns(2)
                rc1.metric("Risk Level", risk_level)
                rc2.metric("Risk Score", f"{risk_score:.1f}")
                notes = generate_notes(
                    total_revenue, total_debits, total_cash_flow,
                    nsf_count, funding_detected, funders, withholding_rate,
                )
                st.markdown("**📝 Underwriting Notes**")
                for note in notes:
                    st.markdown(f"• {note}")

        # ── TAB 5: Export ─────────────────────────────────────────────────
        with tab5:
            st.markdown("### 📥 Download Results")
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️ Download Statement Results",
                    results_df.to_csv(index=False).encode("utf-8"),
                    "orbit_optix_statements.csv",
                    "text/csv",
                )
            with c2:
                summary_df = pd.DataFrame({
                    "Metric": [
                        "Total Revenue", "Total Credits", "Total Debits",
                        "Total Lender Debits", "Total Lender Credits",
                        "Withholding Rate", "Cash Flow",
                        "NSF Count", "Avg Daily Balance", "POS Count",
                    ],
                    "Value": [
                        f"${total_revenue:,.2f}",
                        f"${total_credits:,.2f}",
                        f"${total_debits:,.2f}",
                        f"${total_lender_debits:,.2f}",
                        f"${total_lender_credits:,.2f}",
                        f"{withholding_rate:.2f}%",
                        f"${total_cash_flow:,.2f}",
                        str(nsf_count),
                        f"${avg_daily_balance:,.2f}",
                        str(pos_count),
                    ],
                })
                st.download_button(
                    "⬇️ Download Summary Report",
                    summary_df.to_csv(index=False).encode("utf-8"),
                    "orbit_optix_summary.csv",
                    "text/csv",
                )

    except Exception as exc:
        st.error(f"Error processing files: {exc}")
        if debug_mode:
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
