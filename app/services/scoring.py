# app/services/scoring.py

from decimal import Decimal
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_market_data import ProductMarketData
from app.models.import_simulation import ImportSimulation


def _normalize(value: Optional[Decimal | float | int], min_val: float, max_val: float) -> float:
    if value is None:
        return 0.0
    v = float(value)
    if v <= min_val:
        return 0.0
    if v >= max_val:
        return 1.0
    return (v - min_val) / (max_val - min_val)


def _get_latest_simulation(db: Session, product_id: int) -> Optional[ImportSimulation]:
    return (
        db.query(ImportSimulation)
        .filter(ImportSimulation.product_id == product_id)
        .order_by(ImportSimulation.created_at.desc())
        .first()
    )


def _score_to_label(total_score: float) -> str:
    if total_score >= 80:
        return "campeao"
    if total_score >= 60:
        return "bom"
    if total_score >= 40:
        return "arriscado"
    return "descartar"


def _make_reasons(
    *,
    product: Product,
    market: Optional[ProductMarketData],
    simulation: Optional[ImportSimulation],
    result: dict,
) -> list[str]:
    """Bullets curtos, orientados a decisão (UX)."""
    reasons: list[str] = []

    classification = result.get("classification")
    total = result.get("total_score")

    # 1) classificação + score
    if isinstance(total, int) and isinstance(classification, str):
        if classification == "campeao":
            reasons.append(f"Campeão ({total}/100): candidato forte para priorizar agora.")
        elif classification == "bom":
            reasons.append(f"Bom ({total}/100): vale avaliação completa antes de descartar.")
        elif classification == "arriscado":
            reasons.append(f"Arriscado ({total}/100): só avance se o cenário conservador fechar bem.")
        else:
            reasons.append(f"Fraco ({total}/100): só avance se houver tese/estratégia específica.")

    # 2) demanda
    if market and market.sales_per_day is not None:
        reasons.append(f"Demanda: ~{market.sales_per_day} vendas/dia (sinal de giro).")
    elif market:
        reasons.append("Demanda: dados parciais — complete vendas/dia para melhorar a decisão.")
    else:
        reasons.append("Demanda: sem dados de mercado — o sistema não consegue confirmar giro.")

    # 3) concorrência
    if market:
        parts = []
        if market.competitor_count is not None:
            parts.append(f"{market.competitor_count} concorrentes")
        if market.full_ratio is not None:
            parts.append(f"{market.full_ratio}% FULL")
        if parts:
            reasons.append("Concorrência: " + " • ".join(parts) + ".")
        else:
            reasons.append("Concorrência: dados parciais — complete concorrentes/FULL.")
    else:
        reasons.append("Concorrência: sem dados de mercado — risco de entrar em guerra de preço.")

    # 4) margem (simulação)
    if simulation and simulation.estimated_margin_pct is not None:
        m = round(float(simulation.estimated_margin_pct), 1)
        reasons.append(f"Margem (simulação): ~{m}% ({'aprovada' if simulation.approved else 'reprovada'}).")
    else:
        reasons.append("Margem: sem simulação — rode cenários para confirmar viabilidade.")

    # 5) risco (só se houver sinais)
    risk_flags: list[str] = []
    try:
        weight_kg = float(product.weight_kg or 0)
        if weight_kg > 5:
            risk_flags.append(">5kg (ruim p/ simplificada)")
        elif weight_kg > 2:
            risk_flags.append(">2kg (frete pesa)")
    except Exception:
        pass

    if getattr(product, "fragile", False):
        risk_flags.append("frágil (risco logístico)")
    if getattr(product, "is_famous_brand", False) and not getattr(product, "has_brand_authorization", False):
        risk_flags.append("marca famosa sem autorização (PI)")

    if risk_flags:
        reasons.append("Risco: " + " • ".join(risk_flags) + ".")

    # limitar para UX: 4 a 5 bullets no máximo
    return reasons[:5]


def compute_product_score(db: Session, product_id: int) -> Tuple[dict, list[str]]:
    """
    Mantido para compatibilidade.
    Retorna:
      - dict com sub-scores e total
      - lista de notas / motivos em texto
    """
    notes: list[str] = []

    product: Optional[Product] = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError("Produto não encontrado.")

    market: Optional[ProductMarketData] = (
        db.query(ProductMarketData)
        .filter(ProductMarketData.product_id == product_id)
        .first()
    )
    simulation: Optional[ImportSimulation] = _get_latest_simulation(db, product_id)

    # 1) DEMANDA
    sales_per_day = market.sales_per_day if market else None
    sales_per_month = market.sales_per_month if market else None
    visits = market.visits if market else None

    sales_day_score = _normalize(sales_per_day or 0, 0, 150) * 100
    sales_month_score = _normalize(sales_per_month or 0, 0, 4000) * 100
    visits_score = _normalize(visits or 0, 0, 10000) * 100

    demand_score = (0.6 * sales_day_score + 0.3 * sales_month_score + 0.1 * visits_score)

    if sales_per_day:
        notes.append(f"Demanda: ~{sales_per_day} vendas/dia.")
    if not market:
        notes.append("Sem dados de mercado cadastrados; demanda considerada neutra/baixa.")

    # 2) CONCORRÊNCIA
    full_ratio = market.full_ratio if market else None
    competitor_count = market.competitor_count if market else None
    ranking_position = market.ranking_position if market else None

    full_penalty = _normalize(full_ratio or 0, 0, 80) * 100
    competitors_penalty = _normalize(competitor_count or 0, 0, 30) * 100
    ranking_penalty = _normalize(ranking_position or 50000, 1, 50000) * 100

    competition_score = max(
        0.0,
        100.0 - (0.4 * full_penalty + 0.4 * competitors_penalty + 0.2 * ranking_penalty),
    )

    if full_ratio is not None:
        notes.append(f"Concorrência FULL: ~{full_ratio}% dos principais anúncios.")
    if competitor_count is not None:
        notes.append(f"Concorrentes relevantes: ~{competitor_count}.")
    if ranking_position is not None:
        notes.append(f"Ranking aproximado do líder: {ranking_position}.")

    # 3) MARGEM
    margin_pct = simulation.estimated_margin_pct if simulation else None
    margin_score = _normalize(margin_pct or 0, 10, 60) * 100

    if margin_pct is not None:
        notes.append(f"Margem estimada na última simulação: {round(float(margin_pct), 1)}%.")
    else:
        notes.append("Sem simulação de importação cadastrada; margem considerada baixa.")

    # 4) RISCO
    risk_score = 100.0

    weight_kg = float(product.weight_kg or 0)
    if weight_kg > 5:
        risk_score -= 30
        notes.append("Produto pesado (>5kg) — ruim para Importação Simplificada.")
    elif weight_kg > 2:
        risk_score -= 15
        notes.append("Produto moderadamente pesado (>2kg).")

    if product.fragile:
        risk_score -= 15
        notes.append("Produto frágil — risco logístico maior.")

    if product.is_famous_brand and not product.has_brand_authorization:
        risk_score -= 40
        notes.append("Marca famosa sem autorização — alto risco de PI / apreensão.")

    risk_score = max(0.0, min(100.0, risk_score))

    # 5) SCORE FINAL
    total_score = (
        0.40 * demand_score +
        0.25 * competition_score +
        0.25 * margin_score +
        0.10 * risk_score
    )

    classification = _score_to_label(total_score)

    if classification == "campeao":
        notes.append("Produto classificado como CAMPEÃO (score >= 80).")
    elif classification == "bom":
        notes.append("Produto VIÁVEL para teste (score entre 60 e 79).")
    elif classification == "arriscado":
        notes.append("Produto ARRISCADO (score entre 40 e 59).")
    else:
        notes.append("Produto RECOMENDADO PARA DESCARTE (score < 40).")

    result = {
        "demand_score": int(round(demand_score)),
        "competition_score": int(round(competition_score)),
        "margin_score": int(round(margin_score)),
        "risk_score": int(round(risk_score)),
        "total_score": int(round(total_score)),
        "classification": classification,
        "sales_per_day": sales_per_day,
        "sales_per_month": sales_per_month,
        "visits": visits,
        "price_average_brl": market.price_average_brl if market else None,
        "estimated_margin_pct": margin_pct,
        "has_latest_simulation": simulation is not None,
        "product_name": product.name,
        "product_id": product.id,
    }

    return result, notes


def compute_product_score_v2(db: Session, product_id: int) -> Tuple[dict, list[str], list[str]]:
    """
    V2: retorna também "reasons" (bullets curtos) para UI.

    Retorna:
      - dict com sub-scores e total
      - notes (texto mais longo, debug)
      - reasons (bullets curtos e consistentes)
    """
    result, notes = compute_product_score(db, product_id)

    product: Optional[Product] = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        # compute_product_score já teria falhado, mas mantemos segurança
        return result, notes, []

    market: Optional[ProductMarketData] = (
        db.query(ProductMarketData)
        .filter(ProductMarketData.product_id == product_id)
        .first()
    )
    simulation: Optional[ImportSimulation] = _get_latest_simulation(db, product_id)

    reasons = _make_reasons(product=product, market=market, simulation=simulation, result=result)
    return result, notes, reasons
