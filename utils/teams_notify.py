# Teams notification

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

URL = "https://default87067de17bff468994aa610cdb27ba.92.environment.api.powerplatform.com:443/powerautomate/automations/direct/workflows/b449ad98e06b4e4487c9d3d209c9c98e/triggers/manual/paths/invoke?api-version=1&sp=%2Ftriggers%2Fmanual%2Frun&sv=1.0&sig=k2Q0trEDG7vw9f6nvkdETz0qsRH0LhfiW_QzNwm_b-g"

def _extract_sales_rep(client_id: str) -> str:
    if not client_id: 
        return "unkown"
    return client_id.split("-")[0].strip() or "unknown"


def notify_teams(filename: str, client_id: str, results: dict) -> bool:
    url = os.getenv("POWER_AUTOMATE_URL", "") or URL

    sales_rep = _extract_sales_rep(client_id)

    payload = {
        "filename":          filename,
        "client_id":         client_id,
        "sales_rep":         sales_rep,
        "credits":           results.get("credits", 0),
        "debits":            results.get("debits", 0),
        "lender_debits":     results.get("lender_debits", 0),
        "withholding_rate":  results.get("withholding_rate", 0),
        "nsf_count":         results.get("nsf_count", 0),
        "pos_count":         results.get("pos_count", 0),
        "avg_daily_balance": results.get("avg_daily_balance", 0),
        "cash_flow":         results.get("cash_flow", 0),
        "lender_list":       ", ".join(results.get("lender_list", [])) or "None",
        "analyzed_at":       datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code in (200, 202):
            logger.info("Teams notification sent (HTTP %d)", resp.status_code)
            return True
        else:
            logger.error("Teams notification failed (HTTP %d): %s", resp.status_code, resp.text)
            return False
    except Exception as exc:
        logger.error("Teams notification error: %s", exc)
        return False
