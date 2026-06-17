"""
utils/ocr.py
------------
OCR extraction pipeline for PDF and image bank statements.
Priority order: pdfplumber (digital) → EasyOCR → Tesseract fallback.
"""

import re
import streamlit as st
import numpy as np
import cv2
import pdfplumber

from langdetect import detect
from PIL import Image

from utils.cleaning import fix_spaced_ocr_text
from utils.pdf_render import pdf_to_images

# ---------------------------------------------------------------------------
# Configuration  (adjust paths per deployment environment)
# ---------------------------------------------------------------------------

import pytesseract
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
POPPLER_PATH = r"C:\Users\MohammedBharoocha\Downloads\poppler\poppler-26.02.0\Library\bin"

# ---------------------------------------------------------------------------
# EasyOCR reader (cached so it is only loaded once per Streamlit session)
# ---------------------------------------------------------------------------

@st.cache_resource
def _load_easyocr_reader():
    import easyocr
    return easyocr.Reader(["en", "fr", "es", "pt"], gpu=False)


# ---------------------------------------------------------------------------
# Image pre-processing
# ---------------------------------------------------------------------------

def preprocess_image(image) -> np.ndarray:
    """
    Enhanced OCR preprocessing for narrow / scanned bank statements.
    Improves ACH text detection without affecting parser logic.
    """

    arr = np.array(image)

    # Convert to grayscale
    gray = cv2.cvtColor(arr, cv2.COLOR_RGB2GRAY) if arr.ndim == 3 else arr

    # Upscale small / narrow statements for OCR readability
    gray = cv2.resize(
        gray,
        None,
        fx=2.5,
        fy=2.5,
        interpolation=cv2.INTER_CUBIC,
    )

    # Denoise scan artifacts
    gray = cv2.fastNlMeansDenoising(gray)

    # Sharpen text slightly
    kernel = np.array([
        [-1, -1, -1],
        [-1,  9, -1],
        [-1, -1, -1]
    ])

    gray = cv2.filter2D(gray, -1, kernel)

    # Adaptive threshold for faint ACH text
    thresh = cv2.adaptiveThreshold(
        gray,
        255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        31,
        11,
    )

    return thresh


# ---------------------------------------------------------------------------
# Single-engine extractors
# ---------------------------------------------------------------------------

def _extract_pdfplumber(uploaded_file) -> str:
    text = ""
    try:
        uploaded_file.seek(0)
        with pdfplumber.open(uploaded_file) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception as exc:
        print(f"[pdfplumber] {exc}")
    return text


def _extract_easyocr_pdf(uploaded_file) -> str:
    reader = _load_easyocr_reader()
    uploaded_file.seek(0)
    pages = pdf_to_images(uploaded_file.read(), dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    bar = st.progress(0)
    for i, page in enumerate(pages):
        processed = preprocess_image(page)
        results = reader.readtext(processed, detail=0, paragraph=True)
        full_text += "\n".join(results) + "\n"
        bar.progress((i + 1) / len(pages))
    return full_text


def _extract_tesseract_pdf(uploaded_file) -> str:
    uploaded_file.seek(0)
    pages = pdf_to_images(uploaded_file.read(), dpi=300, poppler_path=POPPLER_PATH)
    full_text = ""
    bar = st.progress(0)
    for i, page in enumerate(pages):
        full_text += pytesseract.image_to_string(page) + "\n"
        bar.progress((i + 1) / len(pages))
    return full_text


def _extract_easyocr_image(uploaded_file) -> str:
    reader = _load_easyocr_reader()
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    processed = preprocess_image(image)
    results = reader.readtext(processed, detail=0, paragraph=True)
    return "\n".join(results)


def _extract_tesseract_image(uploaded_file) -> str:
    uploaded_file.seek(0)
    image = Image.open(uploaded_file)
    return pytesseract.image_to_string(image)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_text_from_pdf(uploaded_file, debug_mode: bool = False) -> str:
    """
    Extract text from a PDF file using a three-tier fallback:
      1. pdfplumber  (digital/selectable text)
      2. EasyOCR     (scanned)
      3. Tesseract   (last resort)
    """
    with st.status("Extracting PDF text…", expanded=False) as status:

        # Tier 1 — digital PDF
        text = _extract_pdfplumber(uploaded_file)
        if len(text.strip()) >= 500:
            status.update(label="Digital PDF extracted successfully", state="complete")
            return fix_spaced_ocr_text(text)

        # Tier 2 — EasyOCR
        status.update(label="Attempting EasyOCR…", state="running")
        try:
            text = _extract_easyocr_pdf(uploaded_file)
            if len(text.strip()) >= 300:
                status.update(label="EasyOCR extraction successful", state="complete")
                return fix_spaced_ocr_text(text)
        except Exception as exc:
            print(f"[EasyOCR PDF] {exc}")

        # Tier 3 — Tesseract
        status.update(label="Using Tesseract fallback…", state="running")
        text = _extract_tesseract_pdf(uploaded_file)
        status.update(label="Extraction complete", state="complete")
        return fix_spaced_ocr_text(text)


def extract_text_from_image(uploaded_file) -> str:
    """
    Extract text from a PNG/JPG image with EasyOCR → Tesseract fallback.
    """
    with st.status("Extracting image text…", expanded=False) as status:
        try:
            text = _extract_easyocr_image(uploaded_file)
            if len(text.strip()) >= 100:
                status.update(label="EasyOCR extraction successful", state="complete")
                return fix_spaced_ocr_text(text)
        except Exception as exc:
            print(f"[EasyOCR image] {exc}")

        status.update(label="Using Tesseract fallback…", state="running")
        text = _extract_tesseract_image(uploaded_file)
        status.update(label="Extraction complete", state="complete")
        return fix_spaced_ocr_text(text)


def translate_to_english(text: str) -> str:
    """
    Auto-detect and translate non-English statement text to English.
    Chunked to stay within API limits.
    """
    try:
        from deep_translator import GoogleTranslator
        if not text or not str(text).strip():
            return text
        text = str(text)
        chunk_size = 4_500
        chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]
        translated = [
            GoogleTranslator(source="auto", target="en").translate(c)
            for c in chunks
        ]
        return "\n".join(translated)
    except Exception as exc:
        print(f"[Translation] {exc}")
        return text
