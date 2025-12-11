# app/models/product.py

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


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)

    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(String(100), nullable=True)  # ex.: "PET", "Casa e cozinha"

    reference_marketplace_url = Column(String(500), nullable=True)
    supplier_url = Column(String(500), nullable=True)

    # Relacionamentos
    supplier_id = Column(Integer, ForeignKey("suppliers.id"), nullable=True)
    ncm_id = Column(Integer, ForeignKey("ncm.id"), nullable=True)

    # Dados físicos
    weight_kg = Column(Numeric(10, 3), nullable=True)
    length_cm = Column(Numeric(10, 2), nullable=True)
    width_cm = Column(Numeric(10, 2), nullable=True)
    height_cm = Column(Numeric(10, 2), nullable=True)
    fragile = Column(Boolean, default=False)

    # Dados de preço base
    fob_price_usd = Column(Numeric(12, 4), nullable=True)   # preço unitário FOB
    freight_usd = Column(Numeric(12, 4), nullable=True)     # frete unitário estimado
    insurance_usd = Column(Numeric(12, 4), nullable=True)

    # Marca / propriedade intelectual
    is_famous_brand = Column(Boolean, default=False)
    has_brand_authorization = Column(Boolean, default=False)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(
        DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow,
    )

    # Relações
    supplier = relationship("Supplier", back_populates="products")
    ncm = relationship("Ncm", back_populates="products")
    evaluations = relationship("ProductEvaluation", back_populates="product")
    simulations = relationship(
        "ImportSimulation",
        back_populates="product",
        cascade="all, delete-orphan",
    )
    market_data = relationship(
        "ProductMarketData",
        back_populates="product",
        uselist=False,
        cascade="all, delete-orphan",
    )

