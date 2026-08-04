"""
Indian stock/index market data — Angel One SmartAPI.
Fetches NIFTY50 (trend-only), ITC, WIPRO, HDFCBANK (full signal).

Angel One requires:
  1. TOTP-based login to get a JWT session token (refreshed periodically — token
     is valid for the trading day, must re-login each morning / on expiry).
  2. Instrument token lookup (symbol -> token) from their published instrument master.

This service handles session management + historical candle + LTP fetch.
Install dependency: pip install smartapi-python pyotp
"""

import pyotp
import httpx
from datetime import datetime, timedelta
from typing import List, Optional
from app.config import settings
from app.schemas.market import Candle, MarketSnapshot, AssetType
from app.utils.logger import get_logger

logger = get_logger("indian_stock_service")

# Angel One instrument tokens (NSE) — fetch dynamically from their instrument master
# in production; hardcoded here for the fixed instrument set we decided on.
INSTRUMENT_TOKENS = {
    "NIFTY50": {"token": "99926000", "symbol": "Nifty 50", "exch": "NSE"},
    "ITC": {"token": "1660", "symbol": "ITC-EQ", "exch": "NSE"},
    "WIPRO": {"token": "3787", "symbol": "WIPRO-EQ", "exch": "NSE"},
    "HDFCBANK": {"token": "1333", "symbol": "HDFCBANK-EQ", "exch": "NSE"},
}


class AngelOneService:
    def __init__(self):
        self.base_url = settings.ANGEL_ONE_BASE_URL
        self.api_key = settings.ANGEL_ONE_API_KEY
        self.client_id = settings.ANGEL_ONE_CLIENT_ID
        self.password = settings.ANGEL_ONE_PASSWORD
        self.totp_secret = settings.ANGEL_ONE_TOTP_SECRET
        self._jwt_token: Optional[str] = None
        self._token_expiry: Optional[datetime] = None

    async def _login(self):
        """Authenticate using client id + password + TOTP, cache JWT for reuse."""
        totp = pyotp.TOTP(self.totp_secret).now()
        payload = {
            "clientcode": self.client_id,
            "password": self.password,
            "totp": totp,
        }
        headers = {
            "Content-Type": "application/json",
            "X-PrivateKey": self.api_key,
            "X-UserType": "USER",
            "X-SourceID": "WEB",
        }
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.post(
                f"{self.base_url}/rest/auth/angelbroking/user/v1/loginByPassword",
                json=payload, headers=headers,
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("status"):
                raise RuntimeError(f"Angel One login failed: {data.get('message')}")
            self._jwt_token = data["data"]["jwtToken"]
            self._token_expiry = datetime.utcnow() + timedelta(hours=8)
            logger.info("Angel One session established")

    async def _ensure_session(self):
        if not self._jwt_token or (self._token_expiry and datetime.utcnow() >= self._token_expiry):
            await self._login()

    def _auth_headers(self) -> dict:
        return {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self._jwt_token}",
            "X-PrivateKey": self.api_key,
            "X-UserType": "USER",
            "X-SourceID": "WEB",
        }

    async def get_candles(self, instrument_key: str, interval: str, from_date: datetime, to_date: datetime) -> List[Candle]:
        """interval: ONE_DAY, FOUR_HOUR, ONE_HOUR, FIFTEEN_MINUTE"""
        await self._ensure_session()
        info = INSTRUMENT_TOKENS[instrument_key]
        payload = {
            "exchange": info["exch"],
            "symboltoken": info["token"],
            "interval": interval,
            "fromdate": from_date.strftime("%Y-%m-%d %H:%M"),
            "todate": to_date.strftime("%Y-%m-%d %H:%M"),
        }
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.post(
                f"{self.base_url}/rest/secure/angelbroking/historical/v1/getCandleData",
                json=payload, headers=self._auth_headers(),
            )
            resp.raise_for_status()
            data = resp.json()
            if not data.get("status"):
                raise RuntimeError(f"Angel One candle fetch failed: {data.get('message')}")

            candles = [
                Candle(
                    timestamp=datetime.fromisoformat(row[0]),
                    open=row[1], high=row[2], low=row[3], close=row[4], volume=row[5],
                )
                for row in data["data"]
            ]
            return candles

    async def fetch_snapshot(self, instrument_key: str) -> MarketSnapshot:
        now = datetime.utcnow()
        daily = await self.get_candles(instrument_key, "ONE_DAY", now - timedelta(days=365), now)
        h1 = await self.get_candles(instrument_key, "ONE_HOUR", now - timedelta(days=30), now)
        m15 = await self.get_candles(instrument_key, "FIFTEEN_MINUTE", now - timedelta(days=7), now)

        asset_type = AssetType.INDEX if instrument_key == "NIFTY50" else AssetType.STOCK
        price = daily[-1].close if daily else 0.0

        logger.info(f"Fetched Angel One snapshot for {instrument_key}: price={price}")

        return MarketSnapshot(
            instrument=instrument_key,
            asset_type=asset_type,
            price=price,
            candles_daily=daily,
            candles_4h=h1,  # Angel One has no native 4h; long-term engine resamples from 1h if needed
            candles_1h=h1,
            candles_15m=m15,
        )

    async def fetch_all(self) -> List[MarketSnapshot]:
        snapshots = []
        for key in list(settings.STOCK_SYMBOLS) + list(settings.INDEX_SYMBOLS):
            try:
                snap = await self.fetch_snapshot(key)
                snapshots.append(snap)
            except Exception as e:
                logger.error(f"Angel One fetch failed for {key}: {e}")
        return snapshots


indian_stock_service = AngelOneService()
