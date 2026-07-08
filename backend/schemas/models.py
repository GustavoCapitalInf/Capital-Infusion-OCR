from __future__ import annotations
from typing import Any
from pydantic import BaseModel


class StatementResult(BaseModel):
    filename: str
    statement_date: str | None
    period_start: str | None = None
    period_end: str | None = None
    credits: float
    debits: float
    cash_flow: float
    lender_debits: float
    lender_credits: float
    withholding_rate: float
    nsf_count: int
    loan_count: int
    pos_count: int
    avg_daily_balance: float
    charges_only: float


class Totals(BaseModel):
    credits: float
    debits: float
    cash_flow: float
    lender_debits: float
    lender_credits: float
    true_revenue: float
    nsf_count: int
    loan_count: int
    pos_count: int
    avg_daily_balance: float
    withholding_rate: float


class LenderRow(BaseModel):
    lender: str
    keyword: str
    amount: float
    monthly_amount: float | None = None
    statement: str


class FlaggedRow(BaseModel):
    keyword: str
    line: str
    amount: float
    statement: str


class RiskResult(BaseModel):
    score: float
    level: str
    notes: list[str]


class UploadResponse(BaseModel):
    session_id: str
    statements: list[StatementResult]
    totals: Totals
    averages: Totals
    lenders: list[LenderRow]
    flagged: list[FlaggedRow]
    risk: RiskResult
    transactions: list[dict[str, Any]]
