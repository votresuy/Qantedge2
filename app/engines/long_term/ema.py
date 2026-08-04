"""Long-term engine — EMA step. Uses Daily candles, EMA50 and EMA200."""

from typing import List
from app.schemas.market import Candle
from app.utils.indicators import closes, ema


def get_ema50(daily_candles: List[Candle]) -> List[float]:
    return ema(closes(daily_candles), period=50)


def get_ema200(daily_candles: List[Candle]) -> List[float]:
    return ema(closes(daily_candles), period=200)
