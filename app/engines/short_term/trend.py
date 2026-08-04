"""
Short-term engine — Trend Decision step.

Uses the 4H timeframe with a "stacked EMA" read (EMA5/10/20/30):
  Bullish  : EMA5 > EMA10 > EMA20 > EMA30 (fully stacked up, fast above slow)
  Bearish  : EMA5 < EMA10 < EMA20 < EMA30 (fully stacked down)
  Sideways : EMAs interleaved / not cleanly stacked

Confidence is based on how wide the EMA fan is (stronger separation = stronger trend).
"""

from typing import List, Tuple
from app.schemas.market import Candle, TrendDirection
from app.engines.short_term.ema import get_ema_stack


def decide_trend_4h(candles_4h: List[Candle]) -> Tuple[TrendDirection, float, dict]:
    stack = get_ema_stack(candles_4h)
    ema5, ema10, ema20, ema30 = stack["ema5"], stack["ema10"], stack["ema20"], stack["ema30"]

    if not (ema5 and ema10 and ema20 and ema30):
        return TrendDirection.SIDEWAYS, 0.0, {"reason": "insufficient_4h_data"}

    e5, e10, e20, e30 = ema5[-1], ema10[-1], ema20[-1], ema30[-1]
    indicators = {"ema5": round(e5, 5), "ema10": round(e10, 5), "ema20": round(e20, 5), "ema30": round(e30, 5)}

    bullish_stack = e5 > e10 > e20 > e30
    bearish_stack = e5 < e10 < e20 < e30

    if bullish_stack:
        trend = TrendDirection.BULLISH
        spread_pct = ((e5 - e30) / e30) * 100
        confidence = min(50 + spread_pct * 8, 100)
    elif bearish_stack:
        trend = TrendDirection.BEARISH
        spread_pct = ((e30 - e5) / e30) * 100
        confidence = min(50 + spread_pct * 8, 100)
    else:
        trend = TrendDirection.SIDEWAYS
        confidence = 30.0

    confidence = round(max(0.0, min(confidence, 100.0)), 2)
    return trend, confidence, indicators
