from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_decision import ProductDecision
from app.models.product_market_data import ProductMarketData
from app.models.import_simulation import ImportSimulation
from app.schemas.decision import ProductDecisionOut
from app.schemas.evaluation import (
    Blocker,
    Completeness,
    CompletenessItem,
    EvaluationHeader,
    Metric,
    Pillar,
    ProductEvaluationResponse,
    ScenarioResult, ScoreSummary,
)
from app.services.scoring import compute_product_score_v2


@dataclass(frozen=True)
class EvalConfig:
    min_margin_pct_conservative: float = 35.0
    max_customs_value_usd: float = 3000.0

    # 🔥 NOVO — parâmetros financeiros
    ml_fee_pct: float = 0.16        # comissão ML
    ads_pct: float = 0.05           # ads médio
    local_cost_brl: float = 3.0     # embalagem / perdas / etc por unidade


def _safe_float(value) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _latest_simulation(db: Session, product_id: int) -> Optional[ImportSimulation]:
    return (
        db.query(ImportSimulation)
        .filter(ImportSimulation.product_id == product_id)
        .order_by(ImportSimulation.created_at.desc())
        .first()
    )


def _estimate_total_cost_usd(customs_value_usd: float) -> float:
    # Regra simplificada atual (você já usa): custo total ≈ valor aduaneiro × 2
    return customs_value_usd * 2.0


def _latest_decision(db: Session, product_id: int) -> Optional[ProductDecision]:
    return (
        db.query(ProductDecision)
        .filter(ProductDecision.product_id == product_id)
        .order_by(ProductDecision.created_at.desc())
        .first()
    )



def _scenario_calc(
    *,
    kind: str,
    name: str,
    quantity: int,
    exchange_rate: float,
    target_sale_price_brl: float,
    fob_unit_usd: float,
    freight_total_usd: float,
    insurance_total_usd: float,
    config: EvalConfig,
    sales_per_day: Optional[float] = None,
) -> ScenarioResult:
    fob_total_usd = fob_unit_usd * float(quantity)
    customs_value_usd = fob_total_usd + freight_total_usd + insurance_total_usd

    estimated_total_cost_usd = customs_value_usd * 2.0
    estimated_total_cost_brl = estimated_total_cost_usd * exchange_rate
    unit_cost_brl = estimated_total_cost_brl / float(quantity)

    # 🔥 Receita líquida
    total_fee_pct = config.ml_fee_pct + config.ads_pct
    net_sale_price_brl = target_sale_price_brl * (1 - total_fee_pct)

    # 🔥 Lucro
    profit_unit_brl = net_sale_price_brl - unit_cost_brl - config.local_cost_brl
    profit_total_brl = profit_unit_brl * quantity

    # 🔥 ROI
    capital_total_brl = unit_cost_brl * quantity
    roi_unit_pct = (profit_unit_brl / unit_cost_brl * 100) if unit_cost_brl > 0 else -100.0
    roi_total_pct = (profit_total_brl / capital_total_brl * 100) if capital_total_brl > 0 else -100.0

    # 🔥 Payback
    payback_days = None
    if sales_per_day and sales_per_day > 0 and profit_unit_brl > 0:
        daily_profit = sales_per_day * profit_unit_brl
        payback_days = capital_total_brl / daily_profit

    # Margem clássica (mantida)
    if target_sale_price_brl <= 0:
        margin_pct = -100.0
    else:
        margin_pct = (target_sale_price_brl - unit_cost_brl) / target_sale_price_brl * 100.0

    approved = True
    reason = None

    if customs_value_usd > config.max_customs_value_usd:
        approved = False
        reason = f"Valor aduaneiro acima de {config.max_customs_value_usd:.0f} USD."
    elif kind == "conservative" and margin_pct < config.min_margin_pct_conservative:
        approved = False
        reason = f"Margem abaixo de {config.min_margin_pct_conservative:.0f}% no conservador."

    return ScenarioResult(
        kind=kind,
        name=name,
        quantity=quantity,
        exchange_rate=exchange_rate,
        fob_total_usd=round(fob_total_usd, 2),
        freight_total_usd=round(freight_total_usd, 2),
        insurance_total_usd=round(insurance_total_usd, 2),
        customs_value_usd=round(customs_value_usd, 2),
        estimated_total_cost_usd=round(estimated_total_cost_usd, 2),
        estimated_total_cost_brl=round(estimated_total_cost_brl, 2),
        unit_cost_brl=round(unit_cost_brl, 2),
        target_sale_price_brl=round(target_sale_price_brl, 2),
        net_sale_price_brl=round(net_sale_price_brl, 2),
        profit_unit_brl=round(profit_unit_brl, 2),
        profit_total_brl=round(profit_total_brl, 2),
        roi_unit_pct=round(roi_unit_pct, 2),
        roi_total_pct=round(roi_total_pct, 2),
        payback_days=round(payback_days, 1) if payback_days else None,
        estimated_margin_pct=round(margin_pct, 2),
        approved=approved,
        reason=reason,
    )


def compute_product_evaluation(db: Session, product_id: int) -> ProductEvaluationResponse:
    config = EvalConfig()

    product = db.query(Product).filter(Product.id == product_id).first()
    if product is None:
        raise ValueError("Product not found")

    market: Optional[ProductMarketData] = product.market_data  # 1:1 (pode ser None)
    last_sim = _latest_simulation(db, product_id)

    # Completeness (checklist objetivo)
    has_market_data = market is not None
    has_ncm = product.ncm_id is not None
    has_supplier = product.supplier_id is not None
    has_dimensions = all(
        v is not None and float(v) > 0
        for v in [product.weight_kg, product.length_cm, product.width_cm, product.height_cm]
    )

    completeness_items = [
        CompletenessItem(key="market_data", label="Dados de mercado preenchidos", is_complete=has_market_data),
        CompletenessItem(key="ncm", label="NCM definido", is_complete=has_ncm),
        CompletenessItem(key="supplier", label="Fornecedor definido", is_complete=has_supplier),
        CompletenessItem(key="dimensions", label="Peso e dimensões preenchidos", is_complete=has_dimensions),
        CompletenessItem(key="fob", label="FOB preenchido", is_complete=product.fob_price_usd is not None),
    ]
    total = len(completeness_items)
    complete = sum(1 for i in completeness_items if i.is_complete)
    missing = [i.label for i in completeness_items if not i.is_complete]
    completeness = Completeness(
        percent=int(round((complete / total) * 100)),
        items=completeness_items,
        missing=missing,
    )

    # Cenários (primeira versão): usa FOB do produto + freight/insurance do produto
    fob_unit = _safe_float(product.fob_price_usd) or 0.0
    freight_unit = _safe_float(product.freight_usd) or 0.0
    insurance_unit = _safe_float(product.insurance_usd) or 0.0

    # Defaults: se não existir simulação anterior, usamos valores base plausíveis
    base_qty = last_sim.quantity if last_sim else 200
    base_exchange = _safe_float(last_sim.exchange_rate) if last_sim else 5.2
    base_target_price = _safe_float(last_sim.target_sale_price_brl) if last_sim else (_safe_float(market.price_average_brl) if market else 0.0)

    base_qty = int(base_qty) if base_qty and int(base_qty) > 0 else 200
    base_exchange = float(base_exchange) if base_exchange and base_exchange > 0 else 5.2
    base_target_price = float(base_target_price) if base_target_price and base_target_price > 0 else 0.0

    # Totais de frete/seguro por cenário (simples e transparente)
    base_freight_total = freight_unit * base_qty if freight_unit > 0 else 80.0
    base_ins_total = insurance_unit * base_qty if insurance_unit > 0 else 10.0
    sales_per_day = _safe_float(market.sales_per_day) if market else None

    scenarios = [
        _scenario_calc(
            kind="base",
            name="Base",
            quantity=base_qty,
            exchange_rate=base_exchange,
            target_sale_price_brl=base_target_price,
            fob_unit_usd=fob_unit,
            freight_total_usd=base_freight_total,
            insurance_total_usd=base_ins_total,
            config=config,
            sales_per_day=sales_per_day,
        ),
        _scenario_calc(
            kind="conservative",
            name="Conservador",
            quantity=max(50, int(base_qty * 0.6)),
            exchange_rate=base_exchange * 1.05,  # câmbio pior
            target_sale_price_brl=base_target_price * 0.95,  # preço menor
            fob_unit_usd=fob_unit * 1.03,  # FOB pior
            freight_total_usd=base_freight_total * 1.15,
            insurance_total_usd=base_ins_total * 1.1,
            config=config,
            sales_per_day=sales_per_day,
        ),
        _scenario_calc(
            kind="optimistic",
            name="Otimista",
            quantity=int(base_qty * 1.3),
            exchange_rate=base_exchange * 0.97,
            target_sale_price_brl=base_target_price * 1.03,
            fob_unit_usd=max(0.0, fob_unit * 0.98),
            freight_total_usd=base_freight_total * 0.95,
            insurance_total_usd=base_ins_total * 0.95,
            config=config,
            sales_per_day=sales_per_day,
        ),
    ]

    conservative = next(s for s in scenarios if s.kind == "conservative")
    base = next(s for s in scenarios if s.kind == "base")

    blockers: list[Blocker] = []
    notes: list[str] = []

    # Hard stops iniciais (configuráveis depois)
    if product.is_famous_brand and not product.has_brand_authorization:
        blockers.append(
            Blocker(
                key="brand_risk",
                title="Risco de marca",
                reason="Produto marcado como marca famosa sem autorização de revenda/importação.",
            )
        )

    if has_ncm and product.ncm is not None:
        if getattr(product.ncm, "antidumping", False):
            blockers.append(
                Blocker(
                    key="antidumping",
                    title="Antidumping",
                    reason="NCM indica possível antidumping. Requer validação antes de importar.",
                )
            )
        if getattr(product.ncm, "requires_li", False):
            notes.append("NCM indica possível necessidade de LI. Inclua tempo/custo de compliance no cenário real.")
        if getattr(product.ncm, "anvisa", False):
            notes.append("NCM sinaliza possível controle Anvisa. Avaliar exigências e viabilidade.")
        if getattr(product.ncm, "anatel", False):
            notes.append("NCM sinaliza possível controle Anatel. Avaliar homologação.")
        if getattr(product.ncm, "inmetro", False):
            notes.append("NCM sinaliza possível controle Inmetro. Avaliar certificação.")

    # Pilares
    # Mercado
    market_status = "unknown"
    market_summary = "Sem dados de mercado suficientes para concluir demanda/competição."
    market_next = "Preencher vendas/dia, concorrentes, full ratio e preço médio."
    market_metrics: list[Metric] = []

    if market:
        spd = _safe_float(market.sales_per_day)
        comp = _safe_float(market.competitor_count)
        full = _safe_float(market.full_ratio)
        price = _safe_float(market.price_average_brl)

        market_metrics = [
            Metric(key="price_avg", label="Preço médio", value=price, unit="BRL"),
            Metric(key="sales_per_day", label="Vendas/dia", value=spd, unit="un/dia"),
            Metric(key="competitors", label="Concorrentes", value=comp, unit="anúncios"),
            Metric(key="full_ratio", label="Full ratio", value=full, unit="%"),
            Metric(key="visits", label="Visitas", value=_safe_float(market.visits), unit="visitas"),
        ]

        # Heurística simples (vamos melhorar depois):
        if spd is not None and comp is not None:
            if spd >= 5 and comp <= 80:
                market_status = "green"
                market_summary = "Boa combinação de demanda e concorrência."
                market_next = "Validar diferenciação (kit, variação, branding) e sazonalidade."
            elif spd >= 2:
                market_status = "yellow"
                market_summary = "Demanda existe, mas pode haver pressão competitiva."
                market_next = "Checar preço vs top sellers e barreiras (Full, reviews)."
            else:
                market_status = "red"
                market_summary = "Demanda fraca no cenário atual."
                market_next = "Buscar variação/categoria alternativa ou descartar."
        else:
            market_status = "yellow"
            market_summary = "Dados parciais; completar para concluir."
            market_next = "Completar vendas/dia e concorrentes."

    # Unit economics
    ue_status = "unknown"
    ue_summary = "Sem cenário conservador confiável (preço alvo e custos)."
    ue_next = "Definir preço alvo e rodar cenários com quantidade realista."
    ue_metrics = [
        Metric(key="margin_conservative", label="Margem (conservador)", value=conservative.estimated_margin_pct, unit="%"),
        Metric(key="unit_cost_conservative", label="Custo unit. (conservador)", value=conservative.unit_cost_brl, unit="BRL"),
        Metric(key="unit_cost_base", label="Custo unit. (base)", value=base.unit_cost_brl, unit="BRL"),
        Metric(key="customs_value_base", label="Valor aduaneiro (base)", value=base.customs_value_usd, unit="USD"),
    ]
    if conservative.target_sale_price_brl > 0 and fob_unit > 0:
        if conservative.approved:
            ue_status = "green"
            ue_summary = "Margem atende o mínimo no cenário conservador."
            ue_next = "Validar fees do canal e custo real de logística (para margem líquida)."
        else:
            ue_status = "red"
            ue_summary = conservative.reason or "Margem insuficiente no cenário conservador."
            ue_next = "Ajustar preço alvo, reduzir custo (FOB/frete) ou descartar."
    else:
        ue_status = "yellow"
        ue_summary = "Precisa de preço alvo e FOB para concluir unit economics."
        ue_next = "Preencher FOB e/ou preço médio do mercado e rodar novamente."

    # Operations
    ops_status = "yellow" if not has_dimensions else "green"
    ops_summary = "Dimensões/peso pendentes; pode distorcer frete e operação." if not has_dimensions else "Operação parece simples com os dados atuais."
    ops_next = "Preencher peso e dimensões reais do produto/embalagem." if not has_dimensions else "Confirmar MOQ/lead time com fornecedor."
    ops_metrics = [
        Metric(key="weight", label="Peso", value=_safe_float(product.weight_kg), unit="kg"),
        Metric(key="length", label="Comprimento", value=_safe_float(product.length_cm), unit="cm"),
        Metric(key="width", label="Largura", value=_safe_float(product.width_cm), unit="cm"),
        Metric(key="height", label="Altura", value=_safe_float(product.height_cm), unit="cm"),
        Metric(key="fragile", label="Frágil", value=1.0 if product.fragile else 0.0, unit="bool", help="1=sim, 0=não"),
    ]

    # Risk
    risk_status = "green"
    risk_summary = "Risco controlado no estado atual."
    risk_next = "Manter evidências (NCM, marca, compliance) anexadas ao produto."
    risk_metrics = [
        Metric(key="famous_brand", label="Marca famosa", value=1.0 if product.is_famous_brand else 0.0, unit="bool"),
        Metric(key="brand_auth", label="Autorização de marca", value=1.0 if product.has_brand_authorization else 0.0, unit="bool"),
        Metric(key="has_ncm", label="NCM definido", value=1.0 if has_ncm else 0.0, unit="bool"),
    ]
    if blockers:
        risk_status = "red"
        risk_summary = "Há impeditivos objetivos antes de importar."
        risk_next = "Resolver impeditivos (autorização/antidumping/compliance) ou descartar."

    pillars = [
        Pillar(
            key="market",
            title="Mercado",
            status=market_status,  # type: ignore[arg-type]
            summary=market_summary,
            next_action=market_next,
            metrics=market_metrics,
        ),
        Pillar(
            key="unit_economics",
            title="Margem (Unit economics)",
            status=ue_status,  # type: ignore[arg-type]
            summary=ue_summary,
            next_action=ue_next,
            metrics=ue_metrics,
        ),
        Pillar(
            key="operations",
            title="Operação",
            status=ops_status,  # type: ignore[arg-type]
            summary=ops_summary,
            next_action=ops_next,
            metrics=ops_metrics,
        ),
        Pillar(
            key="risk",
            title="Risco & Compliance",
            status=risk_status,  # type: ignore[arg-type]
            summary=risk_summary,
            next_action=risk_next,
            metrics=risk_metrics,
        ),
    ]

    # Decisão
    if blockers:
        decision = "reject"
        decision_reason = "Há impeditivos objetivos (risco/compliance) antes de seguir."
    elif not has_market_data or base_target_price <= 0 or fob_unit <= 0:
        decision = "needs_data"
        decision_reason = "Faltam dados críticos para decidir com segurança."
    elif conservative.approved:
        decision = "approve"
        decision_reason = "Aprova no cenário conservador e não há impeditivos."
    else:
        decision = "reject"
        decision_reason = conservative.reason or "Reprovado no cenário conservador."

    last_decision = _latest_decision(db, product_id)
    latest_decision_out = ProductDecisionOut.model_validate(last_decision) if last_decision else None

    header = EvaluationHeader(
        product_id=product.id,
        product_name=product.name,
        category=product.category,
        has_market_data=has_market_data,
        has_ncm=has_ncm,
        has_supplier=has_supplier,
        has_dimensions=has_dimensions,
        latest_decision=latest_decision_out,
        created_at=product.created_at,
        updated_at=product.updated_at,
    )

    notes.insert(0, "Premissa atual: custo total estimado ≈ valor aduaneiro × 2 (simplificação).")
    if not has_ncm:
        notes.append("Sem NCM, impostos e compliance ficam subestimados.")
    if not has_market_data:
        notes.append("Sem dados de mercado, a avaliação de demanda/competição fica inconclusiva.")

    score_out: Optional[ScoreSummary] = None
    try:
        score_dict, _notes, reasons = compute_product_score_v2(db, product_id)
        score_out = ScoreSummary(
            total_score=score_dict["total_score"],
            classification=score_dict["classification"],
            demand_score=score_dict["demand_score"],
            competition_score=score_dict["competition_score"],
            margin_score=score_dict["margin_score"],
            risk_score=score_dict["risk_score"],
            reasons=reasons,
        )
    except Exception:
        score_out = None

    return ProductEvaluationResponse(
        header=header,
        completeness=completeness,
        decision=decision,  # type: ignore[arg-type]
        decision_reason=decision_reason,
        score=score_out,  # <-- NOVO
        pillars=pillars,
        scenarios=scenarios,
        blockers=blockers,
        notes=notes,
    )
