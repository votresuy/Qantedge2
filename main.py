"""
FastAPI application entry point.

Startup sequence:
  1. Initialize Firebase (Firestore + Auth)
  2. Register routes
  3. Start the background scheduler (market polling + engines)
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.config import settings
from app.firebase.firebase_init import init_firebase
from app.market.scheduler import start_scheduler, stop_scheduler
from app.utils.logger import get_logger

from app.routes import auth_routes, signal_routes, history_routes, subscription_routes, admin_routes, notification_routes

logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up backend...")
    try:
        init_firebase()
    except Exception as e:
        logger.error(f"Firebase init failed on startup: {e}")

    start_scheduler()
    yield

    logger.info("Shutting down backend...")
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(signal_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(history_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(subscription_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(admin_routes.router, prefix=settings.API_V1_PREFIX)
app.include_router(notification_routes.router, prefix=settings.API_V1_PREFIX)


@app.get("/")
async def root():
    return {"status": "ok", "service": settings.APP_NAME}


@app.get("/health")
async def health():
    return {"status": "healthy"}
