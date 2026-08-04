"""
Scheduler Service — Step 1 + pipeline orchestration.

  Every Minute      -> refresh market data (Market Data Service)
  Every 5 Minutes    -> check open positions for Win/Loss outcome
  Every 60 Minutes  -> run Long-Term Engine (daily trend + 1H entry)
  Every 15 Minutes  -> run Short-Term Engine (4H trend + 15M entry)
  Every 24 Hours    -> check for expiring subscriptions/trials, send reminders

Both engines' output is passed to the AI Analysis Engine, then stored in
Firestore (live signal + history), a Win/Loss tracker is registered for
BUY/SELL signals, and a broadcast notification is dispatched for
high-confidence signals.
"""

"""
Scheduler Service — Step 1 + pipeline orchestration.

  Every Minute      -> refresh market data (Market Data Service)
  Every 5 Minutes    -> check open positions for Win/Loss outcome
  Every 60 Minutes  -> run Long-Term Engine (daily trend + 1H entry)
  Every 15 Minutes  -> run Short-Term Engine (4H trend + 15M entry)
  Every 24 Hours    -> check for expiring subscriptions/trials, send reminders

Both engines' output is saved and broadcast IMMEDIATELY with an instant,
rule-based "preliminary" analysis (see build_fallback_analysis) — trade
signals are never delayed or blocked by the AI Analysis Engine. The real
AI-generated narration is then fetched in the background and patches the
signal (cache + Firestore live + history) in place once it's ready. A slow
or unavailable Anthropic API can never hold up a signal going out.
"""

import asyncio
from datetime import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.market.market_data_service import market_data_service
from app.engines.long_term.output import run_long_term_engine
from app.engines.short_term.output import run_short_term_engine
from app.engines.ai.insight import generate_ai_analysis, build_fallback_analysis
from app.firebase.firestore_repo import (
    save_live_signal,
    append_history,
    update_history_ai_analysis,
    get_all_users,
    save_user,
)
from app.services.tracking_service import register_open_position, check_open_positions
from app.services.signal_cache_service import signal_cache_service
from app.schemas.market import AssetType, IndexTrendSignal
from app.utils.logger import get_logger

logger = get_logger("scheduler")

scheduler = AsyncIOScheduler()

EXPIRY_REMINDER_DAYS = 2


async def _enrich_with_real_ai(result, instrument: str, history_doc_id: str):
    """Background task: fetches the real AI narration and patches it into the
    already-published signal. Runs independently of the main publish path, so
    it can take as long as it needs without delaying any trade signal."""
    try:
        ai_analysis = await generate_ai_analysis(result)
        ai_data = ai_analysis.model_dump(mode="json")

        cached = signal_cache_service.get(instrument)
        if cached:
            cached["ai_analysis"] = ai_data
            signal_cache_service.set(instrument, cached)
            save_live_signal(instrument, cached)

        update_history_ai_analysis(history_doc_id, ai_data)
        logger.info(f"AI analysis enriched for {instrument} (history doc {history_doc_id})")
    except Exception as e:
        logger.error(f"Background AI enrichment failed for {instrument}: {e}")


async def _persist_and_notify(result):
    data = result.model_dump(mode="json")

    # Publish immediately with an instant, rule-based analysis — never wait on
    # the Anthropic API before a signal goes live.
    fallback_analysis = build_fallback_analysis(result)
    data["ai_analysis"] = fallback_analysis.model_dump(mode="json")

    # Initial outcome status — RUNNING for tradeable BUY/SELL signals, N/A otherwise
    # (NO_TRADE, or index trend signals which have no entry/SL/TP to track).
    data["status"] = "RUNNING" if data.get("signal") in ("BUY", "SELL") else "N/A"

    save_live_signal(result.instrument, data)
    signal_cache_service.set(result.instrument, data)
    history_doc_id = append_history(result.instrument, data)

    if not isinstance(result, IndexTrendSignal) and result.signal.value != "NO_TRADE":
        register_open_position(data, history_doc_id)

        from app.services.notification_service import notification_service
        await notification_service.notify_new_signal(
            result.instrument, result.signal.value, result.confidence
        )

    # Fire-and-forget: real AI narration replaces the fallback text once ready,
    # without blocking this instrument or delaying the next one in the cycle.
    asyncio.create_task(_enrich_with_real_ai(result, result.instrument, history_doc_id))


async def poll_market_data():
    """Runs every minute — Step 1 + Step 2 of the pipeline."""
    logger.info("Scheduler: polling market data...")
    await market_data_service.refresh_all()


async def run_long_term_cycle():
    """Runs hourly — Step 3 of the pipeline."""
    logger.info("Scheduler: running long-term engine cycle...")
    snapshots = market_data_service.get_all_cached()
    for instrument, snapshot in snapshots.items():
        try:
            result = run_long_term_engine(snapshot)
            await _persist_and_notify(result)
        except Exception as e:
            logger.error(f"Long-term engine failed for {instrument}: {e}")


async def run_short_term_cycle():
    """Runs every 15 min — Step 4 of the pipeline (skips indices, e.g. NIFTY50)."""
    logger.info("Scheduler: running short-term engine cycle...")
    snapshots = market_data_service.get_all_cached()
    for instrument, snapshot in snapshots.items():
        if snapshot.asset_type == AssetType.INDEX:
            continue  # index instruments are trend-only, handled by long-term engine
        try:
            result = run_short_term_engine(snapshot)
            await _persist_and_notify(result)
        except Exception as e:
            logger.error(f"Short-term engine failed for {instrument}: {e}")


async def run_position_tracking_cycle():
    """Runs every 5 minutes — resolves open BUY/SELL positions as WIN/LOSS."""
    try:
        check_open_positions()
    except Exception as e:
        logger.error(f"Position tracking cycle failed: {e}")


async def run_expiry_reminder_cycle():
    """Runs daily — reminds users whose subscription or trial is about to expire."""
    from app.services.notification_service import notification_service

    try:
        users = get_all_users()
    except Exception as e:
        logger.error(f"Expiry reminder cycle failed to load users: {e}")
        return

    now = datetime.utcnow()
    for user in users:
        uid = user.get("uid")
        if not uid:
            continue

        is_trial = not user.get("is_subscribed")
        expiry_str = user.get("subscription_expiry") if not is_trial else user.get("trial_expiry")
        if not expiry_str:
            continue

        try:
            expiry = datetime.fromisoformat(expiry_str)
        except ValueError:
            continue

        days_left = (expiry - now).days
        already_notified = user.get("last_expiry_notified") == expiry_str

        if 0 <= days_left <= EXPIRY_REMINDER_DAYS and not already_notified:
            try:
                await notification_service.notify_expiry_reminder(uid, max(days_left, 0), is_trial)
                save_user(uid, {"last_expiry_notified": expiry_str})
            except Exception as e:
                logger.error(f"Failed to send expiry reminder to {uid}: {e}")


def start_scheduler():
    scheduler.add_job(poll_market_data, "interval", seconds=settings.MARKET_POLL_INTERVAL_SECONDS, id="poll_market_data")
    scheduler.add_job(run_long_term_cycle, "interval", minutes=settings.LONG_TERM_ENGINE_INTERVAL_MINUTES, id="long_term_cycle")
    scheduler.add_job(run_short_term_cycle, "interval", minutes=settings.SHORT_TERM_ENGINE_INTERVAL_MINUTES, id="short_term_cycle")
    scheduler.add_job(run_position_tracking_cycle, "interval", minutes=5, id="position_tracking_cycle")
    scheduler.add_job(run_expiry_reminder_cycle, "interval", hours=24, id="expiry_reminder_cycle")
    scheduler.start()
    logger.info(
        "Scheduler started: market poll (1m), long-term (60m), short-term (15m), "
        "position tracking (5m), expiry reminders (24h)"
    )


def stop_scheduler():
    scheduler.shutdown(wait=False)
