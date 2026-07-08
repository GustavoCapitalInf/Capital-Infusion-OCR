# Orbit Results Notification — Design

## Problem

After the lender-suggestion service finishes analyzing a client (bank statement
metrics + signed application), `application_api.py` fetches the job result from
`{LENDER_APP_URL}/job/{client_id}` in two places:

- `parse_bank_statement()` (after forwarding bank-statement summary metrics)
- `parse_application()` (after forwarding parsed application fields)

Today that job result (`lender_suggestion`) is only returned to whatever
caller hit our API — nothing pushes it onward. Orbit (a separate external
system, `orbit-technology.com`) needs to be notified with the client's matched
lenders and underlying results whenever a job finishes.

## Job response shape (reference)

The job endpoint returns (relevant fields only):

```json
{
  "clientCode": "622900001",
  "status": "complete",
  "timestamp": "2026-07-01T19:52:33.196182+00:00",
  "applicant": { "monthly_revenue": 43703.11, "fico": 680, "...": "..." },
  "bank_statement_metrics": { "nsf_count": 12, "avg_daily_balance": 3752.13, "...": "..." },
  "lender_evaluations": [
    {
      "code": "Fund So Fast",
      "full_name": "Fund So Fast",
      "overall": "QUALIFIES",
      "criteria": [ { "name": "...", "result": "PASS" }, "..." ],
      "notes": "..."
    }
  ],
  "qualifying_lenders": [
    {
      "rank": 1,
      "code": "Fund So Fast",
      "full_name": "Fund So Fast",
      "summary": "Fund So Fast is an excellent fit ...",
      "contact": "...",
      "submission_email": "..."
    }
  ]
}
```

`status` may be `"pending"` if the job hasn't finished — `qualifying_lenders`
will be absent/empty in that case.

## Design

### New module: `utils/orbit_notify.py`

```python
def notify_orbit(client_id: str, job_data: dict) -> dict:
    """POST job results to Orbit once the lender-suggestion job is complete.

    No-op (returns {}) unless job_data["status"] == "complete" and
    qualifying_lenders is non-empty. Never raises — failures are reported
    back via the returned dict, mirroring the lender_app_notified pattern.
    """
```

**Gate:** skip (return `{}`) unless `job_data.get("status") == "complete"` and
`job_data.get("qualifying_lenders")` is truthy.

**matched_lenders:** one entry per item in `qualifying_lenders`, cross-referenced
against `lender_evaluations` by `code`:

| Orbit field   | Source |
|---------------|--------|
| `lender`      | `full_name` |
| `match_score` | `round(pass_count / total_criteria * 100)` from that lender's `criteria` list in `lender_evaluations` (`result == "PASS"`); `None` if no matching evaluation is found |
| `reason`      | `summary` |

**results:**

- `results.summary` = `{"applicant": job_data.get("applicant", {}), "bank_statement_metrics": job_data.get("bank_statement_metrics", {})}`
- `results.lenders` = `job_data.get("lender_evaluations", [])` (unfiltered, full criteria detail)

**Request:**

```
POST https://orbit-technology.com/api/ocr/results
Header: x-api-key: <ORBIT_API_KEY env var, default "orbit-api-k_9f3d7a2b1c8e4f6d0a5b7c9e2f4a6d8b">
Body: {
  "clientId": client_id,
  "analyzedAt": job_data["timestamp"],
  "matched_lenders": [...],
  "results": { "summary": {...}, "lenders": [...] }
}
timeout=10
```

Wrapped in try/except; returns `{"orbit_notified": bool, "orbit_status": <code or error str>}`
to be merged into the caller's JSON response, same convention as the existing
`lender_app_notified` / `lender_app_status` fields.

### Call sites (`application_api.py`)

In both `parse_bank_statement()` and `parse_application()`, immediately after
the existing `jr.json()` / `job_resp.json()` fetch succeeds, call
`notify_orbit(client_id, <job data>)` and merge the returned dict into the
response payload.

## Error handling

- Any network/JSON error inside `notify_orbit` is caught; the function returns
  `{"orbit_notified": False, "orbit_status": str(exc)}` and never raises.
- If the job isn't `"complete"` yet, `notify_orbit` returns `{}` and nothing is
  added to the response (no `orbit_notified` key at all) — distinguishes
  "not attempted" from "attempted and failed".

## Testing

- Unit tests for `notify_orbit` using a mocked `requests.post`:
  - `status != "complete"` → no HTTP call, returns `{}`
  - `status == "complete"` with `qualifying_lenders` → builds correct
    `matched_lenders` (score computed from criteria pass-rate) and posts the
    expected payload/headers
  - HTTP failure / exception → returns `orbit_notified: False` without raising
- Manual check: hit `/parse-bank-statement` or `/parse-application` locally
  with a `client_id` whose job is already `"complete"` on the lender-suggestion
  service, confirm `orbit_notified`/`orbit_status` show up in the response.

## Out of scope

- `app.py` (Streamlit) and `backend/api/upload.py` (FastAPI) are not touched —
  only `application_api.py` gets this integration.
- No retry/queueing if the Orbit POST fails; it's fire-and-forget like the
  existing lender-app forwarding.
