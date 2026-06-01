import io
import json

import pandas as pd
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

router = APIRouter()


@router.post("/export/csv")
async def export_csv(payload: dict):
    statements = payload.get("statements", [])
    df = pd.DataFrame(statements)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orbit_statements.csv"},
    )


@router.post("/export/transactions")
async def export_transactions(payload: dict):
    transactions = payload.get("transactions", [])
    df = pd.DataFrame(transactions)
    buf = io.StringIO()
    df.to_csv(buf, index=False)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=orbit_transactions.csv"},
    )


@router.post("/export/json")
async def export_json(payload: dict):
    content = json.dumps(payload, indent=2, default=str)
    return StreamingResponse(
        iter([content]),
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=orbit_export.json"},
    )
