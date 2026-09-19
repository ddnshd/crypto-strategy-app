"""Runtime-configurable LLM settings.

Values are initialised from environment (via app.config.settings) and can be
updated at runtime through the settings API. Updates are kept in memory and
optionally persisted back to the backend .env file so they survive restarts.
"""
import os
from pathlib import Path
from typing import Any, Dict, Optional

from app.config import settings


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


_runtime: Dict[str, Any] = {
    "base_url": settings.LLM_BASE_URL.rstrip("/"),
    "api_key": settings.LLM_API_KEY,
    "model": settings.LLM_MODEL,
    "max_tokens": settings.LLM_MAX_TOKENS,
    "temperature_generate": _env_float("LLM_TEMPERATURE_GENERATE", 0.3),
    "temperature_explain": _env_float("LLM_TEMPERATURE_EXPLAIN", 0.5),
    "temperature_chat": _env_float("LLM_TEMPERATURE_CHAT", 0.7),
}


def mask_key(key: str) -> str:
    if not key or key == "dummy":
        return "belum diisi"
    if len(key) <= 8:
        return "••••••••"
    return "••••" + key[-4:]


def get_llm_config(include_secret: bool = False) -> Dict[str, Any]:
    cfg = dict(_runtime)
    if not include_secret:
        cfg["api_key"] = mask_key(cfg.get("api_key", ""))
    return cfg


def backend_env_path() -> Path:
    # app/services/llm_config.py -> parents[2] == apps/backend
    return Path(__file__).resolve().parents[2] / ".env"


def _persist_to_env(updates: Dict[str, str]) -> None:
    """Update (or append) KEY=VALUE lines in the backend .env file."""
    path = backend_env_path()
    lines: list[str] = []
    if path.exists():
        lines = path.read_text().splitlines()
    remaining = dict(updates)
    out: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in line:
            out.append(line)
            continue
        key = line.split("=", 1)[0].strip()
        if key in remaining:
            out.append(f"{key}={remaining.pop(key)}")
        else:
            out.append(line)
    for key, value in remaining.items():
        out.append(f"{key}={value}")
    path.write_text("\n".join(out) + "\n")


def update_llm_config(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    model: Optional[str] = None,
    max_tokens: Optional[int] = None,
    temperature_generate: Optional[float] = None,
    temperature_explain: Optional[float] = None,
    temperature_chat: Optional[float] = None,
    persist: bool = True,
) -> Dict[str, Any]:
    """Validate and apply new LLM settings. Returns masked config."""
    updates_env: Dict[str, str] = {}

    if base_url is not None:
        base_url = base_url.strip().rstrip("/")
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise ValueError("base_url harus diawali http:// atau https://")
        _runtime["base_url"] = base_url
        updates_env["LLM_BASE_URL"] = base_url

    if api_key is not None and api_key != "":
        if len(api_key.strip()) < 4:
            raise ValueError("api_key terlalu pendek")
        _runtime["api_key"] = api_key.strip()
        updates_env["LLM_API_KEY"] = api_key.strip()

    if model is not None:
        model = model.strip()
        if not model or len(model) > 128:
            raise ValueError("model tidak valid")
        _runtime["model"] = model
        updates_env["LLM_MODEL"] = model

    if max_tokens is not None:
        max_tokens = int(max_tokens)
        if max_tokens < 100 or max_tokens > 32000:
            raise ValueError("max_tokens harus 100–32000")
        _runtime["max_tokens"] = max_tokens
        updates_env["LLM_MAX_TOKENS"] = str(max_tokens)

    for field, env_key in (
        ("temperature_generate", "LLM_TEMPERATURE_GENERATE"),
        ("temperature_explain", "LLM_TEMPERATURE_EXPLAIN"),
        ("temperature_chat", "LLM_TEMPERATURE_CHAT"),
    ):
        value = locals()[field]
        if value is not None:
            value = float(value)
            if value < 0 or value > 2:
                raise ValueError(f"{field} harus 0–2")
            _runtime[field] = value
            updates_env[env_key] = str(value)

    if persist and updates_env:
        _persist_to_env(updates_env)

    return get_llm_config()
