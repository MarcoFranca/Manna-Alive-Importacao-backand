from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field
from app.schemas.decision import ProductDecisionOut


PillarStatus = Literal["green", "yellow", "red", "unknown"]
Decision = Literal["approve", "reject", "needs_data"]
ScenarioKind = Literal["base", "conservative", "optimistic"]


class Metric(BaseModel):
    key: str
    label: str
    value: Optional[float] = None
    unit: Optional[str] = None
    help: Optional[str] = None


class Pillar(BaseModel):
    key: Literal["market", "unit_economics", "operations", "risk"]
    title: str
    status: PillarStatus
    summary: str
    next_action: Optional[str] = None
    metrics: list[Metric] = Field(default_factory=list)


class CompletenessItem(BaseModel):
    key: str
    label: str
    is_complete: bool


class Completeness(BaseModel):
    percent: int
    items: list[CompletenessItem] = Field(default_factory=list)
    missing: list[str] = Field(default_factory=list)


class Blocker(BaseModel):
    key: str
    title: str
    reason: str


class ScenarioInput(BaseModel):
    kind: ScenarioKind
    name: str
    quantity: int
    exchange_rate: float
    freight_total_usd: float
    insurance_total_usd: float
    target_sale_price_brl: float


class ScenarioResult(BaseModel):
    kind: ScenarioKind
    name: str

    quantity: int
    exchange_rate: float

    fob_total_usd: float
    freight_total_usd: float
    insurance_total_usd: float
    customs_value_usd: float

    estimated_total_cost_usd: float
    estimated_total_cost_brl: float
    unit_cost_brl: float

    target_sale_price_brl: float
    estimated_margin_pct: float

    approved: bool
    reason: Optional[str] = None


class EvaluationHeader(BaseModel):
    product_id: int
    product_name: str
    category: Optional[str] = None
    latest_decision: Optional[ProductDecisionOut] = None

    has_market_data: bool
    has_ncm: bool
    has_supplier: bool
    has_dimensions: bool

    created_at: datetime
    updated_at: datetime


class ProductEvaluationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=False)

    header: EvaluationHeader
    completeness: Completeness

    decision: Decision
    decision_reason: str

    pillars: list[Pillar] = Field(default_factory=list)
    scenarios: list[ScenarioResult] = Field(default_factory=list)

    blockers: list[Blocker] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)
