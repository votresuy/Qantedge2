"""
Shared Pydantic schemas used across market data services and signal engines.
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


class AssetType(str, Enum):
    FOREX = "forex"
    CRYPTO = "crypto"
    STOCK = "stock"
    INDEX = "index"


class Candle(BaseModel):
    """Single OHLCV candle."""
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    volume: Optional[float] = 0.0


class MarketSnapshot(BaseModel):
    """Clean, validated market data passed from Market Data Service to engines."""
    instrument: str
    asset_type: AssetType
    price: float
    candles_daily: List[Candle] = Field(default_factory=list)
    candles_4h: List[Candle] = Field(default_factory=list)
    candles_1h: List[Candle] = Field(default_factory=list)
    candles_15m: List[Candle] = Field(default_factory=list)
    fetched_at: datetime = Field(default_factory=datetime.utcnow)


class TrendDirection(str, Enum):
    BULLISH = "Bullish"
    BEARISH = "Bearish"
    SIDEWAYS = "Sideways"


class SignalAction(str, Enum):
    BUY = "BUY"
    SELL = "SELL"
    NO_TRADE = "NO_TRADE"


class TradeSignal(BaseModel):
    """Full tradeable signal output — used for forex, crypto, and individual stocks."""
    instrument: str
    asset_type: AssetType
    engine: Literal["long_term", "short_term"]
    signal: SignalAction
    entry: Optional[float] = None
    stop_loss: Optional[float] = None
    tp1: Optional[float] = None
    tp2: Optional[float] = None
    risk_reward: Optional[float] = None
    confidence: float = Field(ge=0, le=100)
    trend: TrendDirection
    indicators: dict = Field(default_factory=dict)
    status: Literal["RUNNING", "WIN", "LOSS", "N/A"] = "N/A"
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class IndexTrendSignal(BaseModel):
    """Directional-bias-only output for indices like NIFTY50 — no entry/SL/TP."""
    instrument: str
    asset_type: AssetType = AssetType.INDEX
    trend: TrendDirection
    confidence: float = Field(ge=0, le=100)
    indicators: dict = Field(default_factory=dict)
    generated_at: datetime = Field(default_factory=datetime.utcnow)


class AIAnalysis(BaseModel):
    """Output of the AI Analysis Engine — built ONLY from engine output, never raw market data."""
    instrument: str
    professional_analysis: str
    trade_summary: str
    risk_summary: str
    why_buy: Optional[str] = None
    why_sell: Optional[str] = None
    is_preliminary: bool = False  # True = instant rule-based text, real AI narration still pending
    generated_at: datetime = Field(default_factory=datetime.utcnow)
