"""
Long-term engine — Risk step.

Calculates Stop Loss and Take Profit levels using ATR (Average True Range)
on the Daily timeframe — appropriate for a swing/positional style engine.

  SL  = entry -/+ (1.5 x ATR14)
  TP1 = entry +/- (1.5 x ATR14)   -> Risk:Reward 1:1
  TP2 = entry +/- (3.0 x ATR14)   -> Risk:Reward 1:2
"""

from typing import List, Tuple
from app.schemas.market import Candle, SignalAction


def _atr(daily_candles: List[Candle], period: int = 14) -> float:
    """Wilder's smoothing (RMA) — matches TradingView's default ATR calculation."""
    if len(daily_candles) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, len(daily_candles)):
        high = daily_candles[i].high
        low = daily_candles[i].low
        prev_close = daily_candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    atr = sum(true_ranges[:period]) / period  # seed value = simple average of first `period` TRs
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period  # Wilder's smoothing

    return atr


def calculate_risk(entry: float, action: SignalAction, daily_candles: List[Candle]) -> Tuple[dict, float]:
    atr = _atr(daily_candles)
    if atr == 0 or action == SignalAction.NO_TRADE:
        return {"stop_loss": None, "tp1": None, "tp2": None}, 0.0

    sl_distance = 1.5 * atr

    if action == SignalAction.BUY:
        stop_loss = entry - sl_distance
        tp1 = entry + sl_distance          # 1:1
        tp2 = entry + (2 * sl_distance)    # 1:2
    else:  # SELL
        stop_loss = entry + sl_distance
        tp1 = entry - sl_distance
        tp2 = entry - (2 * sl_distance)

    risk_reward = round(abs(tp2 - entry) / abs(entry - stop_loss), 2) if stop_loss != entry else 0.0

    levels = {
        "stop_loss": round(stop_loss, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "atr14": round(atr, 5),
    }
    return levels, risk_reward
