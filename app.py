"""
app.py — Orbit Optix Financial Intelligence Dashboard
"""

import re
import threading

import requests as _requests

_LENDER_APP_URL = "https://lendersuggestion.onrender.com"

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from banks.base import parse_universal_bank_rows, parse_ocr_transactions, fix_lender_direction
from banks.router import route_and_extract
from utils.balance import extract_average_balance, extract_daily_balances_from_text
from utils.calculations import prepare_dataframe
from utils.cleaning import normalize_transaction_text, clean_money, fix_spaced_ocr_text
from utils.dates import extract_statement_date
from utils.lender_detection import get_lender_debits, get_lender_credits
from utils.metrics import count_nsf, count_loan, extract_charges_only
from utils.ocr import extract_text_from_pdf, extract_text_from_image, translate_to_english
from utils.risk_detection import calculate_risk_level, generate_notes
from utils.teams_notify import notify_teams


# ── Flask API background thread ────────────────────────────────────────────────

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


# ── Page config ────────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="Orbit Optix",
    page_icon="⬡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Theme CSS ──────────────────────────────────────────────────────────────────

THEME = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');

:root {
  --bg:       #F6F8FB;
  --card:     #FFFFFF;
  --sb:       #0B1220;
  --border:   #E5E7EB;
  --t1:       #111827;
  --t2:       #6B7280;
  --t3:       #9CA3AF;
  --blue:     #2563EB;
  --blue-d:   #1D4ED8;
  --blue-l:   #EFF6FF;
  --blue-b:   #BFDBFE;
  --green:    #16A34A;
  --green-l:  #F0FDF4;
  --green-b:  #BBF7D0;
  --red:      #DC2626;
  --red-l:    #FEF2F2;
  --red-b:    #FECACA;
  --amber:    #F59E0B;
  --amber-l:  #FFFBEB;
  --amber-b:  #FDE68A;
  --purple:   #7C3AED;
  --sh:       0 1px 2px rgba(0,0,0,0.05),0 1px 6px rgba(0,0,0,0.04);
  --sh-md:    0 4px 16px rgba(0,0,0,0.08),0 1px 4px rgba(0,0,0,0.04);
  --sh-lg:    0 8px 32px rgba(0,0,0,0.10);
  --r:        12px;
  --rsm:      8px;
  --rlg:      16px;
}

/* ── Reset & base ── */
*,*::before,*::after{box-sizing:border-box;}
html,body,[data-testid="stAppViewContainer"],[data-testid="stMain"],.main{
  background:var(--bg)!important;
  font-family:'Inter',system-ui,sans-serif!important;
  color:var(--t1)!important;
}
.block-container{padding:28px 36px 72px!important;max-width:1440px!important;}

/* ── Sidebar ── */
[data-testid="stSidebar"]{
  background:var(--sb)!important;
  border-right:1px solid rgba(255,255,255,0.05)!important;
}
[data-testid="stSidebar"]>div:first-child{padding:0!important;}
[data-testid="stSidebar"] *{font-family:'Inter',sans-serif!important;}
[data-testid="stSidebar"] p,[data-testid="stSidebar"] span,
[data-testid="stSidebar"] label{color:#6B7280!important;font-size:13px!important;}
[data-testid="stSidebar"] .stTextInput input{
  background:rgba(255,255,255,0.05)!important;
  border:1px solid rgba(255,255,255,0.10)!important;
  border-radius:var(--rsm)!important;
  color:#E2E8F0!important;font-size:13px!important;
  padding:9px 12px!important;
}
[data-testid="stSidebar"] .stTextInput input::placeholder{color:#374151!important;}
[data-testid="stSidebar"] .stTextInput input:focus{
  border-color:var(--blue)!important;
  box-shadow:0 0 0 3px rgba(37,99,235,0.20)!important;
  outline:none!important;
}
[data-testid="stSidebar"] hr{border:none!important;border-top:1px solid rgba(255,255,255,0.06)!important;margin:8px 0!important;}
[data-testid="stSidebar"] [data-testid="stToggle"] label{color:#6B7280!important;}

/* ── Typography ── */
h1,h2,h3{margin:0!important;color:var(--t1)!important;}
p,span,li{color:var(--t2)!important;font-size:14px!important;line-height:1.6!important;}

/* ── Tabs ── */
.stTabs [data-baseweb="tab-list"]{background:transparent!important;border-bottom:1px solid var(--border)!important;gap:0!important;padding:0!important;}
.stTabs [data-baseweb="tab"]{font-size:14px!important;font-weight:500!important;padding:13px 24px!important;color:var(--t3)!important;border-bottom:2px solid transparent!important;background:transparent!important;margin-bottom:-1px!important;transition:color .2s,border-color .2s!important;}
.stTabs [data-baseweb="tab"]:hover{color:var(--t2)!important;}
.stTabs [aria-selected="true"]{color:var(--t1)!important;font-weight:600!important;border-bottom-color:var(--blue)!important;}
.stTabs [data-baseweb="tab-panel"]{padding:32px 0 0!important;}

/* ── Buttons ── */
.stButton>button{background:var(--blue)!important;color:#fff!important;border:none!important;border-radius:var(--rsm)!important;font-size:14px!important;font-weight:600!important;padding:10px 22px!important;box-shadow:0 1px 3px rgba(37,99,235,.30)!important;transition:background .15s,box-shadow .15s,transform .1s!important;letter-spacing:-.1px!important;}
.stButton>button:hover{background:var(--blue-d)!important;transform:translateY(-1px)!important;box-shadow:0 4px 12px rgba(37,99,235,.35)!important;}
.stDownloadButton>button{background:var(--card)!important;color:var(--t1)!important;border:1px solid var(--border)!important;border-radius:var(--r)!important;font-size:14px!important;font-weight:600!important;padding:16px 22px!important;width:100%!important;box-shadow:var(--sh)!important;transition:all .18s!important;}
.stDownloadButton>button:hover{border-color:var(--blue)!important;color:var(--blue)!important;transform:translateY(-2px)!important;box-shadow:var(--sh-md)!important;}

/* ── File uploader ── */
[data-testid="stFileUploader"] section{background:var(--card)!important;border:2px dashed var(--blue-b)!important;border-radius:var(--rlg)!important;padding:48px 36px!important;transition:border-color .2s,background .2s!important;}
[data-testid="stFileUploader"] section:hover{border-color:var(--blue)!important;background:var(--blue-l)!important;}
[data-testid="stFileUploaderDropzone"]{background:transparent!important;}

/* ── Dataframe ── */
[data-testid="stDataFrame"]{border:1px solid var(--border)!important;border-radius:var(--r)!important;overflow:hidden!important;box-shadow:var(--sh)!important;}

/* ── Expander ── */
[data-testid="stExpander"]{background:var(--card)!important;border:1px solid var(--border)!important;border-radius:var(--r)!important;box-shadow:var(--sh)!important;overflow:hidden!important;margin-bottom:12px!important;}
details>summary{padding:18px 22px!important;font-size:14px!important;font-weight:600!important;color:var(--t1)!important;}

/* ── Alerts ── */
[data-testid="stInfo"]{background:#EFF6FF!important;border-radius:var(--rsm)!important;border:1px solid var(--blue-b)!important;}
[data-testid="stSuccess"]{background:var(--green-l)!important;border-radius:var(--rsm)!important;border:1px solid var(--green-b)!important;}
[data-testid="stError"]{background:var(--red-l)!important;border-radius:var(--rsm)!important;border:1px solid var(--red-b)!important;}
[data-testid="stWarning"]{background:var(--amber-l)!important;border-radius:var(--rsm)!important;border:1px solid var(--amber-b)!important;}

/* ── Divider ── */
hr{border:none!important;border-top:1px solid var(--border)!important;margin:32px 0!important;}

/* ── Scrollbar ── */
::-webkit-scrollbar{width:5px;height:5px;}
::-webkit-scrollbar-track{background:transparent;}
::-webkit-scrollbar-thumb{background:#D1D5DB;border-radius:3px;}
::-webkit-scrollbar-thumb:hover{background:#9CA3AF;}

/* ═══ CUSTOM COMPONENTS ═══ */

/* ── Info bar ── */
.info-bar{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:12px 22px;display:flex;align-items:center;gap:0;margin-bottom:24px;box-shadow:var(--sh);font-family:'Inter',sans-serif;}
.ib-item{display:flex;align-items:center;gap:6px;font-size:13px;color:var(--t2);padding:0 16px;}
.ib-item:first-child{padding-left:0;}
.ib-icon{font-size:14px;opacity:.7;}
.ib-label{color:var(--t3);font-weight:500;}
.ib-val{color:var(--t1);font-weight:600;}
.ib-sep{width:1px;height:20px;background:var(--border);flex-shrink:0;}
.ib-live{display:flex;align-items:center;gap:6px;font-size:13px;font-weight:600;color:var(--green);padding:0 16px;}
.ib-dot{width:7px;height:7px;border-radius:50%;background:var(--green);animation:pulse 2s infinite;}
@keyframes pulse{0%,100%{opacity:1;}50%{opacity:.4;}}

/* ── Hero ── */
.hero{background:linear-gradient(135deg,#0B1220 0%,#111827 60%,#0E1A30 100%);border-radius:var(--rlg);padding:40px 44px;margin-bottom:28px;position:relative;overflow:hidden;border:1px solid rgba(37,99,235,0.15);}
.hero-glow{position:absolute;top:-80px;right:-60px;width:360px;height:360px;border-radius:50%;background:radial-gradient(circle,rgba(37,99,235,0.14) 0%,transparent 70%);pointer-events:none;}
.hero-glow2{position:absolute;bottom:-60px;left:20%;width:240px;height:240px;border-radius:50%;background:radial-gradient(circle,rgba(124,58,237,0.08) 0%,transparent 70%);pointer-events:none;}
.hero-content{position:relative;z-index:1;}
.hero-eyebrow{font-size:10px;font-weight:700;letter-spacing:3px;color:#3B82F6;text-transform:uppercase;margin-bottom:12px;}
.hero-title{font-size:30px;font-weight:800;color:#F9FAFB;letter-spacing:-0.8px;line-height:1.15;margin-bottom:10px;}
.hero-sub{font-size:14px;color:#6B7280;line-height:1.7;max-width:520px;margin-bottom:22px;}
.hero-badges{display:flex;align-items:center;gap:8px;flex-wrap:wrap;}
.hero-badge{background:rgba(37,99,235,0.14);color:#93C5FD;border:1px solid rgba(37,99,235,0.28);font-size:12px;font-weight:600;padding:5px 14px;border-radius:999px;}
.hero-badge-idle{background:rgba(22,163,74,0.12);color:#86EFAC;border:1px solid rgba(22,163,74,0.25);font-size:12px;font-weight:600;padding:5px 14px;border-radius:999px;}
.hero-cid{background:rgba(255,255,255,0.05);color:#6B7280;border:1px solid rgba(255,255,255,0.10);font-size:12px;font-weight:500;padding:5px 14px;border-radius:999px;}

/* ── Sidebar components ── */
.sb-brand{padding:24px 20px 18px;border-bottom:1px solid rgba(255,255,255,0.06);margin-bottom:8px;}
.sb-logo-row{display:flex;align-items:center;gap:12px;}
.sb-logo-mark{width:34px;height:34px;border-radius:10px;background:linear-gradient(135deg,#2563EB,#7C3AED);display:flex;align-items:center;justify-content:center;font-size:16px;font-weight:900;color:white;flex-shrink:0;box-shadow:0 2px 8px rgba(37,99,235,0.40);}
.sb-brand-name{font-size:15px;font-weight:700;color:#F1F5F9;letter-spacing:-0.3px;}
.sb-brand-tag{font-size:10px;color:#374151;text-transform:uppercase;letter-spacing:1.5px;margin-top:2px;}
.sb-sect-label{font-size:10px;font-weight:700;letter-spacing:2px;text-transform:uppercase;color:#1F2937;padding:0 20px;margin-top:22px;margin-bottom:10px;display:block;}
.sb-fmt-row{display:flex;flex-wrap:wrap;gap:5px;padding:0 20px;}
.sb-fmt-pill{background:rgba(255,255,255,0.04);color:#4B5563;border:1px solid rgba(255,255,255,0.07);font-size:11px;padding:4px 9px;border-radius:5px;font-weight:500;}
.sb-footer{padding:24px 20px 18px;font-size:11px;color:#1F2937;border-top:1px solid rgba(255,255,255,0.05);margin-top:12px;}

/* ── KPI cards ── */
.kpi-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:24px 24px 20px;box-shadow:var(--sh);height:100%;min-height:120px;font-family:'Inter',sans-serif;transition:box-shadow .2s,transform .2s,border-color .2s;}
.kpi-card:hover{box-shadow:var(--sh-md);transform:translateY(-2px);border-color:#D1D5DB;}
.kpi-top{display:flex;align-items:flex-start;justify-content:space-between;margin-bottom:14px;}
.kpi-label{font-size:12px;font-weight:600;letter-spacing:0.4px;text-transform:uppercase;color:var(--t3);}
.kpi-icon-wrap{width:36px;height:36px;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;}
.kpi-icon-blue{background:#EFF6FF;}.kpi-icon-green{background:var(--green-l);}.kpi-icon-red{background:var(--red-l);}.kpi-icon-amber{background:var(--amber-l);}.kpi-icon-purple{background:#F5F3FF;}
.kpi-value{font-size:32px;font-weight:800;color:var(--t1);letter-spacing:-1.5px;line-height:1;margin-bottom:8px;}
.kpi-sub{font-size:12px;color:var(--t3);font-weight:500;}
.kpi-green{color:var(--green)!important;}
.kpi-red{color:var(--red)!important;}
.kpi-amber{color:var(--amber)!important;}
.kpi-blue{color:var(--blue)!important;}
.kpi-card-blue{border-top:3px solid var(--blue);}
.kpi-card-green{border-top:3px solid var(--green);}
.kpi-card-amber{border-top:3px solid var(--amber);}
.kpi-card-red{border-top:3px solid var(--red);}
.kpi-badge-green{background:var(--green-l);color:#15803D;font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid var(--green-b);}
.kpi-badge-red{background:var(--red-l);color:#B91C1C;font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid var(--red-b);}
.kpi-badge-amber{background:var(--amber-l);color:#B45309;font-size:11px;font-weight:600;padding:3px 10px;border-radius:999px;border:1px solid var(--amber-b);}

/* ── Section header ── */
.sh{display:flex;align-items:center;gap:12px;margin:32px 0 20px;}
.sh-pill{width:36px;height:36px;border-radius:var(--rsm);display:flex;align-items:center;justify-content:center;font-size:17px;flex-shrink:0;}
.sh-indigo{background:#EFF6FF;}.sh-green{background:var(--green-l);}.sh-red{background:var(--red-l);}
.sh-amber{background:var(--amber-l);}.sh-blue{background:#EFF6FF;}.sh-purple{background:#F5F3FF;}
.sht{font-size:20px;font-weight:700;color:var(--t1);letter-spacing:-0.4px;}
.shs{font-size:13px;color:var(--t3);margin-top:3px;}

/* ── Section label ── */
.sect-lbl{font-size:11px;font-weight:700;letter-spacing:1.5px;text-transform:uppercase;color:var(--t3);margin:0 0 16px;}

/* ── Metrics block header ── */
.mbh{display:flex;align-items:center;gap:14px;background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:16px 22px;margin-bottom:18px;box-shadow:var(--sh);}
.mbh-dot{width:10px;height:10px;border-radius:50%;flex-shrink:0;}
.mbh-dot-blue{background:var(--blue);box-shadow:0 0 0 3px rgba(37,99,235,0.15);}
.mbh-dot-purple{background:var(--purple);box-shadow:0 0 0 3px rgba(124,58,237,0.15);}
.mbh-title{font-size:15px;font-weight:700;color:var(--t1);letter-spacing:-0.2px;}
.mbh-sub{font-size:12px;color:var(--t3);margin-top:2px;}
.mbh-badge{margin-left:auto;font-size:12px;font-weight:600;padding:4px 12px;border-radius:999px;}
.mbh-badge-blue{background:var(--blue-l);color:var(--blue);border:1px solid var(--blue-b);}
.mbh-badge-purple{background:#F5F3FF;color:var(--purple);border:1px solid #DDD6FE;}

/* ── Section separator ── */
.section-sep{display:flex;align-items:center;gap:16px;margin:32px 0 28px;}
.section-sep-line{flex:1;height:1px;background:var(--border);}
.section-sep-label{font-size:11px;font-weight:600;letter-spacing:1px;text-transform:uppercase;color:var(--t3);white-space:nowrap;padding:6px 14px;background:var(--card);border:1px solid var(--border);border-radius:999px;}

/* ── Chart card ── */
.chart-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:24px 26px;box-shadow:var(--sh);}

/* ── Table card ── */
.tbl-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:0;box-shadow:var(--sh);overflow:hidden;}
.tbl-head{display:grid;padding:12px 20px;background:#F9FAFB;border-bottom:1px solid var(--border);}
.tbl-row{display:grid;padding:12px 20px;border-bottom:1px solid #F9FAFB;font-size:14px;color:var(--t2);transition:background .12s;}
.tbl-row:hover{background:#FAFAFA;}
.tbl-row:last-child{border-bottom:none;}
.tbl-hcell{font-size:11px;font-weight:700;letter-spacing:.6px;text-transform:uppercase;color:var(--t3);}
.tbl-total{display:grid;padding:12px 20px;background:#F9FAFB;border-top:1px solid var(--border);font-size:14px;font-weight:700;color:var(--t1);}

/* ── NSF alert card ── */
.nsf-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:20px 24px;box-shadow:var(--sh);}
.nsf-header{display:flex;align-items:center;justify-content:space-between;margin-bottom:16px;}
.nsf-title{font-size:12px;font-weight:700;letter-spacing:.8px;text-transform:uppercase;color:var(--t3);}
.nsf-warn{font-size:18px;}
.nsf-row{display:flex;align-items:center;justify-content:space-between;padding:10px 0;border-bottom:1px solid #F9FAFB;font-size:14px;}
.nsf-row:last-child{border-bottom:none;}
.nsf-name{color:var(--t2);font-weight:500;}
.nsf-count{font-weight:700;color:var(--t1);}
.nsf-count.red{color:var(--red);}
.nsf-big{font-size:32px;font-weight:800;color:var(--red);letter-spacing:-1.5px;}

/* ── Empty state ── */
.empty-wrap{text-align:center;padding:64px 24px 52px;}
.empty-icon-ring{width:92px;height:92px;border-radius:50%;background:linear-gradient(135deg,#EFF6FF,#DBEAFE);border:2px solid var(--blue-b);display:flex;align-items:center;justify-content:center;margin:0 auto 24px;box-shadow:0 4px 20px rgba(37,99,235,0.12);}
.empty-icon-inner{font-size:38px;line-height:1;}
.es-title{font-size:24px;font-weight:800;color:var(--t1);margin-bottom:12px;letter-spacing:-0.5px;}
.es-sub{font-size:14px;color:var(--t3);max-width:420px;margin:0 auto 36px;line-height:1.75;}
.es-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:14px;max-width:540px;margin:0 auto;text-align:left;}
.es-card{background:var(--card);border-radius:var(--r);padding:20px;box-shadow:var(--sh);border-left:3px solid transparent;transition:box-shadow .2s,transform .2s;}
.es-card:hover{box-shadow:var(--sh-md);transform:translateY(-1px);}
.es-c1{border-left-color:var(--blue);}.es-c2{border-left-color:var(--green);}.es-c3{border-left-color:var(--amber);}.es-c4{border-left-color:var(--purple);}
.esc-icon{font-size:22px;margin-bottom:9px;}
.esc-t{font-size:13px;font-weight:700;color:var(--t1);margin-bottom:5px;}
.esc-s{font-size:12px;color:var(--t3);line-height:1.6;}

/* ── Risk ── */
.risk-wrap{display:flex;align-items:center;gap:16px;padding:20px 24px;background:var(--card);border:1px solid var(--border);border-radius:var(--r);box-shadow:var(--sh);margin-bottom:16px;}
.risk-badge{padding:6px 16px;border-radius:999px;font-size:13px;font-weight:700;}
.risk-low{background:var(--green-l);color:#15803D;border:1px solid var(--green-b);}
.risk-med{background:var(--amber-l);color:#B45309;border:1px solid var(--amber-b);}
.risk-high{background:var(--red-l);color:#B91C1C;border:1px solid var(--red-b);}
.risk-score{font-size:30px;font-weight:800;color:var(--t1);margin-left:auto;letter-spacing:-1.2px;}
.risk-lbl{font-size:11px;color:var(--t3);text-align:right;margin-top:2px;}

/* ── Insight ── */
.ins-card{background:var(--card);border:1px solid var(--border);border-left:3px solid var(--blue);border-radius:var(--r);padding:16px 20px;box-shadow:var(--sh);margin-bottom:10px;}
.ins-title{font-size:13px;font-weight:600;color:var(--t1);margin-bottom:4px;}
.ins-body{font-size:13px;color:var(--t2);line-height:1.6;}

/* ── Lender bars ── */
.lb-wrap{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:16px 22px;box-shadow:var(--sh);}
.lb-row{display:flex;align-items:center;gap:14px;padding:10px 0;border-bottom:1px solid #F9FAFB;}
.lb-row:last-child{border-bottom:none;}
.lb-name{font-size:13px;font-weight:500;color:var(--t1);min-width:150px;}
.lb-bar-wrap{flex:1;background:#F3F4F6;border-radius:999px;height:6px;}
.lb-bar{height:6px;border-radius:999px;background:linear-gradient(90deg,var(--blue),var(--purple));}
.lb-amt{font-size:13px;font-weight:700;color:var(--t1);min-width:100px;text-align:right;}

/* ── KPI expand toggle ── */
.kpi-toggle-row{display:flex;justify-content:flex-end;margin-top:10px;margin-bottom:4px;}
div[data-testid="stButton"].kpi-expand-btn>button{
  background:var(--card)!important;color:var(--t2)!important;
  border:1px solid var(--border)!important;border-radius:999px!important;
  font-size:12px!important;font-weight:600!important;padding:6px 16px!important;
  box-shadow:none!important;letter-spacing:.2px!important;
  transition:border-color .15s,color .15s!important;
}
div[data-testid="stButton"].kpi-expand-btn>button:hover{
  border-color:var(--blue)!important;color:var(--blue)!important;transform:none!important;box-shadow:none!important;
}

/* ── Export ── */
.exp-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:16px;margin-top:12px;}
.exp-card{background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:32px 24px;text-align:center;box-shadow:var(--sh);transition:all .2s;cursor:pointer;}
.exp-card:hover{border-color:var(--blue);box-shadow:var(--sh-md);transform:translateY(-3px);}
.exp-icon{font-size:34px;margin-bottom:14px;}
.exp-title{font-size:14px;font-weight:700;color:var(--t1);margin-bottom:5px;}
.exp-sub{font-size:12px;color:var(--t3);}
</style>
"""


# ── UI helpers ─────────────────────────────────────────────────────────────────

def _sh(icon: str, title: str, sub: str = "", color: str = "indigo") -> None:
    sub_html = f'<div class="shs">{sub}</div>' if sub else ""
    st.markdown(f"""
    <div class="sh">
      <div class="sh-pill sh-{color}">{icon}</div>
      <div><div class="sht">{title}</div>{sub_html}</div>
    </div>""", unsafe_allow_html=True)


def render_header() -> None:
    st.markdown(THEME, unsafe_allow_html=True)


def render_sidebar() -> tuple[bool, str]:
    with st.sidebar:
        st.markdown("""
        <div class="sb-brand">
          <div class="sb-logo-row">
            <div class="sb-logo-mark">O</div>
            <div>
              <div class="sb-brand-name">Orbit Optix</div>
              <div class="sb-brand-tag">Financial Intelligence</div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
        st.markdown('<span class="sb-sect-label">CLIENT</span>', unsafe_allow_html=True)
        client_id = st.text_input("cid", placeholder="e.g. SMITH-001",
                                  label_visibility="collapsed")
        st.markdown('<span class="sb-sect-label" style="margin-top:20px">SETTINGS</span>',
                    unsafe_allow_html=True)
        debug_mode = st.toggle("Debug Mode", value=False,
                               help="Show raw OCR text and parser output")
        st.markdown('<span class="sb-sect-label" style="margin-top:20px">FORMATS</span>',
                    unsafe_allow_html=True)
        st.markdown("""
        <div class="sb-fmt-row">
          <span class="sb-fmt-pill">PDF</span><span class="sb-fmt-pill">PNG</span>
          <span class="sb-fmt-pill">JPG</span><span class="sb-fmt-pill">CSV</span>
          <span class="sb-fmt-pill">XLSX</span>
        </div>
        <div class="sb-fmt-row" style="margin-top:5px">
          <span class="sb-fmt-pill">English</span><span class="sb-fmt-pill">French</span>
        </div>""", unsafe_allow_html=True)
        st.markdown('<div class="sb-footer">Orbit Optix v3.0 · Capital Infusion</div>',
                    unsafe_allow_html=True)
    return debug_mode, client_id


def render_info_bar(client_id: str, n: int, results_df) -> None:
    date_range = ""
    if not results_df.empty and "Statement Date" in results_df.columns:
        valid = results_df["Statement Date"].dropna()
        if len(valid) >= 2:
            date_range = f"{valid.iloc[0].strftime('%b %Y')} – {valid.iloc[-1].strftime('%b %Y')}"
        elif len(valid) == 1:
            date_range = valid.iloc[0].strftime("%b %Y")
    cid_html = (f'<div class="ib-item"><span class="ib-icon">👤</span>'
                f'<span class="ib-label">Client:</span>'
                f'<span class="ib-val">{client_id}</span></div>'
                f'<div class="ib-sep"></div>' if client_id else "")
    dr_html = (f'<div class="ib-item"><span class="ib-icon">📅</span>'
               f'<span class="ib-label">Range:</span>'
               f'<span class="ib-val">{date_range}</span></div>'
               f'<div class="ib-sep"></div>' if date_range else "")
    st.markdown(f"""
    <div class="info-bar">
      {cid_html}
      <div class="ib-item">
        <span class="ib-icon">🏢</span>
        <span class="ib-label">Platform:</span>
        <span class="ib-val">Orbit Optix</span>
      </div>
      <div class="ib-sep"></div>
      {dr_html}
      <div class="ib-live"><div class="ib-dot"></div>{n} Statement{"s" if n != 1 else ""} Loaded</div>
    </div>""", unsafe_allow_html=True)


def render_hero(n_files: int = 0, client_id: str = "") -> None:
    badge = (f'<span class="hero-badge">📁 {n_files} statement{"s" if n_files != 1 else ""} loaded</span>'
             if n_files else '<span class="hero-badge-idle">Ready — upload to begin</span>')
    cid_badge = f'<span class="hero-cid">Client · {client_id}</span>' if client_id else ""
    st.markdown(f"""
    <div class="hero">
      <div class="hero-glow"></div>
      <div class="hero-glow2"></div>
      <div class="hero-content">
        <div class="hero-eyebrow">Orbit Optix · Financial Intelligence</div>
        <div class="hero-title">Bank Statement Analysis</div>
        <div class="hero-sub">Upload bank statements to extract financial metrics, detect lender activity, and generate risk assessments automatically.</div>
        <div class="hero-badges">{badge}{cid_badge}</div>
      </div>
    </div>""", unsafe_allow_html=True)


def render_empty_state() -> None:
    st.markdown("""
    <div class="empty-wrap">
      <div class="empty-icon-ring"><div class="empty-icon-inner">📊</div></div>
      <div class="es-title">Drop your bank statements above</div>
      <div class="es-sub">PDF, images, CSV, or Excel — Orbit Optix extracts, analyses, and scores everything automatically.</div>
      <div class="es-grid">
        <div class="es-card es-c1"><div class="esc-icon">🔍</div><div class="esc-t">Smart OCR</div><div class="esc-s">Multi-format extraction with automatic language detection</div></div>
        <div class="es-card es-c2"><div class="esc-icon">🏦</div><div class="esc-t">Lender Detection</div><div class="esc-s">Identifies MCA and financing activity across all statements</div></div>
        <div class="es-card es-c3"><div class="esc-icon">⚡</div><div class="esc-t">Risk Scoring</div><div class="esc-s">Instant underwriting risk with NSF and withholding analysis</div></div>
        <div class="es-card es-c4"><div class="esc-icon">📤</div><div class="esc-t">Export Ready</div><div class="esc-s">Download statement breakdowns and summary reports as CSV</div></div>
      </div>
    </div>""", unsafe_allow_html=True)


def render_kpis(total_revenue, total_credits, total_debits,
                total_lender_debits, total_lender_credits, total_cash_flow,
                withholding_rate, nsf_count=0, avg_daily_balance=0.0,
                loan_count=0, n: int = 1, section_key: str = "overall") -> None:
    avg_rev  = total_revenue / max(n, 1)
    cf_pos   = total_cash_flow >= 0
    cf_sign  = "+" if cf_pos else ""
    cf_cls   = "kpi-green" if cf_pos else "kpi-red"
    nsf_cls  = "kpi-red"   if nsf_count > 0 else "kpi-green"
    nsf_top  = "kpi-card-red" if nsf_count > 2 else ("kpi-card-amber" if nsf_count > 0 else "kpi-card-green")
    wh_cls   = "kpi-red" if withholding_rate > 15 else ("kpi-amber" if withholding_rate > 8 else "")
    exp_key  = f"kpi_expanded_{section_key}"
    if exp_key not in st.session_state:
        st.session_state[exp_key] = False
    is_expanded = st.session_state[exp_key]

    # ── Primary row (always visible): Revenue, Credits, Debits, Withholding, Lender Debits ──
    c1, c2, c3, c4, c5 = st.columns(5, gap="small")

    with c1:
        st.markdown(f"""
        <div class="kpi-card kpi-card-blue">
          <div class="kpi-top">
            <span class="kpi-label">Total Revenue</span>
            <div class="kpi-icon-wrap kpi-icon-blue">💰</div>
          </div>
          <div class="kpi-value">${total_revenue:,.2f}</div>
          <div class="kpi-sub">Avg ${avg_rev:,.2f} / mo</div>
        </div>""", unsafe_allow_html=True)

    with c2:
        st.markdown(f"""
        <div class="kpi-card kpi-card-green">
          <div class="kpi-top">
            <span class="kpi-label">Total Credits</span>
            <div class="kpi-icon-wrap kpi-icon-green">📥</div>
          </div>
          <div class="kpi-value kpi-green">${total_credits:,.2f}</div>
          <div class="kpi-sub">Inbound deposits</div>
        </div>""", unsafe_allow_html=True)

    with c3:
        st.markdown(f"""
        <div class="kpi-card kpi-card-red">
          <div class="kpi-top">
            <span class="kpi-label">Total Debits</span>
            <div class="kpi-icon-wrap kpi-icon-red">📤</div>
          </div>
          <div class="kpi-value kpi-red">${total_debits:,.2f}</div>
          <div class="kpi-sub">Outbound payments</div>
        </div>""", unsafe_allow_html=True)

    with c4:
        st.markdown(f"""
        <div class="kpi-card kpi-card-amber">
          <div class="kpi-top">
            <span class="kpi-label">Withholding Rate</span>
            <div class="kpi-icon-wrap kpi-icon-amber">📊</div>
          </div>
          <div class="kpi-value {wh_cls}">{withholding_rate:.1f}%</div>
          <div class="kpi-sub">Lender debits / revenue</div>
        </div>""", unsafe_allow_html=True)

    with c5:
        st.markdown(f"""
        <div class="kpi-card">
          <div class="kpi-top">
            <span class="kpi-label">Lender Debits</span>
            <div class="kpi-icon-wrap kpi-icon-amber">🏢</div>
          </div>
          <div class="kpi-value kpi-amber">${total_lender_debits:,.2f}</div>
          <div class="kpi-sub">MCA repayments</div>
        </div>""", unsafe_allow_html=True)

    # ── Expand toggle ──
    _, btn_col = st.columns([9, 1])
    with btn_col:
        label = "▲ Less" if is_expanded else "▼ More"
        if st.button(label, key=f"btn_{exp_key}"):
            st.session_state[exp_key] = not is_expanded
            st.rerun()

    # ── Secondary row (expandable): Cash Flow, Lender Credits, Avg Balance, NSF, POS ──
    if is_expanded:
        st.markdown("<div style='height:4px'></div>", unsafe_allow_html=True)
        d1, d2, d3, d4, d5 = st.columns(5, gap="small")

        with d1:
            badge_cls = "kpi-badge-green" if cf_pos else "kpi-badge-red"
            badge_txt = "Positive" if cf_pos else "Negative"
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-top">
                <span class="kpi-label">Net Cash Flow</span>
                <span class="{badge_cls}">{badge_txt}</span>
              </div>
              <div class="kpi-value {cf_cls}">{cf_sign}${abs(total_cash_flow):,.2f}</div>
              <div class="kpi-sub">Credits minus debits</div>
            </div>""", unsafe_allow_html=True)

        with d2:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-top">
                <span class="kpi-label">Lender Credits</span>
                <div class="kpi-icon-wrap kpi-icon-purple">💸</div>
              </div>
              <div class="kpi-value">${total_lender_credits:,.2f}</div>
              <div class="kpi-sub">Inbound advances</div>
            </div>""", unsafe_allow_html=True)

        with d3:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-top">
                <span class="kpi-label">Avg Daily Balance</span>
                <div class="kpi-icon-wrap kpi-icon-blue">🏦</div>
              </div>
              <div class="kpi-value">${avg_daily_balance:,.2f}</div>
              <div class="kpi-sub">Across statement period</div>
            </div>""", unsafe_allow_html=True)

        with d4:
            warn_icon = "⚠️" if nsf_count > 0 else "✅"
            st.markdown(f"""
            <div class="kpi-card {nsf_top}">
              <div class="kpi-top">
                <span class="kpi-label">NSF Count</span>
                <span style="font-size:18px">{warn_icon}</span>
              </div>
              <div class="kpi-value {nsf_cls}">{nsf_count}</div>
              <div class="kpi-sub">Returned / bounced items</div>
            </div>""", unsafe_allow_html=True)

        with d5:
            st.markdown(f"""
            <div class="kpi-card">
              <div class="kpi-top">
                <span class="kpi-label">Loan Count</span>
                <div class="kpi-icon-wrap kpi-icon-blue">🏦</div>
              </div>
              <div class="kpi-value">{loan_count}</div>
              <div class="kpi-sub">Loan transactions detected</div>
            </div>""", unsafe_allow_html=True)


def render_chart(results_df: pd.DataFrame) -> None:
    if results_df.empty:
        return

    date_col = (results_df["Statement Date"].dt.strftime("%b %Y")
                if "Statement Date" in results_df.columns else results_df["Statement"])

    fig = go.Figure()
    fig.add_trace(go.Bar(name="Credits", x=date_col, y=results_df["Total Credits"],
                         marker_color="#6366F1", marker_line_width=0))
    fig.add_trace(go.Bar(name="Debits",  x=date_col, y=results_df["Total Debits"],
                         marker_color="#F43F5E", marker_line_width=0))
    if "Total Lender Debits" in results_df.columns:
        fig.add_trace(go.Bar(name="Lender Debits", x=date_col,
                             y=results_df["Total Lender Debits"],
                             marker_color="#8B5CF6", marker_line_width=0))
    fig.update_layout(
        barmode="group", height=290,
        plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter", size=11, color="#64748B"),
        margin=dict(t=10, b=10, l=0, r=0),
        legend=dict(orientation="h", y=1.12, x=0, bgcolor="rgba(0,0,0,0)", font_size=11),
        xaxis=dict(showgrid=False, linecolor="#F1F5F9", tickcolor="#F1F5F9"),
        yaxis=dict(showgrid=True, gridcolor="#F8FAFC", linecolor="#F8FAFC",
                   tickprefix="$", tickformat=",.0f"),
        hoverlabel=dict(bgcolor="#0F172A", font_color="white", font_size=12),
    )

    cash_flow = results_df["Total Credits"] - results_df["Total Debits"]
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=date_col, y=cash_flow, mode="lines+markers",
        line=dict(color="#10B981", width=2.5),
        marker=dict(color="#10B981", size=8, line=dict(color="white", width=2)),
        fill="tozeroy", fillcolor="rgba(16,185,129,0.07)",
    ))
    fig2.update_layout(
        height=290, plot_bgcolor="white", paper_bgcolor="white",
        font=dict(family="Inter", size=11, color="#64748B"),
        margin=dict(t=10, b=10, l=0, r=0), showlegend=False,
        xaxis=dict(showgrid=False, linecolor="#F1F5F9"),
        yaxis=dict(showgrid=True, gridcolor="#F8FAFC", linecolor="#F8FAFC",
                   tickprefix="$", tickformat=",.0f"),
    )

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        _sh("📊", "Revenue vs Debits", "Monthly comparison across statements")
        st.plotly_chart(fig, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with c2:
        st.markdown('<div class="chart-card">', unsafe_allow_html=True)
        _sh("📈", "Net Cash Flow", "Credits minus debits per period")
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)


# ── Data helpers (unchanged) ───────────────────────────────────────────────────

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
        if "date" in lower:                                          col_map[col] = "Date"
        elif "description" in lower or "memo" in lower or "details" in lower: col_map[col] = "Description"
        elif "withdrawal" in lower or "debit" in lower:             col_map[col] = "Debit"
        elif "deposit" in lower or "credit" in lower:               col_map[col] = "Credit"
        elif "amount" in lower:                                      col_map[col] = "Amount"
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
    raw_df = _sanitize_df(raw_df)
    return fix_lender_direction(raw_df)


def _safe_show(df: pd.DataFrame, cols: list[str] | None = None) -> None:
    if df is None or df.empty:
        return
    if cols:
        present = [c for c in cols if c in df.columns]
        df = df[present].copy() if present else df.copy()
    else:
        df = df.copy()
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


# ── Single file processor (unchanged logic) ────────────────────────────────────

def process_file(uploaded_file, all_filenames, debug_mode):
    name = uploaded_file.name.lower()
    raw_df = pd.DataFrame()
    original_text = translated_text = ""
    charges_only_total = 0.0

    with st.status(f"Processing {uploaded_file.name}…", expanded=False) as status:
        if name.endswith(".csv"):
            raw_df = pd.read_csv(uploaded_file)
        elif name.endswith((".xlsx", ".xls")):
            raw_df = pd.read_excel(uploaded_file)
        elif name.endswith(".pdf"):
            status.update(label="Extracting PDF…", state="running")
            original_text   = extract_text_from_pdf(uploaded_file, debug_mode)
            translated_text = normalize_transaction_text(translate_to_english(original_text))
            _, charges_only_total = extract_charges_only(translated_text)
            raw_df = parse_universal_bank_rows(translated_text)
            if raw_df.empty:
                raw_df = parse_ocr_transactions(translated_text)
        else:
            status.update(label="Processing image…", state="running")
            original_text   = extract_text_from_image(uploaded_file)
            translated_text = normalize_transaction_text(translate_to_english(original_text))
            raw_df = parse_universal_bank_rows(translated_text)
            if raw_df.empty:
                raw_df = parse_ocr_transactions(translated_text)

        if debug_mode and translated_text:
            with st.expander("Debug: OCR Output"):
                st.text_area("Extracted Text", translated_text, height=200, disabled=True)

        file_summary = route_and_extract(original_text, translated_text, uploaded_file)
        raw_df  = _prep_raw_df(raw_df) if not raw_df.empty else pd.DataFrame()
        temp_df = prepare_dataframe(raw_df) if not raw_df.empty else pd.DataFrame()

        if debug_mode and not raw_df.empty:
            debug_cols = [c for c in ["Date","Description","Debit","Credit","Amount","Balance"] if c in raw_df.columns]
            st.dataframe(raw_df[debug_cols], use_container_width=True)

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

        if not raw_df.empty:
            clean_df = _sanitize_df(raw_df)
            lender_rows,        lender_debit_total,  _ = get_lender_debits(clean_df, file_revenue)
            lender_credit_rows, lender_credit_total    = get_lender_credits(clean_df)
        else:
            lender_rows = lender_credit_rows = pd.DataFrame()
            lender_debit_total = lender_credit_total = 0.0

        withholding_rate = (lender_debit_total / file_revenue * 100) if file_revenue > 0 else 0.0

        SUSPICIOUS_KEYWORDS = ["SQ","SQUARE","PAYPAL","PAY PAL","STRIPE","SHOPIFY","INTUIT","CLOVER","TOAST"]
        flagged: list[dict] = []
        if translated_text:
            for line in translated_text.split("\n"):
                upper = str(line).upper()
                for kw in SUSPICIOUS_KEYWORDS:
                    if re.search(r"\b" + re.escape(kw) + r"\b", upper):
                        amounts = re.findall(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}", line)
                        flagged.append({"Matched Keyword": kw, "Flagged Line": line,
                                        "Detected Amount": abs(clean_money(amounts[0])) if amounts else 0.0})
                        break
        flagged_df = pd.DataFrame(flagged)

        stmt_nsf = count_nsf(temp_df, original_text)
        stmt_loan = count_loan(temp_df)

        avg_bal_result = extract_average_balance(original_text) if original_text else None
        if avg_bal_result is None:
            daily = extract_daily_balances_from_text(original_text) if original_text else []
            if not daily and not temp_df.empty and "Balance" in temp_df.columns:
                daily = temp_df["Balance"].dropna().tolist()
            stmt_avg_balance = float(sum(daily) / len(daily)) if daily else 0.0
        else:
            stmt_avg_balance = float(avg_bal_result)

        statement_date = extract_statement_date(original_text, uploaded_file.name, all_filenames)
        status.update(label="Complete", state="complete")

    return {
        "Statement":             uploaded_file.name,
        "Statement Date":        statement_date,
        "Total Monthly Revenue": file_revenue,
        "Total Credits":         file_credits,
        "Total Debits":          file_debits,
        "Total Lender Debits":   lender_debit_total,
        "Total Lender Credits":  lender_credit_total,
        "Withholding Rate":      withholding_rate,
        "Credit Transactions":   file_credit_count,
        "Debit Transactions":    file_debit_count,
        "Lender Transactions":   len(lender_rows),
        "NSF Count":             stmt_nsf,
        "Avg Daily Balance":     stmt_avg_balance,
        "Loan Count":            stmt_loan,
    }, temp_df, lender_rows, lender_credit_rows, flagged_df


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    render_header()
    debug_mode, client_id = render_sidebar()

    # ── Hero ──────────────────────────────────────────────────────────────────
    render_hero(client_id=client_id)

    # ── Upload ────────────────────────────────────────────────────────────────
    _sh("📁", "Upload Statements", "PDF, images, CSV, or Excel files")
    uploaded_files = st.file_uploader(
        "Drop bank statement files here",
        type=["csv", "xlsx", "xls", "pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if not uploaded_files:
        render_empty_state()
        return

    try:
        all_filenames           = [f.name for f in uploaded_files]
        statement_results       = []
        all_dataframes          = []
        all_lender_data         = {}
        all_lender_credit_data  = {}
        all_flagged_data        = {}

        for uf in uploaded_files:
            result, temp_df, lender_rows, lender_credit_rows, flagged_df = process_file(
                uf, all_filenames, debug_mode
            )
            statement_results.append(result)
            if not temp_df.empty:
                temp_df["Statement"] = uf.name
                all_dataframes.append(temp_df)
            all_lender_data[uf.name]        = lender_rows
            all_lender_credit_data[uf.name] = lender_credit_rows
            all_flagged_data[uf.name]       = flagged_df

        # ── Build & sort results_df ─────────────────────────────────────────
        results_df = pd.DataFrame(statement_results)
        if "Total Lender Credits" not in results_df.columns:
            results_df["Total Lender Credits"] = 0.0
        results_df["Statement Date"] = pd.to_datetime(results_df["Statement Date"], errors="coerce")
        results_df = results_df.sort_values("Statement Date", na_position="last").reset_index(drop=True)

        for i in range(1, len(results_df)):
            curr = results_df.at[i,     "Statement Date"]
            prev = results_df.at[i - 1, "Statement Date"]
            if pd.isna(curr) or pd.isna(prev):
                continue
            gap = (curr.year - prev.year) * 12 + (curr.month - prev.month)
            if gap > 6:
                results_df.at[i, "Statement Date"] = curr - pd.DateOffset(years=1)
        results_df = results_df.sort_values("Statement Date", na_position="last").reset_index(drop=True)

        if results_df.empty:
            st.error("No statement data could be detected.")
            return

        # ── Aggregate totals ────────────────────────────────────────────────
        n                   = len(results_df)
        total_revenue       = results_df["Total Monthly Revenue"].sum()
        total_credits       = results_df["Total Credits"].sum()
        total_debits        = results_df["Total Debits"].sum()
        total_lender_debits = results_df["Total Lender Debits"].sum()
        total_lender_credits= results_df["Total Lender Credits"].sum()
        total_cash_flow     = total_credits - total_debits
        withholding_rate    = (total_lender_debits / total_revenue * 100) if total_revenue > 0 else 0.0
        avg_daily_balance   = float(results_df["Avg Daily Balance"].mean())

        combined_df = pd.concat(all_dataframes, ignore_index=True) if all_dataframes else pd.DataFrame()
        nsf_count = int(combined_df["NSF Flag"].sum()) if not combined_df.empty and "NSF Flag" in combined_df.columns else 0
        loan_count = count_loan(combined_df) if not combined_df.empty else 0

        # ── Lender app forwarding ───────────────────────────────────────────
        try:
            resp = _requests.post(
                f"{_LENDER_APP_URL}/bank-statement",
                json={"client_id": client_id, "summary_metrics": {
                    "nsf_count":         nsf_count,
                    "loan_count":        loan_count,
                    "total_deposits":    round(total_credits / n, 2),
                    "total_revenue":     round(total_revenue / n, 2),
                    "avg_daily_balance": round(avg_daily_balance, 2),
                }},
                timeout=10,
            )
            if resp.ok:
                st.toast("Sent to lender app", icon="✅")
                cid = resp.json().get("client_id")
                if cid:
                    jr = _requests.get(f"{_LENDER_APP_URL}/job/{cid}", timeout=10)
                    if jr.ok:
                        st.toast("Lender suggestion received", icon="✅")
        except Exception:
            pass

        # ── Info bar (hero already rendered above) ──────────────────────────
        render_info_bar(client_id, n, results_df)

        # ── Tabs ────────────────────────────────────────────────────────────
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "Dashboard", "Statements", "Lenders", "Analysis", "Export",
        ])

        # ═══ TAB 1 — Dashboard ══════════════════════════════════════════════
        with tab1:
            # ── Overall KPIs ─────────────────────────────────────────────
            st.markdown(f"""
            <div class="mbh">
              <div class="mbh-dot mbh-dot-blue"></div>
              <div>
                <div class="mbh-title">Overall Totals</div>
                <div class="mbh-sub">Cumulative figures across all {n} statement{"s" if n != 1 else ""}</div>
              </div>
              <span class="mbh-badge mbh-badge-blue">All time</span>
            </div>""", unsafe_allow_html=True)
            render_kpis(
                total_revenue, total_credits, total_debits,
                total_lender_debits, total_lender_credits, total_cash_flow,
                withholding_rate, nsf_count, avg_daily_balance, loan_count,
                n=n, section_key="overall")

            st.markdown("""
            <div class="section-sep">
              <div class="section-sep-line"></div>
              <div class="section-sep-label">Monthly Average</div>
              <div class="section-sep-line"></div>
            </div>""", unsafe_allow_html=True)
            st.markdown(f"""
            <div class="mbh">
              <div class="mbh-dot mbh-dot-purple"></div>
              <div>
                <div class="mbh-title">Average Monthly</div>
                <div class="mbh-sub">Per-statement averages across {n} month{"s" if n != 1 else ""}</div>
              </div>
              <span class="mbh-badge mbh-badge-purple">Per month</span>
            </div>""", unsafe_allow_html=True)
            render_kpis(
                total_revenue / n,        total_credits / n,
                total_debits / n,         total_lender_debits / n,
                total_lender_credits / n, total_cash_flow / n,
                withholding_rate,
                int(results_df["NSF Count"].mean()),
                float(results_df["Avg Daily Balance"].mean()),
                int(results_df["Loan Count"].mean()), n=1, section_key="monthly")

            st.divider()

            # ── Debt & Risk Profile ──────────────────────────────────────
            st.markdown('<div class="sect-lbl">DEBT &amp; RISK PROFILE</div>',
                        unsafe_allow_html=True)
            # Rebuild lender rows for the dashboard tab
            _all_ldr = pd.concat(
                [df for df in all_lender_data.values() if not df.empty], ignore_index=True,
            ) if any(not df.empty for df in all_lender_data.values()) else pd.DataFrame()

            col_tbl, col_chart, col_nsf = st.columns([4, 3, 3], gap="medium")

            # Lender table
            with col_tbl:
                if not _all_ldr.empty and "Detected Lender" in _all_ldr.columns:
                    ldr_tbl = (_all_ldr
                               .groupby("Detected Lender").agg(
                                   Last_Date=("Date", "last"),
                                   Total=("Lender Debit Amount", "sum"))
                               .reset_index()
                               .sort_values("Total", ascending=False)
                               .head(8))
                    rows_html = "".join(
                        f'<div class="tbl-row" style="grid-template-columns:2fr 1.5fr 1.5fr">'
                        f'<span>{r["Detected Lender"]}</span>'
                        f'<span>{r["Last_Date"] if pd.notna(r["Last_Date"]) else "—"}</span>'
                        f'<span style="font-weight:700">${r["Total"]:,.2f}</span></div>'
                        for _, r in ldr_tbl.iterrows()
                    )
                    total_exp = _all_ldr["Lender Debit Amount"].sum()
                    st.markdown(f"""
                    <div class="tbl-card">
                      <div class="tbl-head" style="grid-template-columns:2fr 1.5fr 1.5fr">
                        <span class="tbl-hcell">Lender</span>
                        <span class="tbl-hcell">Last Date</span>
                        <span class="tbl-hcell">Total Debited</span>
                      </div>
                      {rows_html}
                      <div class="tbl-total" style="grid-template-columns:2fr 1.5fr 1.5fr">
                        <span>Total</span><span></span>
                        <span>${total_exp:,.2f}</span>
                      </div>
                    </div>""", unsafe_allow_html=True)
                else:
                    st.info("No lender activity detected")

            # Exposure donut chart
            with col_chart:
                # Withholding rate gauge: lender debits as % of total revenue
                wr = min(withholding_rate, 100.0)
                remaining = max(100.0 - wr, 0)
                wr_color = ("#E53E3E" if wr > 30 else
                            "#D97706" if wr > 15 else "#4F6EF7")
                fig_donut = go.Figure(go.Pie(
                    values=[wr, remaining],
                    labels=["Lender Exposure", "Free Revenue"],
                    hole=0.68,
                    marker_colors=[wr_color, "#EDF0F5"],
                    textinfo="none",
                    hoverinfo="none",
                    sort=False,
                ))
                fig_donut.update_layout(
                    height=210, margin=dict(t=0, b=0, l=0, r=0),
                    showlegend=False,
                    paper_bgcolor="white", plot_bgcolor="white",
                    annotations=[
                        dict(text=f"{wr:.1f}%", x=0.5, y=0.58,
                             font=dict(size=18, color="#0D1526", family="Inter"),
                             showarrow=False),
                        dict(text="of revenue", x=0.5, y=0.38,
                             font=dict(size=10, color="#9AA5B4", family="Inter"),
                             showarrow=False),
                    ],
                )
                st.markdown('<div style="font-size:11px;font-weight:700;letter-spacing:1px;text-transform:uppercase;color:#9AA5B4;margin-bottom:4px">Withholding Rate</div>',
                            unsafe_allow_html=True)
                st.plotly_chart(fig_donut, use_container_width=True,
                               config={"displayModeBar": False})
                st.markdown(f'<div style="font-size:12px;color:#9AA5B4;text-align:center;margin-top:-12px">${total_lender_debits:,.2f} paid to lenders</div>',
                            unsafe_allow_html=True)

            # NSF alerts panel
            with col_nsf:
                nsf_cls_big = "red" if nsf_count > 0 else ""
                st.markdown(f"""
                <div class="nsf-card">
                  <div class="nsf-header">
                    <span class="nsf-title">NSF Alerts</span>
                    <span class="nsf-warn">{"⚠️" if nsf_count > 0 else "✅"}</span>
                  </div>
                  <div class="nsf-row">
                    <span class="nsf-name">Total NSFs</span>
                    <span class="nsf-count {nsf_cls_big}">{nsf_count}</span>
                  </div>
                  <div class="nsf-row">
                    <span class="nsf-name">Withholding Rate</span>
                    <span class="nsf-count">{withholding_rate:.1f}%</span>
                  </div>
                  <div class="nsf-row">
                    <span class="nsf-name">Avg Daily Balance</span>
                    <span class="nsf-count">${avg_daily_balance:,.0f}</span>
                  </div>
                  <div class="nsf-row">
                    <span class="nsf-name">Loan Count</span>
                    <span class="nsf-count">{loan_count}</span>
                  </div>
                </div>""", unsafe_allow_html=True)

            st.divider()
            render_chart(results_df)

        # ═══ TAB 2 — Statements ═════════════════════════════════════════════
        with tab2:
            _sh("📋", "Statement Summary", f"{n} statements analysed", "indigo")
            display = results_df.copy()
            for col in ["Total Monthly Revenue","Total Credits","Total Debits",
                        "Total Lender Debits","Total Lender Credits"]:
                if col in display.columns:
                    display[col] = display[col].apply(lambda x: f"${x:,.2f}")
            if "Withholding Rate" in display.columns:
                display["Withholding Rate"] = display["Withholding Rate"].apply(lambda x: f"{x:.2f}%")
            st.dataframe(display, use_container_width=True, hide_index=True)

        # ═══ TAB 3 — Lenders ════════════════════════════════════════════════
        with tab3:
            all_lender_rows = pd.concat(
                [df for df in all_lender_data.values() if not df.empty], ignore_index=True,
            ) if any(not df.empty for df in all_lender_data.values()) else pd.DataFrame()

            all_credit_rows = pd.concat(
                [df for df in all_lender_credit_data.values() if not df.empty], ignore_index=True,
            ) if any(not df.empty for df in all_lender_credit_data.values()) else pd.DataFrame()

            _sh("💰", "Lender Overview", "Detected financing relationships", "purple")
            total_ld = all_lender_rows["Lender Debit Amount"].sum() if not all_lender_rows.empty else 0
            total_lc = all_credit_rows["Lender Credit Amount"].sum() if not all_credit_rows.empty else 0
            c1, c2 = st.columns(2, gap="small")
            with c1:
                st.markdown(f"""
                <div class="kpi-card kpi-card-red">
                  <div class="kpi-top"><span class="kpi-label">Total Lender Debits</span></div>
                  <div class="kpi-value kpi-red">${total_ld:,.2f}</div>
                </div>""", unsafe_allow_html=True)
            with c2:
                st.markdown(f"""
                <div class="kpi-card kpi-card-green">
                  <div class="kpi-top"><span class="kpi-label">Total Lender Credits</span></div>
                  <div class="kpi-value kpi-green">${total_lc:,.2f}</div>
                </div>""", unsafe_allow_html=True)

            if not all_lender_rows.empty:
                st.divider()
                _sh("📊", "Lender Exposure", "Debits ranked by total amount", "purple")
                tbl = (all_lender_rows
                       .groupby("Detected Lender")["Lender Debit Amount"].sum()
                       .reset_index()
                       .sort_values("Lender Debit Amount", ascending=False)
                       .reset_index(drop=True))
                max_amt = tbl["Lender Debit Amount"].max()
                bars_html = ""
                for _, row in tbl.iterrows():
                    pct = (row["Lender Debit Amount"] / max_amt * 100) if max_amt else 0
                    bars_html += f"""
                    <div class="lb-row">
                      <div class="lb-name">{row['Detected Lender']}</div>
                      <div class="lb-bar-wrap"><div class="lb-bar" style="width:{pct:.1f}%"></div></div>
                      <div class="lb-amt">${row['Lender Debit Amount']:,.2f}</div>
                    </div>"""
                st.markdown(f'<div style="background:var(--card);border:1px solid var(--border);border-radius:var(--r);padding:16px 20px;box-shadow:var(--sh)">{bars_html}</div>',
                            unsafe_allow_html=True)

            st.divider()
            _sh("📁", "Per-Statement Detail", "", "indigo")
            for fname, lender_data in all_lender_data.items():
                with st.expander(f"📄 {fname}"):
                    lc_data      = all_lender_credit_data.get(fname, pd.DataFrame())
                    flagged_data = all_flagged_data.get(fname, pd.DataFrame())
                    c1, c2 = st.columns(2)
                    with c1:
                        st.markdown("**🔻 Lender Debits**")
                        if not lender_data.empty:
                            _safe_show(lender_data, ["Date","Description","Detected Lender","Lender Debit Amount"])
                        else:
                            st.info("No lender debits detected")
                    with c2:
                        st.markdown("**🟢 Lender Credits**")
                        if not lc_data.empty:
                            _safe_show(lc_data, ["Date","Description","Detected Lender","Lender Credit Amount"])
                        else:
                            st.info("No lender credits detected")
                    if not flagged_data.empty:
                        st.markdown("**⚠️ Flagged Transactions**")
                        _safe_show(flagged_data, ["Matched Keyword","Flagged Line","Detected Amount"])

        # ═══ TAB 4 — Analysis ═══════════════════════════════════════════════
        with tab4:
            if not combined_df.empty:
                funding_detected = (bool(combined_df["Funding Detected"].any())
                                    if "Funding Detected" in combined_df.columns else False)
                funders = (sorted(set(combined_df.loc[combined_df["Funded By"] != "","Funded By"].tolist()))
                           if "Funded By" in combined_df.columns else [])
                risk_score, risk_level = calculate_risk_level(total_revenue, total_debits, nsf_count, funding_detected)

                # Risk assessment card
                _sh("🎯", "Risk Assessment", "Automated underwriting indicators", "red")
                risk_cls = "risk-low" if "low" in risk_level.lower() else ("risk-high" if "high" in risk_level.lower() else "risk-med")
                notes = generate_notes(total_revenue, total_debits, total_cash_flow,
                                       nsf_count, funding_detected, funders, withholding_rate)
                st.markdown(f"""
                <div class="risk-wrap">
                  <span class="risk-badge {risk_cls}">{risk_level}</span>
                  <div style="margin-left:12px;font-size:13px;color:var(--t2)">
                    {"Funding activity detected — " + ", ".join(funders) if funding_detected else "No funding stack detected"}
                  </div>
                  <div style="margin-left:auto;text-align:right">
                    <div class="risk-score">{risk_score:.0f}</div>
                    <div class="risk-label">Risk Score</div>
                  </div>
                </div>""", unsafe_allow_html=True)

                # Insight notes
                if notes:
                    _sh("📝", "Underwriting Notes", f"{len(notes)} observations", "amber")
                    for note in notes:
                        st.markdown(f"""
                        <div class="ins-card">
                          <div class="ins-head"><span class="ins-icon">•</span><span class="ins-title">{note[:60]}{'…' if len(note)>60 else ''}</span></div>
                          <div class="ins-body">{note}</div>
                        </div>""", unsafe_allow_html=True)

                st.divider()
                # Transaction stats
                _sh("💳", "Transaction Details", f"{len(combined_df):,} total rows", "indigo")
                credit_rows = len(combined_df[combined_df["Credit"] > 0]) if "Credit" in combined_df.columns else 0
                debit_rows  = len(combined_df[combined_df["Debit"]  > 0]) if "Debit"  in combined_df.columns else 0
                ca, cb, cc, cd = st.columns(4, gap="small")
                for col, lbl, val, cls in [
                    (ca, "Total Rows",  f"{len(combined_df):,}", ""),
                    (cb, "Credit Rows", f"{credit_rows:,}",       "kpi-green"),
                    (cc, "Debit Rows",  f"{debit_rows:,}",        "kpi-red"),
                    (cd, "NSF Events",  str(nsf_count),           "kpi-red" if nsf_count > 0 else "kpi-green"),
                ]:
                    with col:
                        st.markdown(f"""
                        <div class="kpi-card">
                          <div class="kpi-top"><span class="kpi-label">{lbl}</span></div>
                          <div class="kpi-value {cls}">{val}</div>
                        </div>""", unsafe_allow_html=True)
                st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
                _safe_show(combined_df)
            else:
                st.info("No transaction data available for analysis.")

        # ═══ TAB 5 — Export ═════════════════════════════════════════════════
        with tab5:
            _sh("⬇️", "Export Reports", "Download your analysis results", "green")

            st.markdown("""
            <div class="exp-grid">
              <div class="exp-card"><div class="exp-icon">📄</div><div class="exp-title">Statement Results</div><div class="exp-sub">Per-statement breakdown as CSV</div></div>
              <div class="exp-card"><div class="exp-icon">📊</div><div class="exp-title">Summary Report</div><div class="exp-sub">Aggregated metrics as CSV</div></div>
            </div>""", unsafe_allow_html=True)

            st.markdown("<div style='height:16px'></div>", unsafe_allow_html=True)
            c1, c2 = st.columns(2)
            with c1:
                st.download_button(
                    "⬇️  Download Statement Results (CSV)",
                    results_df.to_csv(index=False).encode("utf-8"),
                    "orbit_optix_statements.csv", "text/csv",
                    use_container_width=True,
                )
            with c2:
                summary_df = pd.DataFrame({
                    "Metric": ["Total Revenue","Total Credits","Total Debits",
                               "Total Lender Debits","Total Lender Credits",
                               "Withholding Rate","Cash Flow",
                               "NSF Count","Avg Daily Balance","Loan Count"],
                    "Value": [f"${total_revenue:,.2f}", f"${total_credits:,.2f}",
                              f"${total_debits:,.2f}",  f"${total_lender_debits:,.2f}",
                              f"${total_lender_credits:,.2f}", f"{withholding_rate:.2f}%",
                              f"${total_cash_flow:,.2f}", str(nsf_count),
                              f"${avg_daily_balance:,.2f}", str(loan_count)],
                })
                st.download_button(
                    "⬇️  Download Summary Report (CSV)",
                    summary_df.to_csv(index=False).encode("utf-8"),
                    "orbit_optix_summary.csv", "text/csv",
                    use_container_width=True,
                )

    except Exception as exc:
        st.error(f"Error processing files: {exc}")
        if debug_mode:
            import traceback
            st.code(traceback.format_exc())


if __name__ == "__main__":
    main()
