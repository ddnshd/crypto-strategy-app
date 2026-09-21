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


class DataFetcher:
    def __init__(self, exchange_id: str = None):
        self.exchange_id = exchange_id or settings.DEFAULT_EXCHANGE
        self._exchange = None

    async def _get_exchange(self) -> ccxt.Exchange:
        if self._exchange is None:
            exchange_class = getattr(ccxt, self.exchange_id)
            self._exchange = exchange_class({
                "enableRateLimit": True,
                "timeout": 30000,
            })
        return self._exchange

    async def close(self):
        if self._exchange:
            await self._exchange.close()
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
        exchange = await self._get_exchange()

        since = None
        if start_date:
            dt = datetime.strptime(start_date, "%Y-%m-%d")
            since = int(dt.timestamp() * 1000)
        elif not since:
            # Default: fetch enough bars based on timeframe
            tf_minutes = TIMEFRAME_MAP.get(timeframe, 60)
            days_back = max(30, (limit * tf_minutes) // 1440 + 1)
            since = int((datetime.utcnow() - timedelta(days=days_back)).timestamp() * 1000)

        all_ohlcv = []
        current_since = since

        try:
            while True:
                ohlcv = await exchange.fetch_ohlcv(
                    pair, timeframe, since=current_since, limit=1000
                )
                if not ohlcv:
                    break

                all_ohlcv.extend(ohlcv)

                # Check if we've reached end_date
                if end_date:
                    end_dt = datetime.strptime(end_date, "%Y-%m-%d")
                    last_ts = ohlcv[-1][0] / 1000
                    if datetime.utcfromtimestamp(last_ts) >= end_dt:
                        break

                # If fewer bars than limit, we've got everything
                if len(ohlcv) < 1000:
                    break

                # Move to next batch
                current_since = ohlcv[-1][0] + 1

        except ccxt.NetworkError as e:
            logger.error(f"Network error fetching {pair}: {e}")
            raise
        except ccxt.ExchangeError as e:
            logger.error(f"Exchange error fetching {pair}: {e}")
            raise

        if not all_ohlcv:
            raise ValueError(f"No OHLCV data returned for {pair} {timeframe}")

        df = pd.DataFrame(
            all_ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        df = df.sort_index()
        # Remove any overlapping/duplicate timestamps from pagination
        df = df[~df.index.duplicated(keep="first")]

        # Filter by end_date if specified (include full 23:59:59 of that date)
        if end_date:
            end_dt = pd.Timestamp(end_date) + pd.Timedelta(days=1) - pd.Timedelta(milliseconds=1)
            df = df[df.index <= end_dt]

        return df

    async def get_current_price(self, pair: str) -> float:
        """Get the latest ticker price."""
        exchange = await self._get_exchange()
        ticker = await exchange.fetch_ticker(pair)
        return float(ticker["last"])

    async def get_latest_ohlcv(self, pair: str, timeframe: str, bars: int = 200) -> pd.DataFrame:
        """Get the latest N bars of OHLCV data."""
        exchange = await self._get_exchange()
        ohlcv = await exchange.fetch_ohlcv(pair, timeframe, limit=bars)

        if not ohlcv:
            raise ValueError(f"No data for {pair} {timeframe}")

        df = pd.DataFrame(
            ohlcv,
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        return df

    async def list_pairs(self, quote_currency: str = "USDT") -> list[str]:
        """List available trading pairs."""
        exchange = await self._get_exchange()
        await exchange.load_markets()
        return [
            symbol for symbol in exchange.symbols
            if symbol.endswith(f"/{quote_currency}") and exchange.markets[symbol].get("active")
        ]
