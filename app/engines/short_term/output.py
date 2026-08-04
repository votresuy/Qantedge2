"""
Short-term engine — Output step.

Orchestrates the full short-term pipeline for one instrument:
  4H Trend -> EMA5/10/20/30 -> 1H Confirmation -> 15M Entry ->
  Risk Reward -> BUY/SELL -> Confidence

Note: short-term engine is not applied to NIFTY50 (index trend-only requirement
is handled by the long-term engine); scheduler only routes tradeable instruments
(forex, crypto, stocks) into this engine.
"""

from app.schemas.market import MarketSnapshot, TradeSignal, SignalAction
from app.engines.short_term.trend import decide_trend_4h
from app.engines.short_term.signal import confirm_1h, get_entry_action
from app.engines.short_term.risk import calculate_risk
from app.utils.logger import get_logger

logger = get_logger("short_term_engine")


def run_short_term_engine(snapshot: MarketSnapshot) -> TradeSignal:
    trend, trend_confidence, trend_indicators = decide_trend_4h(snapshot.candles_4h)

    confirmed, confirm_info = confirm_1h(trend, snapshot.candles_1h)
    action, entry_price = get_entry_action(trend, confirmed, snapshot.candles_15m)

    risk_levels, risk_reward = calculate_risk(entry_price, action, snapshot.candles_15m)

    final_confidence = trend_confidence if action != SignalAction.NO_TRADE else round(trend_confidence * 0.5, 2)

    indicators = {**trend_indicators, **confirm_info, **risk_levels}

    signal = TradeSignal(
        instrument=snapshot.instrument,
        asset_type=snapshot.asset_type,
        engine="short_term",
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

    logger.info(f"[short_term] {snapshot.instrument} signal={action} confidence={final_confidence}")
    return signal
