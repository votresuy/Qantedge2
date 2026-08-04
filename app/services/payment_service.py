"""
Payment Service — Razorpay integration.

Flow:
  User -> Choose Plan -> Razorpay Order -> Client pays -> Webhook Verify ->
  Subscription Active -> Payment record saved -> Notification -> Dashboard Unlock
"""

from datetime import datetime
from fastapi import HTTPException
from app.razorpay.client import create_order, verify_payment_signature, verify_webhook_signature
from app.schemas.user import CreateOrderRequest, CreateOrderResponse, VerifyPaymentRequest
from app.services.subscription_service import PLANS, subscription_service
from app.firebase.firestore_repo import save_payment, get_payments
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("payment_service")


class PaymentService:
    async def create_order(self, uid: str, payload: CreateOrderRequest) -> CreateOrderResponse:
        plan = PLANS.get(payload.plan_id)
        if not plan:
            raise HTTPException(status_code=400, detail="Invalid plan_id")

        order = create_order(
            amount_inr=plan["price_inr"],
            receipt=f"{uid}_{payload.plan_id}_{datetime.utcnow().timestamp()}",
            notes={"uid": uid, "plan_id": payload.plan_id},
        )
        logger.info(f"Created Razorpay order {order['id']} for user {uid}, plan {payload.plan_id}")

        return CreateOrderResponse(
            order_id=order["id"],
            amount=order["amount"],
            razorpay_key_id=settings.RAZORPAY_KEY_ID,
        )

    async def _record_payment_and_notify(self, uid: str, plan_id: str, order_id: str, payment_id: str, status: str):
        plan = PLANS.get(plan_id, {})
        save_payment(uid, {
            "plan_id": plan_id,
            "plan_name": plan.get("name", plan_id),
            "amount_inr": plan.get("price_inr"),
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "status": status,
        })

        if status == "success":
            from app.services.notification_service import notification_service
            await notification_service.notify_payment_success(
                uid, plan.get("name", plan_id), plan.get("price_inr", 0)
            )

    async def verify_and_activate(self, uid: str, payload: VerifyPaymentRequest, plan_id: str):
        """Direct client-side verification path (in addition to webhook, for instant UX)."""
        valid = verify_payment_signature(
            payload.razorpay_order_id, payload.razorpay_payment_id, payload.razorpay_signature
        )
        if not valid:
            await self._record_payment_and_notify(
                uid, plan_id, payload.razorpay_order_id, payload.razorpay_payment_id, "failed"
            )
            raise HTTPException(status_code=400, detail="Payment signature verification failed")

        await subscription_service.activate_subscription(uid, plan_id)
        await self._record_payment_and_notify(
            uid, plan_id, payload.razorpay_order_id, payload.razorpay_payment_id, "success"
        )
        logger.info(f"Payment verified and subscription activated for user {uid}")
        return {"status": "success", "message": "Subscription activated"}

    async def handle_webhook(self, payload_body: bytes, signature: str, event_data: dict):
        """Source of truth — webhook confirms payment server-to-server regardless of client state."""
        if not verify_webhook_signature(payload_body, signature):
            raise HTTPException(status_code=400, detail="Invalid webhook signature")

        event = event_data.get("event")
        if event == "payment.captured":
            payment_entity = event_data["payload"]["payment"]["entity"]
            notes = payment_entity.get("notes", {})
            uid = notes.get("uid")
            plan_id = notes.get("plan_id")
            if uid and plan_id:
                await subscription_service.activate_subscription(uid, plan_id)
                await self._record_payment_and_notify(
                    uid, plan_id, payment_entity.get("order_id", ""), payment_entity.get("id", ""), "success"
                )
                logger.info(f"Webhook activated subscription for user {uid}, plan {plan_id}")
            else:
                logger.warning("Webhook payment.captured missing uid/plan_id in notes")

        return {"status": "ok"}

    def get_payment_history(self, uid: str, limit: int = 50) -> list[dict]:
        return get_payments(uid, limit)


payment_service = PaymentService()
