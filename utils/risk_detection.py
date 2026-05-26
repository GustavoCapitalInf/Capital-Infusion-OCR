"""
utils/risk_detection.py
-----------------------
NSF detection, risk scoring, and underwriting note generation.
"""

from __future__ import annotations


# ---------------------------------------------------------------------------
# NSF / Overdraft Detection
# ---------------------------------------------------------------------------

import re as _re

# Strict patterns — word-boundary aware, no substring false positives.
# "overdraft fee" matches Wells Fargo's "Overdraft Fee for a Transaction…"
# but NOT generic boilerplate that merely mentions overdraft protection.
_NSF_PATTERNS = _re.compile(
    r"\bnsf\b"
    r"|nsf\s+fee"
    r"|non.sufficient\s+funds"
    r"|insufficient\s+funds"
    r"|overdraft\s+fee"
    r"|returned\s+item\s+fee"
    r"|return\s+fee"
    r"|items?\s+returned\s+unpaid"
    r"|returned\s+unpaid",
    _re.IGNORECASE,
)


def detect_nsf(description: str) -> bool:
    """Return True if the transaction description indicates an NSF/overdraft event."""
    return bool(_NSF_PATTERNS.search(str(description)))


# ---------------------------------------------------------------------------
# Risk Scoring
# ---------------------------------------------------------------------------

def calculate_risk_level(
    avg_revenue: float,
    avg_debits: float,
    nsf_count: int,
    funding_detected: bool,
) -> tuple[float, str]:
    """
    Score a business on underwriting risk.

    Returns
    -------
    (risk_score, risk_level)
        risk_level is one of: "Low Risk" | "Medium Risk" | "High Risk"
    """
    risk_score = 0.0

    if avg_revenue < 15_000:
        risk_score += 30

    debit_ratio = avg_debits / avg_revenue if avg_revenue > 0 else 0
    if debit_ratio > 0.85:
        risk_score += 30

    if nsf_count >= 3:
        risk_score += 25

    if funding_detected:
        risk_score += 15

    if risk_score < 30:
        risk_level = "Low Risk"
    elif risk_score < 60:
        risk_level = "Medium Risk"
    else:
        risk_level = "High Risk"

    return risk_score, risk_level


# ---------------------------------------------------------------------------
# Underwriting Notes
# ---------------------------------------------------------------------------

def generate_notes(
    total_revenue: float,
    total_debits: float,
    total_cash_flow: float,
    nsf_count: int,
    funding_detected: bool,
    funders: list[str] | None = None,
    withholding_rate: float = 0.0,
) -> list[str]:
    """Generate plain-English underwriting bullet points."""
    notes: list[str] = []

    # Revenue
    notes.append(
        "Strong monthly revenue detected."
        if total_revenue >= 100_000
        else "Monthly revenue is on the lower side."
    )

    # Cash flow
    notes.append(
        "Positive cash flow detected."
        if total_cash_flow > 0
        else "Negative cash flow detected — debits exceed credits."
    )

    # NSF
    if nsf_count > 0:
        notes.append(f"{nsf_count} NSF / overdraft transaction(s) detected.")
    else:
        notes.append("No NSF activity detected.")

    # Existing funding
    if funding_detected:
        suffix = f": {', '.join(funders)}" if funders else "."
        notes.append(f"Existing MCA/loan funding detected{suffix}")
    else:
        notes.append("No existing funding detected.")

    # Withholding rate
    notes.append(f"Estimated withholding rate: {withholding_rate:.2f}%.")

    return notes
