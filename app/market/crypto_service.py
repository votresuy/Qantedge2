"""
Crypto market data — CoinGecko free API.
Fetches BTCUSDT (bitcoin) and SOLUSDT (solana) as decided in product requirements.

Note: CoinGecko free tier does NOT provide fine-grained (15m) OHLC candles.
- /coins/{id}/ohlc gives candles at fixed granularity depending on `days` param:
    1 day   -> 30 min candles
    7-30 days -> 4 hour candles
    31+ days  -> daily candles
For true 15-minute short-term entries, this is a known limitation. We approximate
short-term entry using the finest available granularity (30 min from days=1) and
document this clearly for the short-term engine.
"""

import httpx
from datetime import datetime
from typing import List
from app.config import settings
from app.schemas.market import Candle, MarketSnapshot, AssetType
from app.utils.logger import get_logger

logger = get_logger("coingecko_service")

# Map internal display symbol -> CoinGecko coin id
SYMBOL_TO_ID = {
    "BTCUSDT": "bitcoin",
    "SOLUSDT": "solana",
}


class CoinGeckoService:
    def __init__(self):
        self.base_url = settings.COINGECKO_BASE_URL
        self.headers = {}
        if settings.COINGECKO_API_KEY:
            self.headers["x-cg-demo-api-key"] = settings.COINGECKO_API_KEY

    async def _get(self, path: str, params: dict) -> dict:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(f"{self.base_url}{path}", params=params, headers=self.headers)
            resp.raise_for_status()
            return resp.json()

    async def get_current_price(self, coin_id: str) -> float:
        data = await self._get("/simple/price", {"ids": coin_id, "vs_currencies": "usd"})
        return float(data[coin_id]["usd"])

    async def get_ohlc(self, coin_id: str, days: int) -> List[Candle]:
        """days: 1 (30m candles), 7/14/30 (4h candles), 90+ (daily candles)."""
        raw = await self._get(f"/coins/{coin_id}/ohlc", {"vs_currency": "usd", "days": days})
        candles = []
        for entry in raw:
            ts, o, h, l, c = entry
            candles.append(
                Candle(
                    timestamp=datetime.utcfromtimestamp(ts / 1000),
                    open=o, high=h, low=l, close=c, volume=0.0,
                )
            )
        return candles

    async def fetch_snapshot(self, symbol: str) -> MarketSnapshot:
        """Fetch full snapshot (price + multi-timeframe candles) for one crypto symbol."""
        coin_id = SYMBOL_TO_ID.get(symbol)
        if not coin_id:
            raise ValueError(f"Unsupported crypto symbol: {symbol}")

        price = await self.get_current_price(coin_id)
        daily = await self.get_ohlc(coin_id, days=90)     # daily candles for long-term trend
        h4 = await self.get_ohlc(coin_id, days=14)          # 4h candles for short-term trend
        m30 = await self.get_ohlc(coin_id, days=1)          # 30m candles (closest to 15m available)

        logger.info(f"Fetched CoinGecko snapshot for {symbol}: price={price}")

        return MarketSnapshot(
            instrument=symbol,
            asset_type=AssetType.CRYPTO,
            price=price,
            candles_daily=daily,
            candles_4h=h4,
            candles_1h=h4,   # CoinGecko free tier has no true 1h; reuse 4h series, engine handles gracefully
            candles_15m=m30,  # closest available granularity
        )

    async def fetch_all(self) -> List[MarketSnapshot]:
        snapshots = []
        for symbol in settings.CRYPTO_SYMBOLS:
            try:
                snap = await self.fetch_snapshot(symbol)
                snapshots.append(snap)
            except Exception as e:
                logger.error(f"CoinGecko fetch failed for {symbol}: {e}")
        return snapshots


coingecko_service = CoinGeckoService()
