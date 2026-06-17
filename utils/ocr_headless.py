"""
utils/ocr_headless.py
---------------------
Streamlit-free OCR extraction for use in Flask API contexts.
Same three-tier pipeline as utils/ocr.py:
  pdfplumber (digital) → EasyOCR (scanned) → Tesseract (fallback)
"""

from __future__ import annotations

import io
import re
from collections import defaultdict

import cv2
import numpy as np
import pandas as pd
import pdfplumber
import pytesseract
from PIL import Image

from utils.cleaning import clean_money, fix_spaced_ocr_text
from utils.pdf_render import pdf_to_images

pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\Users\MohammedBharoocha\Downloads\poppler\poppler-26.02.0\Library\bin"

# Module-level singleton so EasyOCR model loads only once per process
_easyocr_reader = None


def _get_easyocr_reader():
    global _easyocr_reader
    if _easyocr_reader is None:
        import easyocr
        _easyocr_reader = easyocr.Reader(["en", "fr", "es"], gpu=False)
    return _easyocr_reader


def _preprocess(image) -> np.ndarray:
    arr = np.array(image)
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr
    gray = cv2.fastNlMeansDenoising(gray)
    return cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 31, 2
    )


def _to_bytes(file_obj) -> bytes:
    if isinstance(file_obj, (bytes, bytearray)):
        return bytes(file_obj)
    if hasattr(file_obj, "seek"):
        file_obj.seek(0)
    return file_obj.read()


def extract_text_from_pdf(file_obj) -> str:
    raw = _to_bytes(file_obj)

    # Tier 1 — pdfplumber (digital/selectable text)
    text = ""
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as exc:
        print(f"[pdfplumber] {exc}")
    if len(text.strip()) >= 500:
        return fix_spaced_ocr_text(text)

    # Tier 2 — EasyOCR (scanned)
    try:
        reader = _get_easyocr_reader()
        pages = pdf_to_images(raw, dpi=300, poppler_path=POPPLER_PATH)
        full_text = ""
        for page in pages:
            results = reader.readtext(_preprocess(page), detail=0, paragraph=True)
            full_text += "\n".join(results) + "\n"
        if len(full_text.strip()) >= 300:
            return fix_spaced_ocr_text(full_text)
    except Exception as exc:
        print(f"[EasyOCR PDF] {exc}")

    # Tier 3 — Tesseract
    try:
        pages = pdf_to_images(raw, dpi=300, poppler_path=POPPLER_PATH)
        full_text = "".join(pytesseract.image_to_string(page) + "\n" for page in pages)
        return fix_spaced_ocr_text(full_text)
    except Exception as exc:
        print(f"[Tesseract PDF] {exc}")
        return ""


def extract_text_from_image(file_obj) -> str:
    raw = _to_bytes(file_obj)
    image = Image.open(io.BytesIO(raw))

    # Tier 1 — EasyOCR
    try:
        reader = _get_easyocr_reader()
        results = reader.readtext(_preprocess(image), detail=0, paragraph=True)
        text = "\n".join(results)
        if len(text.strip()) >= 100:
            return fix_spaced_ocr_text(text)
    except Exception as exc:
        print(f"[EasyOCR image] {exc}")

    # Tier 2 — Tesseract
    return fix_spaced_ocr_text(pytesseract.image_to_string(image))


_DATE_RE  = re.compile(r"^\d{1,2}/\d{1,2}", re.IGNORECASE)
_MONEY_RE = re.compile(r"^-?\$?[\d,]+\.\d{2}$")


def extract_columnar_transactions_from_pdf(raw_bytes: bytes) -> pd.DataFrame:
    """
    Column-aware transaction extractor for tabular bank statements (Wells Fargo etc.)
    where Credit and Debit amounts live in separate columns on the same page.

    Uses pdfplumber extract_words() x-coordinates to determine which column
    each dollar amount falls in, then assigns it to Credit or Debit accordingly.
    Falls back gracefully — returns an empty DataFrame if the PDF is scanned
    or the column headers cannot be located.
    """
    all_rows: list[dict] = []

    try:
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                words = page.extract_words(x_tolerance=3, y_tolerance=3)
                if not words:
                    continue

                # Search top 40 % of page for column-header landmark words
                header_zone_y = page.height * 0.40
                credit_col_x = debit_col_x = None

                for w in words:
                    if w["top"] > header_zone_y:
                        continue
                    txt = w["text"].upper()
                    if "DEPOSIT" in txt and credit_col_x is None:
                        credit_col_x = (w["x0"] + w["x1"]) / 2
                    if ("WITHDRAWAL" in txt or ("CHECK" in txt and "DEBIT" in txt)) \
                            and debit_col_x is None:
                        debit_col_x = (w["x0"] + w["x1"]) / 2

                if credit_col_x is None or debit_col_x is None:
                    continue

                # Voronoi boundary between the two column centres
                threshold = (credit_col_x + debit_col_x) / 2

                # Group words into rows by y-position (4-point bucket)
                by_y: dict[int, list] = defaultdict(list)
                for w in words:
                    by_y[round(w["top"] / 4) * 4].append(w)

                for y_key in sorted(by_y):
                    line = sorted(by_y[y_key], key=lambda w: w["x0"])
                    if not line or not _DATE_RE.match(line[0]["text"]):
                        continue

                    date = line[0]["text"]
                    desc_parts: list[str] = []
                    amounts: list[tuple[float, float]] = []  # (value, center_x)

                    for w in line[1:]:
                        if _MONEY_RE.match(w["text"]):
                            try:
                                val = clean_money(w["text"])
                                if val != 0:
                                    cx = (w["x0"] + w["x1"]) / 2
                                    amounts.append((val, cx))
                                    continue
                            except Exception:
                                pass
                        desc_parts.append(w["text"])

                    if not amounts:
                        continue

                    description = " ".join(desc_parts)

                    # If multiple amounts: leftmost = transaction, rightmost = running balance
                    amounts_by_x = sorted(amounts, key=lambda a: a[1])
                    tx_val, tx_x = amounts_by_x[0]
                    balance = amounts_by_x[-1][0] if len(amounts_by_x) >= 2 else 0.0

                    if tx_x < threshold:
                        credit, debit = abs(tx_val), 0.0
                    else:
                        credit, debit = 0.0, abs(tx_val)

                    all_rows.append({
                        "Date":        date,
                        "Description": description,
                        "Debit":       round(debit, 2),
                        "Credit":      round(credit, 2),
                        "Amount":      round(credit - debit, 2),
                        "Balance":     round(balance, 2),
                    })

    except Exception as exc:
        print(f"[columnar PDF extraction] {exc}")

    return pd.DataFrame(all_rows)


def translate_to_english(text: str) -> str:
    """Auto-detect and translate non-English text to English. Chunked for API limits."""
    try:
        from deep_translator import GoogleTranslator
        if not text or not str(text).strip():
            return text
        text = str(text)
        chunk_size = 4_500
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        return "\n".join(GoogleTranslator(source="auto", target="en").translate(c) for c in chunks)
    except Exception as exc:
        print(f"[Translation] {exc}")
        return text
