"""
Notification Service — push delivery (FCM) + persisted notification history.

Two kinds of notifications are stored in Firestore's `notifications` collection:
  - Per-user (uid set): payment confirmations, subscription/trial expiry reminders
  - Broadcast (uid = None): new high-confidence signal alerts, visible to everyone

The frontend's Notifications page reads this history via
GET /api/v1/notifications — separate from the FCM push, which is best-effort
and fire-and-forget.
"""

from typing import Optional
from firebase_admin import messaging
from app.firebase.firestore_repo import save_notification, get_notifications, mark_notification_read
from app.utils.logger import get_logger

logger = get_logger("notification_service")

MIN_CONFIDENCE_FOR_ALERT = 70.0


class NotificationService:
    # ---------------- Push delivery (best-effort) ----------------
    def _send_push(self, fcm_tokens: list[str], title: str, body: str):
        if not fcm_tokens:
            return
        message = messaging.MulticastMessage(
            notification=messaging.Notification(title=title, body=body),
            tokens=fcm_tokens,
        )
        try:
            response = messaging.send_multicast(message)
            logger.info(f"Push sent: {response.success_count} succeeded, {response.failure_count} failed")
        except Exception as e:
            logger.error(f"Push send failed: {e}")

    # ---------------- New signal alert (broadcast) ----------------
    async def notify_new_signal(
        self,
        instrument: str,
        action: str,
        confidence: float,
        fcm_tokens: Optional[list[str]] = None,
    ):
        if confidence < MIN_CONFIDENCE_FOR_ALERT:
            return

        title = f"New {action} Signal: {instrument}"
        body = f"Confidence: {confidence}% — check the app for entry, SL, and targets."

        save_notification({
            "uid": None,  # broadcast — visible to all users
            "type": "new_signal",
            "title": title,
            "body": body,
            "instrument": instrument,
        })

        if fcm_tokens:
            self._send_push(fcm_tokens, title, body)

    # ---------------- Payment confirmation (per-user) ----------------
    async def notify_payment_success(self, uid: str, plan_name: str, amount_inr: int, fcm_token: Optional[str] = None):
        title = "Payment successful"
        body = f"Your {plan_name} subscription is now active. Amount charged: ₹{amount_inr:,}."

        save_notification({
            "uid": uid,
            "type": "payment_success",
            "title": title,
            "body": body,
        })

        if fcm_token:
            self._send_push([fcm_token], title, body)

    # ---------------- Subscription/trial expiry reminder (per-user) ----------------
    async def notify_expiry_reminder(self, uid: str, days_left: int, is_trial: bool, fcm_token: Optional[str] = None):
        kind = "free trial" if is_trial else "subscription"
        title = f"Your {kind} ends in {days_left} day{'s' if days_left != 1 else ''}"
        body = "Renew now to keep full access to every market." if not is_trial else "Subscribe to keep full access after your trial ends."

        save_notification({
            "uid": uid,
            "type": "expiry_reminder",
            "title": title,
            "body": body,
        })

        if fcm_token:
            self._send_push([fcm_token], title, body)

    # ---------------- History retrieval ----------------
    def get_user_notifications(self, uid: str, limit: int = 50) -> list[dict]:
        return get_notifications(uid, limit)

    def mark_read(self, notification_id: str):
        mark_notification_read(notification_id)


notification_service = NotificationService()
