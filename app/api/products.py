# app/api/products.py

from typing import List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.product import Product  # noqa: F401
from app.models.import_simulation import ImportSimulation
from app.models.product_market_data import ProductMarketData
from app.schemas.product import ProductCreate, ProductOut, ProductUpdate
from app.schemas.simulation import SimulationInput, SimulationOut
from app.schemas.market_data import MarketDataCreate, MarketDataOut
from app.schemas.score import ProductScoreOut
from app.services.scoring import compute_product_score


router = APIRouter(prefix="/products", tags=["products"])


@router.get("/", response_model=List[ProductOut])
def list_products(db: Session = Depends(get_db)):
    """
    Lista todos os produtos cadastrados.
    """
    products = db.query(Product).order_by(Product.id.desc()).all()
    return products


@router.post("/", response_model=ProductOut, status_code=status.HTTP_201_CREATED)
def create_product(payload: ProductCreate, db: Session = Depends(get_db)):
    """
    Cria um novo produto.
    """
    # (Opcional) regra simples para evitar nome duplicado
    existing = (
        db.query(Product)
        .filter(Product.name == payload.name)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Já existe um produto com esse nome.",
        )

    product = Product(
        name=payload.name,
        description=payload.description,
        category=payload.category,
        reference_marketplace_url=str(payload.reference_marketplace_url)
        if payload.reference_marketplace_url
        else None,
        supplier_url=str(payload.supplier_url)
        if payload.supplier_url
        else None,
        supplier_id=payload.supplier_id,
        ncm_id=payload.ncm_id,
        weight_kg=payload.weight_kg,
        length_cm=payload.length_cm,
        width_cm=payload.width_cm,
        height_cm=payload.height_cm,
        fragile=payload.fragile,
        fob_price_usd=payload.fob_price_usd,
        freight_usd=payload.freight_usd,
        insurance_usd=payload.insurance_usd,
        is_famous_brand=payload.is_famous_brand,
        has_brand_authorization=payload.has_brand_authorization,
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


@router.post(
    "/{product_id}/simulate",
    response_model=SimulationOut,
    status_code=status.HTTP_201_CREATED,
)
def simulate_import_for_product(
    product_id: int,
    payload: SimulationInput,
    db: Session = Depends(get_db),
):
    """
    Simula uma importação para um produto específico usando a regra rápida:
    - custo aduaneiro = (FOB + frete + seguro) * quantidade
    - custo total ≈ custo aduaneiro * 2 (aéreo / simplificada)
    - converte para BRL, calcula custo unitário e margem
    """

    # 1) Buscar o produto no banco
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    if product.fob_price_usd is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Produto não possui FOB definido.",
        )

    # 2) Calcular totais em USD
    quantity = payload.quantity
    exchange_rate = payload.exchange_rate
    target_price = payload.target_sale_price_brl

    # FOB total (produto * quantidade)
    fob_total_usd = product.fob_price_usd * quantity

    # Frete total: pode vir do payload ou usar frete unitário do produto
    if payload.freight_total_usd is not None:
        freight_total_usd = payload.freight_total_usd
    else:
        freight_total_usd = (product.freight_usd or 0) * quantity

    # Seguro total: pode vir do payload ou usar o unitário do produto
    if payload.insurance_total_usd is not None:
        insurance_total_usd = payload.insurance_total_usd
    else:
        insurance_total_usd = (product.insurance_usd or 0) * quantity

    customs_value_usd = fob_total_usd + freight_total_usd + insurance_total_usd

    # 3) Regra rápida: custo total ≈ custo aduaneiro * 2
    estimated_total_cost_usd = customs_value_usd * 2
    estimated_total_cost_brl = estimated_total_cost_usd * exchange_rate

    unit_cost_brl = estimated_total_cost_brl / quantity

    # 4) Margem em %
    estimated_margin_pct = (target_price - unit_cost_brl) / target_price * 100

    # 5) Regras de aprovação simples (você pode ajustar depois)
    reasons = []
    approved = True

    # Limite da Importação Simplificada por operação (US$ 3.000 de valor aduaneiro)
    if customs_value_usd > 3000:
        approved = False
        reasons.append("Excede o limite de US$ 3.000 de valor aduaneiro por remessa.")

    # Margem mínima (ex.: 35%)
    MIN_MARGIN = 35
    if estimated_margin_pct < MIN_MARGIN:
        approved = False
        reasons.append(f"Margem abaixo de {MIN_MARGIN}%.")

    reason_text = " ".join(reasons) if reasons else "Aprovado nos critérios definidos."

    # 6) Salvar a simulação no banco
    simulation = ImportSimulation(
        product_id=product.id,
        quantity=quantity,
        exchange_rate=exchange_rate,
        fob_total_usd=fob_total_usd,
        freight_total_usd=freight_total_usd,
        insurance_total_usd=insurance_total_usd,
        customs_value_usd=customs_value_usd,
        estimated_total_cost_usd=estimated_total_cost_usd,
        estimated_total_cost_brl=estimated_total_cost_brl,
        unit_cost_brl=unit_cost_brl,
        target_sale_price_brl=target_price,
        estimated_margin_pct=estimated_margin_pct,
        approved=approved,
        reason=reason_text,
    )

    db.add(simulation)
    db.commit()
    db.refresh(simulation)

    return simulation


@router.get("/{product_id}", response_model=ProductOut)
def get_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )
    return product


@router.put("/{product_id}", response_model=ProductOut)
def update_product(
    product_id: int,
    payload: ProductUpdate,
    db: Session = Depends(get_db),
):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    # Pydantic v2: model_dump(exclude_unset=True)
    data = payload.model_dump(exclude_unset=True)

    for field, value in data.items():
        setattr(product, field, value)

    db.add(product)
    db.commit()
    db.refresh(product)

    return product


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_product(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    # 1) Apagar antes as simulações vinculadas
    db.query(ImportSimulation).filter(
        ImportSimulation.product_id == product_id
    ).delete(synchronize_session=False)

    # (se você tiver avaliações ligadas a produto, pode fazer algo similar aqui)

    # 2) Agora apagar o produto
    db.delete(product)
    db.commit()

    return None


@router.get(
    "/{product_id}/market-data",
    response_model=MarketDataOut,
)
def get_market_data(product_id: int, db: Session = Depends(get_db)):
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    market = (
        db.query(ProductMarketData)
        .filter(ProductMarketData.product_id == product_id)
        .first()
    )
    if not market:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Dados de mercado não cadastrados para este produto.",
        )

    return market


@router.post(
    "/{product_id}/market-data",
    response_model=MarketDataOut,
    status_code=status.HTTP_201_CREATED,
)
def upsert_market_data(
    product_id: int,
    payload: MarketDataCreate,
    db: Session = Depends(get_db),
):
    """
    Cria ou atualiza os dados de mercado de um produto.
    Você vai preencher manualmente com base no Avant Pro.
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    market = (
        db.query(ProductMarketData)
        .filter(ProductMarketData.product_id == product_id)
        .first()
    )

    data = payload.model_dump(exclude_unset=True)

    if market is None:
        market = ProductMarketData(product_id=product_id, **data)
        db.add(market)
    else:
        for field, value in data.items():
            setattr(market, field, value)

    db.commit()
    db.refresh(market)

    return market


@router.get(
    "/{product_id}/score",
    response_model=ProductScoreOut,
)
def get_product_score(product_id: int, db: Session = Depends(get_db)):
    """
    Calcula o score de viabilidade do produto com base em:
    - dados de mercado (se existirem)
    - última simulação de importação
    - atributos de risco (peso, marca, fragilidade)
    """
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    result, notes = compute_product_score(db, product_id)

    return ProductScoreOut(
        **result,
        notes=" ".join(notes),
    )


@router.get(
    "/scores/ranking",
    response_model=List[ProductScoreOut],
)
def get_products_ranking(limit: int = 20, db: Session = Depends(get_db)):
    """
    Retorna os produtos ordenados pelo score de viabilidade.
    Útil para decidir quais importar primeiro.
    """
    products = db.query(Product).all()
    scores: list[ProductScoreOut] = []

    for p in products:
        try:
            result, notes = compute_product_score(db, p.id)
            scores.append(
                ProductScoreOut(
                    **result,
                    notes=" ".join(notes),
                )
            )
        except Exception:
            # se der erro para um produto (dados inconsistentes), simplesmente pula
            continue

    # ordena do maior score para o menor
    scores.sort(key=lambda s: s.total_score, reverse=True)

    return scores[:limit]



@router.get(
    "/{product_id}/simulations/last",
    response_model=SimulationOut,
)
def get_last_simulation(product_id: int, db: Session = Depends(get_db)):
    """
    Retorna a simulação de importação mais recente para o produto.
    Útil para mostrar o custo unitário, margem, aprovação, etc.
    """
    # Confere se o produto existe
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Produto não encontrado.",
        )

    # Busca a última simulação pela data de criação
    last_sim = (
        db.query(ImportSimulation)
        .filter(ImportSimulation.product_id == product_id)
        .order_by(ImportSimulation.created_at.desc())
        .first()
    )

    if not last_sim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Nenhuma simulação encontrada para este produto.",
        )

    return last_sim