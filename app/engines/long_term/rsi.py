"""Long-term engine — RSI step. Uses Daily candles, RSI 14."""

from typing import List
from app.schemas.market import Candle
from app.utils.indicators import closes, rsi


def get_rsi14(daily_candles: List[Candle]) -> List[float]:
    return rsi(closes(daily_candles), period=14)
