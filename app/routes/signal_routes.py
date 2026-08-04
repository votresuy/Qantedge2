from fastapi import APIRouter, Depends, HTTPException
from app.services.signal_cache_service import signal_cache_service
from app.services.subscription_service import subscription_service
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/signals", tags=["Signals"])


@router.get("/live")
async def get_all_live_signals(user: dict = Depends(get_current_user)):
    """
    All current live signals across forex, crypto, stocks, and NIFTY50 trend.
    Served from an in-memory cache (max 24h old — see SIGNAL_CACHE_TTL_HOURS),
    not read from Firestore on every request.

    NIFTY50 and XAUUSD live signals are always included (free). Other
    instruments are only included if the user has an active paid subscription
    or is within their 10-day new-user trial.
    """
    all_signals = signal_cache_service.get_all()
    has_full_access = await subscription_service.is_active(user["uid"])

    if has_full_access:
        return all_signals

    return [
        s for s in all_signals
        if subscription_service.is_free_instrument(s.get("instrument", ""))
    ]


@router.get("/live/{instrument}")
async def get_live_signal(instrument: str, user: dict = Depends(get_current_user)):
    instrument = instrument.upper()

    allowed = await subscription_service.can_access(user["uid"], instrument)
    if not allowed:
        raise HTTPException(
            status_code=402,
            detail="This instrument requires an active subscription. NIFTY50 and XAUUSD live "
                   "signals are free; new users also get 10 days of full access.",
        )

    signal = signal_cache_service.get(instrument)
    if not signal:
        raise HTTPException(status_code=404, detail="No live signal found for this instrument")
    return signal
