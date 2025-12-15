# app/services/triage.py

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from sqlalchemy import and_, func
from sqlalchemy.orm import Session, selectinload

from app.models.import_simulation import ImportSimulation
from app.models.product import Product
from app.models.product_market_data import ProductMarketData
from app.schemas.triage import (
    ProductTriageOut,
    ScoreSummaryOut,
    SimulationSummaryOut,
    TriageStatus,
)
from app.services.scoring import compute_product_score, compute_product_score_v2


@dataclass(frozen=True)
class _Flags:
    has_fob: bool
    has_freight: bool
    has_market: bool
    has_sim: bool


def _status_and_action(flags: _Flags) -> Tuple[TriageStatus, str, int]:
    """Retorna (status, next_action, priority_rank). Menor priority_rank = avaliar antes."""
    if not flags.has_fob or not flags.has_freight:
        if not flags.has_fob:
            return "needs_costs", "Preencher FOB (custo base do fornecedor)", 30
        return "needs_costs", "Preencher frete (estimativa para simulação)", 20

    if not flags.has_market:
        return "needs_market", "Preencher dados de mercado (Avant Pro / ML)", 10

    if not flags.has_sim:
        return "needs_simulation", "Rodar simulação (cenários e margem)", 5

    return "ready", "Avaliar e decidir (aprovar / reprovar)", 0


def _build_alerts(product: Product, flags: _Flags) -> List[str]:
    alerts: List[str] = []

    if not flags.has_fob:
        alerts.append("Sem FOB: custo base do fornecedor não informado.")
    if not flags.has_freight:
        alerts.append("Sem frete: simulação tende a ficar imprecisa.")
    if not flags.has_market:
        alerts.append("Sem dados de mercado: demanda/concorrência não avaliadas.")
    if not flags.has_sim:
        alerts.append("Sem simulação: margem ainda não validada.")

    # riscos clássicos
    if product.is_famous_brand and not product.has_brand_authorization:
        alerts.append("Risco alto: marca famosa sem autorização (PI / apreensão).")
    if product.fragile:
        alerts.append("Atenção: produto frágil (risco logístico).")

    try:
        weight = float(product.weight_kg or 0)
        if weight > 5:
            alerts.append("Atenção: produto pesado (>5kg) — ruim para simplificada.")
        elif weight > 2:
            alerts.append("Atenção: peso moderado (>2kg) — impacta frete.")
    except Exception:
        pass

    if product.ncm_id is None:
        alerts.append("Sem NCM definido: pode travar decisão/compliance.")

    return alerts


def _get_last_simulations(db: Session) -> Dict[int, ImportSimulation]:
    """Map product_id -> última simulação (por created_at), evitando N+1."""
    subq = (
        db.query(
            ImportSimulation.product_id.label("product_id"),
            func.max(ImportSimulation.created_at).label("max_created"),
        )
        .group_by(ImportSimulation.product_id)
        .subquery()
    )

    rows = (
        db.query(ImportSimulation)
        .join(
            subq,
            and_(
                ImportSimulation.product_id == subq.c.product_id,
                ImportSimulation.created_at == subq.c.max_created,
            ),
        )
        .all()
    )

    return {r.product_id: r for r in rows}


def _get_market_map(db: Session) -> Dict[int, ProductMarketData]:
    rows = db.query(ProductMarketData).all()
    return {r.product_id: r for r in rows}


def build_products_triage(
    db: Session,
    *,
    limit: int = 200,
    include_score: bool = True,
    include_notes: bool = False,
) -> List[ProductTriageOut]:
    """Monta a lista de triagem agregada.

    - include_score: calcula total_score/classificação (usa compute_product_score)
    - include_notes: inclui notas do score (texto), útil para debug/UX
    """

    products: List[Product] = (
        db.query(Product)
        .options(selectinload(Product.market_data))
        .order_by(Product.created_at.desc())
        .limit(limit)
        .all()
    )

    last_sim_map = _get_last_simulations(db)
    market_map = _get_market_map(db)

    out: List[ProductTriageOut] = []

    for p in products:
        has_fob = p.fob_price_usd is not None
        has_freight = p.freight_usd is not None
        has_market = p.id in market_map
        has_sim = p.id in last_sim_map

        flags = _Flags(
            has_fob=has_fob,
            has_freight=has_freight,
            has_market=has_market,
            has_sim=has_sim,
        )

        status, next_action, priority_rank = _status_and_action(flags)
        alerts = _build_alerts(p, flags)

        last_sim = last_sim_map.get(p.id)
        last_sim_out: Optional[SimulationSummaryOut] = (
            SimulationSummaryOut.model_validate(last_sim) if last_sim else None
        )

        score_out: Optional[ScoreSummaryOut] = None
        if include_score:
            try:
                result, notes, reasons = compute_product_score_v2(db, p.id)
                market = market_map.get(p.id)

                score_out = ScoreSummaryOut(
                    total_score=result["total_score"],
                    classification=result["classification"],
                    demand_score=result["demand_score"],
                    competition_score=result["competition_score"],
                    margin_score=result["margin_score"],
                    risk_score=result["risk_score"],
                    sales_per_day=result.get("sales_per_day"),
                    sales_per_month=result.get("sales_per_month"),
                    visits=result.get("visits"),
                    competitor_count=(market.competitor_count if market else None),
                    full_ratio=(market.full_ratio if market else None),
                    price_average_brl=result.get("price_average_brl"),
                    estimated_margin_pct=result.get("estimated_margin_pct"),
                    has_latest_simulation=result.get("has_latest_simulation", False),
                    reasons=reasons,
                    notes=(" ".join(notes) if include_notes else None),
                )
            except Exception:
                score_out = None

        out.append(
            ProductTriageOut(
                product_id=p.id,
                product_name=p.name,
                category=p.category,
                created_at=p.created_at,
                fob_price_usd=p.fob_price_usd,
                freight_usd=p.freight_usd,
                insurance_usd=p.insurance_usd,
                has_fob=has_fob,
                has_freight=has_freight,
                has_market_data=has_market,
                has_latest_simulation=has_sim,
                status=status,
                next_action=next_action,
                priority_rank=priority_rank,
                last_simulation=last_sim_out,
                score=score_out,
                alerts=alerts,
            )
        )

    # Ordenação estratégica: prioridade + score + mais recente
    def _sort_key(x: ProductTriageOut):
        score = x.score.total_score if x.score else -1
        return (x.priority_rank, -score, -(x.created_at.timestamp() if x.created_at else 0))

    out.sort(key=_sort_key)
    return out
