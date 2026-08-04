"""
Market Data Service — Step 2 of the pipeline.

Receive APIs -> Validate -> Clean -> Cache -> Send to Engines

This is the single entry point the scheduler calls every minute. It fans out
to the three market source services (crypto/forex/stocks), validates each
snapshot, cleans obviously bad candles, writes to cache, and returns the
clean snapshot list so engines can consume it.
"""

from typing import List
from app.schemas.market import MarketSnapshot, Candle
from app.market.crypto_service import coingecko_service
from app.market.forex_service import forex_service
from app.market.indian_stock_service import indian_stock_service
from app.market.cache import market_cache
from app.utils.logger import get_logger

logger = get_logger("market_data_service")


def _validate_snapshot(snapshot: MarketSnapshot) -> bool:
    """Basic sanity checks before trusting the data."""
    if snapshot.price <= 0:
        logger.warning(f"Invalid price for {snapshot.instrument}: {snapshot.price}")
        return False
    if not snapshot.candles_daily:
        logger.warning(f"No daily candles for {snapshot.instrument}")
        return False
    return True


def _clean_candles(candles: List[Candle]) -> List[Candle]:
    """Remove zero/negative OHLC rows and obviously duplicate timestamps."""
    seen = set()
    cleaned = []
    for c in candles:
        if c.open <= 0 or c.high <= 0 or c.low <= 0 or c.close <= 0:
            continue
        if c.high < c.low:
            continue
        if c.timestamp in seen:
            continue
        seen.add(c.timestamp)
        cleaned.append(c)
    return cleaned


def _clean_snapshot(snapshot: MarketSnapshot) -> MarketSnapshot:
    snapshot.candles_daily = _clean_candles(snapshot.candles_daily)
    snapshot.candles_4h = _clean_candles(snapshot.candles_4h)
    snapshot.candles_1h = _clean_candles(snapshot.candles_1h)
    snapshot.candles_15m = _clean_candles(snapshot.candles_15m)
    return snapshot


class MarketDataService:
    async def refresh_all(self) -> List[MarketSnapshot]:
        """Fetch fresh data from all three sources, validate + clean + cache."""
        all_snapshots: List[MarketSnapshot] = []

        for fetcher_name, fetcher in [
            ("crypto", coingecko_service.fetch_all),
            ("forex", forex_service.fetch_all),
            ("stocks", indian_stock_service.fetch_all),
        ]:
            try:
                snapshots = await fetcher()
                for snap in snapshots:
                    if not _validate_snapshot(snap):
                        continue
                    snap = _clean_snapshot(snap)
                    market_cache.set(snap.instrument, snap)
                    all_snapshots.append(snap)
                logger.info(f"{fetcher_name}: {len(snapshots)} snapshots refreshed")
            except Exception as e:
                logger.error(f"{fetcher_name} fetch pipeline failed: {e}")

        return all_snapshots

    def get_cached(self, instrument: str) -> MarketSnapshot | None:
        return market_cache.get(instrument)

    def get_all_cached(self):
        return market_cache.get_all()


market_data_service = MarketDataService()
