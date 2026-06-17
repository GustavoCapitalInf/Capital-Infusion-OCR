import os
import uuid

import requests as _requests
from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from backend.services.processor import process_files

router = APIRouter()

_ALLOWED       = {".pdf", ".png", ".jpg", ".jpeg", ".csv", ".xlsx", ".xls"}
_LENDER_APP_URL = "https://lendersuggestion.onrender.com"


def _forward_to_lender_app(client_id: str, result: dict) -> dict:
    """
    Mirror the forwarding logic from app.py:
    POST /bank-statement with summary metrics, then GET /job/{client_id}.
    Returns a dict of lender_app_* fields to merge into the response.
    """
    totals   = result.get("totals", {})
    averages = result.get("averages", {})
    n        = max(len(result.get("statements", [])), 1)

    payload = {
        "client_id": client_id,
        "summary_metrics": {
            "nsf_count":         totals.get("nsf_count", 0),
            "loan_count":        totals.get("loan_count", 0),
            "total_deposits":    averages.get("credits", 0),
            "total_revenue":     averages.get("credits", 0),
            "avg_daily_balance": totals.get("avg_daily_balance", 0),
        },
    }

    try:
        resp = _requests.post(
            f"{_LENDER_APP_URL}/bank-statement",
            json=payload,
            timeout=10,
        )
        out = {
            "lender_app_notified": resp.ok,
            "lender_app_status":   resp.status_code,
        }
        if resp.ok:
            cid = resp.json().get("client_id") or client_id
            if cid:
                jr = _requests.get(f"{_LENDER_APP_URL}/job/{cid}", timeout=10)
                out["lender_suggestion"] = jr.json() if jr.ok else {"error": jr.status_code}
        return out
    except Exception as exc:
        return {"lender_app_notified": False, "lender_app_status": str(exc)}


@router.post("/upload")
async def upload_statements(
    files: list[UploadFile] = File(...),
    client_id: str = Form(default=""),
):
    if not files:
        raise HTTPException(status_code=400, detail="No files provided.")

    for f in files:
        ext = os.path.splitext(f.filename.lower())[1]
        if ext not in _ALLOWED:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {f.filename}")

    file_data = []
    for f in files:
        raw = await f.read()
        file_data.append((raw, f.filename))

    try:
        result = process_files(file_data)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

    lender_fields = {}
    if client_id:
        lender_fields = _forward_to_lender_app(client_id, result)

    return {
        "session_id": str(uuid.uuid4()),
        "client_id":  client_id,
        **result,
        **lender_fields,
    }
