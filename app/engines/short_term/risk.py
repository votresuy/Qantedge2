"""
Short-term engine — Risk step.

Uses ATR on the 15-minute timeframe (tighter, faster-reacting stop than the
long-term engine's daily ATR) since this engine trades short intraday moves.

  SL  = entry -/+ (1.0 x ATR14_15m)
  TP1 = entry +/- (1.0 x ATR14_15m)  -> Risk:Reward 1:1
  TP2 = entry +/- (2.0 x ATR14_15m)  -> Risk:Reward 1:2
"""

from typing import List, Tuple
from app.schemas.market import Candle, SignalAction


def _atr(candles: List[Candle], period: int = 14) -> float:
    """Wilder's smoothing (RMA) — matches TradingView's default ATR calculation."""
    if len(candles) < period + 1:
        return 0.0
    true_ranges = []
    for i in range(1, len(candles)):
        high = candles[i].high
        low = candles[i].low
        prev_close = candles[i - 1].close
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        true_ranges.append(tr)

    atr = sum(true_ranges[:period]) / period  # seed value = simple average of first `period` TRs
    for tr in true_ranges[period:]:
        atr = (atr * (period - 1) + tr) / period  # Wilder's smoothing

    return atr


def calculate_risk(entry: float, action: SignalAction, candles_15m: List[Candle]) -> Tuple[dict, float]:
    atr = _atr(candles_15m)
    if atr == 0 or action == SignalAction.NO_TRADE:
        return {"stop_loss": None, "tp1": None, "tp2": None}, 0.0

    sl_distance = 1.0 * atr

    if action == SignalAction.BUY:
        stop_loss = entry - sl_distance
        tp1 = entry + sl_distance
        tp2 = entry + (2 * sl_distance)
    else:
        stop_loss = entry + sl_distance
        tp1 = entry - sl_distance
        tp2 = entry - (2 * sl_distance)

    risk_reward = round(abs(tp2 - entry) / abs(entry - stop_loss), 2) if stop_loss != entry else 0.0

    levels = {
        "stop_loss": round(stop_loss, 5),
        "tp1": round(tp1, 5),
        "tp2": round(tp2, 5),
        "atr14_15m": round(atr, 5),
    }
    return levels, risk_reward
