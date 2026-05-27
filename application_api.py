"""
application_api.py
------------------
Flask API endpoint that receives a completed Capital Infusion funding
application PDF and returns parsed fields as JSON.

Usage:
    python application_api.py

POST /parse-application
    Content-Type: multipart/form-data
    Body:         file=<pdf>

Response (200):
    {
      "business_description":   "Plumbing Business",
      "estimated_fico_score":   680,
      "ownership_percentage":   "100.00%",
      "time_in_business_years": 4
    }
"""

import requests as _requests

from flask import Flask, jsonify, request

from utils.application_ocr import parse_signed_application

_LENDER_APP_URL = "https://lendersuggestion.onrender.com"

app = Flask(__name__)


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
        "client_id":             client_id,
        "estimated_fico_score":  ocr.get("estimated_fico_score"),
        "business_description":  ocr.get("business_description"),
        "ownership_percentage":  ocr.get("ownership_percentage"),
        "time_in_business_years":ocr.get("time_in_business_years"),
        "state":                 ocr.get("business_state"),
        "zip":                   ocr.get("business_zip"),
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


if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 5001))
    app.run(host="0.0.0.0", port=port, debug=False)
