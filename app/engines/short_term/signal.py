"""
Short-term engine — Signal step.

  1H Confirmation : RSI14 on 1H must agree with the 4H trend direction
                     (RSI > 50 for bullish, RSI < 50 for bearish).
  15M Entry        : latest 15-minute close is used as the precise entry price,
                     once 4H trend + 1H confirmation both align.
"""

from typing import List, Tuple
from app.schemas.market import Candle, TrendDirection, SignalAction
from app.engines.short_term.rsi import get_rsi14


def confirm_1h(trend_4h: TrendDirection, candles_1h: List[Candle]) -> Tuple[bool, dict]:
    rsi_series = get_rsi14(candles_1h)
    if not rsi_series:
        return False, {"reason": "insufficient_1h_data"}

    rsi1h = rsi_series[-1]
    info = {"rsi_1h": round(rsi1h, 2)}

    if trend_4h == TrendDirection.BULLISH and rsi1h > 50:
        return True, info
    if trend_4h == TrendDirection.BEARISH and rsi1h < 50:
        return True, info

    info["reason"] = "1h_rsi_not_aligned"
    return False, info


def get_entry_action(trend_4h: TrendDirection, confirmed: bool, candles_15m: List[Candle]) -> Tuple[SignalAction, float]:
    if not confirmed or trend_4h == TrendDirection.SIDEWAYS or not candles_15m:
        return SignalAction.NO_TRADE, 0.0

    entry_price = candles_15m[-1].close
    action = SignalAction.BUY if trend_4h == TrendDirection.BULLISH else SignalAction.SELL
    return action, entry_price
