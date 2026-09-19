import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import settings
from app.core.database import init_db
from app.core.redis import close_redis
from app.api.v1 import api_router
from app.services.scanner import get_scanner

logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

_scanner_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown lifecycle."""
    global _scanner_task

    # Initialize database tables
    logger.info("Initializing database...")
    await init_db()

    # Start signal scanner background task
    logger.info("Starting signal scanner...")
    scanner = get_scanner()
    _scanner_task = asyncio.create_task(scanner.start(), name="signal_scanner")

    logger.info(f"API ready — {settings.APP_NAME} v{settings.APP_VERSION}")
    yield

    # Shutdown
    logger.info("Shutting down...")
    scanner = get_scanner()
    await scanner.stop()
    if _scanner_task and not _scanner_task.done():
        _scanner_task.cancel()
        try:
            await _scanner_task
        except asyncio.CancelledError:
            pass

    await close_redis()
    logger.info("Shutdown complete")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="AI Crypto Strategy Builder & Signal Scanner API",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
app.include_router(api_router)


@app.get("/health")
async def health_check():
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/")
async def root():
    return {
        "message": "AI Crypto Strategy Builder API",
        "docs": "/docs",
        "version": settings.APP_VERSION,
    }
