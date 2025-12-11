# app/models/import_simulation.py

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    Boolean,
    Numeric,
    String,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ImportSimulation(Base):
    __tablename__ = "import_simulations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    quantity = Column(Integer, nullable=False)
    exchange_rate = Column(Numeric(12, 4), nullable=False)  # câmbio da simulação

    # Valores em USD
    fob_total_usd = Column(Numeric(14, 4), nullable=False)
    freight_total_usd = Column(Numeric(14, 4), nullable=False)
    insurance_total_usd = Column(Numeric(14, 4), nullable=True)
    customs_value_usd = Column(Numeric(14, 4), nullable=False)  # FOB + frete + seguro

    estimated_total_cost_usd = Column(Numeric(14, 4), nullable=False)
    estimated_total_cost_brl = Column(Numeric(14, 4), nullable=False)
    unit_cost_brl = Column(Numeric(14, 4), nullable=False)

    target_sale_price_brl = Column(Numeric(14, 4), nullable=False)
    estimated_margin_pct = Column(Numeric(5, 2), nullable=False)

    approved = Column(Boolean, default=False)
    reason = Column(String(255), nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="simulations")
