# main.py

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware

from app.core.database import engine, Base

# Importa os models para registrá-los no Base.metadata
from app.models.supplier import Supplier  # noqa: F401
from app.models.ncm import Ncm  # noqa: F401
from app.models.product import Product  # noqa: F401
from app.models.product_evaluation import ProductEvaluation  # noqa: F401
from app.models.import_simulation import ImportSimulation  # noqa: F401
from app.models.import_operation import ImportOperation  # noqa: F401

from app.api.product_decisions import router as product_decisions_router
from app.api.products import router as products_router

app = FastAPI(
    title="Manna Alive Import API",
    version="0.1.0",
)

# === CORS: liberar acesso do front (Next em localhost:3000) ===
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,          # pode colocar ["*"] em dev, se preferir
    allow_credentials=True,
    allow_methods=["*"],            # libera GET, POST, PUT, DELETE, OPTIONS etc.
    allow_headers=["*"],
)

@app.on_event("startup")
def on_startup():
    Base.metadata.create_all(bind=engine)


app.include_router(products_router)
app.include_router(product_decisions_router)


@app.get("/health")
def health_check():
    return {"status": "ok"}
