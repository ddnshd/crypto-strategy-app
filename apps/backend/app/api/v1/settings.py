import logging
from typing import Optional
import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.services.llm_config import get_llm_config, update_llm_config
from app.services.ai_client import AIClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/settings", tags=["settings"])


class AISettingsUpdate(BaseModel):
    base_url: Optional[str] = Field(None, description="OpenAI-compatible base URL, cth. https://.../v1")
    api_key: Optional[str] = Field(None, description="API key baru; kosongkan jika tidak diubah")
    model: Optional[str] = Field(None, description="Nama model, cth. ag/claude-sonnet-4-6")
    max_tokens: Optional[int] = Field(None, description="100–32000")
    temperature_generate: Optional[float] = Field(None, description="0–2, untuk generate strategi")
    temperature_explain: Optional[float] = Field(None, description="0–2, untuk penjelasan")
    temperature_chat: Optional[float] = Field(None, description="0–2, untuk chat")


@router.get("/ai")
async def get_ai_settings():
    """Lihat konfigurasi AI saat ini (API key disensor)."""
    return get_llm_config()


@router.put("/ai")
async def put_ai_settings(data: AISettingsUpdate):
    """Ubah konfigurasi AI saat runtime + simpan ke .env agar permanen."""
    try:
        return update_llm_config(
            base_url=data.base_url,
            api_key=data.api_key,
            model=data.model,
            max_tokens=data.max_tokens,
            temperature_generate=data.temperature_generate,
            temperature_explain=data.temperature_explain,
            temperature_chat=data.temperature_chat,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except OSError as e:
        logger.error(f"Gagal menyimpan .env: {e}")
        raise HTTPException(status_code=500, detail="Gagal menyimpan pengaturan ke .env")


@router.post("/ai/test")
async def test_ai_settings():
    """Tes koneksi ke endpoint AI dengan pesan singkat."""
    try:
        reply = await AIClient().chat([{"role": "user", "content": "Balas hanya dengan kata: ok"}])
        return {"ok": True, "reply": reply[:300]}
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=503, detail=f"AI API error: {e.response.status_code}")
    except Exception as e:
        logger.error(f"AI test failed: {e}")
        raise HTTPException(status_code=503, detail="AI tidak dapat dihubungi. Periksa base URL / API key / model.")
