import uuid
import json
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.models.strategy import Strategy, BacktestResult
from app.schemas.strategy import BacktestRequest, BacktestResponse
from app.services.backtester import Backtester


def _json_safe(obj):
    """Ensure all values in nested dicts/lists are JSON-serializable."""
    return json.loads(json.dumps(obj, default=lambda x: int(x) if isinstance(x, bool) else float(x) if hasattr(x, '__float__') else str(x)))

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/backtest", tags=["backtest"])


async def _run_and_save_backtest(
    strategy_id: str,
    backtest_id: str,
    strategy: Strategy,
    request: BacktestRequest,
    db_session_factory,
):
    """Background task to run backtest and save results."""
    backtester = Backtester()
    try:
        pair = request.pair or strategy.pair
        timeframe = request.timeframe or strategy.timeframe

        result = await backtester.run(
            strategy_definition=strategy.definition,
            pair=pair,
            timeframe=timeframe,
            start_date=request.start_date,
            end_date=request.end_date,
            initial_capital=request.initial_capital,
            enable_walk_forward=request.enable_walk_forward,
        )

        async with db_session_factory() as session:
            # Update strategy status first (before adding backtest)
            strat_result = await session.execute(
                select(Strategy).where(Strategy.id == strategy_id)
            )
            strat = strat_result.scalar_one_or_none()
            if strat:
                strat.is_backtested = True
                strat.backtest_score = result["score"]

            # Now add backtest result
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
                score=float(result["score"]),
                is_qualified=bool(result["is_qualified"]),
                equity_curve=_json_safe(result["equity_curve"]),
                trade_log=_json_safe(result["trade_log"]),
                walk_forward=_json_safe(result["walk_forward"]) if result.get("walk_forward") else None,
            )
            session.add(backtest)
            await session.commit()

    except Exception as e:
        logger.error(f"Backtest failed for strategy {strategy_id}: {e}", exc_info=True)


@router.post("/run", response_model=dict)
async def run_backtest(
    request: BacktestRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
):
    """
    Start a backtest run. Runs in background and returns immediately with backtest_id.
    Poll GET /backtest/{backtest_id} to check results.
    """
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
        "message": "Backtest sedang dijalankan, poll GET /backtest/{backtest_id} untuk hasil"
    }


@router.get("/strategy/{strategy_id}", response_model=list[BacktestResponse])
async def get_strategy_backtests(strategy_id: str, db: AsyncSession = Depends(get_db)):
    """Get all backtest results for a strategy."""
    result = await db.execute(
        select(BacktestResult)
        .where(BacktestResult.strategy_id == strategy_id)
        .order_by(BacktestResult.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{backtest_id}", response_model=BacktestResponse)
async def get_backtest_result(backtest_id: str, db: AsyncSession = Depends(get_db)):
    """Get backtest result by ID. Returns 404 while still running."""
    result = await db.execute(
        select(BacktestResult).where(BacktestResult.id == backtest_id)
    )
    backtest = result.scalar_one_or_none()
    if not backtest:
        raise HTTPException(status_code=404, detail="Backtest result not found or still running")
    return backtest
