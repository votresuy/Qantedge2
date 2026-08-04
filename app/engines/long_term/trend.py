"""
Long-term engine — Trend Decision step.

Combines Daily Trend + EMA50 + EMA200 + RSI14 into a single directional bias.

Rules:
  Bullish  : price > EMA50 > EMA200  AND RSI14 > 50
  Bearish  : price < EMA50 < EMA200  AND RSI14 < 50
  Sideways : anything else (EMAs not aligned, or RSI disagreeing with EMA structure)

Confidence is scored 0-100 based on how strongly the three signals agree
(EMA separation strength + RSI distance from midline).
"""

from typing import List, Tuple
from app.schemas.market import Candle, TrendDirection
from app.engines.long_term.ema import get_ema50, get_ema200
from app.engines.long_term.rsi import get_rsi14


def decide_trend(daily_candles: List[Candle]) -> Tuple[TrendDirection, float, dict]:
    ema50_series = get_ema50(daily_candles)
    ema200_series = get_ema200(daily_candles)
    rsi_series = get_rsi14(daily_candles)

    if not ema50_series or not ema200_series or not rsi_series:
        return TrendDirection.SIDEWAYS, 0.0, {"reason": "insufficient_data"}

    price = daily_candles[-1].close
    ema50 = ema50_series[-1]
    ema200 = ema200_series[-1]
    rsi14 = rsi_series[-1]

    indicators = {"ema50": round(ema50, 4), "ema200": round(ema200, 4), "rsi14": round(rsi14, 2), "price": price}

    bullish_structure = price > ema50 > ema200
    bearish_structure = price < ema50 < ema200

    if bullish_structure and rsi14 > 50:
        trend = TrendDirection.BULLISH
        # confidence: EMA separation % + RSI distance from 50, capped at 100
        ema_gap_pct = min(((ema50 - ema200) / ema200) * 100, 10)  # cap contribution
        rsi_strength = min(rsi14 - 50, 30)
        confidence = 50 + (ema_gap_pct * 2) + rsi_strength
    elif bearish_structure and rsi14 < 50:
        trend = TrendDirection.BEARISH
        ema_gap_pct = min(((ema200 - ema50) / ema200) * 100, 10)
        rsi_strength = min(50 - rsi14, 30)
        confidence = 50 + (ema_gap_pct * 2) + rsi_strength
    else:
        trend = TrendDirection.SIDEWAYS
        confidence = 35.0  # low confidence — no clean structure

    confidence = round(max(0.0, min(confidence, 100.0)), 2)
    return trend, confidence, indicators
