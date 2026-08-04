from fastapi import APIRouter, Depends, Query, HTTPException
from typing import Optional
from app.services.history_service import history_service
from app.services.subscription_service import subscription_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/history", tags=["History"])


@router.get("")
async def get_history(
    instrument: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    user: dict = Depends(get_current_user),
):
    """
    Signal history always requires an active paid subscription or an active
    10-day new-user trial — this applies to EVERY instrument, including
    NIFTY50 and XAUUSD. Only their live signal is free; past history is not.
    """
    has_full_access = await subscription_service.is_active(user["uid"])
    if not has_full_access:
        raise HTTPException(
            status_code=402,
            detail="Signal history requires an active subscription or trial. "
                   "NIFTY50 and XAUUSD live signals are free, but history is a paid feature.",
        )

    if instrument:
        instrument = instrument.upper()
    return history_service.get_signal_history(instrument=instrument, limit=limit)
