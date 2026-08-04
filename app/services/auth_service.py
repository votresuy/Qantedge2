"""
Authentication Service.
Uses Firebase Authentication for user identity, and issues our own JWT
access/refresh tokens for API authorization (so the FastAPI backend doesn't
need to call Firebase on every request).
"""

from datetime import datetime, timedelta
from jose import jwt, JWTError
from passlib.context import CryptContext
from fastapi import HTTPException, status

from app.config import settings
from app.firebase.firebase_init import get_auth
from app.firebase.firestore_repo import save_user, get_user
from app.schemas.user import UserSignup, UserLogin, TokenResponse
from app.utils.logger import get_logger

logger = get_logger("auth_service")

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def _create_token(data: dict, expires_delta: timedelta) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + expires_delta
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(uid: str) -> str:
    return _create_token(
        {"sub": uid, "type": "access"},
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(uid: str) -> str:
    return _create_token(
        {"sub": uid, "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
        return payload
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")


class AuthService:
    async def signup(self, payload: UserSignup) -> TokenResponse:
        firebase_auth = get_auth()
        try:
            user_record = firebase_auth.create_user(
                email=payload.email,
                password=payload.password,
                display_name=payload.full_name,
            )
        except Exception as e:
            logger.error(f"Signup failed for {payload.email}: {e}")
            raise HTTPException(status_code=400, detail="Signup failed. Email may already be in use.")

        from app.services.subscription_service import subscription_service
        trial_expiry = subscription_service.start_trial(user_record.uid)

        save_user(user_record.uid, {
            "uid": user_record.uid,
            "email": payload.email,
            "full_name": payload.full_name,
            "is_subscribed": False,
            "trial_expiry": trial_expiry,
            "created_at": datetime.utcnow().isoformat(),
        })
        logger.info(f"New user {user_record.uid} granted trial until {trial_expiry}")

        access = create_access_token(user_record.uid)
        refresh = create_refresh_token(user_record.uid)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def login(self, payload: UserLogin) -> TokenResponse:
        """
        NOTE: Firebase Admin SDK cannot verify passwords directly (that's a
        client-side operation via Firebase Auth REST API / client SDK).
        In production, the Next.js client authenticates with Firebase client
        SDK and sends the resulting Firebase ID token here for verification
        instead of raw email/password. This method is kept for reference /
        server-side testing flows using the Firebase Auth REST API.
        """
        import httpx
        api_key = settings.FIREBASE_PROJECT_ID  # placeholder — use actual Web API key in env
        url = f"https://identitytoolkit.googleapis.com/v1/accounts:signInWithPassword?key={api_key}"
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(url, json={
                "email": payload.email,
                "password": payload.password,
                "returnSecureToken": True,
            })
        if resp.status_code != 200:
            raise HTTPException(status_code=401, detail="Invalid email or password")

        data = resp.json()
        uid = data["localId"]
        access = create_access_token(uid)
        refresh = create_refresh_token(uid)
        return TokenResponse(access_token=access, refresh_token=refresh)

    async def verify_firebase_id_token(self, id_token: str) -> str:
        """Preferred flow: client sends Firebase ID token, we verify and issue our own JWTs."""
        firebase_auth = get_auth()
        try:
            decoded = firebase_auth.verify_id_token(id_token)
            return decoded["uid"]
        except Exception as e:
            logger.error(f"Firebase ID token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid Firebase ID token")

    def refresh_access_token(self, refresh_token: str) -> str:
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        return create_access_token(payload["sub"])


auth_service = AuthService()
