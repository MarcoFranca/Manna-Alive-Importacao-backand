# app/schemas/simulation.py

from decimal import Decimal
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict


class SimulationInput(BaseModel):
    quantity: int
    exchange_rate: Optional[Decimal] = None  # <-- AGORA opcional
    target_sale_price_brl: Decimal

    freight_total_usd: Optional[Decimal] = None
    insurance_total_usd: Optional[Decimal] = None


class SimulationOut(BaseModel):
    # Pydantic v2: substitui o antigo orm_mode = True
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int

    quantity: int
    exchange_rate: Decimal

    fob_total_usd: Decimal
    freight_total_usd: Decimal
    insurance_total_usd: Decimal
    customs_value_usd: Decimal

    estimated_total_cost_usd: Decimal
    estimated_total_cost_brl: Decimal
    unit_cost_brl: Decimal

    target_sale_price_brl: Decimal
    estimated_margin_pct: Decimal

    approved: bool
    reason: Optional[str] = None
    created_at: datetime
