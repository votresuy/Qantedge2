from fastapi import APIRouter, Depends, Body
from app.schemas.user import UserSignup, UserLogin, TokenResponse
from app.services.auth_service import auth_service, decode_token
from app.middleware.auth_middleware import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post("/signup", response_model=TokenResponse)
async def signup(payload: UserSignup):
    return await auth_service.signup(payload)


@router.post("/login", response_model=TokenResponse)
async def login(payload: UserLogin):
    return await auth_service.login(payload)


@router.post("/firebase-login", response_model=TokenResponse)
async def firebase_login(id_token: str = Body(..., embed=True)):
    """Preferred flow: Next.js client authenticates via Firebase client SDK,
    sends the Firebase ID token here, we verify and issue our own JWTs.
    On first login, creates the Firestore user record and grants the trial."""
    from datetime import datetime
    from app.services.auth_service import create_access_token, create_refresh_token
    from app.services.subscription_service import subscription_service
    from app.firebase.firestore_repo import get_user, save_user
    from app.firebase.firebase_init import get_auth

    uid = await auth_service.verify_firebase_id_token(id_token)

    existing = get_user(uid)
    if not existing:
        firebase_user = get_auth().get_user(uid)
        trial_expiry = subscription_service.start_trial(uid)
        save_user(uid, {
            "uid": uid,
            "email": firebase_user.email,
            "full_name": firebase_user.display_name or "",
            "is_subscribed": False,
            "trial_expiry": trial_expiry,
            "created_at": datetime.utcnow().isoformat(),
        })

    return TokenResponse(access_token=create_access_token(uid), refresh_token=create_refresh_token(uid))


@router.post("/refresh")
async def refresh(refresh_token: str = Body(..., embed=True)):
    new_access = auth_service.refresh_access_token(refresh_token)
    return {"access_token": new_access, "token_type": "bearer"}


@router.get("/me")
async def get_me(user: dict = Depends(get_current_user)):
    return user
