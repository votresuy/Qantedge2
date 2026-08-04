"""
Firebase Admin SDK initialization — used for Firestore (data) and
Firebase Authentication (optional, if not using pure JWT).

Place your service account JSON at the path in settings.FIREBASE_CREDENTIALS_PATH.
Never commit this file to version control.
"""

import firebase_admin
from firebase_admin import credentials, firestore, auth
from app.config import settings
from app.utils.logger import get_logger

logger = get_logger("firebase")

_app = None
_db = None


def init_firebase():
    global _app, _db
    if _app is not None:
        return _app

    try:
        cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
        _app = firebase_admin.initialize_app(cred, {"projectId": settings.FIREBASE_PROJECT_ID})
        _db = firestore.client()
        logger.info("Firebase initialized successfully")
    except Exception as e:
        logger.error(f"Firebase initialization failed: {e}")
        raise
    return _app


def get_firestore():
    global _db
    if _db is None:
        init_firebase()
    return _db


def get_auth():
    if _app is None:
        init_firebase()
    return auth
