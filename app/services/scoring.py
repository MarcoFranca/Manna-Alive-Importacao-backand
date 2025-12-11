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


def compute_product_score(db: Session, product_id: int) -> Tuple[dict, list[str]]:
    """
    Calcula o score de um produto com base em:
    - dados de mercado (ProductMarketData)
    - última simulação de importação (ImportSimulation)
    - atributos do próprio produto (peso, marca, fragilidade)
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

    # ---------------------------
    # 1) DEMANDA (0–100)
    # ---------------------------
    sales_per_day = market.sales_per_day if market else None
    sales_per_month = market.sales_per_month if market else None
    visits = market.visits if market else None

    sales_day_score = _normalize(sales_per_day or 0, 0, 150) * 100  # 150+ vendas/dia = nota máxima
    sales_month_score = _normalize(sales_per_month or 0, 0, 4000) * 100
    visits_score = _normalize(visits or 0, 0, 10000) * 100

    # peso maior para vendas/dia
    demand_score = (
        0.6 * sales_day_score +
        0.3 * sales_month_score +
        0.1 * visits_score
    )

    if sales_per_day:
        notes.append(f"Demanda: ~{sales_per_day} vendas/dia.")
    if not market:
        notes.append("Sem dados de mercado cadastrados; demanda considerada neutra/baixa.")

    # ---------------------------
    # 2) CONCORRÊNCIA (0–100)
    # quanto MAIOR, MELHOR (concorrência mais amigável)
    # ---------------------------
    full_ratio = market.full_ratio if market else None
    competitor_count = market.competitor_count if market else None
    ranking_position = market.ranking_position if market else None

    # Quanto maior o FULL, pior (nota cai)
    full_penalty = _normalize(full_ratio or 0, 0, 80) * 100  # 80%+ full = bem ruim
    # Quanto mais concorrentes, pior
    competitors_penalty = _normalize(competitor_count or 0, 0, 30) * 100  # 30+ concorrentes = máximo
    # Ranking alto (pior), diminui nota. Ranking 1 = top.
    ranking_penalty = _normalize(ranking_position or 50000, 1, 50000) * 100

    # comece em 100 e subtraia as penalidades (limitando a 0)
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

    # ---------------------------
    # 3) MARGEM (0–100)
    # ---------------------------
    margin_pct = simulation.estimated_margin_pct if simulation else None
    margin_score = _normalize(margin_pct or 0, 10, 60) * 100  # 10% = ruim, 60%+ = ótimo

    if margin_pct is not None:
        notes.append(f"Margem estimada na última simulação: {round(float(margin_pct), 1)}%.")
    else:
        notes.append("Sem simulação de importação cadastrada; margem considerada baixa.")

    # ---------------------------
    # 4) RISCO (0–100)
    # quanto MAIOR, MELHOR (menor risco)
    # ---------------------------
    risk_score = 100.0

    # Peso: produtos muito pesados são piores para simplificada
    weight_kg = float(product.weight_kg or 0)
    if weight_kg > 5:
        risk_score -= 30
        notes.append("Produto pesado (>5kg) — ruim para Importação Simplificada.")
    elif weight_kg > 2:
        risk_score -= 15
        notes.append("Produto moderadamente pesado (>2kg).")

    # Fragilidade
    if product.fragile:
        risk_score -= 15
        notes.append("Produto frágil — risco logístico maior.")

    # Marca famosa sem autorização
    if product.is_famous_brand and not product.has_brand_authorization:
        risk_score -= 40
        notes.append("Marca famosa sem autorização — alto risco de PI / apreensão.")

    # Garante limites
    risk_score = max(0.0, min(100.0, risk_score))

    # ---------------------------
    # 5) SCORE FINAL (0–100)
    # ---------------------------
    total_score = (
        0.40 * demand_score +
        0.25 * competition_score +
        0.25 * margin_score +
        0.10 * risk_score
    )

    # classificação
    if total_score >= 80:
        classification = "campeao"
    elif total_score >= 60:
        classification = "bom"
    elif total_score >= 40:
        classification = "arriscado"
    else:
        classification = "descartar"

    if classification == "campeao":
        notes.append("Produto classificado como CAMPEÃO (score >= 80).")
    elif classification == "bom":
        notes.append("Produto VIÁVEL para teste (score entre 60 e 79).")
    elif classification == "arriscado":
        notes.append("Produto ARRISCADO (score entre 40 e 59).")
    else:
        notes.append("Produto RECOMENDADO PARA DESCARTE (score < 40).")

    # dict para montar o schema depois
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
