"""Short-term engine — RSI step. Uses 1H candles for confirmation, RSI 14."""

from typing import List
from app.schemas.market import Candle
from app.utils.indicators import closes, rsi


def get_rsi14(candles: List[Candle]) -> List[float]:
    return rsi(closes(candles), period=14)
