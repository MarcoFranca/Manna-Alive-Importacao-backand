from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.decision import ProductDecisionCreate, ProductDecisionOut
from app.services.decisions import create_product_decision, get_latest_product_decision

router = APIRouter(prefix="/products", tags=["Product Decisions"])


@router.post("/{product_id}/decisions", response_model=ProductDecisionOut)
def post_decision(product_id: int, payload: ProductDecisionCreate, db: Session = Depends(get_db)) -> ProductDecisionOut:
    try:
        decision = create_product_decision(db, product_id=product_id, payload=payload)
        return ProductDecisionOut.model_validate(decision)
    except ValueError as e:
        msg = str(e).lower()
        if "not found" in msg:
            raise HTTPException(status_code=404, detail=str(e))
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{product_id}/decisions/latest", response_model=ProductDecisionOut | None)
def get_latest_decision(product_id: int, db: Session = Depends(get_db)) -> ProductDecisionOut | None:
    decision = get_latest_product_decision(db, product_id=product_id)
    return ProductDecisionOut.model_validate(decision) if decision else None
