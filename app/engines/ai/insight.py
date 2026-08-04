"""
AI Analysis Engine — Insight step.

Calls the Anthropic API with the prompt built from engine output (trend +
indicators + confidence + entry/SL/TP) and returns a structured AIAnalysis.
This is the ONLY place in the codebase that talks to the AI model.

`build_fallback_analysis()` is a separate, instant, rule-based text generator
with NO network call — the scheduler uses it to publish a signal immediately,
then replaces it with the real AI narration once `generate_ai_analysis()`
finishes in the background. This means a slow or down Anthropic API never
delays or blocks a trade signal from going out.
"""

import httpx
from typing import Union
from app.config import settings
from app.schemas.market import TradeSignal, IndexTrendSignal, AIAnalysis, SignalAction
from app.engines.ai.prompt import build_prompt
from app.engines.ai.formatter import parse_ai_response
from app.utils.logger import get_logger

logger = get_logger("ai_engine")

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"


def build_fallback_analysis(result: Union[TradeSignal, IndexTrendSignal]) -> AIAnalysis:
    """Instant, template-based analysis built only from engine output — no API call,
    so it can never be slow or fail. Marked is_preliminary=True so the frontend/caller
    can tell this apart from the real AI narration that follows."""

    if isinstance(result, IndexTrendSignal):
        return AIAnalysis(
            instrument=result.instrument,
            professional_analysis=(
                f"{result.instrument} is showing a {result.trend.value.lower()} trend on the "
                f"daily timeframe with {result.confidence}% confidence."
            ),
            trade_summary="Direction-only signal — no entry, stop loss, or targets for index instruments.",
            risk_summary="Confidence reflects indicator alignment strength; treat as directional bias only.",
            is_preliminary=True,
        )

    if result.signal == SignalAction.NO_TRADE:
        return AIAnalysis(
            instrument=result.instrument,
            professional_analysis=(
                f"{result.instrument} trend is {result.trend.value.lower()} on the higher "
                f"timeframe, but entry-timeframe confirmation hasn't aligned yet."
            ),
            trade_summary="No trade right now — waiting for timeframe alignment.",
            risk_summary="No open risk since there is no active position.",
            is_preliminary=True,
        )

    action = result.signal.value
    return AIAnalysis(
        instrument=result.instrument,
        professional_analysis=(
            f"{result.instrument} shows a {result.trend.value.lower()} structure, with the "
            f"{result.engine.replace('_', ' ')} engine confirming a {action} at {result.entry}."
        ),
        trade_summary=(
            f"{action} {result.instrument} at {result.entry}, stop loss {result.stop_loss}, "
            f"targets {result.tp1} / {result.tp2}."
        ),
        risk_summary=(
            f"Risk:Reward approximately 1:{result.risk_reward} at {result.confidence}% confidence."
        ),
        why_buy="Trend and timeframe alignment support upside continuation." if action == "BUY" else None,
        why_sell="Trend and timeframe alignment support downside continuation." if action == "SELL" else None,
        is_preliminary=True,
    )


async def generate_ai_analysis(result: Union[TradeSignal, IndexTrendSignal]) -> AIAnalysis:
    prompt = build_prompt(result)

    headers = {
        "x-api-key": settings.ANTHROPIC_API_KEY,
        "anthropic-version": "2023-06-01",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.ANTHROPIC_MODEL,
        "max_tokens": 500,
        "messages": [{"role": "user", "content": prompt}],
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            resp.raise_for_status()
            data = resp.json()

        raw_text = "".join(
            block.get("text", "") for block in data.get("content", []) if block.get("type") == "text"
        )
        parsed = parse_ai_response(raw_text)

        return AIAnalysis(
            instrument=result.instrument,
            professional_analysis=parsed.get("professional_analysis") or "Analysis unavailable.",
            trade_summary=parsed.get("trade_summary") or "Summary unavailable.",
            risk_summary=parsed.get("risk_summary") or "Risk summary unavailable.",
            why_buy=parsed.get("why_buy"),
            why_sell=parsed.get("why_sell"),
            is_preliminary=False,
        )

    except Exception as e:
        logger.error(f"AI analysis generation failed for {result.instrument}: {e}")
        # Graceful fallback — never block signal delivery because AI narration failed.
        # Still marked is_preliminary so a later cycle/retry can attempt to replace it.
        return AIAnalysis(
            instrument=result.instrument,
            professional_analysis="AI analysis temporarily unavailable.",
            trade_summary="See raw signal data.",
            risk_summary="Trade at your own discretion; AI commentary could not be generated.",
            is_preliminary=True,
        )
