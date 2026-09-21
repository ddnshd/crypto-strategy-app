import os
from pathlib import Path
from dotenv import load_dotenv
from typing import Optional, List

BACKEND_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BACKEND_DIR / ".env")


class Settings:
    # App
    APP_NAME: str = os.getenv("APP_NAME", "Crypto Strategy API")
    APP_VERSION: str = os.getenv("APP_VERSION", "1.0.0")
    DEBUG: bool = os.getenv("DEBUG", "false").lower() == "true"

    # Database — always absolute to backend directory
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL",
        f"sqlite+aiosqlite:///{BACKEND_DIR.as_posix()}/cryptostrategy.db"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")

    # AI / LLM
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://9route.sdn188bandungbaru.com/v1")
    LLM_API_KEY: str = os.getenv("LLM_API_KEY", "dummy")
    LLM_MODEL: str = os.getenv("LLM_MODEL", "gpt-4o")
    LLM_MAX_TOKENS: int = int(os.getenv("LLM_MAX_TOKENS", "2000"))

    # Crypto Exchange
    DEFAULT_EXCHANGE: str = os.getenv("DEFAULT_EXCHANGE", "binance")

    # Firebase FCM
    FIREBASE_CREDENTIALS_PATH: Optional[str] = os.getenv("FIREBASE_CREDENTIALS_PATH")

    # Signal Scanner
    SCANNER_INTERVAL_SECONDS: int = int(os.getenv("SCANNER_INTERVAL_SECONDS", "60"))

    # CORS
    ALLOWED_ORIGINS: List[str] = ["*"]


settings = Settings()
