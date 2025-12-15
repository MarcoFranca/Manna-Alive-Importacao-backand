# app/schemas/triage.py

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict

from app.schemas.decision import ProductDecisionOut


TriageStatus = Literal[
    "ready",
    "needs_simulation",
    "needs_market",
    "needs_costs",
]


class SimulationSummaryOut(BaseModel):
    id: int
    created_at: datetime
    approved: bool

    unit_cost_brl: Decimal
    target_sale_price_brl: Decimal
    estimated_margin_pct: Decimal

    model_config = ConfigDict(from_attributes=True)


class ScoreSummaryOut(BaseModel):
    total_score: int
    classification: str

    demand_score: int
    competition_score: int
    margin_score: int
    risk_score: int

    sales_per_day: Optional[int] = None
    sales_per_month: Optional[int] = None
    visits: Optional[int] = None
    competitor_count: Optional[int] = None
    full_ratio: Optional[Decimal] = None
    price_average_brl: Optional[Decimal] = None
    estimated_margin_pct: Optional[Decimal] = None
    has_latest_simulation: bool = False

    reasons: List[str] = []
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=False)


class ProductTriageOut(BaseModel):
    product_id: int
    product_name: str
    category: Optional[str] = None
    created_at: datetime

    fob_price_usd: Optional[Decimal] = None
    freight_usd: Optional[Decimal] = None
    insurance_usd: Optional[Decimal] = None

    has_fob: bool
    has_freight: bool
    has_market_data: bool
    has_latest_simulation: bool

    status: TriageStatus
    next_action: str
    priority_rank: int

    last_simulation: Optional[SimulationSummaryOut] = None
    score: Optional[ScoreSummaryOut] = None

    # NOVO: última decisão registrada
    latest_decision: Optional[ProductDecisionOut] = None

    alerts: List[str] = []

    model_config = ConfigDict(from_attributes=False)
