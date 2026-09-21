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


def _json_safe(obj):
    """Ensure all values in nested dicts/lists are JSON-serializable."""
    return json.loads(json.dumps(obj, default=lambda x: int(x) if isinstance(x, bool) else float(x) if hasattr(x, '__float__') else str(x)))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])

# In-memory status tracker for running backtests
_backtest_status = {}


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
    ai_client = AIClient()
    try:
        analysis_result = await ai_client.analyze_and_optimize_backtest(
            strategy_name=strategy.name,
            strategy_def=strategy.definition,
            backtest_summary=backtest_summary,
            user_goal=user_goal,
        )
    except ValueError as ve:
        raise HTTPException(status_code=422, detail=str(ve))
    except Exception as e:
        logger.error(f"AI backtest optimize error: {e}", exc_info=True)
        raise HTTPException(status_code=503, detail=f"Gagal menghubungi AI untuk analisis: {e}")

    return BacktestOptimizeResponse(**analysis_result)
