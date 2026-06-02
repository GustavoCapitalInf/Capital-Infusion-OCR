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

import re

from banks.base import BankParser
from utils.cleaning import clean_money


class RBCParser(BankParser):

    NAME = "RBC"

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        return bool(re.search(r"\bRBC\b|ROYAL\s+BANK\s+OF\s+CANADA", flat))

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
