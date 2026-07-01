"""
utils/orbit_notify.py
----------------------
Forwards a completed lender-suggestion job to Orbit
(https://orbit-technology.com) once qualifying lenders are known.
"""
import os

import requests

_ORBIT_URL = "https://orbit-technology.com/api/ocr/results"
_ORBIT_API_KEY = os.environ.get(
    "ORBIT_API_KEY", "orbit-api-k_9f3d7a2b1c8e4f6d0a5b7c9e2f4a6d8b"
)


def _match_score(code: str, lender_evaluations: list[dict]) -> float | None:
    for evaluation in lender_evaluations:
        if evaluation.get("code") == code:
            criteria = evaluation.get("criteria", [])
            if not criteria:
                return None
            passed = sum(1 for c in criteria if c.get("result") == "PASS")
            return round(passed / len(criteria) * 100)
    return None


def notify_orbit(client_id: str, job_data: dict) -> dict:
    """POST a completed lender-suggestion job to Orbit.

    No-op (returns {}) unless the job is complete with qualifying lenders.
    Never raises: network/JSON failures are reported via the returned dict.
    """
    if job_data.get("status") != "complete":
        return {}
    qualifying_lenders = job_data.get("qualifying_lenders") or []
    if not qualifying_lenders:
        return {}

    lender_evaluations = job_data.get("lender_evaluations", [])
    matched_lenders = [
        {
            "lender": lender.get("full_name"),
            "match_score": _match_score(lender.get("code"), lender_evaluations),
            "reason": lender.get("summary"),
        }
        for lender in qualifying_lenders
    ]

    payload = {
        "clientId": client_id,
        "analyzedAt": job_data.get("timestamp"),
        "matched_lenders": matched_lenders,
        "results": {
            "summary": {
                "applicant": job_data.get("applicant", {}),
                "bank_statement_metrics": job_data.get("bank_statement_metrics", {}),
            },
            "lenders": lender_evaluations,
        },
    }

    try:
        resp = requests.post(
            _ORBIT_URL,
            json=payload,
            headers={"x-api-key": _ORBIT_API_KEY},
            timeout=10,
        )
        return {"orbit_notified": resp.ok, "orbit_status": resp.status_code}
    except Exception as exc:
        return {"orbit_notified": False, "orbit_status": str(exc)}
