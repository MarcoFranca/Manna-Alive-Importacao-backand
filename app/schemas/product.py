# app/schemas/product.py

from datetime import datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, HttpUrl, ConfigDict


class ProductBase(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None

    reference_marketplace_url: Optional[HttpUrl] = None
    supplier_url: Optional[HttpUrl] = None

    supplier_id: Optional[int] = None
    ncm_id: Optional[int] = None

    weight_kg: Optional[Decimal] = None
    length_cm: Optional[Decimal] = None
    width_cm: Optional[Decimal] = None
    height_cm: Optional[Decimal] = None
    fragile: Optional[bool] = False

    fob_price_usd: Optional[Decimal] = None
    freight_usd: Optional[Decimal] = None
    insurance_usd: Optional[Decimal] = None

    is_famous_brand: Optional[bool] = False
    has_brand_authorization: Optional[bool] = False


class ProductCreate(ProductBase):
    name: str


class ProductUpdate(ProductBase):
    pass


class ProductOut(ProductBase):
    id: int
    created_at: datetime
    updated_at: datetime

    # Pydantic v2:
    model_config = ConfigDict(from_attributes=True)
