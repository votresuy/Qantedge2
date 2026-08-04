"""
AI Analysis Engine — Prompt step.

CRITICAL RULE: AI never reads market APIs directly. It only receives the
already-computed engine output (trend, indicators, confidence, entry, SL, TP).
This keeps the AI's job purely explanatory/analytical, not decision-making.
"""

from typing import Union
from app.schemas.market import TradeSignal, IndexTrendSignal


def build_prompt(result: Union[TradeSignal, IndexTrendSignal]) -> str:
    if isinstance(result, IndexTrendSignal):
        return f"""You are a professional market analyst. Based ONLY on the structured data below
(do not invent any numbers not present here), write a concise professional analysis.

Instrument: {result.instrument}
Trend: {result.trend.value}
Confidence: {result.confidence}%
Indicators: {result.indicators}

Respond in this exact format:
PROFESSIONAL_ANALYSIS: <2-3 sentence market read>
TRADE_SUMMARY: <one sentence, note this is directional bias only, no trade levels>
RISK_SUMMARY: <one sentence on risk/caution given the confidence level>
"""

    action_line = f"Signal: {result.signal.value}"
    levels_line = (
        f"Entry: {result.entry}, Stop Loss: {result.stop_loss}, TP1: {result.tp1}, "
        f"TP2: {result.tp2}, Risk:Reward: {result.risk_reward}"
        if result.signal.value != "NO_TRADE" else "No trade levels — signal is NO_TRADE."
    )

    return f"""You are a professional market analyst. Based ONLY on the structured data below
(do not invent any numbers not present here), write a concise professional analysis.

Instrument: {result.instrument}
Engine: {result.engine}
Trend: {result.trend.value}
{action_line}
{levels_line}
Confidence: {result.confidence}%
Indicators: {result.indicators}

Respond in this exact format:
PROFESSIONAL_ANALYSIS: <2-3 sentence market read explaining the trend and setup>
TRADE_SUMMARY: <one sentence summarizing the trade plan>
RISK_SUMMARY: <one sentence on risk given confidence and risk:reward>
WHY_BUY: <one sentence, only if signal is BUY, else write "N/A">
WHY_SELL: <one sentence, only if signal is SELL, else write "N/A">
"""
