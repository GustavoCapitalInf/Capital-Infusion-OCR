"""
utils/pdf_render.py
-------------------
Rasterize PDF pages to PIL images for OCR.

The original pipeline rendered pages with pdf2image, which shells out to
poppler (pdftoppm).  Poppler is an external binary that must be installed
separately and pointed to via POPPLER_PATH — a per-machine hardcoded path that
breaks on any deployment where poppler is missing, causing scanned PDFs to
yield no text and every downstream metric to come out 0.

This helper prefers PyMuPDF (the ``fitz`` package), a pip-installable wheel
that bundles its own renderer and needs no external binary, and falls back to
pdf2image/poppler only when PyMuPDF is unavailable.  That makes scanned-PDF OCR
work out of the box on machines without poppler.
"""

from __future__ import annotations

import io


def pdf_to_images(raw_bytes: bytes, dpi: int = 300, poppler_path: str | None = None):
    """
    Convert PDF bytes to a list of PIL.Image pages.

    Tries PyMuPDF first (no external dependency), then pdf2image with the
    given *poppler_path*, then pdf2image relying on poppler being on PATH.
    Returns an empty list if every backend fails.
    """
    # ── Backend 1 — PyMuPDF (no poppler needed) ─────────────────────────────
    try:
        import fitz  # PyMuPDF
        from PIL import Image

        images = []
        with fitz.open(stream=raw_bytes, filetype="pdf") as doc:
            for page in doc:
                pix = page.get_pixmap(dpi=dpi)
                images.append(Image.open(io.BytesIO(pix.tobytes("png"))).convert("RGB"))
        if images:
            return images
    except Exception as exc:  # noqa: BLE001
        print(f"[pdf_to_images] PyMuPDF failed: {exc}")

    # ── Backend 2/3 — pdf2image + poppler ───────────────────────────────────
    try:
        from pdf2image import convert_from_bytes
        if poppler_path:
            try:
                return convert_from_bytes(raw_bytes, dpi=dpi, poppler_path=poppler_path)
            except Exception as exc:  # noqa: BLE001
                print(f"[pdf_to_images] pdf2image(poppler_path) failed: {exc}")
        return convert_from_bytes(raw_bytes, dpi=dpi)  # poppler on PATH
    except Exception as exc:  # noqa: BLE001
        print(f"[pdf_to_images] pdf2image failed: {exc}")

    return []
