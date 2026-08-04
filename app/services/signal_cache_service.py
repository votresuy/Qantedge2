"""
Signal Cache Service — in-memory store for LIVE signals only.

This is deliberately separate from `app/market/cache.py` (which caches raw
market data / candles for a few minutes). This cache stores the *computed*
signal output (BUY/SELL, entry, SL, TP, confidence, AI analysis) and is what
`/signals/live` and `/signals/live/{instrument}` read from — Firestore's
`signals` collection is still written to (for durability/admin visibility),
but is no longer read on every request.

Entries older than SIGNAL_CACHE_TTL_HOURS (default 24h) are treated as
expired and dropped, so a stopped scheduler can't leave stale signals
looking "live" forever.

NOTE: this is a single-process in-memory cache. If you ever run multiple
backend instances/workers, swap this for Redis (same get/set/get_all shape).
"""

from datetime import datetime, timedelta
from typing import Dict, Optional, List
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("signal_cache_service")


class SignalCacheService:
    def __init__(self, ttl_hours: int = None):
        self._store: Dict[str, dict] = {}
        self._cached_at: Dict[str, datetime] = {}
        self.ttl = timedelta(hours=ttl_hours or settings.SIGNAL_CACHE_TTL_HOURS)

    def set(self, instrument: str, data: dict):
        self._store[instrument] = data
        self._cached_at[instrument] = datetime.utcnow()

    def get(self, instrument: str) -> Optional[dict]:
        cached_at = self._cached_at.get(instrument)
        if not cached_at or datetime.utcnow() - cached_at > self.ttl:
            return None
        return self._store.get(instrument)

    def get_all(self) -> List[dict]:
        """Returns all non-expired cached signals."""
        now = datetime.utcnow()
        results = []
        expired = []
        for instrument, cached_at in self._cached_at.items():
            if now - cached_at > self.ttl:
                expired.append(instrument)
                continue
            results.append(self._store[instrument])

        for instrument in expired:
            self._store.pop(instrument, None)
            self._cached_at.pop(instrument, None)

        if expired:
            logger.info(f"Signal cache: expired {len(expired)} stale entr(y/ies): {expired}")

        return results


signal_cache_service = SignalCacheService()
