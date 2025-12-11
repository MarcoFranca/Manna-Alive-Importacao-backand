# app/schemas/score.py

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class ProductScoreOut(BaseModel):
    product_id: int
    product_name: str

    total_score: int

    demand_score: int
    competition_score: int
    margin_score: int
    risk_score: int

    classification: str          # "campeao", "bom", "arriscado", "descartar"
    notes: str

    # opcional: alguns dados de apoio
    sales_per_day: Optional[int] = None
    sales_per_month: Optional[int] = None
    visits: Optional[int] = None
    price_average_brl: Optional[Decimal] = None
    estimated_margin_pct: Optional[Decimal] = None
    has_latest_simulation: bool = False

    model_config = ConfigDict(from_attributes=False)
