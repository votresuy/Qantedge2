"""
Simple in-memory cache for the latest validated market snapshots.
Swap this for Redis in production if running multiple backend instances.
"""

from typing import Dict, Optional
from datetime import datetime, timedelta
from app.schemas.market import MarketSnapshot
from app.utils.logger import get_logger

logger = get_logger("market_cache")


class MarketCache:
    def __init__(self, ttl_seconds: int = 180):
        self._store: Dict[str, MarketSnapshot] = {}
        self.ttl = timedelta(seconds=ttl_seconds)

    def set(self, instrument: str, snapshot: MarketSnapshot):
        self._store[instrument] = snapshot

    def get(self, instrument: str) -> Optional[MarketSnapshot]:
        snap = self._store.get(instrument)
        if not snap:
            return None
        if datetime.utcnow() - snap.fetched_at > self.ttl:
            logger.warning(f"Cache stale for {instrument}, older than TTL")
            return None
        return snap

    def get_all(self) -> Dict[str, MarketSnapshot]:
        return dict(self._store)

    def is_fresh(self, instrument: str) -> bool:
        return self.get(instrument) is not None


market_cache = MarketCache()
