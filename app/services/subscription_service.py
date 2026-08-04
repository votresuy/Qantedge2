"""Subscription Service — plan catalog, free instruments, trial, and activation/expiry logic."""

from datetime import datetime, timedelta
from app.firebase.firestore_repo import update_subscription, get_user
from app.utils.logger import get_logger

logger = get_logger("subscription_service")

PLANS = {
    "monthly": {"plan_id": "monthly", "name": "Monthly Plan", "price_inr": 999, "duration_days": 30},
    "quarterly": {"plan_id": "quarterly", "name": "Quarterly Plan", "price_inr": 2499, "duration_days": 90},
    "yearly": {"plan_id": "yearly", "name": "Yearly Plan", "price_inr": 8999, "duration_days": 365},
}

# Always-free instruments — accessible to every user, subscribed or not, forever.
FREE_INSTRUMENTS = {"NIFTY50", "XAUUSD"}

# New users get full access (all instruments) free for this many days after signup.
NEW_USER_TRIAL_DAYS = 10


class SubscriptionService:
    FREE_INSTRUMENTS = FREE_INSTRUMENTS
    NEW_USER_TRIAL_DAYS = NEW_USER_TRIAL_DAYS

    async def activate_subscription(self, uid: str, plan_id: str):
        plan = PLANS.get(plan_id)
        if not plan:
            raise ValueError(f"Unknown plan_id: {plan_id}")

        expiry = datetime.utcnow() + timedelta(days=plan["duration_days"])
        update_subscription(uid, plan_id, expiry.isoformat())
        logger.info(f"Subscription activated for {uid}: {plan_id}, expires {expiry.isoformat()}")

    def start_trial(self, uid: str) -> str:
        """Called once at signup — grants NEW_USER_TRIAL_DAYS of full access."""
        trial_expiry = (datetime.utcnow() + timedelta(days=NEW_USER_TRIAL_DAYS)).isoformat()
        return trial_expiry

    async def is_paid_active(self, uid: str) -> bool:
        """True only if the user has an active PAID subscription."""
        user = get_user(uid)
        if not user or not user.get("is_subscribed"):
            return False
        expiry_str = user.get("subscription_expiry")
        if not expiry_str:
            return False
        return datetime.utcnow() < datetime.fromisoformat(expiry_str)

    async def is_trial_active(self, uid: str) -> bool:
        user = get_user(uid)
        if not user:
            return False
        trial_expiry_str = user.get("trial_expiry")
        if not trial_expiry_str:
            return False
        return datetime.utcnow() < datetime.fromisoformat(trial_expiry_str)

    async def is_active(self, uid: str) -> bool:
        """True if user has full access — either a paid subscription OR an active new-user trial."""
        if await self.is_paid_active(uid):
            return True
        return await self.is_trial_active(uid)

    def is_free_instrument(self, instrument: str) -> bool:
        return instrument.upper() in FREE_INSTRUMENTS

    async def can_access(self, uid: str, instrument: str) -> bool:
        """Access to a specific instrument: always-free instruments OR full active access."""
        if self.is_free_instrument(instrument):
            return True
        return await self.is_active(uid)

    def get_plans(self) -> list[dict]:
        return list(PLANS.values())


subscription_service = SubscriptionService()
