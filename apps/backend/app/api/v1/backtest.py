import uuid
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.models.strategy import Strategy, BacktestResult
from app.schemas.strategy import (
    BacktestRequest, BacktestResponse,
    BacktestOptimizeRequest, BacktestOptimizeResponse
)
from app.services.backtester import Backtester
from app.services.ai_client import AIClient
from app.services.data_fetcher import DataFetcher


def _json_safe(obj):
    """Ensure all values in nested dicts/lists are JSON-serializable."""
    return json.loads(json.dumps(obj, default=lambda x: int(x) if isinstance(x, bool) else float(x) if hasattr(x, '__float__') else str(x)))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])

# In-memory status tracker for running backtests
_backtest_status = {}


async def fetch_market_context(pair: str, timeframe: str, start_date: str, end_date: str) -> dict:
    """Fetch OHLCV from exchange (Binance-first) for the backtest period and compute market stats."""
    try:
        import pandas as pd
        import ta as ta_lib

        fetcher = DataFetcher()
        try:
            df = await fetcher.fetch_ohlcv(
                pair=pair, timeframe=timeframe,
                start_date=start_date, end_date=end_date,
            )
        finally:
            await fetcher.close()

        if df is None or len(df) < 20:
            return {"error": f"Data OHLCV tidak cukup ({0 if df is None else len(df)} bar)"}

        close = df["close"]
        high = df["high"]
        low = df["low"]
        volume = df["volume"]

        # Trend via EMA stack
        ema20 = close.ewm(span=20).mean()
        ema50 = close.ewm(span=50).mean()
        ema200 = close.ewm(span=min(200, max(50, len(close) // 3))).mean()
        e20, e50, e200 = float(ema20.iloc[-1]), float(ema50.iloc[-1]), float(ema200.iloc[-1])
        if e20 > e50 > e200:
            trend = "uptrend kuat (EMA20>EMA50>EMA200)"
        elif e20 < e50 < e200:
            trend = "downtrend kuat (EMA20<EMA50<EMA200)"
        elif e20 > e50:
            trend = "uptrend lemah / fase pemulihan"
        elif e20 < e50:
            trend = "downtrend lemah / fase koreksi"
        else:
            trend = "sideways / ranging"

        period_return_pct = (float(close.iloc[-1]) / float(close.iloc[0]) - 1) * 100

        # ATR volatility
        atr = ta_lib.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
        atr_pct = float((atr / close).mean() * 100)

        # RSI distribution
        rsi = ta_lib.momentum.RSIIndicator(close, window=14).rsi()
        rsi_avg = float(rsi.mean())
        rsi_last = float(rsi.iloc[-1])
        rsi_oversold_pct = float((rsi < 30).mean() * 100)
        rsi_overbought_pct = float((rsi > 70).mean() * 100)

        # S/R approximation: rolling extremes
        sr_res = float(high.tail(min(50, len(df))).max())
        sr_sup = float(low.tail(min(50, len(df))).min())

        # Volume
        vol_avg = float(volume.mean())
        vol_last = float(volume.iloc[-1])
        vol_ratio = vol_last / vol_avg if vol_avg > 0 else 1.0

        # Compact recent candles so the LLM can "see" price action
        recent_candles = []
        for ts, row in df.tail(20).iterrows():
            recent_candles.append({
                "t": str(ts),
                "o": round(float(row["open"]), 2),
                "h": round(float(row["high"]), 2),
                "l": round(float(row["low"]), 2),
                "c": round(float(row["close"]), 2),
                "v": round(float(row["volume"]), 4),
            })

        return {
            "data_source": "Binance OHLCV (via ccxt, fallback otomatis)",
            "total_bars": len(df),
            "trend": trend,
            "period_return_pct": round(period_return_pct, 2),
            "last_close": round(float(close.iloc[-1]), 2),
            "period_high": round(float(high.max()), 2),
            "period_low": round(float(low.min()), 2),
            "atr14_pct_avg": round(atr_pct, 3),
            "rsi14_avg": round(rsi_avg, 1),
            "rsi14_last": round(rsi_last, 1),
            "rsi_oversold_pct_bars": round(rsi_oversold_pct, 1),
            "rsi_overbought_pct_bars": round(rsi_overbought_pct, 1),
            "short_term_resistance": round(sr_res, 2),
            "short_term_support": round(sr_sup, 2),
            "volume_avg": round(vol_avg, 4),
            "volume_last_vs_avg_ratio": round(vol_ratio, 2),
            "recent_candles": recent_candles,
        }
    except Exception as e:
        logger.warning(f"Market context fetch failed for {pair}: {e}")
        return {"error": f"Gagal mengambil data pasar: {e}"}


def build_trade_samples(trade_log: list, max_losers: int = 8, max_winners: int = 8) -> dict:
    """Pick the worst losers and best winners so AI can diagnose concrete failures."""
    trades = [t for t in (trade_log or []) if isinstance(t, dict)]
    losers = sorted(
        [t for t in trades if not t.get("is_win")],
        key=lambda x: float(x.get("pnl_usd") or 0),
    )[:max_losers]
    winners = sorted(
        [t for t in trades if t.get("is_win")],
        key=lambda x: float(x.get("pnl_usd") or 0),
        reverse=True,
    )[:max_winners]

    def slim(t: dict) -> dict:
        return {
            "trade_num": t.get("trade_num"),
            "entry_date": t.get("entry_date"),
            "exit_date": t.get("exit_date"),
            "direction": t.get("direction"),
            "entry_price": t.get("entry_price"),
            "exit_price": t.get("exit_price"),
            "pnl_pct": t.get("pnl_pct"),
            "pnl_usd": t.get("pnl_usd"),
            "exit_reason": t.get("exit_reason"),
        }

    return {
        "total_trades": len(trades),
        "worst_losers": [slim(t) for t in losers],
        "best_winners": [slim(t) for t in winners],
    }


def build_equity_insight(equity_curve: list) -> dict:
    """Summarize equity curve: max DD window + downsampled series for the prompt."""
    points = [p for p in (equity_curve or []) if isinstance(p, dict) and p.get("value") is not None]
    if not points:
        return {}

    values = [float(p["value"]) for p in points]
    peak = values[0]
    peak_idx = 0
    max_dd = 0.0
    dd_start = dd_end = 0
    for i, v in enumerate(values):
        if v > peak:
            peak = v
            peak_idx = i
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
            dd_start = peak_idx
            dd_end = i

    # Downsample to ~40 points so prompt stays compact
    step = max(1, len(points) // 40)
    sampled = points[::step]
    if sampled[-1] is not points[-1]:
        sampled.append(points[-1])

    return {
        "max_drawdown_pct": round(max_dd * 100, 2),
        "max_dd_start_date": points[dd_start].get("date"),
        "max_dd_bottom_date": points[dd_end].get("date"),
        "final_equity": values[-1],
        "start_equity": values[0],
        "equity_sample": [
            {"date": p.get("date"), "value": p.get("value")} for p in sampled
        ],
    }


async def _run_and_save_backtest(
    strategy_id: str,
    backtest_id: str,
    strategy: Strategy,
    request: BacktestRequest,
    db_session_factory,
):
    """Background task to run backtest and save results."""
    _backtest_status[backtest_id] = {"status": "running", "error": None}
    backtester = Backtester()
    try:
        pair = request.pair or strategy.pair
        timeframe = request.timeframe or strategy.timeframe

        result = await backtester.run(
            strategy_definition=strategy.definition,
            pair=pair,
            timeframe=timeframe,
            period=request.period,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            position_size_pct=request.position_size_pct,
            enable_walk_forward=request.enable_walk_forward,
        )

        async with db_session_factory() as session:
            strat_result = await session.execute(
                select(Strategy).where(Strategy.id == strategy_id)
            )
            strat = strat_result.scalar_one_or_none()
            if strat:
                strat.is_backtested = True
                strat.backtest_score = result["score"]

            backtest = BacktestResult(
                id=backtest_id,
                strategy_id=strategy_id,
                pair=result["pair"],
                timeframe=result["timeframe"],
                start_date=result["start_date"],
                end_date=result["end_date"],
                win_rate=float(result["win_rate"]),
                profit_factor=float(result["profit_factor"]),
                max_drawdown=float(result["max_drawdown"]),
                total_return=float(result["total_return"]),
                sharpe_ratio=float(result["sharpe_ratio"]) if result.get("sharpe_ratio") is not None else None,
                avg_rr=float(result["avg_rr"]) if result.get("avg_rr") is not None else None,
                total_trades=int(result["total_trades"]),
                winning_trades=int(result["winning_trades"]),
                losing_trades=int(result["losing_trades"]),
                total_commission=float(result.get("total_commission", 0)),
                direction=result.get("direction", "long"),
                score=float(result["score"]),
                is_qualified=bool(result["is_qualified"]),
                equity_curve=_json_safe(result["equity_curve"]),
                trade_log=_json_safe(result["trade_log"]),
                walk_forward=_json_safe(result["walk_forward"]) if result.get("walk_forward") else None,
            )
            session.add(backtest)
            await session.commit()

        _backtest_status[backtest_id]["status"] = "done"

    except Exception as e:
        logger.error(f"Backtest failed for strategy {strategy_id}: {e}", exc_info=True)
        _backtest_status[backtest_id]["status"] = "failed"
        _backtest_status[backtest_id]["error"] = str(e)


@router.post("/run", response_model=dict)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Strategy).where(Strategy.id == request.strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    backtest_id = str(uuid.uuid4())
    from app.core.database import AsyncSessionLocal
    background_tasks.add_task(
        _run_and_save_backtest,
        strategy.id,
        backtest_id,
        strategy,
        request,
        AsyncSessionLocal,
    )

    return {
        "backtest_id": backtest_id,
        "status": "running",
        "message": "Backtest sedang dijalankan"
    }


@router.get("/strategy/{strategy_id}", response_model=list[BacktestResponse])
async def get_strategy_backtests(strategy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(BacktestResult)
        .where(BacktestResult.strategy_id == strategy_id)
        .order_by(BacktestResult.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{backtest_id}")
async def get_backtest_result(backtest_id: str, db: AsyncSession = Depends(get_db)):
    # Check if still running or failed
    status = _backtest_status.get(backtest_id)
    if status:
        if status["status"] == "running":
            return {"id": backtest_id, "status": "running", "message": "Backtest masih dijalankan..."}
        elif status["status"] == "failed":
            return {"id": backtest_id, "status": "failed", "error": status.get("error", "Unknown error")}

    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    if not backtest:
        return {"id": backtest_id, "status": "running", "message": "Backtest masih dijalankan..."}
    return backtest


@router.post("/{backtest_id}/ai-optimize", response_model=BacktestOptimizeResponse)
async def ai_optimize_backtest(
    backtest_id: str,
    request: BacktestOptimizeRequest = None,
    db: AsyncSession = Depends(get_db),
):
    """Analyze backtest result metrics using AI and generate an optimized strategy definition."""
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    if not backtest:
        raise HTTPException(status_code=404, detail="Hasil backtest tidak ditemukan")

    strat_result = await db.execute(
        select(Strategy).where(Strategy.id == backtest.strategy_id)
    )
    strategy = strat_result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategi tidak ditemukan")

    exit_reasons = {}
    for t in (backtest.trade_log or []):
        if isinstance(t, dict):
            r = t.get("exit_reason", "unknown")
            exit_reasons[r] = exit_reasons.get(r, 0) + 1

    wf = backtest.walk_forward or {}
    wf_deg = wf.get("degradation_pct", "N/A")
    wf_cons = "Konsisten" if isinstance(wf_deg, (int, float)) and wf_deg < 10 else "Overfitting" if isinstance(wf_deg, (int, float)) and wf_deg > 25 else "Cukup Konsisten"

    backtest_summary = {
        "pair": backtest.pair,
        "timeframe": backtest.timeframe,
        "start_date": backtest.start_date,
        "end_date": backtest.end_date,
        "total_trades": backtest.total_trades,
        "winning_trades": backtest.winning_trades,
        "losing_trades": backtest.losing_trades,
        "win_rate_pct": round(float(backtest.win_rate or 0) * 100, 1),
        "profit_factor": round(float(backtest.profit_factor or 0), 2),
        "total_return_pct": round(float(backtest.total_return or 0) * 100, 1),
        "max_drawdown_pct": round(float(backtest.max_drawdown or 0) * 100, 1),
        "sharpe_ratio": round(float(backtest.sharpe_ratio or 0), 2),
        "avg_rr": round(float(backtest.avg_rr or 0), 2),
        "total_commission": round(float(backtest.total_commission or 0), 2),
        "score": round(float(backtest.score or 0), 1),
        "exit_reasons": exit_reasons,
        "wf_degradation": wf_deg,
        "wf_consistency": wf_cons,
    }

    user_goal = request.user_goal if request else None

    # Enrich with real market data (Binance OHLCV) + concrete trade/equity samples
    market_context = await fetch_market_context(
        pair=backtest.pair,
        timeframe=backtest.timeframe,
        start_date=backtest.start_date,
        end_date=backtest.end_date,
    )
    trade_samples = build_trade_samples(backtest.trade_log)
    equity_insight = build_equity_insight(backtest.equity_curve)

    ai_client = AIClient()
    try:
        analysis_result = await ai_client.analyze_and_optimize_backtest(
            strategy_name=strategy.name,
            strategy_def=strategy.definition,
            backtest_summary=backtest_summary,
            user_goal=user_goal,
            market_context=market_context,
            trade_samples=trade_samples,
            equity_insight=equity_insight,
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"AI backtest optimize error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Gagal menghubungi AI untuk analisis: {e}")

    return BacktestOptimizeResponse(**analysis_result)
