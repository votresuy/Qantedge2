"""
Forex market data — Twelve Data API.
Fetches XAU/USD and EUR/USD as decided in product requirements.

Free tier limits: 8 requests/minute, 800 requests/day.
With only 2 pairs and 4 timeframes each, a full multi-timeframe fetch = 8 calls.
Scheduler should be mindful of this — see market/scheduler.py for batching/interval logic.
"""

import httpx
from datetime import datetime
from typing import List
from app.config import settings
from app.schemas.market import Candle, MarketSnapshot, AssetType
from app.utils.logger import get_logger

logger = get_logger("forex_service")


class TwelveDataService:
    def __init__(self):
        self.base_url = settings.TWELVE_DATA_BASE_URL
        self.api_key = settings.TWELVE_DATA_API_KEY

    async def _get(self, path: str, params: dict) -> dict:
        params["apikey"] = self.api_key
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params)
            resp.raise_for_status()
            data = resp.json()
            if isinstance(data, dict) and data.get("status") == "error":
                raise RuntimeError(f"Twelve Data error: {data.get('message')}")
            return data

    async def get_price(self, symbol: str) -> float:
        data = await self._get("/price", {"symbol": symbol})
        return float(data["price"])

    async def get_time_series(self, symbol: str, interval: str, outputsize: int = 100) -> List[Candle]:
        """interval: '1day', '4h', '1h', '15min'"""
        data = await self._get(
            "/time_series",
            {"symbol": symbol, "interval": interval, "outputsize": outputsize},
        )
        values = data.get("values", [])
        candles = [
            Candle(
                timestamp=datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S")
                if len(v["datetime"]) > 10 else datetime.strptime(v["datetime"], "%Y-%m-%d"),
                open=float(v["open"]),
                high=float(v["high"]),
                low=float(v["low"]),
                close=float(v["close"]),
                volume=float(v.get("volume", 0) or 0),
            )
            for v in values
        ]
        candles.reverse()  # Twelve Data returns newest first; we want chronological order
        return candles

    async def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        price = await self.get_price(symbol)
        daily = await self.get_time_series(symbol, "1day", 250)
        h4 = await self.get_time_series(symbol, "4h", 150)
        h1 = await self.get_time_series(symbol, "1h", 100)
        m15 = await self.get_time_series(symbol, "15min", 100)

        logger.info(f"Fetched Twelve Data snapshot for {symbol}: price={price}")

        return MarketSnapshot(
            instrument=symbol.replace("/", ""),
            asset_type=AssetType.FOREX,
            price=price,
            candles_daily=daily,
            candles_4h=h4,
            candles_1h=h1,
            candles_15m=m15,
        )

    async def fetch_all(self) -> List[MarketSnapshot]:
        snapshots = []
        for pair in settings.FOREX_PAIRS:
            try:
                snap = await self.fetch_snapshot(pair)
                snapshots.append(snap)
            except Exception as e:
                logger.error(f"Twelve Data fetch failed for {pair}: {e}")
        return snapshots


forex_service = TwelveDataService()
