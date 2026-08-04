from fastapi import APIRouter, Depends
from app.services.notification_service import notification_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/notifications", tags=["Notifications"])


@router.get("")
async def get_notifications(user: dict = Depends(get_current_user)):
    """Returns per-user notifications (payments, expiry reminders) merged with
    broadcast notifications (new high-confidence signals), newest first."""
    return notification_service.get_user_notifications(user["uid"])


@router.post("/{notification_id}/read")
async def mark_read(notification_id: str, user: dict = Depends(get_current_user)):
    notification_service.mark_read(notification_id)
    return {"status": "ok"}
