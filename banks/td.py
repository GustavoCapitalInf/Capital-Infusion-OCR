"""
banks/td.py
-----------
TD Bank statement parser.

Detected by: "TD Bank" header + "Electronic Deposits" AND "Electronic Payments".

TD Bank Account Summary lists individual category subtotals, not a single
credit/debit line.  We accumulate them:

  Credits:
    Deposits (non-electronic)  $X,XXX.XX   ← was missing; now included
    Electronic Deposits        $X,XXX.XX
    Other Credits              $X,XXX.XX

  Debits (summed):
    Checks Paid                $X,XXX.XX
    Electronic Payments        $X,XXX.XX
    Other Withdrawals          $X,XXX.XX
    Service Charges            $X,XXX.XX
"""

from __future__ import annotations

import io
import re
import traceback

import pdfplumber

from banks.base import BankParser
from utils.cleaning import clean_money, fix_spaced_ocr_text


class TDParser(BankParser):

    NAME = "TD Bank"

    # Sections whose transactions are credits
    _CREDIT_SECTS = {"deposits", "electronic deposits", "other credits"}
    # Sections whose transactions are debits
    _DEBIT_SECTS = {
        "checks paid", "electronic payments",
        "other withdrawals", "service charges",
    }

    _AMOUNT_PAT = re.compile(r"([\d,]+\.\d{2})")
    _TX_DATE    = re.compile(r"^(\d{2}/\d{2})\s?")   # \s? — date may butt up against desc

    # Boundary detectors — \s* handles compressed PDFs where spaces are stripped
    _ACT_START = re.compile(r"DAILY\s*ACCOUNT\s*ACTIVITY", re.IGNORECASE)
    _ACT_END   = re.compile(
        r"DAILY\s*BALANCE\s*SUMMARY|HOW\s*TO\s*BALANCE", re.IGNORECASE
    )
    _POST_HDR  = re.compile(r"POSTING\s*DATE", re.IGNORECASE)

    # Section-header patterns keyed to canonical section name.
    _SECT_PAT: dict[str, re.Pattern] = {
        "deposits":            re.compile(r"^DEPOSITS?(\s|$|\()", re.IGNORECASE),
        "electronic deposits": re.compile(r"^ELECTRONIC\s*DEPOSITS?", re.IGNORECASE),
        "other credits":       re.compile(r"^OTHER\s*CREDITS?", re.IGNORECASE),
        "checks paid":         re.compile(r"^CHECKS?\s*PAID", re.IGNORECASE),
        "electronic payments": re.compile(r"^ELECTRONIC\s*PAYMENTS?", re.IGNORECASE),
        "other withdrawals":   re.compile(r"^OTHER\s*WITHDRAWALS?", re.IGNORECASE),
        "service charges":     re.compile(r"^SERVICE\s*CHARGES?", re.IGNORECASE),
    }

    # TD Canada Trust month abbreviation → zero-padded month number
    _CA_MONTH: dict[str, str] = {
        "JAN": "01", "FEB": "02", "MAR": "03", "APR": "04",
        "MAY": "05", "JUN": "06", "JUL": "07", "AUG": "08",
        "SEP": "09", "OCT": "10", "NOV": "11", "DEC": "12",
    }
    _CA_DATE_RE = re.compile(r"^([A-Z]{3})\s*(\d{1,2})$", re.IGNORECASE)

    # -----------------------------------------------------------------------
    # Identification
    # -----------------------------------------------------------------------

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        # US TD Bank
        if (re.search(r"\bTD\s*BANK\b", flat)
                and re.search(r"ELECTRONIC\s*DEPOSITS", flat)
                and re.search(r"ELECTRONIC\s*PAYMENTS", flat)):
            return True
        # TD Canada Trust (Toronto-Dominion Bank)
        if (re.search(r"TORONTO[\-\s]DOMINION\s*BANK", flat)
                and re.search(r"CHEQUE.{0,10}DEBIT", flat)):
            return True
        return False

    @classmethod
    def _is_canada_trust(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        # Primary: explicit bank name
        if re.search(r"TORONTO[\-\s]DOMINION\s*BANK|TD\s+CANADA\s+TRUST", flat):
            return True
        # Fallback: characteristic column headers + account type phrase
        # (bank name may not always appear in pdfplumber's text extraction)
        return bool(
            re.search(r"CHEQUE.{0,5}DEBIT", flat)
            and re.search(r"DEPOSIT.{0,5}CREDIT", flat)
            and re.search(r"BUSINESS\s+CHEQU", flat)
        )

    # -----------------------------------------------------------------------
    # Summary extraction from OCR text
    # -----------------------------------------------------------------------

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        # TD Canada Trust: summary box is extracted with left-column boilerplate
        # interleaved, e.g. "Credits MONTHLY AVER. CR. BAL. $294.88 2 12,023.20".
        # Strategy: find the transaction COUNT (a small whole number NOT followed
        # by a decimal) then the AMOUNT immediately after it.
        if cls._is_canada_trust(text):
            def _sum_ca(label: str) -> float:
                total = 0.0
                # (\d{1,3})(?!\.\d{2}) — count, not a decimal amount
                # \s+([\d,]+\.\d{2})   — the actual dollar total right after
                for m in re.finditer(
                    rf"{label}.*?(\d{{1,3}})(?!\.\d{{2}})\s+([\d,]+\.\d{{2}})",
                    flat, re.IGNORECASE,
                ):
                    total += abs(clean_money(m.group(2)))
                return total

            credits = _sum_ca("Credits")
            debits  = _sum_ca("Debits")
            # Always return — do NOT fall through to US TD Bank patterns.
            return {
                "credits_amount": round(credits, 2),
                "debits_amount":  round(debits, 2),
                "credit_count": 0,
                "debit_count":  0,
            }

        credit_patterns = [
            # "Deposits" alone (not preceded by "Electronic" or "Other")
            r"(?<!Electronic )(?<!Other )(?<!\w)Deposits\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s*Deposits\s+\$?([\d,]+\.\d{2})",
            r"Other\s*Credits\s+\$?([\d,]+\.\d{2})",
        ]
        debit_patterns = [
            r"Checks\s*Paid\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s*Payments\s+\$?([\d,]+\.\d{2})",
            r"Other\s*Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Service\s*Charges?\s+\$?([\d,]+\.\d{2})",
        ]

        credits = sum(
            abs(clean_money(m.group(1)))
            for p in credit_patterns
            for m in re.finditer(p, flat, re.IGNORECASE)
        )
        debits = sum(
            abs(clean_money(m.group(1)))
            for p in debit_patterns
            for m in re.finditer(p, flat, re.IGNORECASE)
        )

        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }

    # -----------------------------------------------------------------------
    # Direct PDF extraction (higher accuracy than OCR for digital PDFs)
    # -----------------------------------------------------------------------

    @classmethod
    def extract_summary_from_pdf(cls, uploaded_file) -> dict:
        td_credit = 0.0
        td_debit = 0.0
        debit_cats = 0

        try:
            uploaded_file.seek(0)
            with pdfplumber.open(uploaded_file) as pdf:
                for page in pdf.pages:
                    raw = page.extract_text() or ""
                    for line in fix_spaced_ocr_text(raw).split("\n"):
                        clean = re.sub(r"\s+", " ", line).strip().upper()
                        amounts = re.findall(r"\d{1,3}(?:,\d{3})*\.\d{2}|\d+\.\d{2}", line)
                        if not amounts:
                            continue
                        amt = abs(clean_money(amounts[-1]))

                        if "CHECKS PAID" in clean and "NO." not in clean:
                            td_debit += amt; debit_cats += 1
                        elif "ELECTRONIC PAYMENTS" in clean:
                            td_debit += amt; debit_cats += 1
                        elif "OTHER WITHDRAWALS" in clean:
                            td_debit += amt; debit_cats += 1
                        elif "SERVICE CHARGES" in clean and "SUMMARY" not in clean:
                            td_debit += amt; debit_cats += 1

                        if "ELECTRONIC DEPOSITS" in clean:
                            td_credit += amt
                        elif "OTHER CREDITS" in clean:
                            td_credit += amt
                        elif ("DEPOSITS" in clean
                              and "ELECTRONIC" not in clean
                              and "OTHER" not in clean
                              and "SUBTOTAL" not in clean
                              and "POSTING" not in clean):
                            td_credit += amt

        except Exception as exc:
            print(f"[TD PDF extract] {exc}")

        return {
            "credits_amount": round(td_credit, 2),
            "debits_amount": round(td_debit, 2) if debit_cats >= 2 else 0.0,
            "credit_count": 0,
            "debit_count": 0,
        }

    # -----------------------------------------------------------------------
    # Transaction extraction — section-aware, multi-line-aware
    # -----------------------------------------------------------------------

    # -----------------------------------------------------------------------
    # TD Canada Trust — table-based transaction extractor
    # -----------------------------------------------------------------------

    @classmethod
    def _fmt_ca_date(cls, raw: str, year: str) -> str:
        """Convert 'OCT10' or 'OCT 10' → 'YYYY-MM-DD' (ISO, unambiguous for pandas)."""
        m = cls._CA_DATE_RE.match(raw.strip())
        if not m:
            return raw
        mon = cls._CA_MONTH.get(m.group(1).upper(), "01")
        day = m.group(2).zfill(2)
        return f"{year}-{mon}-{day}"

    _CA_SKIP = re.compile(
        r"^(BALANCE\s+FORWARD|DESCRIPTION|0\s+CHQS|NEXT\s+STATEMENT|"
        r"MONTHLY\s+AVER|MONTHLY\s+MIN|DEP\s+CONTENT|"
        r"Credits\b|Debits\b|NO\.\s*AMOUNT)",
        re.IGNORECASE,
    )

    @classmethod
    def _parse_canada_trust(cls, raw_bytes: bytes) -> list[dict]:
        """
        Parse TD Canada Trust statements.
        Layout: DESCRIPTION | CHEQUE/DEBIT | DEPOSIT/CREDIT | DATE | BALANCE

        Primary strategy: extract_table() with vertical=lines (uses actual PDF
        column-separator rules) + horizontal=text (infers rows from baselines).
        Fallback: word-position analysis with printed diagnostics.
        """
        import datetime
        rows: list[dict] = []
        year = str(datetime.date.today().year)

        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                # Extract statement year from header e.g. "SEP 29/25 - OCT 31/25"
                for page in pdf.pages:
                    ym = re.search(r"/(\d{2})\s*[-–]", page.extract_text() or "")
                    if ym:
                        year = "20" + ym.group(1)
                        break

                for page in pdf.pages:
                    page_rows = cls._parse_ca_page(page, year)
                    rows.extend(page_rows)

        except Exception:
            print(traceback.format_exc())

        return rows

    @classmethod
    def _parse_ca_page(cls, page, year: str) -> list[dict]:
        """Try extract_table first; fall back to word-position analysis."""
        rows = cls._parse_ca_table(page, year)
        if rows:
            return rows
        return cls._parse_ca_words(page, year)

    @classmethod
    def _parse_ca_table(cls, page, year: str) -> list[dict]:
        """
        Use pdfplumber extract_table() — relies on the PDF's actual vertical
        separator lines to define columns exactly.  Works when the PDF has
        explicit column-rule geometry.
        """
        _DATE_CELL = re.compile(r"([A-Z]{3})\s*(\d{1,2})", re.IGNORECASE)
        _MONEY_CELL = re.compile(r"\d{1,3}(?:,\d{3})*\.\d{2}")

        try:
            tbl = page.extract_table({
                "vertical_strategy":   "lines",
                "horizontal_strategy": "text",
                "min_words_vertical":  3,
                "text_y_tolerance":    3,
                "intersection_tolerance": 5,
            })
        except Exception:
            tbl = None

        if not tbl or len(tbl) < 2:
            return []

        # Find header row
        header_idx = None
        for i, row in enumerate(tbl):
            upper = " ".join(str(c or "").upper() for c in row)
            if "CHEQUE" in upper and "DEPOSIT" in upper:
                header_idx = i
                break
        if header_idx is None:
            return []

        # Map column indices
        hdr = [str(c or "").upper() for c in tbl[header_idx]]
        desc_col = debit_col = credit_col = date_col = None
        for i, h in enumerate(hdr):
            if "DESCRIPTION" in h and desc_col is None:
                desc_col = i
            elif ("CHEQUE" in h or ("DEBIT" in h and "CREDIT" not in h)) and debit_col is None:
                debit_col = i
            elif ("DEPOSIT" in h or "CREDIT" in h) and credit_col is None:
                credit_col = i
            elif h.strip() == "DATE" and date_col is None:
                date_col = i

        if debit_col is None or credit_col is None:
            return []
        if desc_col is None:
            desc_col = 0

        rows: list[dict] = []
        for row in tbl[header_idx + 1:]:
            if not row:
                continue
            desc = str(row[desc_col] or "").strip()
            if not desc or cls._CA_SKIP.match(desc):
                continue

            debit_str  = str(row[debit_col]  or "").strip() if debit_col  < len(row) else ""
            credit_str = str(row[credit_col] or "").strip() if credit_col < len(row) else ""
            date_cell  = str(row[date_col]   or "").strip() if date_col is not None and date_col < len(row) else ""

            # Parse date from cell (format: "OCT10" or "OCT 10")
            dm = _DATE_CELL.search(date_cell)
            if not dm:
                continue
            mon = cls._CA_MONTH.get(dm.group(1).upper(), "01")
            day = dm.group(2).zfill(2)
            date_str = f"{year}-{mon}-{day}"

            debit_m  = _MONEY_CELL.search(debit_str)
            credit_m = _MONEY_CELL.search(credit_str)
            debit_val  = abs(clean_money(debit_m.group(0)))  if debit_m  else 0.0
            credit_val = abs(clean_money(credit_m.group(0))) if credit_m else 0.0

            if debit_val == 0 and credit_val == 0:
                continue

            # TD CA Trust: each transaction is exclusively debit OR credit.
            # If both are set, two consecutive rows were merged by pdfplumber —
            # split them using newline-separated description lines.
            if debit_val > 0 and credit_val > 0:
                desc_lines = [p.strip() for p in desc.split("\n") if p.strip()]
                if len(desc_lines) >= 2:
                    types = [cls._ca_tx_type(d) for d in desc_lines]
                    # If first line looks like a debit, swap so credit is first
                    if types[0] == "debit" or types[1] == "credit":
                        desc_lines[0], desc_lines[1] = desc_lines[1], desc_lines[0]
                    credit_desc = desc_lines[0]
                    debit_desc  = " ".join(desc_lines[1:])
                else:
                    credit_desc = debit_desc = desc
                rows.append({
                    "Date": date_str, "Description": credit_desc,
                    "Debit": 0.0, "Credit": round(credit_val, 2),
                    "Amount": round(credit_val, 2), "Balance": 0.0,
                })
                rows.append({
                    "Date": date_str, "Description": debit_desc,
                    "Debit": round(debit_val, 2), "Credit": 0.0,
                    "Amount": -round(debit_val, 2), "Balance": 0.0,
                })
                continue

            rows.append({
                "Date":        date_str,
                "Description": desc,
                "Debit":       round(debit_val, 2) if debit_val else 0.0,
                "Credit":      round(credit_val, 2) if credit_val else 0.0,
                "Amount":      round(credit_val - debit_val, 2),
                "Balance":     0.0,
            })

        print(f"[TD CA table] {len(rows)} rows from extract_table()")
        return rows

    @staticmethod
    def _ca_tx_type(desc: str) -> str:
        """Return 'credit', 'debit', or 'unknown' for a TD Canada Trust description."""
        u = desc.upper()
        if re.search(r"\bTFR-FR\b|\bMSP\b", u):
            return "credit"
        if re.search(r"\bTFR-TO\b|\bSEND\s+E-TFR\b|\bFEE\b|\bPAYMENT\b"
                     r"|\bCHARGE\b|\bINTEREST\b|\bWITHDR", u):
            return "debit"
        return "unknown"

    @classmethod
    def _parse_ca_words(cls, page, year: str) -> list[dict]:
        """
        Word-position fallback.  Prints column anchors + every amount so we
        can diagnose classification issues without touching server code.
        """
        _MONEY_RE = re.compile(r"^\d{1,3}(?:,\d{3})*\.\d{2}$")
        _DATE_RE  = re.compile(r"^([A-Z]{3})(\d{1,2})$", re.IGNORECASE)
        _LINE_TOL = 3

        words = page.extract_words(x_tolerance=5, y_tolerance=3)
        if not words:
            return []

        # Group into lines
        lines_list: list[tuple[float, list]] = []
        for w in sorted(words, key=lambda x: (x["top"], x["x0"])):
            placed = False
            for y, lw in lines_list:
                if abs(w["top"] - y) <= _LINE_TOL:
                    lw.append(w)
                    placed = True
                    break
            if not placed:
                lines_list.append((w["top"], [w]))

        # Detect header and column anchors
        debit_x = credit_x = date_x = None
        header_idx = None
        for i, (y, lw) in enumerate(lines_list):
            row_text = " ".join(w["text"].upper() for w in lw)
            if "CHEQUE" in row_text and "DEBIT" in row_text and "DEPOSIT" in row_text:
                header_idx = i
                for w in lw:
                    t = w["text"].upper()
                    if "CHEQUE" in t and debit_x is None:
                        debit_x = (w["x0"] + w["x1"]) / 2
                    elif "DEPOSIT" in t and credit_x is None:
                        credit_x = (w["x0"] + w["x1"]) / 2
                    elif t == "DATE" and date_x is None:
                        date_x = (w["x0"] + w["x1"]) / 2
                break

        if debit_x is None or credit_x is None:
            return []

        col_mid = (debit_x + credit_x) / 2
        print(f"[TD CA words] debit_x={debit_x:.1f} credit_x={credit_x:.1f} "
              f"col_mid={col_mid:.1f} date_x={date_x}")

        rows: list[dict] = []
        for i, (y, lw) in enumerate(lines_list):
            if header_idx is not None and i <= header_idx:
                continue

            lw_sorted = sorted(lw, key=lambda w: w["x0"])
            desc_parts: list[str] = []
            debit_val = credit_val = 0.0
            date_str = ""

            for w in lw_sorted:
                t  = w["text"]
                xc = (w["x0"] + w["x1"]) / 2

                dm = _DATE_RE.match(t)
                if dm:
                    mon = cls._CA_MONTH.get(dm.group(1).upper(), "01")
                    day = dm.group(2).zfill(2)
                    date_str = f"{year}-{mon}-{day}"
                    continue

                if _MONEY_RE.match(t):
                    amt = abs(clean_money(t))
                    if date_x is not None and xc >= date_x:
                        tag = "BALANCE"
                    elif xc <= col_mid:
                        debit_val = amt
                        tag = "DEBIT"
                    else:
                        credit_val = amt
                        tag = "CREDIT"
                    print(f"[TD CA words]   {t:12} xc={xc:.1f} col_mid={col_mid:.1f} → {tag}")
                    continue

                if xc < debit_x - 5:
                    desc_parts.append(t)

            desc = " ".join(desc_parts).strip()
            if not desc or cls._CA_SKIP.match(desc):
                continue
            if debit_val == 0 and credit_val == 0:
                continue
            if not date_str:
                continue

            rows.append({
                "Date":        date_str,
                "Description": desc,
                "Debit":       round(debit_val, 2),
                "Credit":      round(credit_val, 2),
                "Amount":      round(credit_val - debit_val, 2),
                "Balance":     0.0,
            })

        print(f"[TD CA words] {len(rows)} rows from word extraction")
        return rows

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    @classmethod
    def parse_transactions(cls, raw_bytes: bytes):
        """
        Parse TD Bank transactions directly from the PDF.
        Returns a pandas DataFrame with: Date, Description, Debit, Credit,
        Amount, Balance columns.
        Dispatches to the Canada Trust table parser or the US section parser
        depending on which format is detected.
        """
        import pandas as pd

        # Detect format from first page text
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                first_text = pdf.pages[0].extract_text() or "" if pdf.pages else ""
        except Exception:
            first_text = ""

        if cls._is_canada_trust(first_text):
            print("[TD.parse_transactions] detected TD Canada Trust format")
            rows = cls._parse_canada_trust(raw_bytes)
            print(f"[TD.parse_transactions] Canada Trust parser: {len(rows)} rows")
            return pd.DataFrame(rows) if rows else pd.DataFrame()

        # US TD Bank (section-based)
        print(f"[TD.parse_transactions] US TD Bank, bytes={len(raw_bytes)}")
        rows: list[dict] = []
        try:
            with pdfplumber.open(io.BytesIO(raw_bytes)) as pdf:
                pages = [page.extract_text() or "" for page in pdf.pages]
                print(f"[TD.parse_transactions] {len(pages)} pages extracted")
                all_text = "\n".join(pages)
            print(f"[TD.parse_transactions] text preview: {all_text[:500]!r}")
            rows = cls._parse_sections(all_text)
            print(f"[TD.parse_transactions] _parse_sections returned {len(rows)} rows")
        except Exception:
            print(traceback.format_exc())

        return pd.DataFrame(rows) if rows else pd.DataFrame()

    # -----------------------------------------------------------------------

    @classmethod
    def _parse_sections(cls, text: str) -> list[dict]:
        # Extract statement year — \s* handles compressed "StatementPeriod:"
        ym = re.search(r"Statement\s*Period:.*?(\d{4})", text)
        year = ym.group(1) if ym else str(__import__("datetime").date.today().year)

        in_activity = False
        current_section: str | None = None
        is_credit = False

        # Accumulate multi-line transaction blocks
        # Each entry: (date_str, [lines], is_credit)
        blocks: list[tuple[str, list[str], bool]] = []
        cur_date: str | None = None
        cur_lines: list[str] = []
        cur_is_credit = False

        def _flush():
            nonlocal cur_date, cur_lines
            if cur_date:
                blocks.append((cur_date, cur_lines[:], cur_is_credit))
            cur_date = None
            cur_lines = []

        _BOILERPLATE = re.compile(
            r"CALL\s*1-800|FDIC\s*INSURED|EQUAL\s*HOUSING|TD\s*BANK,?\s*N\.?A\.?"
            r"|AMERICA.?S\s*MOST\s*CONVENIENT",
            re.IGNORECASE,
        )
        _SKIP_HDR = re.compile(
            r"^(Page\s*:|Statement\s*Period\s*:|Cust\s*Ref|Primary\s*Account|xxxxxx)",
            re.IGNORECASE,
        )

        for raw in text.split("\n"):
            line = re.sub(r"\s+", " ", raw).strip()
            if not line:
                continue
            upper = line.upper()

            # ── Activity section boundaries (regex handles compressed text) ──
            if cls._ACT_START.search(upper):
                in_activity = True
                continue
            if cls._ACT_END.search(upper):
                _flush()
                in_activity = False
                continue
            if not in_activity:
                continue

            # ── Skip boilerplate / page headers ─────────────────────────
            if _BOILERPLATE.search(upper):
                continue
            if _SKIP_HDR.match(line):
                continue

            # ── Detect section header (no date prefix) ───────────────────
            if not cls._TX_DATE.match(line):
                matched_sect = None
                for sect_name, pat in cls._SECT_PAT.items():
                    if pat.match(line):
                        matched_sect = sect_name
                        break
                if matched_sect:
                    _flush()
                    current_section = matched_sect
                    is_credit = matched_sect in cls._CREDIT_SECTS
                    continue

            if current_section is None:
                continue

            # ── Skip column-header and subtotal rows ────────────────────
            if cls._POST_HDR.search(upper) or "SUBTOTAL" in upper:
                continue
            if upper.startswith("DATE") and ("SERIAL" in upper or "AMOUNT" in upper):
                continue

            # ── New transaction (starts with MM/DD) ─────────────────────
            dm = cls._TX_DATE.match(line)
            if dm:
                _flush()
                cur_date = dm.group(1)
                cur_lines = [line]
                cur_is_credit = is_credit
            elif cur_date:
                # Continuation line — append unless it's a subtotal
                if "SUBTOTAL" not in upper:
                    cur_lines.append(line)

        _flush()

        # ── Build rows from blocks ───────────────────────────────────────
        rows: list[dict] = []
        for date_str, lines, cred in blocks:
            if not lines:
                continue

            full_block = " ".join(lines)

            # Checks Paid: may have 2 entries per row (date serial amt date serial amt)
            if not cred:
                check_hits = re.findall(
                    r"(\d{2}/\d{2})\s+(\d+\*?)\s+([\d,]+\.\d{2})", full_block
                )
                if len(check_hits) >= 2 or (
                    check_hits
                    and re.match(r"^\d{2}/\d{2}\s+\d+\*?\s+[\d,]+\.\d{2}", lines[0])
                ):
                    for ds, serial, amt_s in check_hits:
                        v = abs(clean_money(amt_s))
                        rows.append({
                            "Date": f"{ds}/{year}",
                            "Description": f"Check #{serial}",
                            "Debit": v, "Credit": 0.0,
                            "Amount": -v, "Balance": 0.0,
                        })
                    continue

            # Find the transaction amount (last monetary value in the block)
            amts = cls._AMOUNT_PAT.findall(full_block)
            if not amts:
                continue
            tx_val = abs(clean_money(amts[-1]))
            if tx_val == 0:
                continue

            # Description = first line (minus date) + continuation lines
            first = re.sub(r"^\d{2}/\d{2}\s+", "", lines[0])
            # Remove trailing amount from first line
            first = re.sub(r"\s*" + re.escape(amts[-1]) + r"\s*$", "", first).strip()
            # Also remove any other trailing amount that crept in
            first = re.sub(r"\s+[\d,]+\.\d{2}\s*$", "", first).strip()

            cont_parts: list[str] = []
            for cont in lines[1:]:
                if re.match(r"^\d{12,20}$", cont):   # card/account numbers
                    continue
                if "SUBTOTAL" in cont.upper():
                    continue
                cont_parts.append(cont)

            desc = (first + " " + " ".join(cont_parts)).strip()
            # Strip trailing amounts from combined description
            desc = re.sub(r"\s+[\d,]+\.\d{2}\s*$", "", desc).strip()

            full_date = f"{date_str}/{year}"
            if cred:
                rows.append({
                    "Date": full_date, "Description": desc,
                    "Debit": 0.0, "Credit": tx_val,
                    "Amount": tx_val, "Balance": 0.0,
                })
            else:
                rows.append({
                    "Date": full_date, "Description": desc,
                    "Debit": tx_val, "Credit": 0.0,
                    "Amount": -tx_val, "Balance": 0.0,
                })

        return rows
