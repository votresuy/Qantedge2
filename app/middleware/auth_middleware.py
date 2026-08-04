"""FastAPI dependencies for authenticating requests via our JWT and checking subscription status."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.services.auth_service import decode_token
from app.services.subscription_service import subscription_service
from app.firebase.firestore_repo import get_user

security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise HTTPException(status_code=401, detail="Invalid token type")

    uid = payload["sub"]
    user = get_user(uid)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return user


async def require_active_subscription(user: dict = Depends(get_current_user)) -> dict:
    active = await subscription_service.is_active(user["uid"])
    if not active:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Active subscription required to access this resource",
        )
    return user


async def require_admin(user: dict = Depends(get_current_user)) -> dict:
    if not user.get("is_admin", False):
        raise HTTPException(status_code=403, detail="Admin access required")
    return user
