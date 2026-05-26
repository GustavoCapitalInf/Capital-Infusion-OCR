"""
banks/td.py
-----------
TD Bank statement parser.

Detected by: "TD Bank" header + "Electronic Deposits" AND "Electronic Payments".

TD Bank Account Summary lists individual category subtotals, not a single
credit/debit line.  We accumulate them:

  Credits:
    Electronic Deposits        $X,XXX.XX
    Other Credits              $X,XXX.XX
    Deposits (non-electronic)  $X,XXX.XX

  Debits (summed):
    Checks Paid                $X,XXX.XX
    Electronic Payments        $X,XXX.XX
    Other Withdrawals          $X,XXX.XX
    Service Charges            $X,XXX.XX

NSF: TD uses "Items Returned Unpaid" section; each dated line = 1 NSF.
POS: Descriptions containing "POS" or "PURCHASE".
"""

from __future__ import annotations

import re

import pdfplumber

from banks.base import BankParser
from utils.cleaning import clean_money, fix_spaced_ocr_text


class TDParser(BankParser):

    NAME = "TD Bank"

    # -----------------------------------------------------------------------
    # Identification
    # -----------------------------------------------------------------------

    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", text).upper()
        return bool(
            re.search(r"\bTD\s*BANK\b", flat)
            and re.search(r"ELECTRONIC\s*DEPOSITS", flat)
            and re.search(r"ELECTRONIC\s*PAYMENTS", flat)
        )

    # -----------------------------------------------------------------------
    # Summary extraction from OCR text
    # -----------------------------------------------------------------------

    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)

        credit_patterns = [
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
        except Exception as exc:
            print(f"[TD PDF extract] {exc}")

        return {
            "credits_amount": round(td_credit, 2),
            "debits_amount": round(td_debit, 2) if debit_cats >= 2 else 0.0,
            "credit_count": 0,
            "debit_count": 0,
        }
