# app/models/product_evaluation.py

from datetime import datetime
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Boolean,
    Numeric,
    DateTime,
    ForeignKey,
)
from sqlalchemy.orm import relationship
from app.core.database import Base


class ProductEvaluation(Base):
    __tablename__ = "product_evaluations"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False)

    # Mercado
    demand_score = Column(Integer, nullable=True)      # 1–5
    competition_score = Column(Integer, nullable=True) # 1–5
    price_score = Column(Integer, nullable=True)       # 1–5
    market_score = Column(Integer, nullable=True)      # agregada

    # Logística
    logistic_score = Column(Integer, nullable=True)    # 1–5

    # Finanças
    financial_score = Column(Integer, nullable=True)   # 1–5
    estimated_margin_pct = Column(Numeric(5, 2), nullable=True)

    # Regulatório (texto simples por enquanto)
    regulatory_status = Column(String(50), nullable=True)
    # Ex.: "simplified_allowed", "blocked_li", etc.

    overall_score = Column(Integer, nullable=True)
    approved_for_test = Column(Boolean, default=False)

    comments = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    product = relationship("Product", back_populates="evaluations")
