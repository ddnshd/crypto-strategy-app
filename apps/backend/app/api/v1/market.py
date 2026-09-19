from fastapi import APIRouter
from app.services.data_fetcher import DataFetcher

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/ohlcv")
async def get_ohlcv(
    pair: str,
    timeframe: str = "1h",
    limit: int = 100,
):
    """Get latest OHLCV candles for charting on mobile."""
    fetcher = DataFetcher()
    try:
        df = await fetcher.get_latest_ohlcv(pair, timeframe, bars=limit)
        records = []
        for ts, row in df.iterrows():
            records.append({
                "timestamp": ts.isoformat(),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row["volume"]),
            })
        return {"pair": pair, "timeframe": timeframe, "data": records}
    finally:
        await fetcher.close()


@router.get("/price/{pair:path}")
async def get_price(pair: str):
    """Get current price of a pair."""
    fetcher = DataFetcher()
    try:
        price = await fetcher.get_current_price(pair)
        return {"pair": pair, "price": price}
    finally:
        await fetcher.close()


@router.get("/pairs")
async def list_pairs(quote: str = "USDT"):
    """List available trading pairs."""
    fetcher = DataFetcher()
    try:
        pairs = await fetcher.list_pairs(quote_currency=quote)
        return {"pairs": pairs[:200]}  # limit to 200
    finally:
        await fetcher.close()
