"""
Firestore collection helpers — Step 6 of the pipeline (Store).

Collections:
  signals         -> latest live signal per instrument (overwritten each cycle)
  history         -> append-only log of every generated signal (for track record)
  open_positions  -> BUY/SELL signals currently being tracked for Win/Loss outcome
  users           -> user profiles + subscription state
  payments        -> record of every verified Razorpay payment
  notifications   -> per-user + broadcast notification history
"""

from datetime import datetime
from typing import Optional, List
from app.firebase.firebase_init import get_firestore
from app.utils.logger import get_logger

logger = get_logger("firestore_repo")

SIGNALS_COLLECTION = "signals"
HISTORY_COLLECTION = "history"
OPEN_POSITIONS_COLLECTION = "open_positions"
USERS_COLLECTION = "users"
PAYMENTS_COLLECTION = "payments"
NOTIFICATIONS_COLLECTION = "notifications"


# ---------------- Signals & History ----------------

def save_live_signal(instrument: str, data: dict):
    db = get_firestore()
    data["updated_at"] = datetime.utcnow().isoformat()
    db.collection(SIGNALS_COLLECTION).document(instrument).set(data)
    logger.info(f"Saved live signal for {instrument}")


def append_history(instrument: str, data: dict) -> str:
    """Returns the Firestore document id so callers (e.g. tracking_service) can
    later update this exact record's outcome status."""
    db = get_firestore()
    data["created_at"] = datetime.utcnow().isoformat()
    data.setdefault("status", "RUNNING" if data.get("signal") in ("BUY", "SELL") else "N/A")
    _, doc_ref = db.collection(HISTORY_COLLECTION).add(data)
    logger.info(f"Appended history record for {instrument} ({doc_ref.id})")
    return doc_ref.id


def update_history_status(history_doc_id: str, status: str, closed_price: Optional[float] = None):
    db = get_firestore()
    update = {"status": status, "resolved_at": datetime.utcnow().isoformat()}
    if closed_price is not None:
        update["closed_price"] = closed_price
    db.collection(HISTORY_COLLECTION).document(history_doc_id).update(update)


def update_history_ai_analysis(history_doc_id: str, ai_analysis: dict):
    """Patches in the real AI-generated analysis once ready, replacing the
    instant rule-based fallback that was saved when the signal first fired."""
    db = get_firestore()
    db.collection(HISTORY_COLLECTION).document(history_doc_id).update({"ai_analysis": ai_analysis})


def get_live_signal(instrument: str) -> Optional[dict]:
    db = get_firestore()
    doc = db.collection(SIGNALS_COLLECTION).document(instrument).get()
    return doc.to_dict() if doc.exists else None


def get_all_live_signals() -> List[dict]:
    db = get_firestore()
    docs = db.collection(SIGNALS_COLLECTION).stream()
    return [d.to_dict() for d in docs]


def get_history(instrument: Optional[str] = None, limit: int = 50) -> List[dict]:
    db = get_firestore()
    query = db.collection(HISTORY_COLLECTION)
    if instrument:
        query = query.where("instrument", "==", instrument)
    query = query.order_by("created_at", direction="DESCENDING").limit(limit)
    results = []
    for d in query.stream():
        record = d.to_dict()
        record["id"] = d.id
        results.append(record)
    return results


# ---------------- Open Positions (Win/Loss tracking) ----------------

def create_open_position(data: dict) -> str:
    db = get_firestore()
    data["opened_at"] = datetime.utcnow().isoformat()
    data["status"] = "RUNNING"
    _, doc_ref = db.collection(OPEN_POSITIONS_COLLECTION).add(data)
    return doc_ref.id


def get_open_positions() -> List[dict]:
    db = get_firestore()
    query = db.collection(OPEN_POSITIONS_COLLECTION).where("status", "==", "RUNNING")
    results = []
    for d in query.stream():
        record = d.to_dict()
        record["id"] = d.id
        results.append(record)
    return results


def close_open_position(position_id: str, status: str, closed_price: float):
    db = get_firestore()
    db.collection(OPEN_POSITIONS_COLLECTION).document(position_id).update({
        "status": status,
        "closed_price": closed_price,
        "closed_at": datetime.utcnow().isoformat(),
    })


# ---------------- Users & Subscription ----------------

def get_user(uid: str) -> Optional[dict]:
    db = get_firestore()
    doc = db.collection(USERS_COLLECTION).document(uid).get()
    return doc.to_dict() if doc.exists else None


def get_all_users() -> List[dict]:
    db = get_firestore()
    docs = db.collection(USERS_COLLECTION).stream()
    return [d.to_dict() for d in docs]


def save_user(uid: str, data: dict):
    db = get_firestore()
    db.collection(USERS_COLLECTION).document(uid).set(data, merge=True)


def update_subscription(uid: str, plan: str, expiry_iso: str):
    db = get_firestore()
    db.collection(USERS_COLLECTION).document(uid).update({
        "is_subscribed": True,
        "subscription_plan": plan,
        "subscription_expiry": expiry_iso,
    })
    logger.info(f"Updated subscription for user {uid}: plan={plan}")


# ---------------- Payments ----------------

def save_payment(uid: str, data: dict) -> str:
    db = get_firestore()
    data["uid"] = uid
    data["created_at"] = datetime.utcnow().isoformat()
    _, doc_ref = db.collection(PAYMENTS_COLLECTION).add(data)
    logger.info(f"Saved payment record for user {uid} ({doc_ref.id})")
    return doc_ref.id


def get_payments(uid: str, limit: int = 50) -> List[dict]:
    db = get_firestore()
    query = (
        db.collection(PAYMENTS_COLLECTION)
        .where("uid", "==", uid)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )
    results = []
    for d in query.stream():
        record = d.to_dict()
        record["id"] = d.id
        results.append(record)
    return results


# ---------------- Notifications ----------------

def save_notification(data: dict) -> str:
    """data['uid'] = None means a broadcast notification (visible to all users)."""
    db = get_firestore()
    data["created_at"] = datetime.utcnow().isoformat()
    data.setdefault("read", False)
    _, doc_ref = db.collection(NOTIFICATIONS_COLLECTION).add(data)
    return doc_ref.id


def get_notifications(uid: str, limit: int = 50) -> List[dict]:
    db = get_firestore()

    user_query = (
        db.collection(NOTIFICATIONS_COLLECTION)
        .where("uid", "==", uid)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )
    broadcast_query = (
        db.collection(NOTIFICATIONS_COLLECTION)
        .where("uid", "==", None)
        .order_by("created_at", direction="DESCENDING")
        .limit(limit)
    )

    results = []
    for d in list(user_query.stream()) + list(broadcast_query.stream()):
        record = d.to_dict()
        record["id"] = d.id
        results.append(record)

    results.sort(key=lambda r: r.get("created_at", ""), reverse=True)
    return results[:limit]


def mark_notification_read(notification_id: str):
    db = get_firestore()
    db.collection(NOTIFICATIONS_COLLECTION).document(notification_id).update({"read": True})
