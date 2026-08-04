"""Short-term engine — EMA step. Uses 4H candles, EMA 5/10/20/30 (stacked-EMA trend read)."""

from typing import List
from app.schemas.market import Candle
from app.utils.indicators import closes, ema


def get_ema_stack(candles: List[Candle]) -> dict:
    c = closes(candles)
    return {
        "ema5": ema(c, period=5),
        "ema10": ema(c, period=10),
        "ema20": ema(c, period=20),
        "ema30": ema(c, period=30),
    }
