# app/core/database.py

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

SQLALCHEMY_DATABASE_URL = settings.DATABASE_URL

# Para SQLite, é importante usar connect_args={"check_same_thread": False}
if SQLALCHEMY_DATABASE_URL.startswith("sqlite"):
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        connect_args={"check_same_thread": False},
        echo=False,
        future=True,
    )
else:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        echo=False,
        future=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# Dependência para usar em endpoints (vamos usar depois)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
