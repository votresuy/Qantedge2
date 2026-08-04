"""Admin Service — admin-only operations: user management, manual signal overrides, stats."""

from app.firebase.firebase_init import get_firestore
from app.firebase.firestore_repo import USERS_COLLECTION, SIGNALS_COLLECTION, HISTORY_COLLECTION
from app.utils.logger import get_logger

logger = get_logger("admin_service")


class AdminService:
    def list_users(self, limit: int = 100) -> list[dict]:
        db = get_firestore()
        docs = db.collection(USERS_COLLECTION).limit(limit).stream()
        return [d.to_dict() for d in docs]

    def revoke_subscription(self, uid: str):
        db = get_firestore()
        db.collection(USERS_COLLECTION).document(uid).update({"is_subscribed": False})
        logger.info(f"Admin revoked subscription for user {uid}")

    def get_platform_stats(self) -> dict:
        db = get_firestore()
        users_count = len(list(db.collection(USERS_COLLECTION).stream()))
        active_signals = len(list(db.collection(SIGNALS_COLLECTION).stream()))
        history_count = len(list(db.collection(HISTORY_COLLECTION).limit(1000).stream()))
        return {
            "total_users": users_count,
            "active_signals": active_signals,
            "history_records_sampled": history_count,
        }

    def delete_signal(self, instrument: str):
        db = get_firestore()
        db.collection(SIGNALS_COLLECTION).document(instrument).delete()
        logger.info(f"Admin deleted live signal for {instrument}")


admin_service = AdminService()
