from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class ProductDecision(Base):
    __tablename__ = "product_decisions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    product_id: Mapped[int] = mapped_column(Integer, ForeignKey("products.id"), index=True, nullable=False)

    # approve_test | approve_import | reject | needs_data
    decision: Mapped[str] = mapped_column(String(32), nullable=False, index=True)

    # opcional: por enquanto manual; depois pode vir do login
    decided_by: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)

    reason: Mapped[str] = mapped_column(Text, nullable=False)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    product = relationship("Product", back_populates="decisions")
