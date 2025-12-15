from __future__ import annotations

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_decision import ProductDecision
from app.schemas.decision import ProductDecisionCreate


def create_product_decision(db: Session, product_id: int, payload: ProductDecisionCreate) -> ProductDecision:
    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise ValueError("Product not found")

    decision = ProductDecision(
        product_id=product_id,
        decision=payload.decision,
        reason=payload.reason,
        decided_by=payload.decided_by,
    )
    db.add(decision)
    db.commit()
    db.refresh(decision)
    return decision


def get_latest_product_decision(db: Session, product_id: int) -> ProductDecision | None:
    return (
        db.query(ProductDecision)
        .filter(ProductDecision.product_id == product_id)
        .order_by(ProductDecision.created_at.desc())
        .first()
    )
