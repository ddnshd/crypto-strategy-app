import ccxt.async_support as ccxt
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional
from app.config import settings
import logging

logger = logging.getLogger(__name__)

TIMEFRAME_MAP = {
    "1m": 1,
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "2h": 120,
    "4h": 240,
    "6h": 360,
    "8h": 480,
    "12h": 720,
    "1d": 1440,
    "3d": 4320,
    "1w": 10080,
}


FALLBACK_EXCHANGES = ["binance", "binanceus", "okx", "gate", "kraken"]


class DataFetcher:
    _active_exchange_id: Optional[str] = None

    def __init__(self, exchange_id: str = None):
        self.exchange_id = exchange_id or DataFetcher._active_exchange_id or settings.DEFAULT_EXCHANGE
        self._exchange = None

    async def _get_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            exchange_class = getattr(ccxt, self.exchange_id)
            self._exchange = exchange_class({
                "enableRateLimit": True,
                "timeout": 30000,
            })
        return self._exchange

    async def _switch_exchange(self, failed_id: str):
        """Switch to next working exchange if current one is geographically restricted."""
        await self.close()
        candidates = [e for e in FALLBACK_EXCHANGES if e != failed_id]
        if candidates:
            next_ex = candidates[0]
            logger.warning(f"Exchange '{failed_id}' restricted/unavailable. Auto-switching to '{next_ex}'...")
            self.exchange_id = next_ex
            DataFetcher._active_exchange_id = next_ex
            return await self._get_exchange()
        raise RuntimeError(f"All fallback exchanges exhausted after {failed_id} failure")

    async def close(self):
        if self._exchange:
            try:
                await self._exchange.close()
            except Exception:
                pass
            self._exchange = None

    async def fetch_ohlcv(
        self,
        pair: str,
        timeframe: str = "1h",
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        limit: int = 500,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV data and return as DataFrame.
        Columns: timestamp, open, high, low, close, volume
        """
        candidates = [self.exchange_id] + [e for e in FALLBACK_EXCHANGES if e != self.exchange_id]

        for current_candidate in candidates:
            try:
                self.exchange_id = current_candidate
                exchange = await self._get_exchange()

                since = None
                if start_date:
                    dt = datetime.strptime(start_date, "%Y-%m-%d")
                    since = int(dt.timestamp() * 1000)
                elif not since:
                    tf_minutes = TIMEFRAME_MAP.get(timeframe, 60)
                    days_back = max(30, (limit * tf_minutes) // 1440 + 1)
                    since = int((datetime.utcnow() - timedelta(days=days_back)).timestamp() * 1000)

                all_ohlcv = []
                current_since = since

                while True:
                    ohlcv = await exchange.fetch_ohlcv(
                        pair, timeframe, since=current_since, limit=1000
                    )
                    if not ohlcv:
                        break

                    all_ohlcv.extend(ohlcv)

                    if end_date:
                        end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                        last_ts = ohlcv[-1][0] / 1000
                        if datetime.utcfromtimestamp(last_ts) >= end_dt:
                            break

                    if len(ohlcv) < 1000:
                        break

                    current_since = ohlcv[-1][0] + 1

                if all_ohlcv:
                    DataFetcher._active_exchange_id = current_candidate
                    df = pd.DataFrame(
                        all_ohlcv,
                        columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    df = df.set_index("timestamp")
                    df = df.sort_index()
                    df = df[~df.index.duplicated(keep="first")]

                    if end_date:
                        end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
                        df = df[df.index <= end_dt]

                    return df

            except (ccxt.ExchangeNotAvailable, ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                err_str = str(e).lower()
                if "451" in err_str or "restricted location" in err_str or "unavailable" in err_str:
                    logger.warning(f"Exchange '{current_candidate}' restricted: {e}. Trying fallback...")
                    await self.close()
                    continue
                logger.error(f"Exchange error fetching {pair} on {current_candidate}: {e}")
                raise
            except Exception as e:
                logger.error(f"Error fetching {pair} on {current_candidate}: {e}")
                raise

        raise ValueError(f"No OHLCV data returned for {pair} {timeframe} across all available exchanges")

    async def get_current_price(self, pair: str) -> float:
        """Get the latest ticker price with automatic fallback."""
        candidates = [self.exchange_id] + [e for e in FALLBACK_EXCHANGES if e != self.exchange_id]
        for current_candidate in candidates:
            try:
                self.exchange_id = current_candidate
                exchange = await self._get_exchange()
                ticker = await exchange.fetch_ticker(pair)
                DataFetcher._active_exchange_id = current_candidate
                return float(ticker["last"])
            except (ccxt.ExchangeNotAvailable, ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                err_str = str(e).lower()
                if "451" in err_str or "restricted location" in err_str or "unavailable" in err_str:
                    await self.close()
                    continue
                raise
        raise RuntimeError(f"Could not fetch price for {pair} on any exchange")

    async def get_latest_ohlcv(self, pair: str, timeframe: str, bars: int = 200) -> pd.DataFrame:
        """Get the latest N bars of OHLCV data with automatic fallback."""
        candidates = [self.exchange_id] + [e for e in FALLBACK_EXCHANGES if e != self.exchange_id]
        for current_candidate in candidates:
            try:
                self.exchange_id = current_candidate
                exchange = await self._get_exchange()
                ohlcv = await exchange.fetch_ohlcv(pair, timeframe, limit=bars)
                if ohlcv:
                    DataFetcher._active_exchange_id = current_candidate
                    df = pd.DataFrame(
                        ohlcv,
                        columns=["timestamp", "open", "high", "low", "close", "volume"]
                    )
                    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
                    df = df.set_index("timestamp")
                    return df
            except (ccxt.ExchangeNotAvailable, ccxt.AuthenticationError, ccxt.ExchangeError) as e:
                err_str = str(e).lower()
                if "451" in err_str or "restricted location" in err_str or "unavailable" in err_str:
                    await self.close()
                    continue
                raise
        raise ValueError(f"No data for {pair} {timeframe} across all available exchanges")

    async def list_pairs(self, quote_currency: str = "USDT") -> list[str]:
        """List available trading pairs."""
        candidates = [self.exchange_id] + [e for e in FALLBACK_EXCHANGES if e != self.exchange_id]
        for current_candidate in candidates:
            try:
                self.exchange_id = current_candidate
                exchange = await self._get_exchange()
                await exchange.load_markets()
                pairs = [
                    symbol for symbol in exchange.symbols
                    if symbol.endswith(f"/{quote_currency}") and exchange.markets[symbol].get("active")
                ]
                if pairs:
                    DataFetcher._active_exchange_id = current_candidate
                    return pairs
            except Exception:
                await self.close()
                continue
        return ["BTC/USDT", "ETH/USDT", "SOL/USDT"]
