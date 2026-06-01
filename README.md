# Orbit Optix — Bank Statement Analysis Platform

Full-stack application that OCRs bank statement PDFs/images, extracts financial metrics, detects lender activity, scores risk, and presents everything in an interactive React dashboard.

---

## Architecture

```
ocr_draft/
├── application_api.py     # Flask API (legacy/standalone)
├── backend/               # FastAPI app (primary, used by the frontend)
│   ├── main.py            # App entry point, CORS, router registration
│   ├── api/
│   │   ├── upload.py      # POST /api/upload
│   │   └── export.py      # POST /api/export/*
│   └── services/
│       └── processor.py   # Core OCR + metric extraction logic
├── utils/                 # Shared utilities (OCR, cleaning, lender detection, etc.)
├── banks/                 # Bank-specific parsers (Chase, BofA, Wells Fargo, etc.)
├── lender_keywords.json   # Persisted custom lender keywords (auto-created)
└── frontend/              # React + Vite UI
    └── src/
        ├── pages/         # Dashboard, Statements, Lenders, Analysis, Export
        ├── components/    # Charts, KpiGrid, AddLenderModal, etc.
        ├── store/         # Zustand global state (useStore.js)
        └── services/      # api.js — all HTTP calls to the backend
```

---

## Running the App

**Backend (FastAPI)**
```bash
cd ocr_draft
uvicorn backend.main:app --reload --port 8000
```

**Frontend (React + Vite)**
```bash
cd ocr_draft/frontend
npm install
npm run dev        # http://localhost:5173
```

The Vite dev server proxies `/api/*` to `http://localhost:8000`.

**Legacy Flask API (standalone, no frontend)**
```bash
cd ocr_draft
python application_api.py
```

---

## API Endpoints

### FastAPI (`backend/main.py`) — used by the React frontend

All routes are prefixed `/api` and served on port `8000`.

---

#### `GET /health`
Health check.

**Response**
```json
{ "status": "ok", "service": "Orbit Optix API" }
```

---

#### `POST /api/upload`
Upload one or more bank statement files. Returns per-statement metrics, aggregated totals, monthly averages, detected lender activity, flagged transactions, and a risk score.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `files` | File(s) | Yes | PDF, PNG, JPG, CSV, XLSX, XLS |
| `client_id` | string | No | Client identifier — triggers forwarding to the lender suggestion service |

**Response**
```json
{
  "session_id": "uuid",
  "client_id": "string",
  "statements": [
    {
      "filename": "statement.pdf",
      "statement_date": "2026-03-01",
      "credits": 52000.00,
      "debits": 48000.00,
      "cash_flow": 4000.00,
      "lender_debits": 2100.00,
      "lender_credits": 0.00,
      "withholding_rate": 4.04,
      "nsf_count": 0,
      "pos_count": 312,
      "avg_daily_balance": 8400.00,
      "charges_only": 0.00
    }
  ],
  "totals": {
    "credits": 52000.00,
    "debits": 48000.00,
    "cash_flow": 4000.00,
    "lender_debits": 2100.00,
    "lender_credits": 0.00,
    "nsf_count": 0,
    "pos_count": 312,
    "avg_daily_balance": 8400.00,
    "withholding_rate": 4.04
  },
  "averages": { "...same keys as totals, divided by number of statements..." },
  "lenders": [
    { "lender": "Kapitus", "keyword": "kapitus", "amount": 2100.00, "statement": "statement.pdf" }
  ],
  "flagged": [
    { "keyword": "stripe", "amount": 500.00, "statement": "statement.pdf", "line": "STRIPE PAYOUT..." }
  ],
  "risk": {
    "score": 22,
    "level": "Low Risk",
    "notes": ["No NSF events detected", "Withholding rate is healthy at 4.0%"]
  },
  "transactions": [
    { "Date": "2026-03-15", "Description": "KAPITUS FUNDING", "Debit": 700.00, "Credit": null, "Balance": 12300.00, "statement": "statement.pdf" }
  ],
  "lender_app_notified": true,
  "lender_app_status": 200,
  "lender_suggestion": { "...lender suggestion response..." }
}
```

---

#### `POST /api/export/csv`
Export statement summary as a CSV file download.

**Request** — JSON body
```json
{ "statements": [ { "...statement objects..." } ] }
```

**Response** — `text/csv` file download (`orbit_statements.csv`)

---

#### `POST /api/export/transactions`
Export full transaction list as a CSV file download.

**Request** — JSON body
```json
{ "transactions": [ { "Date": "...", "Description": "...", "Debit": 0, "Credit": 0, "Balance": 0 } ] }
```

**Response** — `text/csv` file download (`orbit_transactions.csv`)

---

#### `POST /api/export/json`
Export the full analysis payload as a JSON file download.

**Request** — JSON body (any shape — typically the full upload response)

**Response** — `application/json` file download (`orbit_export.json`)

---

### Flask API (`application_api.py`) — standalone / external integrations

Served on port `5001` by default (`PORT` env var overrides).

---

#### `POST /parse-bank-statement`
Same OCR + extraction logic as `/api/upload` but as a standalone Flask endpoint. Useful for direct API integrations without the FastAPI layer.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `files[]` or `files` | File(s) | Yes | PDF, PNG, JPG, CSV, XLSX, XLS |
| `client_id` | string | No | Triggers lender app forwarding |

**Response** — same structure as `/api/upload`

**Example**
```bash
curl -X POST http://localhost:5001/parse-bank-statement \
  -F "files[]=@march_statement.pdf" \
  -F "files[]=@april_statement.pdf" \
  -F "client_id=CLIENT123"
```

---

#### `POST /parse-application`
OCR a Capital Infusion funding application PDF and return parsed fields.

**Request** — `multipart/form-data`

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | PDF only |
| `client_id` | string | No | Forwarded to lender app |

**Response** — JSON with extracted application fields (business name, DBA, owner info, etc.)

---

#### `GET /health`
```json
{ "status": "ok" }
```

---

#### `GET /lender-keywords`
Return all saved custom lender keywords. Called by the frontend on app load to pre-populate the auto-detection list.

**Response**
```json
[
  { "name": "Expansio Capital", "type": "debit" },
  { "name": "PayPal", "type": "credit" }
]
```

---

#### `POST /lender-keywords`
Save a new custom lender keyword. Automatically deduplicated. Persisted to `lender_keywords.json` on the server — shared across all users and sessions.

**Request** — JSON body

| Field | Values | Description |
|---|---|---|
| `name` | string | Lender name matched against transaction descriptions (case-insensitive `includes`) |
| `type` | `"debit"` or `"credit"` | Whether to match debit or credit transactions |

```json
{ "name": "Expansio Capital", "type": "debit" }
```

**Response** — updated full list of keywords

---

#### `DELETE /lender-keywords`
Remove a saved keyword. Future uploads will no longer auto-detect it.

**Request** — JSON body
```json
{ "name": "Expansio Capital", "type": "debit" }
```

**Response** — updated full list of keywords

---

## Custom Lender Keyword System

When a user clicks **+** on a transaction in the Statements tab, types a lender name (e.g. "PayPal"), and confirms:

1. All transactions whose description **contains** that name (case-insensitive) are added as lender rows
2. The keyword is saved server-side via `POST /lender-keywords` to `lender_keywords.json`
3. On every future upload, `applyCustomKeywords()` in the store scans new transactions against all saved keywords and automatically injects matching rows + adjusts totals and withholding rate

Keywords are managed in the **Lenders tab** under "Tracked Lender Keywords" — each can be removed individually with the × button.

---

## Analysis Tab — Charts

| Chart | Type | Description |
|---|---|---|
| Revenue Forecast | Area + dashed projection | Linear regression prediction for next month's revenue. Confidence: Low (1–2 months), Medium (3–5), High (6+) |
| Revenue vs Debits | Grouped bar | Credits, debits, lender debits per statement |
| Cash Flow Trend | Area | Net cash position per statement |
| Daily Balance Trend | Area | Avg daily balance per statement |
| Financial Overview | Multi-line | Cash flow + lender credits + avg daily balance |
| Withholding Rate | Area (amber) | % of revenue consumed by lender repayments |
| NSF Count | Bar (red/gray) | Non-sufficient fund events — bars turn red when count > 0 |
| Debt Load | Donut | Lender vs organic share of total outflows. Center shows lender %. Thresholds: <15% healthy, 15–30% watch, >30% high risk |
| MoM Revenue Change | Bar (green/red) | % change in credits vs prior statement. Requires 2+ statements |
| Balance / Obligation | Line (colored dots) | Avg daily balance ÷ lender debits. Dot colors: green ≥2×, amber 1–2×, red <1×. Reference line at 1× |
| Lender In vs Out | Grouped bar | MCA advances received vs repayments made per statement |

All charts display **newest month first** (left to right). Dates parsed from `statement_date` ISO field or extracted from filenames (supports spelled-out month names and numeric patterns).

---

## Risk Scoring

Calculated server-side in `utils/risk_detection.py`. Score is 0–100 (lower is better).

| Level | Badge |
|---|---|
| Low Risk | Green |
| Medium Risk | Amber |
| High Risk | Red |

Factors: NSF count, withholding rate, cash flow trend, avg daily balance, lender activity patterns.

---

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `5001` | Flask API port |
| `CORS_ORIGINS` | `http://localhost:5173,http://localhost:3000` | Allowed CORS origins for FastAPI |

---

## Frontend Tech Stack

| Library | Version | Purpose |
|---|---|---|
| React | 18 | UI framework |
| Vite | 5 | Build tool / dev server |
| Tailwind CSS | 3 | Styling |
| Recharts | 2 | All charts |
| Zustand | 4 | Global state management |
| react-router-dom | 6 | Tab-based routing |
| lucide-react | — | Icons |
| axios | — | HTTP client |
| react-dropzone | — | File upload drag-and-drop |
| clsx | — | Conditional className utility |
