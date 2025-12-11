# app/models/ncm.py

from sqlalchemy import Column, Integer, String, Boolean, Numeric
from app.core.database import Base
from sqlalchemy.orm import relationship


class Ncm(Base):
    __tablename__ = "ncm"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(10), unique=True, index=True, nullable=False)  # ex.: "39269090"
    description = Column(String(500), nullable=False)

    # Flags de tratamento administrativo (vamos refinar depois se precisar)
    requires_li = Column(Boolean, default=False)
    anvisa = Column(Boolean, default=False)
    anatel = Column(Boolean, default=False)
    inmetro = Column(Boolean, default=False)
    mapa = Column(Boolean, default=False)
    army = Column(Boolean, default=False)
    antidumping = Column(Boolean, default=False)

    # Alíquotas (opcional por enquanto)
    ii = Column(Numeric(5, 2), nullable=True)
    ipi = Column(Numeric(5, 2), nullable=True)
    pis = Column(Numeric(5, 2), nullable=True)
    cofins = Column(Numeric(5, 2), nullable=True)

    # Relação com Product
    products = relationship("Product", back_populates="ncm")
