# app/core/config.py

import os
from dotenv import load_dotenv

# Caminho da raiz do projeto (onde está o main.py e o .env)
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
ENV_PATH = os.path.join(BASE_DIR, ".env")

# Carrega variáveis do arquivo .env, se existir
if os.path.exists(ENV_PATH):
    load_dotenv(ENV_PATH)


class Settings:
    def __init__(self) -> None:
        # Para começar, vamos usar SQLite por padrão se não houver .env
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "sqlite:///./mannaalive.db",
        )


settings = Settings()
