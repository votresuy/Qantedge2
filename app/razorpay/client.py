"""Razorpay client wrapper — order creation and signature verification."""

import razorpay
import hmac
import hashlib
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("razorpay_client")

client = razorpay.Client(auth=(settings.RAZORPAY_KEY_ID, settings.RAZORPAY_KEY_SECRET))


def create_order(amount_inr: int, receipt: str, notes: dict | None = None) -> dict:
    """amount_inr is in rupees; Razorpay expects paise."""
    order = client.order.create({
        "amount": amount_inr * 100,
        "currency": "INR",
        "receipt": receipt,
        "payment_capture": 1,
        "notes": notes or {},
    })
    return order


def verify_payment_signature(order_id: str, payment_id: str, signature: str) -> bool:
    try:
        client.utility.verify_payment_signature({
            "razorpay_order_id": order_id,
            "razorpay_payment_id": payment_id,
            "razorpay_signature": signature,
        })
        return True
    except razorpay.errors.SignatureVerificationError:
        logger.error("Razorpay payment signature verification failed")
        return False


def verify_webhook_signature(payload_body: bytes, received_signature: str) -> bool:
    expected_signature = hmac.new(
        settings.RAZORPAY_WEBHOOK_SECRET.encode(),
        payload_body,
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(expected_signature, received_signature)
