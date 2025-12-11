# app/schemas/market_data.py

from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


class MarketDataBase(BaseModel):
    price_average_brl: Optional[Decimal] = None
    sales_per_day: Optional[int] = None
    sales_per_month: Optional[int] = None
    visits: Optional[int] = None

    ranking_position: Optional[int] = None
    full_ratio: Optional[Decimal] = None
    competitor_count: Optional[int] = None
    listing_age_days: Optional[int] = None
    avg_reviews: Optional[Decimal] = None


class MarketDataCreate(MarketDataBase):
    """
    Usado para criar/atualizar dados de mercado de um produto.
    """
    pass


class MarketDataOut(MarketDataBase):
    id: int
    product_id: int

    model_config = ConfigDict(from_attributes=True)
