"""
banks/regions.py
----------------
Regions Bank statement parser (LifeGreen Checking and similar).

Detected by: "Regions Bank" / "LIFEGREEN" / "regions.com" in text.

Regions statements are image-only (scanned) PDFs, so the production pipeline
reads them with EasyOCR.  EasyOCR groups the page into column "paragraphs",
which means the SUMMARY labels, the transaction dates, the descriptions and
the dollar amounts each land on **separate lines** instead of one row per
transaction.  EasyOCR also frequently misreads a leading "$" as an "8"
(e.g. "$29,566.71" → "829,566.71", "$8.00" → "88.00").

Summary layout (LifeGreen Checking):
    SUMMARY
    Beginning Balance      $86,739.72
    Deposits & Credits     $29,566.71 +
    Withdrawals            $509.59    -
    Fees                   $8.00      -
    Automatic Transfers    $0.00      +
    Checks                 $0.00      -
    Ending Balance         $115,788.84

Credits  = Deposits & Credits
Debits   = Withdrawals + Fees + Checks

Two extraction strategies are tried, in order:
  1. Clean labelled lines ("Deposits & Credits $29,566.71") — works on the
     Tesseract / digital-PDF layout where label and amount stay together.
  2. Section-sum — sum the individual transaction amounts inside each
     ALL-CAPS section ("DEPOSITS & CREDITS", "WITHDRAWALS", "FEES").  Because
     the individual amounts carry no "$", they are read cleanly, so summing
     them sidesteps the "$"→"8" misread that corrupts the printed totals.
     The printed section total (which IS corrupted) is detected and removed
     by checking whether a token equals the sum of the other tokens.
"""

from __future__ import annotations

import io
import re
import traceback

import pandas as pd

from banks.base import BankParser
from utils.cleaning import clean_money


_MONEY = re.compile(r"[\d,]+\.\d{2}")
_DATE = re.compile(r"\b(\d{1,2}/\d{1,2})\b")
_TOL = 0.05  # dollar tolerance for "is this token the section total?" check


def _strip_lead8(value: float) -> float | None:
    """
    Undo EasyOCR's "$"→"8" misread: a value whose integer part has a spurious
    leading "8" (the dollar sign).  "829566.71" → 29566.71, "88.00" → 8.00,
    "80.00" → 0.00, "8509.59" → 509.59.  Returns None when not applicable.
    """
    s = f"{value:.2f}"
    int_part, dec = s.split(".")
    if int_part.startswith("8") and len(int_part) > 1:
        try:
            return float(int_part[1:] + "." + dec)
        except ValueError:
            return None
    return None


def _section_sum(region: str) -> float:
    """
    Sum the individual transaction amounts in a statement section, removing
    the printed section total when it is present.

    The printed total equals the sum of the other tokens (allowing for the
    "$"→"8" misread), so we look for a single token that matches that sum and
    exclude it.  When no token matches (the total lives outside the region),
    every token is a transaction amount and we sum them all.
    """
    tokens = [clean_money(m.group(0)) for m in _MONEY.finditer(region)]
    tokens = [t for t in tokens if t > 0]
    if not tokens:
        return 0.0

    for i, tok in enumerate(tokens):
        rest_sum = sum(tokens[:i] + tokens[i + 1:])
        if rest_sum <= 0:
            continue
        tol = max(_TOL, rest_sum * 0.002)
        corrected = _strip_lead8(tok)
        if abs(tok - rest_sum) <= tol or (corrected is not None and abs(corrected - rest_sum) <= tol):
            return round(rest_sum, 2)

    return round(sum(tokens), 2)


class RegionsParser(BankParser):

    NAME = "Regions"

    # ── Identification ──────────────────────────────────────────────────────

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", str(text))
        return bool(
            re.search(
                r"REGIONS\s+BANK|LIFEGREEN|REGIONS\.COM|REGIONSMORTGAGE"
                r"|REGIONS\s+DEPOSIT|BANKING\s+WITH\s+REGIONS",
                flat,
                re.IGNORECASE,
            )
        )

    # ── Summary extraction ──────────────────────────────────────────────────

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        credits = cls._extract_credits(text)
        debits = cls._extract_debits(text)

        print(f"[Regions.extract_summary] credits={credits} debits={debits}")
        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }

    # -- credits -------------------------------------------------------------

    @classmethod
    def _extract_credits(cls, text: str) -> float:
        flat = cls._flatten(text)

        # Strategy 1 — clean labelled line ("Deposits & Credits $29,566.71").
        # Anchored so "Total Deposits & Credits" matches too (same value).
        m = re.search(
            r"Deposits\s*&?\s*Credits\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        if m:
            return abs(clean_money(m.group(1)))

        # Strategy 2 — section-sum over the ALL-CAPS "DEPOSITS & CREDITS"
        # block (case-sensitive so the Title-Case summary label is ignored).
        region = cls._section_region(
            text,
            start_pat=r"DEPOSITS\s*&?\s*CREDITS",
            end_pat=r"Total\s+Deposits|WITHDRAWALS|\Z",
        )
        if region:
            return _section_sum(region)
        return 0.0

    # -- debits --------------------------------------------------------------

    @classmethod
    def _extract_debits(cls, text: str) -> float:
        flat = cls._flatten(text)

        withdrawals = fees = checks = 0.0

        # Strategy 1 — clean labelled summary lines.  Exclude "Total
        # Withdrawals", whose printed amount carries the "$"→"8" misread under
        # EasyOCR ("8509.59"); that case is handled correctly by section-sum.
        wm = re.search(
            r"(?<![A-Za-z])(?<!Total\s)Withdrawals\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        fm = re.search(
            r"(?<![A-Za-z])Fees\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        cm = re.search(
            r"(?<![A-Za-z])Checks\s+\$?\s*([\d,]+\.\d{2})",
            flat, re.IGNORECASE,
        )
        if wm:
            withdrawals = abs(clean_money(wm.group(1)))
        if fm:
            fees = abs(clean_money(fm.group(1)))
        if cm:
            checks = abs(clean_money(cm.group(1)))

        if withdrawals > 0:
            return round(withdrawals + fees + checks, 2)

        # Strategy 2 — section-sum over the ALL-CAPS sections.
        wd_region = cls._section_region(
            text,
            start_pat=r"WITHDRAWALS",
            end_pat=r"Total\s+Withdrawals|\bFEES\b|\Z",
            after_pat=r"DEPOSITS\s*&?\s*CREDITS",
        )
        withdrawals = _section_sum(wd_region) if wd_region else 0.0

        # Fees: the "Monthly Fee" amount (the "Total ... Fees" footer rows are
        # all 0.00 and harmless, but pin to Monthly Fee to be safe).
        fm2 = re.search(r"Monthly\s+Fee\s+\$?\s*([\d,]+\.\d{2})", flat, re.IGNORECASE)
        if fm2:
            fees = abs(clean_money(fm2.group(1)))
        else:
            fee_region = cls._section_region(
                text, start_pat=r"\bFEES\b",
                end_pat=r"Total\s+Overdraft|Total\s+Returned|\Z",
            )
            fees = _section_sum(fee_region) if fee_region else 0.0

        return round(withdrawals + fees + checks, 2)

    # -- region helper -------------------------------------------------------

    @classmethod
    def _section_region(
        cls,
        text: str,
        start_pat: str,
        end_pat: str,
        after_pat: str | None = None,
        end_ignorecase: bool = True,
    ) -> str:
        """
        Return the flattened text between the first case-sensitive match of
        *start_pat* (the ALL-CAPS section header) and the next match of
        *end_pat*.  When *after_pat* is given, the search for *start_pat*
        begins only after that pattern (used to skip the summary block).

        *end_ignorecase* — set False when the end marker is itself an ALL-CAPS
        section header that must not match a Title-Case summary label of the
        same words (e.g. ending the SUMMARY block at "DEPOSITS & CREDITS").
        """
        flat = cls._flatten(text)

        offset = 0
        if after_pat:
            am = re.search(after_pat, flat)  # case-sensitive: ALL-CAPS header
            if am:
                offset = am.end()

        sm = re.search(start_pat, flat[offset:])  # case-sensitive
        if not sm:
            return ""
        start = offset + sm.end()

        em = re.search(end_pat, flat[start:], re.IGNORECASE if end_ignorecase else 0)
        end = start + em.start() if em else len(flat)
        return flat[start:end]

    # ── Average daily balance (estimate) ────────────────────────────────────

    @classmethod
    def estimate_avg_balance(cls, text: str) -> float:
        """
        Regions does not print an average daily balance, and the transaction
        rows carry no running balance, so estimate it as the midpoint of the
        Beginning and Ending balances.

        The SUMMARY block always lists Beginning Balance first and Ending
        Balance last, so the first and last money tokens inside that block are
        those two figures — and both are read cleanly (no "$"→"8" misread)
        even under EasyOCR, which separates the labels from their values.
        """
        region = cls._section_region(
            text, start_pat=r"SUMMARY", end_pat=r"DEPOSITS\s*&?\s*CREDITS|\Z",
            end_ignorecase=False,
        )
        tokens = [clean_money(m.group(0)) for m in _MONEY.finditer(region)]
        tokens = [t for t in tokens if t > 0]
        if len(tokens) >= 2:
            return round((tokens[0] + tokens[-1]) / 2, 2)
        if tokens:
            return round(tokens[0], 2)
        return 0.0

    # ── Transaction extraction ──────────────────────────────────────────────

    # Section headers (ALL-CAPS) → transaction direction.
    _CREDIT_HEADER = re.compile(r"^DEPOSITS\s*&?\s*CREDITS\b")
    _DEBIT_HEADER = re.compile(r"^(WITHDRAWALS|FEES)\b")
    # Box-level header detection is per-word, so tolerate EasyOCR splitting
    # "DEPOSITS & CREDITS" into separate boxes — a lone ALL-CAPS "DEPOSITS"
    # only ever starts the credits section (the summary label and section
    # total print it Title-Case as "Deposits").
    _BOX_CREDIT_HDR = re.compile(r"^DEPOSITS\b")
    _BOX_DEBIT_HDR = re.compile(r"^(WITHDRAWALS|FEES)\b")
    _STOP_ROW = re.compile(
        r"^Total\s+(Deposits|Withdrawals|Overdraft|Returned|For\s+This|Calendar)",
        re.IGNORECASE,
    )
    # A clean one-line transaction: "MM/DD  description  amount"
    _TX_LINE = re.compile(
        r"^(\d{1,2}/\d{1,2})\s+(.+?)\s+\$?(-?[\d,]+\.\d{2})\s*$"
    )

    @classmethod
    def parse_transactions(cls, raw_bytes_or_text) -> pd.DataFrame:
        """
        Extract transaction rows.

        1. If given OCR text with clean one-line transactions (digital PDF or
           Tesseract), parse those directly.
        2. Otherwise (image PDF read by EasyOCR's column-grouped output), fall
           back to word-box reconstruction so dates, descriptions and amounts
           are re-joined into real rows.
        """
        # Caller may pass raw PDF bytes or already-extracted text.
        text = ""
        raw_bytes = None
        if isinstance(raw_bytes_or_text, (bytes, bytearray)):
            raw_bytes = bytes(raw_bytes_or_text)
        elif hasattr(raw_bytes_or_text, "read"):
            try:
                raw_bytes_or_text.seek(0)
            except Exception:
                pass
            raw_bytes = raw_bytes_or_text.read()
        else:
            text = str(raw_bytes_or_text or "")

        rows: list[dict] = []
        if text:
            rows = cls._parse_clean_lines(text)

        if not rows and raw_bytes is not None:
            rows = cls._parse_clean_lines(_text_from_pdf(raw_bytes))
            if not rows:
                rows = cls._parse_via_boxes(raw_bytes)

        print(f"[Regions.parse_transactions] {len(rows)} rows")
        return pd.DataFrame(rows)

    # -- strategy 1: clean one-line transactions -----------------------------

    @classmethod
    def _parse_clean_lines(cls, text: str) -> list[dict]:
        rows: list[dict] = []
        section = ""  # "Credit" | "Debit" | ""
        for raw in str(text).split("\n"):
            line = re.sub(r"[ \t]+", " ", raw).strip()
            if not line:
                continue

            if cls._CREDIT_HEADER.match(line):
                section = "Credit"
                continue
            if cls._DEBIT_HEADER.match(line):
                section = "Debit"
                continue
            if cls._STOP_ROW.match(line):
                continue
            if not section:
                continue

            m = cls._TX_LINE.match(line)
            if not m:
                continue
            amount = abs(clean_money(m.group(3)))
            if amount <= 0:
                continue
            desc = m.group(2).strip()
            if section == "Credit":
                rows.append(cls._row(m.group(1), desc, 0.0, amount, "Credit"))
            else:
                rows.append(cls._row(m.group(1), desc, amount, 0.0, "Debit"))
        return rows

    # -- strategy 2: EasyOCR word-box reconstruction -------------------------

    @classmethod
    def _parse_via_boxes(cls, raw_bytes: bytes) -> list[dict]:
        """
        Re-OCR the image pages with EasyOCR bounding boxes (detail=1) and
        re-cluster word boxes by y-position into real transaction rows.
        """
        try:
            from utils.ocr_headless import _get_easyocr_reader, _preprocess, POPPLER_PATH
            from utils.pdf_render import pdf_to_images
            pages = pdf_to_images(raw_bytes, dpi=300, poppler_path=POPPLER_PATH)
        except Exception:
            print("[Regions._parse_via_boxes] rasterization failed")
            print(traceback.format_exc())
            return []
        if not pages:
            return []

        rows: list[dict] = []
        try:
            reader = _get_easyocr_reader()
            section = ""
            for page in pages:
                results = reader.readtext(_preprocess(page), detail=1, paragraph=False)
                page_rows, section = cls.rows_from_boxes(results, section)
                rows.extend(page_rows)
        except Exception:
            print(traceback.format_exc())
        return rows

    # Matches a standalone MM/DD transaction date (the left-column anchor).
    _DATE_ONLY = re.compile(r"^\d{1,2}/\d{1,2}$")

    @classmethod
    def rows_from_boxes(cls, results: list, section: str = "") -> tuple[list[dict], str]:
        """
        Reconstruct transaction rows from EasyOCR detail=1 word boxes.

        *results* is a list of (bbox, text, conf) where bbox is four (x, y)
        corner points.  EasyOCR returns one box per word, so a transaction's
        date, description and amount arrive as separate boxes that share
        roughly the same vertical centre.  Regions packs rows tightly (the row
        pitch is barely larger than the line height), so instead of bucketing
        by y we anchor on the left-column MM/DD date that begins every row and
        attach each remaining word to its nearest date anchor.

        The current credit/debit *section* is tracked from the ALL-CAPS header
        boxes ("DEPOSITS & CREDITS" → credit, "WITHDRAWALS"/"FEES" → debit) and
        returned so it carries across page boundaries.

        Returns (rows, ending_section).
        """
        words = []
        for item in results:
            try:
                bbox, txt, _conf = item
            except (ValueError, TypeError):
                continue
            txt = str(txt).strip()
            if not txt:
                continue
            ys = [p[1] for p in bbox]
            xs = [p[0] for p in bbox]
            words.append({
                "text": txt,
                "yc": (min(ys) + max(ys)) / 2,
                "x0": min(xs),
            })
        if not words:
            return [], section

        page_w = max(w["x0"] for w in words) or 1.0
        left_max_x = page_w * 0.30

        # Header events (yc → new section) and date anchors (left-column MM/DD).
        headers: list[tuple[float, str]] = []
        dates: list[dict] = []
        for w in words:
            if cls._BOX_CREDIT_HDR.match(w["text"]):
                headers.append((w["yc"], "Credit"))
            elif cls._BOX_DEBIT_HDR.match(w["text"]):
                headers.append((w["yc"], "Debit"))
            elif cls._DATE_ONLY.match(w["text"]) and w["x0"] <= left_max_x:
                dates.append(w)
        headers.sort(key=lambda h: h[0])
        dates.sort(key=lambda d: d["yc"])
        if not dates:
            return [], (headers[-1][1] if headers else section)

        # Row pitch → how far a word may sit from its date and still belong to it.
        if len(dates) >= 2:
            gaps = sorted(dates[i + 1]["yc"] - dates[i]["yc"] for i in range(len(dates) - 1))
            pitch = gaps[len(gaps) // 2]
        else:
            pitch = 40.0
        max_gap = max(pitch * 0.6, 18.0)

        def _section_for(yc: float) -> str:
            sec = section
            for hy, hs in headers:
                if hy <= yc:
                    sec = hs
                else:
                    break
            return sec

        # Bucket every non-date word onto its nearest date anchor.
        buckets: dict[int, list[dict]] = {i: [] for i in range(len(dates))}
        for w in words:
            if cls._DATE_ONLY.match(w["text"]) and w["x0"] <= left_max_x:
                continue
            nearest = min(range(len(dates)), key=lambda i: abs(dates[i]["yc"] - w["yc"]))
            if abs(dates[nearest]["yc"] - w["yc"]) <= max_gap:
                buckets[nearest].append(w)

        rows: list[dict] = []
        for i, d in enumerate(dates):
            sec = _section_for(d["yc"])
            if not sec:
                continue
            parts = sorted(buckets[i], key=lambda w: w["x0"])
            line = " ".join(w["text"] for w in parts).strip()
            if cls._STOP_ROW.match(line):
                continue
            amts = _MONEY.findall(line)
            if not amts:
                continue
            amount = abs(clean_money(amts[-1]))
            if amount <= 0:
                continue

            desc = line[:line.rfind(amts[-1])] if amts[-1] in line else line
            desc = re.sub(r"\s+", " ", desc).strip()

            if sec == "Credit":
                rows.append(cls._row(d["text"], desc, 0.0, amount, "Credit"))
            else:
                rows.append(cls._row(d["text"], desc, amount, 0.0, "Debit"))

        ending_section = headers[-1][1] if headers else section
        return rows, ending_section

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _row(date: str, desc: str, debit: float, credit: float, section: str) -> dict:
        return {
            "Date": date,
            "Description": desc,
            "Debit": round(debit, 2),
            "Credit": round(credit, 2),
            "Amount": round(credit - debit, 2),
            "Balance": 0.0,
            "Section": section,
        }


def _text_from_pdf(raw_bytes: bytes) -> str:
    """Best-effort selectable-text extraction (empty for scanned PDFs)."""
    try:
        import pdfplumber
        out = []
        with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
            for page in pdf.pages:
                out.append(page.extract_text() or "")
        return "\n".join(out)
    except Exception:
        return ""
