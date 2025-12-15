from __future__ import annotations

from decimal import Decimal
import httpx

USD_BRL_URL = "https://economia.awesomeapi.com.br/json/last/USD-BRL"

async def fetch_usd_brl_rate() -> Decimal:
    async with httpx.AsyncClient(timeout=10) as client:
        r = await client.get(USD_BRL_URL)
        r.raise_for_status()
        data = r.json()
        bid = data["USDBRL"]["bid"]  # string tipo "5.2345"
        return Decimal(bid)
