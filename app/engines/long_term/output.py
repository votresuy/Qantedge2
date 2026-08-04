"""
Long-term engine — Output step.

Orchestrates the full long-term pipeline for one instrument:
  Daily Trend -> EMA50 -> EMA200 -> RSI14 -> Trend Decision -> 1H Entry ->
  Risk Calculation -> BUY/SELL -> Confidence

For NIFTY50 (index), the pipeline stops at Trend Decision — no entry/SL/TP,
per product requirement (direction only, no trade execution logic).
"""

from typing import Union
from app.schemas.market import MarketSnapshot, AssetType, TradeSignal, IndexTrendSignal, SignalAction
from app.engines.long_term.trend import decide_trend
from app.engines.long_term.signal import confirm_entry_signal
from app.engines.long_term.risk import calculate_risk
from app.utils.logger import get_logger

logger = get_logger("long_term_engine")


def run_long_term_engine(snapshot: MarketSnapshot) -> Union[TradeSignal, IndexTrendSignal]:
    trend, trend_confidence, trend_indicators = decide_trend(snapshot.candles_daily)

    # ---- Index (NIFTY50): trend/direction only, stop here ----
    if snapshot.asset_type == AssetType.INDEX:
        logger.info(f"[long_term] {snapshot.instrument} index trend={trend} confidence={trend_confidence}")
        return IndexTrendSignal(
            instrument=snapshot.instrument,
            trend=trend,
            confidence=trend_confidence,
            indicators=trend_indicators,
        )

    # ---- Forex / Crypto / Stocks: full trade signal ----
    action, entry_info = confirm_entry_signal(trend, snapshot.candles_1h)
    entry_price = snapshot.candles_1h[-1].close if snapshot.candles_1h else snapshot.price

    risk_levels, risk_reward = calculate_risk(entry_price, action, snapshot.candles_daily)

    # Confidence combines daily trend confidence with entry alignment
    final_confidence = trend_confidence if action != SignalAction.NO_TRADE else round(trend_confidence * 0.5, 2)

    indicators = {**trend_indicators, **entry_info, **risk_levels}

    signal = TradeSignal(
        instrument=snapshot.instrument,
        asset_type=snapshot.asset_type,
        engine="long_term",
        signal=action,
        entry=round(entry_price, 5) if action != SignalAction.NO_TRADE else None,
        stop_loss=risk_levels.get("stop_loss"),
        tp1=risk_levels.get("tp1"),
        tp2=risk_levels.get("tp2"),
        risk_reward=risk_reward,
        confidence=final_confidence,
        trend=trend,
        indicators=indicators,
    )

    logger.info(f"[long_term] {snapshot.instrument} signal={action} confidence={final_confidence}")
    return signal
