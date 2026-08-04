"""
Long-term engine — Signal step.

Takes the Daily Trend Decision and confirms/times the entry using the 1-Hour
timeframe. Produces the final BUY / SELL / NO_TRADE action.

Logic:
  - If Daily trend is Bullish: look for 1H EMA50 to be above 1H EMA200 (trend
    aligned across timeframes) -> BUY. If 1H structure disagrees -> NO_TRADE
    (wait for alignment rather than force a trade).
  - Mirror logic for Bearish -> SELL.
  - Sideways daily trend never produces a trade.
"""

from typing import List, Tuple
from app.schemas.market import Candle, TrendDirection, SignalAction
from app.utils.indicators import closes, ema


def confirm_entry_signal(daily_trend: TrendDirection, hourly_candles: List[Candle]) -> Tuple[SignalAction, dict]:
    if daily_trend == TrendDirection.SIDEWAYS:
        return SignalAction.NO_TRADE, {"reason": "daily_trend_sideways"}

    h_ema50 = ema(closes(hourly_candles), period=50)
    h_ema200 = ema(closes(hourly_candles), period=200)

    if not h_ema50 or not h_ema200:
        return SignalAction.NO_TRADE, {"reason": "insufficient_1h_data"}

    h_ema50_last = h_ema50[-1]
    h_ema200_last = h_ema200[-1]
    hourly_bullish = h_ema50_last > h_ema200_last
    hourly_bearish = h_ema50_last < h_ema200_last

    info = {"ema50_1h": round(h_ema50_last, 4), "ema200_1h": round(h_ema200_last, 4)}

    if daily_trend == TrendDirection.BULLISH and hourly_bullish:
        return SignalAction.BUY, info
    if daily_trend == TrendDirection.BEARISH and hourly_bearish:
        return SignalAction.SELL, info

    info["reason"] = "1h_not_aligned_with_daily_trend"
    return SignalAction.NO_TRADE, info
