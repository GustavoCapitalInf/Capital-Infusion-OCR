"""
utils/application_ocr.py
------------------------
OCR parser for Capital Infusion signed funding applications.
Extracts specific fields from the standard single-page application PDF.
"""

import io
import re
from datetime import datetime

import pdfplumber


def _extract_text(pdf_input) -> str:
    """Pull text from page 1 of the application PDF via pdfplumber."""
    try:
        if isinstance(pdf_input, bytes):
            pdf_input = io.BytesIO(pdf_input)
        elif hasattr(pdf_input, "seek"):
            pdf_input.seek(0)

        with pdfplumber.open(pdf_input) as pdf:
            return (pdf.pages[0].extract_text() or "") if pdf.pages else ""
    except Exception as exc:
        print(f"[application_ocr] pdfplumber error: {exc}")
        return ""


def _parse_field(text: str, label: str, stop_pattern: str = None) -> str | None:
    """
    Generic label-value extractor.
    Matches  '<label>: <value>'  and stops at stop_pattern or end of line.
    """
    stop = stop_pattern or r"(?=\s{2,}[A-Z]|$)"
    pattern = rf"{re.escape(label)}\s*:?\s*(.+?)\s*{stop}"
    m = re.search(pattern, text, re.IGNORECASE)
    return m.group(1).strip() if m else None


def parse_application_text(text: str) -> dict:
    """
    Parse extracted application text and return the required fields.

    Fields returned:
      business_description     – from Business Property Information
      estimated_fico_score     – from Business Property Information (int)
      ownership_percentage     – Principle Owner's Ownership % (string, e.g. "100.00%")
      time_in_business_years   – current_year minus business start year (int)
      business_state           – 2-letter state code from business address
      business_zip             – 5-digit ZIP code from business address
    """
    result = {
        "business_description": None,
        "estimated_fico_score": None,
        "ownership_percentage": None,
        "time_in_business_years": None,
        "business_state": None,
        "business_zip": None,
    }

    # ── Business Description ─────────────────────────────────────────────────
    # Format: "Business Description: Plumbing Business  Annual Business Revenue: ..."
    m = re.search(
        r"Business Description\s*:\s*(.+?)\s+Annual Business Revenue",
        text,
        re.IGNORECASE,
    )
    if m:
        result["business_description"] = m.group(1).strip()

    # ── Estimated FICO Score ─────────────────────────────────────────────────
    # Format: "Estimated Fico Score: 680"
    m = re.search(r"Estimated Fico Score\s*:\s*(\d+)", text, re.IGNORECASE)
    if m:
        result["estimated_fico_score"] = int(m.group(1))

    # ── Principle Owner Ownership % ──────────────────────────────────────────
    # Format: "Principle Owner Name: Islam Sala  Ownership %: 100.00  Email: ..."
    # Match only the first Ownership % (Principle Owner) by anchoring to that line.
    m = re.search(
        r"Principle Owner Name\s*:.*?Ownership\s*%\s*:\s*([\d.]+)",
        text,
        re.IGNORECASE | re.DOTALL,
    )
    if m:
        result["ownership_percentage"] = m.group(1).strip() + "%"

    # ── Time in Business ─────────────────────────────────────────────────────
    # Format: "Business Start Date (MM/YYYY): 11/2022"
    m = re.search(
        r"Business Start Date\s*\(MM/YYYY\)\s*:\s*(\d{1,2}/\d{4})",
        text,
        re.IGNORECASE,
    )
    if m:
        try:
            _, start_year = m.group(1).split("/")
            result["time_in_business_years"] = datetime.now().year - int(start_year)
        except Exception:
            pass

    # ── Business State ───────────────────────────────────────────────────────
    # Format: "State: TX"
    m = re.search(r"State\s*:\s*([A-Za-z]{2})", text)
    if m:
        result["business_state"] = m.group(1).upper()

    # ── Business ZIP ─────────────────────────────────────────────────────────
    # Format: "Zip: 77001" or "Zip Code: 77001" or "ZIP: 77001-1234"
    m = re.search(
        r"\bZip(?:\s*Code)?\s*:\s*(\d{5})(?:-\d{4})?",
        text,
        re.IGNORECASE,
    )
    if m:
        result["business_zip"] = m.group(1)

    return result


def parse_signed_application(pdf_input) -> dict:
    """
    Main entry point. Accepts bytes or a file-like object.
    Returns a dict with the parsed application fields.
    """
    text = _extract_text(pdf_input)
    if not text.strip():
        return {"error": "Could not extract text from PDF"}
    return parse_application_text(text)
