"""
Shared technical indicator calculations.
Both long-term and short-term engines import from here — only the periods
and timeframes they apply these to differ.
"""

from typing import List
from app.schemas.market import Candle


def closes(candles: List[Candle]) -> List[float]:
    return [c.close for c in candles]


def ema(values: List[float], period: int) -> List[float]:
    """Exponential Moving Average. Returns a list aligned with `values`
    (first `period-1` entries are None-equivalent, we return an empty prefix)."""
    if len(values) < period:
        return []

    ema_values = []
    multiplier = 2 / (period + 1)

    # seed with SMA of first `period` values
    sma = sum(values[:period]) / period
    ema_values.append(sma)

    for price in values[period:]:
        prev = ema_values[-1]
        ema_values.append((price - prev) * multiplier + prev)

    return ema_values


def rsi(values: List[float], period: int = 14) -> List[float]:
    """Relative Strength Index using Wilder's smoothing method."""
    if len(values) < period + 1:
        return []

    gains, losses = [], []
    for i in range(1, len(values)):
        delta = values[i] - values[i - 1]
        gains.append(max(delta, 0))
        losses.append(max(-delta, 0))

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    rsi_values = []
    rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
    rsi_values.append(100 - (100 / (1 + rs)))

    for i in range(period, len(gains)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        rs = avg_gain / avg_loss if avg_loss != 0 else float("inf")
        rsi_values.append(100 - (100 / (1 + rs)))

    return rsi_values


def latest(values: List[float]):
    return values[-1] if values else None


def crossed_above(fast: List[float], slow: List[float]) -> bool:
    """True if the fast series just crossed above the slow series on the latest bar."""
    if len(fast) < 2 or len(slow) < 2:
        return False
    return fast[-2] <= slow[-2] and fast[-1] > slow[-1]


def crossed_below(fast: List[float], slow: List[float]) -> bool:
    if len(fast) < 2 or len(slow) < 2:
        return False
    return fast[-2] >= slow[-2] and fast[-1] < slow[-1]
