"""
Schemas for authentication, user profile, and subscription flows.
"""

from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime


class UserSignup(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class UserProfile(BaseModel):
    uid: str
    email: EmailStr
    full_name: str
    photo_url: Optional[str] = None
    is_subscribed: bool = False
    subscription_plan: Optional[str] = None
    subscription_expiry: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class PlanType(BaseModel):
    plan_id: str
    name: str
    price_inr: int
    duration_days: int
    features: list[str] = []


class CreateOrderRequest(BaseModel):
    plan_id: str


class CreateOrderResponse(BaseModel):
    order_id: str
    amount: int
    currency: str = "INR"
    razorpay_key_id: str


class VerifyPaymentRequest(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class WebhookEvent(BaseModel):
    event: str
    payload: dict
