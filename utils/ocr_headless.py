"""
utils/ocr_headless.py
---------------------
Streamlit-free OCR extraction for use in Flask API contexts.
Same three-tier pipeline as utils/ocr.py:
  pdfplumber (digital) → EasyOCR (scanned) → Tesseract (fallback)
"""

from __future__ import annotations

import io

import cv2
import numpy as np
import pdfplumber
import pytesseract
from pdf2image import convert_from_bytes
from PIL import Image

from utils.cleaning import fix_spaced_ocr_text

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
        pages = convert_from_bytes(raw, dpi=300, poppler_path=POPPLER_PATH)
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
        pages = convert_from_bytes(raw, dpi=300, poppler_path=POPPLER_PATH)
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
