"""
Position Tracking Service — Win/Loss outcome tracking.

When a BUY/SELL signal is generated, its entry/SL/TP1 levels are registered
as an "open position". On every scheduler cycle, each open position is
checked against the latest cached market price:

  BUY:  price <= stop_loss -> LOSS   |   price >= tp1 -> WIN
  SELL: price >= stop_loss -> LOSS   |   price <= tp1 -> WIN

Resolution uses TP1 (the first target) as the win threshold, so outcomes are
decided promptly rather than waiting indefinitely for TP2. Both the
`open_positions` record and the original `history` record are updated so the
Signal History page can show real Win/Loss/Running status.
"""

from typing import Optional
from app.firebase.firestore_repo import (
    create_open_position,
    get_open_positions,
    close_open_position,
    update_history_status,
)
from app.market.cache import market_cache
from app.utils.logger import get_logger

logger = get_logger("tracking_service")


def register_open_position(signal_data: dict, history_doc_id: str) -> Optional[str]:
    """Called right after a signal is persisted — starts tracking BUY/SELL outcomes.
    NO_TRADE and index trend signals (no entry/SL/TP) are skipped."""
    if signal_data.get("signal") not in ("BUY", "SELL"):
        return None
    if signal_data.get("stop_loss") is None or signal_data.get("tp1") is None:
        return None

    position_id = create_open_position({
        "instrument": signal_data["instrument"],
        "engine": signal_data.get("engine"),
        "signal": signal_data["signal"],
        "entry": signal_data["entry"],
        "stop_loss": signal_data["stop_loss"],
        "tp1": signal_data["tp1"],
        "tp2": signal_data.get("tp2"),
        "history_doc_id": history_doc_id,
    })
    logger.info(f"Registered open position for {signal_data['instrument']} ({position_id})")
    return position_id


def _evaluate(position: dict, price: float) -> Optional[str]:
    action = position["signal"]
    sl = position["stop_loss"]
    tp1 = position["tp1"]

    if action == "BUY":
        if price <= sl:
            return "LOSS"
        if price >= tp1:
            return "WIN"
    elif action == "SELL":
        if price >= sl:
            return "LOSS"
        if price <= tp1:
            return "WIN"
    return None


def check_open_positions() -> None:
    """Scheduler job — runs every cycle, resolves any position that has hit SL or TP1."""
    positions = get_open_positions()
    if not positions:
        return

    resolved_count = 0
    for pos in positions:
        snapshot = market_cache.get(pos["instrument"])
        if not snapshot:
            continue

        outcome = _evaluate(pos, snapshot.price)
        if outcome:
            close_open_position(pos["id"], outcome, snapshot.price)
            if pos.get("history_doc_id"):
                update_history_status(pos["history_doc_id"], outcome, snapshot.price)
            logger.info(
                f"Position resolved: {pos['instrument']} {pos['signal']} -> {outcome} @ {snapshot.price}"
            )
            resolved_count += 1

    if resolved_count:
        logger.info(f"check_open_positions: resolved {resolved_count} position(s)")
