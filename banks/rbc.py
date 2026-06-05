"""
banks/rbc.py
------------
Royal Bank of Canada (RBC) statement parser.

Detected by: "RBC" or "Royal Bank of Canada" in text.

RBC Business Account Summary format:
  Total deposits & credits (44) + 68,770.44
  Total cheques & debits (144) - 74,947.80

Extraction strategy:
  1. Two-step: find the count marker "(N)", then scan FORWARD from that
     position for a signed amount (+ for credits, - for debits).
     This handles both same-line and separate-column pdfplumber output.
  2. Fallback: loose search anywhere in the flattened document text.
"""

from __future__ import annotations

import io
import re
import traceback
from collections import defaultdict

import pandas as pd
import pdfplumber

from banks.base import BankParser
from utils.cleaning import clean_money


class RBCParser(BankParser):

    NAME = "RBC"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        # Bank name (may be an image in some PDFs and not extracted as text)
        if re.search(r"\bRBC\b|ROYAL\s+BANK\s+OF\s+CANADA|RBCROYALBANK", flat):
            return True
        # "Cheques" (British spelling) is unique to RBC among Canadian banks;
        # combined with "debits" it's an unambiguous fingerprint of the summary line
        # "Total cheques & debits (N) - amount" that pdfplumber DOES extract.
        if re.search(r"CHEQUES?\s*[&＆]\s*DEBITS?", flat):
            return True
        return False

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = str(text).replace("&amp;", "&")
        flat = re.sub(r"[–—−]", "-", flat)
        flat = re.sub(r"\s+", " ", flat)

        # ── Debug: show what text we actually received ──────────────────────
        print(f"[RBC.extract_summary] text_len={len(flat)}")
        print(f"[RBC.extract_summary] preview={flat[:400]!r}")

        credits = debits = 0.0
        credit_count = debit_count = 0

        # ── Credits ─────────────────────────────────────────────────────────
        # Strategy 1 (two-step): find "(N)" count marker, then scan FORWARD
        # for the "+" sign immediately followed by the credit amount.
        # Works for both same-line ("(44) + 68,770.44") and
        # separate-column ("(44) … many chars … + 68,770.44") layouts.
        cm = re.search(
            r"deposits\s*[&＆]\s*credits\s*\((\d+)\)",
            flat, re.IGNORECASE,
        )
        if cm:
            credit_count = int(cm.group(1))
            rest = flat[cm.end():]
            # Look for explicit "+" sign followed by the amount
            m2 = re.search(r"\+\s*([\d,]+\.\d{2})", rest)
            if m2:
                credits = abs(clean_money(m2.group(1)))
                print(f"[RBC] credits two-step (+sign): count={credit_count}, amount={credits}")
            else:
                # No explicit "+", take the first standalone dollar amount
                m2 = re.search(r"(?<!\d)([\d,]+\.\d{2})", rest)
                if m2:
                    credits = abs(clean_money(m2.group(1)))
                    print(f"[RBC] credits two-step (first amount): count={credit_count}, amount={credits}")

        # Strategy 2: "deposits and credits (N) + amount" (Google-Translate variant)
        if not credits:
            cm = re.search(
                r"deposits\s+and\s+credits\s*\((\d+)\)",
                flat, re.IGNORECASE,
            )
            if cm:
                credit_count = int(cm.group(1))
                rest = flat[cm.end():]
                m2 = re.search(r"\+\s*([\d,]+\.\d{2})", rest)
                if m2:
                    credits = abs(clean_money(m2.group(1)))
                    print(f"[RBC] credits 'and' variant: count={credit_count}, amount={credits}")

        # Strategy 3: single-pattern with precise sign handling
        if not credits:
            m = re.search(
                r"deposits\s*[&＆]\s*credits\s*\((\d+)\)\s*\+\s*([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if m:
                credit_count = int(m.group(1))
                credits = abs(clean_money(m.group(2)))
                print(f"[RBC] credits inline pattern: count={credit_count}, amount={credits}")

        # Strategy 4: loose — any amount after "deposits & credits"
        if not credits:
            m = re.search(
                r"deposits\s*[&＆and]+\s*credits.*?([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if m:
                credits = abs(clean_money(m.group(1)))
                print(f"[RBC] credits loose fallback: amount={credits}")

        # ── Debits ──────────────────────────────────────────────────────────
        # Strategy 1 (two-step): find "(N)" count marker, then scan FORWARD
        # for the "−" sign followed by the debit amount.
        # The opening balance "-$216.54" has a "$" that blocks digit matching,
        # so we naturally skip it and land on "- 74,947.80".
        dm = re.search(
            r"cheques?\s*[&＆]\s*debits?\s*\((\d+)\)",
            flat, re.IGNORECASE,
        )
        if dm:
            debit_count = int(dm.group(1))
            rest = flat[dm.end():]
            # Look for explicit "-" sign directly before digits (no "$")
            m2 = re.search(r"-\s*([\d,]+\.\d{2})", rest)
            if m2:
                debits = abs(clean_money(m2.group(1)))
                print(f"[RBC] debits two-step (-sign): count={debit_count}, amount={debits}")
            else:
                m2 = re.search(r"(?<!\d)([\d,]+\.\d{2})", rest)
                if m2:
                    debits = abs(clean_money(m2.group(1)))
                    print(f"[RBC] debits two-step (first amount): count={debit_count}, amount={debits}")

        # Strategy 2: "checks and debits (N)" (Google-Translate variant)
        if not debits:
            dm = re.search(
                r"checks?\s+and\s+debits?\s*\((\d+)\)",
                flat, re.IGNORECASE,
            )
            if dm:
                debit_count = int(dm.group(1))
                rest = flat[dm.end():]
                m2 = re.search(r"-\s*([\d,]+\.\d{2})", rest)
                if m2:
                    debits = abs(clean_money(m2.group(1)))
                    print(f"[RBC] debits 'checks/and' variant: count={debit_count}, amount={debits}")

        # Strategy 3: single-pattern with precise sign
        if not debits:
            m = re.search(
                r"cheques?\s*[&＆]\s*debits?\s*\((\d+)\)\s*-\s*([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if m:
                debit_count = int(m.group(1))
                debits = abs(clean_money(m.group(2)))
                print(f"[RBC] debits inline pattern: count={debit_count}, amount={debits}")

        # Strategy 4: loose — any amount after "cheques & debits"
        if not debits:
            m = re.search(
                r"cheques?\s*[&＆and]+\s*debits?.*?([\d,]+\.\d{2})",
                flat, re.IGNORECASE,
            )
            if m:
                debits = abs(clean_money(m.group(1)))
                print(f"[RBC] debits loose fallback: amount={debits}")

        print(
            f"[RBC.extract_summary] FINAL: credits={credits}, debits={debits}, "
            f"credit_count={credit_count}, debit_count={debit_count}"
        )

        return {
            "credits_amount": round(credits, 2),
            "debits_amount":  round(debits, 2),
            "credit_count":   credit_count,
            "debit_count":    debit_count,
        }

    # ── Transaction extraction ────────────────────────────────────────────────

    _MONEY_RE  = re.compile(r"^-?\$?[\d,]+\.\d{2}$")
    _MONTHS    = {"jan","feb","mar","apr","may","jun","jul","aug","sep","oct","nov","dec"}
    _SKIP_FRAGS = (
        "opening balance", "closing balance", "account fees",
        "account activity details",
    )
    # Regex version handles compressed text where spaces are missing
    _SKIP_FRAGS_RE = re.compile(
        r"opening\s*balance|closing\s*balance|account\s*fees?|account\s*activity\s*details",
        re.IGNORECASE,
    )

    # Credit / debit keyword patterns — \s* matches both spaced and compressed text
    _CREDIT_KW = re.compile(
        r"ATM\s*deposit|e-Transfer\s*received|Online\s*transfer\s*received"
        r"|Misc\s*Payment\s*MRCH\d+"
        r"|Cheque\s*returned|Item\s*returned|Web\s*payment\s*BIZFUND\s*CA\s*LTD",
        re.IGNORECASE,
    )
    _DEBIT_KW = re.compile(
        r"Monthly\s*fee|Regular\s*transaction\s*fee|ATM\s*cash\s*deposited\s*fee"
        r"|In\s*branch\s*cash\s*deposited\s*fee|NSF\s*item\s*fee"
        r"|Online\s*Banking\s*payment|Online\s*Banking\s*transfer"
        r"|e-Transfer\s*sent|Online\s*transfer\s*sent"
        r"|Cheque\s*-\s*\d|Interac\s*purchase|Contactless\s*Interac"
        r"|Bill\s*Payment|Insurance|Equipment\s*Rent"
        r"|Business\s*PAD|Misc\s*Payment\s*Fundfi|Misc\s*Payment\s*BIZFUND\s*ACHDEBIT"
        r"|Misc\s*Payment\s*2313833|Misc\s*Payment\s*PAY-FILE"
        r"|Misc\s*Payment\s*Canacap",
        re.IGNORECASE,
    )

    @classmethod
    def parse_transactions(cls, raw_bytes: bytes) -> pd.DataFrame:
        """
        RBC transaction extractor — three strategies tried in order:
          1. pdfplumber extract_tables()
          2. pdfplumber extract_words() with x-coordinate column detection
          3. extract_text() line-by-line with keyword direction detection
        Exceptions are printed to stdout so server logs capture them.
        """
        # Normalise raw_bytes → actual bytes (handles both bytes and file-like objects)
        if isinstance(raw_bytes, (bytes, bytearray)):
            pdf_bytes = bytes(raw_bytes)
        else:
            try:
                if hasattr(raw_bytes, "seek"):
                    raw_bytes.seek(0)
                pdf_bytes = raw_bytes.read()
            except Exception as e:
                print(f"[RBC.parse_transactions] could not read raw_bytes: {e}")
                return pd.DataFrame()

        print(f"[RBC.parse_transactions] pdf_bytes type={type(pdf_bytes).__name__} len={len(pdf_bytes)}")

        all_rows: list[dict] = []
        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                print(f"[RBC.parse_transactions] {len(pdf.pages)} pages")
                for page in pdf.pages:
                    page_rows = cls._page_via_table(page)
                    if not page_rows:
                        page_rows = cls._page_via_words(page)
                    all_rows.extend(page_rows)
        except Exception:
            print(traceback.format_exc())

        if not all_rows:
            print("[RBC.parse_transactions] strategies 1+2 gave 0 rows → trying text strategy")
            all_rows = cls._parse_via_text(pdf_bytes)

        print(f"[RBC.parse_transactions] total rows={len(all_rows)}")
        return pd.DataFrame(all_rows)

    # ── Strategy 1: table extraction ─────────────────────────────────────────

    @classmethod
    def _page_via_table(cls, page) -> list[dict]:
        rows_out: list[dict] = []
        for settings in [
            {"vertical_strategy": "text", "horizontal_strategy": "lines"},
            {"vertical_strategy": "text", "horizontal_strategy": "lines_strict"},
            {"vertical_strategy": "text", "horizontal_strategy": "text"},
        ]:
            try:
                tables = page.extract_tables(settings) or []
            except Exception as e:
                print(f"[RBC._page_via_table] p{page.page_number} {settings}: {e}")
                continue

            for table in tables:
                if not table or len(table) < 3:
                    continue

                # Find row containing "Cheques" AND "Deposits"
                header_idx = None
                for i, row in enumerate(table):
                    rs = " ".join(str(c or "") for c in row)
                    if ("Cheques" in rs or "CHEQUES" in rs.upper()) and \
                       ("Deposits" in rs or "DEPOSITS" in rs.upper()):
                        header_idx = i
                        break
                if header_idx is None:
                    continue

                # Map header cells → column indices
                hrow = table[header_idx]
                ncols = len(hrow)
                col_d = col_desc = col_deb = col_cred = col_bal = None
                for i, h in enumerate(hrow):
                    hu = str(h or "").upper()
                    if "DATE" in hu and col_d is None:       col_d    = i
                    if "DESCRIPTION" in hu and col_desc is None: col_desc = i
                    if "CHEQUE" in hu and col_deb is None:   col_deb  = i
                    if "DEPOSIT" in hu and col_cred is None: col_cred = i
                    if "BALANCE" in hu and col_bal is None:  col_bal  = i
                # Positional defaults: Date=0 Desc=1 Debit=2 Credit=3 Bal=4
                if col_d    is None: col_d    = 0
                if col_desc is None: col_desc = 1
                if col_deb  is None and ncols >= 3: col_deb  = 2
                if col_cred is None and ncols >= 4: col_cred = 3
                if col_bal  is None and ncols >= 5: col_bal  = 4

                print(f"[RBC._page_via_table] p{page.page_number} "
                      f"cols: date={col_d} desc={col_desc} deb={col_deb} "
                      f"cred={col_cred} bal={col_bal}  rows={len(table)-header_idx-1}")

                current_date = ""
                for row in table[header_idx + 1:]:
                    def _c(i):
                        try: return str(row[i] or "").strip() if i is not None and i < len(row) else ""
                        except: return ""
                    dt   = _c(col_d)
                    desc = _c(col_desc).replace("\n", " ").strip()
                    deb  = _c(col_deb)
                    cred = _c(col_cred)
                    bal  = _c(col_bal)

                    m = re.match(r"^(\d{1,2})\s+([A-Za-z]{3})\b", dt)
                    if m:
                        current_date = f"{m.group(1)} {m.group(2)}"
                    if not current_date:
                        continue

                    dv = abs(clean_money(deb))  if deb  else 0.0
                    cv = abs(clean_money(cred)) if cred else 0.0
                    bv = abs(clean_money(bal))  if bal  else 0.0

                    if dv == 0.0 and cv == 0.0:
                        continue
                    if any(s in desc.lower() for s in cls._SKIP_FRAGS):
                        continue

                    rows_out.append({
                        "Date": current_date, "Description": desc,
                        "Debit": round(dv, 2), "Credit": round(cv, 2),
                        "Amount": round(cv - dv, 2), "Balance": round(bv, 2),
                    })

            if rows_out:
                print(f"[RBC._page_via_table] p{page.page_number}: "
                      f"{len(rows_out)} rows via {settings}")
                return rows_out
        return rows_out

    # ── Strategy 2: word-position extraction ─────────────────────────────────

    @classmethod
    def _page_via_words(cls, page) -> list[dict]:
        rows_out: list[dict] = []
        try:
            words = page.extract_words(x_tolerance=3, y_tolerance=3)
            upper_set = {w["text"].upper() for w in words}
            print(f"[RBC._page_via_words] p{page.page_number}: {len(words)} words, "
                  f"CHEQUES_exact={('CHEQUES' in upper_set)} "
                  f"CHEQUES_sub={any('CHEQUES' in t for t in upper_set)} "
                  f"DEPOSITS_sub={any('DEPOSITS' in t for t in upper_set)}")

            if not words:
                return rows_out

            by_y: dict[int, list] = defaultdict(list)
            for w in words:
                by_y[round(w["top"] / 10) * 10].append(w)

            # Merge lone date-digit rows (e.g. {"text": "02"}) with the next
            # y-key when that row starts with a month abbreviation.  This
            # recovers the date when the day and month land in separate buckets
            # due to PDF baseline offsets (banker's-rounding edge case).
            _sorted_yk = sorted(by_y.keys())
            _skip: set[int] = set()
            merged_by_y: dict[int, list] = {}
            for _i, _yk in enumerate(_sorted_yk):
                if _yk in _skip:
                    continue
                _row = by_y[_yk]
                if (len(_row) == 1
                        and re.match(r"^\d{1,2}$", _row[0]["text"])
                        and _i + 1 < len(_sorted_yk)):
                    _next_yk = _sorted_yk[_i + 1]
                    _next = sorted(by_y[_next_yk], key=lambda w: w["x0"])
                    if _next and _next[0]["text"].lower() in cls._MONTHS:
                        merged_by_y[_yk] = _row + _next
                        _skip.add(_next_yk)
                        continue
                merged_by_y[_yk] = _row

            debit_col_x = credit_col_x = balance_col_x = None
            header_y_key = None

            # Pass 1: exact word match ("Cheques" and "Deposits" as standalone words)
            for y_key in sorted(merged_by_y):
                row_texts = {w["text"].upper() for w in merged_by_y[y_key]}
                if "CHEQUES" in row_texts and "DEPOSITS" in row_texts:
                    for w in merged_by_y[y_key]:
                        t  = w["text"].upper()
                        cx = (w["x0"] + w["x1"]) / 2
                        if t == "CHEQUES":    debit_col_x  = cx
                        elif t == "DEPOSITS": credit_col_x = cx
                        elif t == "BALANCE" and w["x0"] > page.width * 0.5:
                            balance_col_x = cx
                    header_y_key = y_key
                    break

            # Pass 2: substring match (handles merged words like "Cheques&Debits($)")
            if debit_col_x is None or credit_col_x is None:
                for y_key in sorted(merged_by_y):
                    row_concat = " ".join(w["text"].upper() for w in merged_by_y[y_key])
                    if "CHEQUES" in row_concat and "DEPOSITS" in row_concat:
                        for w in merged_by_y[y_key]:
                            wt = w["text"].upper()
                            cx = (w["x0"] + w["x1"]) / 2
                            if "CHEQUES" in wt and debit_col_x is None:
                                debit_col_x  = cx
                            if "DEPOSITS" in wt and credit_col_x is None:
                                credit_col_x = cx
                            if "BALANCE" in wt and w["x0"] > page.width * 0.5 and balance_col_x is None:
                                balance_col_x = cx
                        header_y_key = y_key
                        print(f"[RBC._page_via_words] p{page.page_number}: "
                              f"found via substring debit={debit_col_x:.0f} credit={credit_col_x:.0f}")
                        break

            # Pass 3: hardcoded RBC layout percentages (Letter 612pt wide)
            if debit_col_x is None or credit_col_x is None:
                debit_col_x   = page.width * 0.55   # Cheques & Debits centre
                credit_col_x  = page.width * 0.72   # Deposits & Credits centre
                balance_col_x = page.width * 0.88   # Balance centre
                print(f"[RBC._page_via_words] p{page.page_number}: "
                      f"using hardcoded cols debit={debit_col_x:.0f} "
                      f"credit={credit_col_x:.0f} bal={balance_col_x:.0f}")

            print(f"[RBC._page_via_words] p{page.page_number}: "
                  f"debit_col={debit_col_x:.0f} credit_col={credit_col_x:.0f} "
                  f"bal_col={balance_col_x:.0f} header_y={header_y_key}")

            if balance_col_x is None:
                balance_col_x = page.width * 0.88
            amount_min_x = min(debit_col_x, credit_col_x) - 40

            current_date = ""
            pending_desc = ""

            for y_key in sorted(merged_by_y):
                if y_key == header_y_key:
                    continue
                line = sorted(merged_by_y[y_key], key=lambda w: w["x0"])
                if not line:
                    continue

                first_text = line[0]["text"]
                # Undo bold/shadow doubling: "0022JJaann" → "02Jan"
                # (each character appears exactly twice consecutively)
                _ft = first_text
                if (len(_ft) >= 2 and len(_ft) % 2 == 0
                        and all(_ft[i] == _ft[i + 1] for i in range(0, len(_ft), 2))):
                    _ft = _ft[::2]
                # Case 1: "01" and "Dec" as separate words
                has_date_sep = (
                    len(line) >= 2
                    and re.match(r"^\d{1,2}$", _ft)
                    and line[1]["text"].lower() in cls._MONTHS
                )
                # Case 2: "01Dec" merged (or "0022JJaann" undoubled to "02Jan")
                m_merged = re.match(
                    r"^(\d{1,2})(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)(.*)?$",
                    _ft, re.IGNORECASE,
                )
                if has_date_sep:
                    current_date = f"{line[0]['text']} {line[1]['text']}"
                    line = line[2:]
                    pending_desc = ""
                elif m_merged:
                    current_date = f"{m_merged.group(1)} {m_merged.group(2).capitalize()}"
                    remainder = m_merged.group(3) or ""
                    if remainder:
                        w0 = dict(line[0]); w0["text"] = remainder
                        line = [w0] + line[1:]
                    else:
                        line = line[1:]
                    pending_desc = ""
                if not current_date:
                    continue

                desc_parts: list[str] = []
                amounts: list[tuple[float, float]] = []
                for w in line:
                    cx = (w["x0"] + w["x1"]) / 2
                    if cls._MONEY_RE.match(w["text"]) and cx >= amount_min_x:
                        v = clean_money(w["text"])
                        if v != 0:
                            amounts.append((abs(v), cx))
                    else:
                        desc_parts.append(w["text"])

                desc_text = " ".join(desc_parts).strip()
                if cls._SKIP_FRAGS_RE.search(desc_text):
                    pending_desc = ""
                    continue

                if not amounts:
                    if desc_text:
                        pending_desc = ((pending_desc + " " + desc_text).strip()
                                       if pending_desc else desc_text)
                    continue

                full_desc    = ((pending_desc + " " + desc_text).strip()
                               if pending_desc else desc_text)
                pending_desc = ""

                debit = credit = balance = 0.0
                for val, cx in sorted(amounts, key=lambda a: a[1]):
                    if cx >= balance_col_x - 30:
                        balance = val
                    else:
                        dd = abs(cx - debit_col_x)
                        dc = abs(cx - credit_col_x)
                        if dd <= dc: debit  = val
                        else:        credit = val

                if debit == 0.0 and credit == 0.0:
                    continue

                rows_out.append({
                    "Date": current_date, "Description": full_desc,
                    "Debit": round(debit, 2), "Credit": round(credit, 2),
                    "Amount": round(credit - debit, 2), "Balance": round(balance, 2),
                })

            print(f"[RBC._page_via_words] p{page.page_number}: {len(rows_out)} rows")
        except Exception:
            print(traceback.format_exc())
        return rows_out

    # ── Strategy 3: text-based (most robust fallback) ─────────────────────────

    @classmethod
    def _parse_via_text(cls, pdf_bytes: bytes) -> list[dict]:
        """
        Line-by-line parser using page.extract_text() + fix_spaced_ocr_text.

        KEY: fix_spaced_ocr_text MUST be applied to each page's raw text before
        splitting on newlines — without it the PDF text is one compressed blob
        and split('\\n') yields nothing useful.

        Direction logic:
          • Balance tracking: running_bal ± tx ≈ new_bal → confirmed debit/credit
          • Keyword matching: fallback when no balance is shown on the line
          • Digit-only lines after MRCH descriptions → credit continuation
        """
        rows: list[dict] = []
        AMOUNT_RE = re.compile(r"([\d,]+\.\d{2})")

        try:
            from utils.cleaning import fix_spaced_ocr_text as _fsoct
        except Exception:
            _fsoct = lambda x: x  # noqa: E731

        try:
            with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
                print(f"[RBC._parse_via_text] {len(pdf.pages)} pages")

                current_date = ""
                running_bal  = 0.0      # seed from "Opening balance"
                prev_desc    = ""
                prev_is_mrch = False

                for page in pdf.pages:
                    raw  = page.extract_text() or ""
                    text = _fsoct(raw)
                    all_lines = text.split("\n")

                    # Show first-page diagnostics so we can see the text structure
                    if page.page_number == 1:
                        print(f"[RBC._parse_via_text] p1: raw_len={len(raw)} "
                              f"text_len={len(text)} n_lines={len(all_lines)}")
                        for i, sl in enumerate(all_lines[:20]):
                            print(f"[RBC._parse_via_text]   [{i}]: {sl[:100]!r}")

                    for raw_line in all_lines:
                        line = re.sub(r"\s+", " ", raw_line).strip()
                        if not line:
                            continue
                        low = line.lower()

                        # Seed the running balance from the opening-balance line
                        if re.search(r"opening\s*balance", low):
                            found = AMOUNT_RE.findall(line)
                            if found:
                                running_bal = abs(clean_money(found[-1]))
                            continue

                        # Skip header / footer / summary rows
                        if cls._SKIP_FRAGS_RE.search(low):
                            continue
                        if re.match(r"^\d+\s+of\s+\d+$", line):
                            continue

                        # ── Date detection — handles both "01 Dec rest" and
                        #    compressed "01Decrest" (no spaces between tokens) ──
                        dm = re.match(
                            r"^(\d{1,2})\s*(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s*(.*)",
                            line, re.IGNORECASE,
                        )
                        if dm:
                            current_date = f"{dm.group(1)} {dm.group(2).capitalize()}"
                            rest         = dm.group(3).strip()
                            prev_is_mrch = False
                        else:
                            rest = line

                        if not current_date:
                            continue

                        # All positive dollar amounts on this line
                        all_amts = [abs(clean_money(m)) for m in AMOUNT_RE.findall(rest)
                                    if clean_money(m) > 0]

                        if not all_amts:
                            # Pure description line (e.g. first half of MRCH entry)
                            prev_desc    = rest.strip()
                            prev_is_mrch = bool(re.search(
                                r"Misc\s*Payment\s*MRCH\d+", prev_desc, re.IGNORECASE))
                            continue

                        # Description = text before the first amount
                        first_m = AMOUNT_RE.search(rest)
                        desc    = rest[:first_m.start()].strip() if first_m else rest

                        # ── Digit-only line → MRCH credit continuation ───────
                        if re.match(r"^\d{6,}", rest) and prev_is_mrch and prev_desc:
                            credit = all_amts[-1]
                            rows.append({
                                "Date": current_date, "Description": prev_desc,
                                "Debit": 0.0, "Credit": round(credit, 2),
                                "Amount": round(credit, 2), "Balance": 0.0,
                            })
                            running_bal += credit
                            prev_is_mrch = False
                            prev_desc    = ""
                            continue

                        # ── Which amount is tx vs balance? ────────────────────
                        # Default: LAST amount = tx (amounts earlier in line are
                        # embedded in the description, e.g. "7 Drs @ 2.50 17.50")
                        tx_amount = all_amts[-1]
                        balance_v = 0.0

                        if len(all_amts) >= 2:
                            cand_tx  = all_amts[-2]
                            cand_bal = all_amts[-1]
                            # Confirm as balance if running_bal ± cand_tx ≈ cand_bal
                            if running_bal > 0:
                                if abs(running_bal - cand_tx - cand_bal) < 2.0:
                                    tx_amount = cand_tx
                                    balance_v = cand_bal
                                elif abs(running_bal + cand_tx - cand_bal) < 2.0:
                                    tx_amount = cand_tx
                                    balance_v = cand_bal

                        # ── Direction: keyword matching ───────────────────────
                        full_desc   = desc if desc else prev_desc
                        srch        = full_desc + " " + (prev_desc or "")
                        is_credit   = bool(cls._CREDIT_KW.search(srch))
                        is_debit    = bool(cls._DEBIT_KW.search(srch))

                        # Balance-delta override (most reliable signal)
                        if balance_v > 0 and running_bal > 0:
                            delta = balance_v - running_bal
                            if abs(delta + tx_amount) < 2.0:
                                is_debit = True;  is_credit = False
                            elif abs(delta - tx_amount) < 2.0:
                                is_credit = True; is_debit = False

                        if not is_credit and not is_debit:
                            prev_desc    = full_desc
                            prev_is_mrch = bool(re.search(
                                r"Misc\s*Payment\s*MRCH\d+", full_desc, re.IGNORECASE))
                            continue

                        debit_v  = tx_amount if is_debit  and not is_credit else 0.0
                        credit_v = tx_amount if is_credit and not is_debit  else 0.0
                        if is_credit and is_debit:          # both matched → debit
                            debit_v = tx_amount; credit_v = 0.0

                        # Update running balance
                        if balance_v > 0:
                            running_bal = balance_v
                        elif debit_v > 0:
                            running_bal = max(0.0, running_bal - debit_v)
                        else:
                            running_bal += credit_v

                        prev_is_mrch = bool(re.search(
                            r"Misc\s*Payment\s*MRCH\d+", full_desc, re.IGNORECASE))
                        prev_desc = ""

                        rows.append({
                            "Date":        current_date,
                            "Description": full_desc,
                            "Debit":       round(debit_v, 2),
                            "Credit":      round(credit_v, 2),
                            "Amount":      round(credit_v - debit_v, 2),
                            "Balance":     round(balance_v, 2),
                        })

        except Exception:
            print(traceback.format_exc())

        print(f"[RBC._parse_via_text] total rows={len(rows)}")
        return rows
