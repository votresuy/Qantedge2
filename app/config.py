"""
Central configuration for the trading signal backend.
All secrets are loaded from environment variables — never hardcode keys here.
"""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import List


class Settings(BaseSettings):
    # ---------- App ----------
    APP_NAME: str = "TradeSignal Backend"
    ENV: str = "development"  # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # ---------- JWT Auth ----------
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ---------- Firebase ----------
    FIREBASE_CREDENTIALS_PATH: str = "app/firebase/service_account.json"
    FIREBASE_PROJECT_ID: str = ""

    # ---------- Razorpay ----------
    RAZORPAY_KEY_ID: str = ""
    RAZORPAY_KEY_SECRET: str = ""
    RAZORPAY_WEBHOOK_SECRET: str = ""

    # ---------- Market Data APIs ----------
    # Crypto — CoinGecko (free tier, no key required for public endpoints)
    COINGECKO_BASE_URL: str = "https://api.coingecko.com/api/v3"
    COINGECKO_API_KEY: str = ""  # optional, only needed for demo/pro plan

    # Forex — Twelve Data
    TWELVE_DATA_API_KEY: str
    TWELVE_DATA_BASE_URL: str = "https://api.twelvedata.com"

    # Indian Stocks — Angel One SmartAPI
    ANGEL_ONE_API_KEY: str = ""
    ANGEL_ONE_CLIENT_ID: str = ""
    ANGEL_ONE_PASSWORD: str = ""
    ANGEL_ONE_TOTP_SECRET: str = ""
    ANGEL_ONE_BASE_URL: str = "https://apiconnect.angelone.in"

    # ---------- Instruments (fixed set as per product decision) ----------
    FOREX_PAIRS: List[str] = ["XAU/USD", "EUR/USD"]
    CRYPTO_PAIRS: List[str] = ["bitcoin", "solana"]  # CoinGecko ids
    CRYPTO_SYMBOLS: List[str] = ["BTCUSDT", "SOLUSDT"]  # display symbols
    STOCK_SYMBOLS: List[str] = ["ITC", "WIPRO", "HDFCBANK"]
    INDEX_SYMBOLS: List[str] = ["NIFTY50"]

    # ---------- AI Engine (Anthropic) ----------
    ANTHROPIC_API_KEY: str = ""
    ANTHROPIC_MODEL: str = "claude-sonnet-4-6"

    # ---------- Scheduler ----------
    MARKET_POLL_INTERVAL_SECONDS: int = 60  # every minute
    LONG_TERM_ENGINE_INTERVAL_MINUTES: int = 60  # runs hourly (daily trend, 1H entry)
    SHORT_TERM_ENGINE_INTERVAL_MINUTES: int = 15  # runs every 15 min

    # ---------- Signal Cache ----------
    # Live signals are served from an in-memory cache, not read from Firestore
    # on every request. Entries older than this are treated as stale/expired.
    SIGNAL_CACHE_TTL_HOURS: int = 24

    # ---------- CORS ----------
    ALLOWED_ORIGINS: List[str] = ["http://localhost:3000"]

    # ---------- Logging ----------
    LOG_LEVEL: str = "INFO"
    LOG_DIR: str = "app/logs"

    class Config:
        env_file = ".env"
        case_sensitive = True


@lru_cache()
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
