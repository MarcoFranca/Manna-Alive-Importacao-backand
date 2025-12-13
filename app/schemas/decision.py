from __future__ import annotations

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


DecisionKind = Literal["approve_test", "approve_import", "reject", "needs_data"]


class ProductDecisionCreate(BaseModel):
    decision: DecisionKind
    reason: str = Field(min_length=3, max_length=2000)
    decided_by: Optional[str] = Field(default=None, max_length=120)


class ProductDecisionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    decision: DecisionKind
    reason: str
    decided_by: Optional[str]
    created_at: datetime
