from fastapi import APIRouter, Depends
from app.services.admin_service import admin_service
from app.middleware.auth_middleware import require_admin

router = APIRouter(prefix="/admin", tags=["Admin"])


@router.get("/users")
async def list_users(admin: dict = Depends(require_admin)):
    return admin_service.list_users()


@router.post("/users/{uid}/revoke")
async def revoke_subscription(uid: str, admin: dict = Depends(require_admin)):
    admin_service.revoke_subscription(uid)
    return {"status": "revoked"}


@router.get("/stats")
async def platform_stats(admin: dict = Depends(require_admin)):
    return admin_service.get_platform_stats()


@router.delete("/signals/{instrument}")
async def delete_signal(instrument: str, admin: dict = Depends(require_admin)):
    admin_service.delete_signal(instrument.upper())
    return {"status": "deleted"}
