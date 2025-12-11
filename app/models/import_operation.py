# app/models/import_operation.py

from datetime import datetime, date
from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    Date,
    DateTime,
    Numeric,
    ForeignKey,
)
from app.core.database import Base


class ImportOperation(Base):
    __tablename__ = "import_operations"

    id = Column(Integer, primary_key=True, index=True)
    simulation_id = Column(Integer, ForeignKey("import_simulations.id"), nullable=True)

    operation_date = Column(Date, nullable=False, default=date.today)
    courier = Column(String(100), nullable=True)           # DHL, FedEx, etc.
    tracking_code = Column(String(100), nullable=True)

    customs_value_usd = Column(Numeric(14, 4), nullable=False)
    total_taxes_brl = Column(Numeric(14, 4), nullable=True)
    total_cost_brl = Column(Numeric(14, 4), nullable=True)
    total_units = Column(Integer, nullable=False)

    notes = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
