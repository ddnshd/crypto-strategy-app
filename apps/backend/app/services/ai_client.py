import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

STRATEGY_SYSTEM_PROMPT = """Kamu adalah AI assistant ahli trading crypto. Tugasmu adalah membantu trader mengkonversi ide strategi trading dalam bahasa natural menjadi definisi strategi yang terstruktur dalam format JSON.

Kamu HARUS mengembalikan respons dalam format JSON yang valid dengan struktur berikut:
{
  "strategy": {
    "name": "Nama strategi yang deskriptif",
    "style": "scalp|intraday|swing|position",
    "pair": "BTC/USDT",
    "timeframe": "1m|3m|5m|15m|30m|1h|2h|4h|6h|8h|12h|1d",
    "entry_conditions": [
      {
        "indicator": "RSI|EMA|SMA|EMA_CROSS|SMA_CROSS|MACD|BBANDS|ATR|STOCH|VOLUME|VOLUME_SMA|PRICE",
        "params": {"period": 14},
        "operator": "<|>|<=|>=|==|cross_above|cross_below",
        "value": 30,
        "compare_to": null
      }
    ],
    "exit_conditions": {
      "take_profit_pct": 2.0,
      "stop_loss_pct": 1.0,
      "trailing_stop_pct": null,
      "max_bars_held": null,
      "exit_conditions": []
    },
    "filters": [],
    "position_size_pct": 1.0,
    "notes": "Penjelasan singkat strategi"
  },
  "explanation": "Penjelasan lengkap strategi dalam bahasa Indonesia",
  "suggestions": ["Saran 1", "Saran 2"],
  "warnings": ["Peringatan 1", "Peringatan 2"]
}

Aturan penting:
1. entry_conditions: array kondisi yang SEMUA harus terpenuhi (AND logic)
2. operator cross_above/cross_below: untuk persilangan, tidak perlu "value"
3. operator <, >, <=, >=, ==: butuh "value" (angka)
4. compare_to: nama indikator lain untuk dibandingkan (opsional)
5. Selalu sertakan SL dan TP dalam persen
6. Style: scalp (<1h TF), intraday (1h-4h), swing (4h-1d), position (>1d)
7. Berikan peringatan jika strategi berisiko overfitting atau terlalu kompleks
8. Berikan saran penyempurnaan yang konkret

Indikator yang tersedia:
- RSI: params {period: int} — nilai 0-100
- EMA: params {period: int} — exponential moving average
- SMA: params {period: int} — simple moving average
- EMA_CROSS: params {fast: int, slow: int} — persilangan EMA, gunakan cross_above/cross_below
- SMA_CROSS: params {fast: int, slow: int} — persilangan SMA
- MACD: params {fast:12, slow:26, signal:9} — gunakan operator dengan value 0
- BBANDS: params {period:20, std:2} — Bollinger Bands
- STOCH: params {k:14, d:3} — Stochastic, nilai 0-100
- ATR: params {period:14} — Average True Range (volatility)
- VOLUME_SMA: params {period:20} — volume moving average
- VOLUME: tanpa params — volume bar saat ini
- PRICE/CLOSE: harga penutupan

PASTIKAN output adalah JSON yang valid. Jangan tambahkan teks di luar JSON."""


class AIClient:
    def __init__(self):
        self.base_url = settings.LLM_BASE_URL.rstrip("/")
        self.api_key = settings.LLM_API_KEY
        self.model = settings.LLM_MODEL
        self.max_tokens = settings.LLM_MAX_TOKENS
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

    async def _chat_completion(self, messages: list, temperature: float = 0.3) -> str:
        """Call OpenAI-compatible chat completions endpoint."""
        payload = {
            "model": self.model,
            "messages": messages,
            "max_tokens": self.max_tokens,
            "temperature": temperature,
            "stream": False,
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
            )
            resp.raise_for_status()
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_strategy(self, user_input: str, existing_strategy: dict = None) -> dict:
        """Generate or refine a strategy from natural language input."""
        if existing_strategy:
            user_message = f"""Tolong sempurnakan strategi berikut berdasarkan masukan user.

Strategi yang ada:
{json.dumps(existing_strategy, indent=2, ensure_ascii=False)}

Masukan user untuk penyempurnaan:
{user_input}

Kembalikan strategi yang sudah disempurnakan dalam format JSON yang sama."""
        else:
            user_message = f"""User ingin membuat strategi trading dengan deskripsi berikut:

"{user_input}"

Konversikan ke format strategi JSON yang terstruktur."""

        messages = [
            {"role": "system", "content": STRATEGY_SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ]

        try:
            content = await self._chat_completion(messages, temperature=0.3)

            # Extract JSON from markdown code blocks if present
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()

            result = json.loads(content)
            return result

        except json.JSONDecodeError as e:
            logger.error(f"AI returned invalid JSON: {e}")
            raise ValueError(f"AI gagal menghasilkan JSON yang valid: {e}")
        except httpx.HTTPStatusError as e:
            logger.error(f"AI API HTTP error: {e.response.status_code} {e.response.text[:200]}")
            raise RuntimeError(f"AI API error: {e.response.status_code}")
        except Exception as e:
            logger.error(f"AI client error: {e}")
            raise

    async def explain_strategy(self, strategy_def: dict) -> str:
        """Generate human-readable explanation of a strategy."""
        try:
            content = await self._chat_completion([
                {
                    "role": "system",
                    "content": "Kamu adalah expert trading crypto. Jelaskan strategi trading berikut dengan bahasa yang mudah dipahami dalam Bahasa Indonesia."
                },
                {
                    "role": "user",
                    "content": f"Jelaskan strategi ini:\n{json.dumps(strategy_def, indent=2, ensure_ascii=False)}"
                }
            ], temperature=0.5)
            return content
        except Exception as e:
            logger.error(f"Explain strategy error: {e}")
            return "Gagal mengambil penjelasan dari AI."

    async def chat(self, messages: list) -> str:
        """General chat for strategy discussion."""
        system_msg = {
            "role": "system",
            "content": "Kamu adalah AI assistant ahli trading crypto dan analisis teknikal. Bantu user dalam bahasa Indonesia untuk memahami, membuat, dan mengoptimalkan strategi trading mereka."
        }
        try:
            return await self._chat_completion([system_msg] + messages, temperature=0.7)
        except Exception as e:
            logger.error(f"Chat error: {e}")
            raise
