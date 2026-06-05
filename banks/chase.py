"""
banks/chase.py
--------------
Chase Bank statement parser.
"""
 
from __future__ import annotations
 
import re
import pandas as pd
 
from banks.base import BankParser
from utils.cleaning import clean_money
 
 
class ChaseParser(BankParser):
 
    NAME = "Chase"
 
    @classmethod
    def is_this_bank(cls, text: str) -> bool:
        flat = re.sub(r"\s+", " ", str(text)).upper()
        has_chase = bool(re.search(r"\bJPMORGAN\b|\bCHASE\b", flat))
        # "THROUGH" may be squished to adjacent word (e.g. "THROUGHJANUARY")
        has_through = bool(re.search(r"THROUGH", flat))
        return has_chase and has_through
 
    @classmethod
    def extract_summary(cls, text: str) -> dict:
        flat = cls._flatten(text)
 
        credits = cls._grab_amount(
            r"Deposits\s+and\s+Additions\s+\$?([\d,]+\.\d{2})",
            flat,
        )
 
        debit_patterns = [
            r"ATM\s*&?\s*Debit\s+Card\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Electronic\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"Checks\s*Paid\s+\$?([\d,]+\.\d{2})",
            r"Service\s+Fees?\s+\$?([\d,]+\.\d{2})",
            r"Other\s+Withdrawals\s+\$?([\d,]+\.\d{2})",
            r"^Fees\s+\d+\s+-?([\d,]+\.\d{2})",       # "Fees  1  -12.50" summary row
            r"Total\s+Fees\s+\$?([\d,]+\.\d{2})",      # "Total Fees $12.50"
        ]
 
        debit_seen = set()
        debits = 0.0
 
        for pattern in debit_patterns:
            for m in re.finditer(pattern, flat, re.IGNORECASE):
                amount = abs(clean_money(m.group(1)))
                key = (pattern, round(amount, 2))
 
                if key in debit_seen:
                    continue
 
                debit_seen.add(key)
                debits += amount
 
        return {
            "credits_amount": round(credits, 2),
            "debits_amount": round(debits, 2),
            "credit_count": 0,
            "debit_count": 0,
        }
 
    @classmethod
    def parse_transactions(cls, text: str) -> pd.DataFrame:
        """
        Chase-specific transaction parser.
 
        pdfplumber extracts Chase section headers AFTER their transactions
        (at the bottom of each section block), so we cannot rely on headers
        appearing before data.  Strategy:
 
        1. Collect multi-line ACH transactions into a buffer (no section yet).
        2. When a section header is seen, retroactively tag the BUFFERED
           transactions with that section, flush them, then reset the buffer.
        3. At EOF, classify any remaining buffered transactions by keywords.
        """
        _SECTION_MAP = {
            "DEPOSITS AND ADDITIONS": "Credit",
            "CHECKS PAID":            "Debit",
            "ATM & DEBIT CARD WITHDRAWALS": "Debit",
            "ATM AND DEBIT CARD WITHDRAWALS": "Debit",
            "ELECTRONIC WITHDRAWALS": "Debit",
            "FEES":                   "Debit",
            "SERVICE FEES":           "Debit",
            "OTHER WITHDRAWALS":      "Debit",
        }
        _STOP_RE = re.compile(
            r"^(DAILY\s+ENDING\s+BALANCE|SERVICE\s+CHARGE\s+(SUMMARY|DETAIL)|"
            r"SAVINGS\s+SUMMARY|TRANSACTION\s+DETAIL)",
            re.IGNORECASE,
        )
        # Keywords for fallback classification when no section header was seen
        _CREDIT_KW = re.compile(
            r"DESCR:DEPOSIT|DEPOSIT\s+\d|ONLINE\s+TRANSFER\s+FROM|"
            r"INTEREST\s+PAYMENT|WIRE\s+IN\b",
            re.IGNORECASE,
        )
 
        _date_re  = re.compile(r"^(\d{1,2}/\d{1,2}(?:/\d{2,4})?)\s+(.*)$")
        _money_re = re.compile(r"-?\$?\d{1,3}(?:,\d{3})*\.\d{2}|-?\$?\d+\.\d{2}")

        # Lines that must never be appended to a pending transaction's text.
        # "Total Electronic Withdrawals $310,772.48" appearing right after the
        # last transaction on a page would otherwise corrupt the amount.
        _SKIP_LINE_RE = re.compile(
            r"^(Total\b|Subtotal\b|Monthly\s+Service\s+Fee\b|"
            r"Other\s+Service\s+Charges\b|Will\s+be\s+assessed\b|"
            r"As\s+an\s+added\s+benefit\b)",
            re.IGNORECASE,
        )
        # Daily ending balance rows start with a date but the text that follows
        # is an amount (no description), e.g. "12/01 $64,163.52 12/11 ...".
        # Detect by checking whether the text group begins with an amount token.
        _BALANCE_ROW_RE = re.compile(r"^\$?\d[\d,]*\.\d{2}\b")
 
        lines = [re.sub(r"\s+", " ", l).strip()
                 for l in str(text).splitlines() if l.strip()]
 
        # Buffer holds (date, full_text) for transactions without a section yet
        buf: list[tuple[str, str]] = []
        merged: list[tuple[str, str, str]] = []  # (date, text, section)
 
        pending_date = ""
        pending_text = ""
        current_section = ""

        def _flush_pending():
            if pending_date and pending_text.strip():
                buf.append((pending_date, pending_text.strip()))
 
        def _flush_buf(section: str):
            for d, t in buf:
                merged.append((d, t, section))
            buf.clear()
 
        for line in lines:
            if line.startswith("*"):
                continue
 
            upper = line.upper()
 
            if _STOP_RE.match(upper):
                break
 
            # Section header — retroactively assign to buffered transactions
            found_section = ""
            for label, sec in _SECTION_MAP.items():
                if upper.startswith(label):
                    found_section = sec
                    break
 
            if found_section:
                _flush_pending()
                pending_date = ""
                pending_text = ""
                # Continuation headers (e.g. "DEPOSITS AND ADDITIONS (continued)")
                # appear at the TOP of their page, before the transactions that
                # belong to them.  At that point buf is empty, so the retroactive
                # flush is a no-op and current_section carries the right label for
                # the transactions that follow.  For first-occurrence headers the
                # buf already holds those transactions, so we flush retroactively.
                flush_section = current_section if (buf and current_section) else found_section
                _flush_buf(flush_section)
                current_section = found_section
                continue
 
            dm = _date_re.match(line)
            if dm:
                if _BALANCE_ROW_RE.match(dm.group(2)):
                    continue  # daily ending balance row — not a transaction
                _flush_pending()
                pending_date = dm.group(1)
                pending_text = dm.group(2)
            elif _SKIP_LINE_RE.match(line):
                pass  # "Total ...", "Monthly Service Fee ...", etc. — don't corrupt pending amount
            elif pending_date:
                pending_text += " " + line
 
        _flush_pending()
        # Remaining buffered items: use current_section when known, else keyword fallback
        for d, t in buf:
            sec = current_section if current_section else ("Credit" if _CREDIT_KW.search(t) else "Debit")
            merged.append((d, t, sec))
        buf.clear()
 
        # ── Parse each merged transaction ──────────────────────────────────
        rows: list[dict] = []
        for date, full_text, section in merged:
            amounts_found = list(_money_re.finditer(full_text))
            if not amounts_found:
                continue
            amounts = [abs(clean_money(m.group(0))) for m in amounts_found]
            amounts = [a for a in amounts if a > 0]
            if not amounts:
                continue
 
            amount = amounts[-1]
            desc   = re.sub(r"\s{2,}", " ", _money_re.sub("", full_text)).strip()
 
            debit  = amount if section == "Debit"  else 0.0
            credit = amount if section == "Credit" else 0.0
 
            rows.append({
                "Date":        date,
                "Description": desc,
                "Debit":       round(debit, 2),
                "Credit":      round(credit, 2),
                "Amount":      round(credit - debit, 2),
                "Balance":     0.0,
                "Section":     section,
            })
 
        return pd.DataFrame(rows)
 
    @classmethod
    def count_nsf(cls, text: str) -> int:
        section_match = re.search(
            r"Items\s+returned\s+unpaid(.*?)(?:\n\n|\Z)",
            text,
            re.IGNORECASE | re.DOTALL,
        )
        if not section_match:
            return 0
 
        section_text = section_match.group(1)
        return len(re.findall(r"^\s*\d{1,2}/\d{1,2}", section_text, re.MULTILINE))