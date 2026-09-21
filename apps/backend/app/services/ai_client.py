import json
import logging
import httpx
from app.services.llm_config import get_llm_config

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
    """Thin client for an OpenAI-compatible chat API.

    Connection settings are read dynamically from the runtime LLM config
    (see app.services.llm_config) so changes via the settings API apply
    immediately without restarting the backend.
    """

    async def _chat_completion(self, messages: list, temperature: float = None) -> str:
        """Call OpenAI-compatible chat completions endpoint."""
        cfg = get_llm_config(include_secret=True)
        if temperature is None:
            temperature = cfg["temperature_chat"]
        payload = {
            "model": cfg["model"],
            "messages": messages,
            "max_tokens": cfg["max_tokens"],
            "temperature": temperature,
            "stream": False,
        }
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json",
        }
        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(
                f"{cfg['base_url']}/chat/completions",
                json=payload,
                headers=headers,
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
            cfg = get_llm_config(include_secret=True)
            content = await self._chat_completion(messages, temperature=cfg["temperature_generate"])

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
            cfg = get_llm_config(include_secret=True)
            content = await self._chat_completion([
                {
                    "role": "system",
                    "content": "Kamu adalah expert trading crypto. Jelaskan strategi trading berikut dengan bahasa yang mudah dipahami dalam Bahasa Indonesia."
                },
                {
                    "role": "user",
                    "content": f"Jelaskan strategi ini:\n{json.dumps(strategy_def, indent=2, ensure_ascii=False)}"
                }
            ], temperature=cfg["temperature_explain"])
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
            cfg = get_llm_config(include_secret=True)
            return await self._chat_completion([system_msg] + messages, temperature=cfg["temperature_chat"])
        except Exception as e:
            logger.error(f"Chat error: {e}")
            return "Maaf, terjadi gangguan saat menghubungi AI."

    async def analyze_and_optimize_backtest(
        self,
        strategy_name: str,
        strategy_def: dict,
        backtest_summary: dict,
        user_goal: str = None,
    ) -> dict:
        """Analyze backtest performance metrics and generate an optimized strategy definition."""
        system_prompt = """Kamu adalah Senior Quantitative Trader & AI Strategy Optimization Specialist.
Tugasmu adalah menganalisis hasil backtest strategi trading crypto secara analitis, mendiagnosa titik kegagalan (drawdown, overtrading, false signals, rasio R:R tidak seimbang, dll.), dan menyusun VERSI BARU STRATEGI YANG LEBIH OPTIMAL.

Format output WAJIB JSON murni tanpa markdown pembungkus di luar JSON, dengan struktur persis seperti ini:
{
  "diagnosis": "Penjelasan mendalam mengapa performa backtest menghasilkan metrik tersebut (Bahasa Indonesia)...",
  "weaknesses": [
    "Poin kelemahan 1 (misal: Stop Loss terlalu sempit kena noise)",
    "Poin kelemahan 2 (misal: Kurang filter konfirmasi tren utama)"
  ],
  "improvements": [
    "Perbaikan konkret 1 (misal: Tambah filter harga di atas EMA 200)",
    "Perbaikan konkret 2 (misal: Naikkan Take Profit dari 2% menjadi 3.5%)"
  ],
  "optimized_strategy": {
    "name": "Nama strategi (Versi Optimasi AI)",
    "style": "scalp|intraday|swing|position",
    "pair": "BTC/USDT",
    "timeframe": "1h",
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
      "take_profit_pct": 3.0,
      "stop_loss_pct": 1.5,
      "trailing_stop_pct": 1.0,
      "max_bars_held": 48,
      "exit_conditions": []
    },
    "filters": [],
    "position_size_pct": 100,
    "notes": "Penjelasan ringkas logika versi optimasi"
  },
  "explanation": "Penjelasan menyeluruh mengapa versi baru ini diproyeksikan lebih konsisten dan profitable..."
}

Aturan Penting:
1. Hanya gunakan indikator valid: RSI, EMA, SMA, EMA_CROSS, SMA_CROSS, MACD, BBANDS, ATR, STOCH, VOLUME, VOLUME_SMA, PRICE.
2. Operator valid: <, >, <=, >=, ==, cross_above, cross_below.
3. filters harus berupa list dict kondisi indikator valid (jangan string teks deskripsi murni).
4. Pertahankan pair & timeframe yang sama agar relevan dengan instrumen yang diuji.
5. Berikan parameter angka yang rasional dan terbukti secara teknikal.
"""

        user_content = f"""Berikut adalah data strategi dan hasil backtestnya:

NAMA STRATEGI: {strategy_name}
DEFINISI STRATEGI LAMA:
{json.dumps(strategy_def, indent=2, ensure_ascii=False)}

HASIL METRIK BACKTEST:
- Pasangan Aset & TF: {backtest_summary.get('pair')} ({backtest_summary.get('timeframe')})
- Periode Pengujian: {backtest_summary.get('start_date')} s/d {backtest_summary.get('end_date')}
- Total Transaksi: {backtest_summary.get('total_trades')} trade ({backtest_summary.get('winning_trades')} menang / {backtest_summary.get('losing_trades')} kalah)
- Win Rate: {backtest_summary.get('win_rate_pct')}%
- Profit Factor: {backtest_summary.get('profit_factor')}
- Total Return: {backtest_summary.get('total_return_pct')}%
- Maximum Drawdown: {backtest_summary.get('max_drawdown_pct')}%
- Sharpe Ratio: {backtest_summary.get('sharpe_ratio')}
- Average Risk:Reward: {backtest_summary.get('avg_rr')}
- Total Komisi & Slippage: ${backtest_summary.get('total_commission')}
- Skor Algoritma: {backtest_summary.get('score')}/100
- Alasan Exit Breakdown: {json.dumps(backtest_summary.get('exit_reasons', {}))}
- Walk-Forward Degradasi: {backtest_summary.get('wf_degradation')}% ({backtest_summary.get('wf_consistency')})
{f"- Fokus Permintaan User: {user_goal}" if user_goal else ""}

Silakan diagnosa dan hasilkan versi strategi yang telah disempurnakan (JSON)."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_content},
        ]

        try:
            cfg = get_llm_config(include_secret=True)
            content = await self._chat_completion(messages, temperature=cfg["temperature_generate"])
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            result = json.loads(content)
            return result
        except json.JSONDecodeError as e:
            logger.error(f"AI returned invalid JSON in backtest optimize: {e}")
            raise ValueError(f"AI gagal menghasilkan format JSON yang valid: {e}")
        except Exception as e:
            logger.error(f"AI backtest optimize error: {e}")
            raise
            raise
