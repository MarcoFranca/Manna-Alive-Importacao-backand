# app/models/product_market_data.py

from sqlalchemy import Column, Integer, Numeric, ForeignKey
from sqlalchemy.orm import relationship

from app.core.database import Base


class ProductMarketData(Base):
    """
    Guarda dados coletados manualmente do Avant Pro / Mercado Livre
    para um produto específico.
    """
    __tablename__ = "product_market_data"

    id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"), nullable=False, unique=True)

    # Preço médio atual de venda no ML
    price_average_brl = Column(Numeric(12, 2), nullable=True)

    # Demanda
    sales_per_day = Column(Integer, nullable=True)
    sales_per_month = Column(Integer, nullable=True)
    visits = Column(Integer, nullable=True)

    # Concorrência
    ranking_position = Column(Integer, nullable=True)   # posição do anúncio líder
    full_ratio = Column(Numeric(5, 2), nullable=True)  # % de vendedores FULL (0–100)
    competitor_count = Column(Integer, nullable=True)   # nº de concorrentes relevantes
    listing_age_days = Column(Integer, nullable=True)   # idade do principal anúncio líder em dias
    avg_reviews = Column(Numeric(5, 2), nullable=True)  # média de avaliações dos top sellers

    # Relação com produto
    product = relationship("Product", back_populates="market_data")
