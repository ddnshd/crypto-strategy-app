import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.models.strategy import Signal, Strategy
from app.schemas.strategy import SignalResponse
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/signals", tags=["signals"])


@router.get("", response_model=list[SignalResponse])
async def list_signals(
    device_id: str = Query(...),
    strategy_id: Optional[str] = Query(None),
    pair: Optional[str] = Query(None),
    limit: int = Query(default=50, le=200),
    db: AsyncSession = Depends(get_db),
):
    """List signals for a device."""
    query = (
        select(Signal, Strategy.name.label("strategy_name"))
        .join(Strategy, Signal.strategy_id == Strategy.id, isouter=True)
        .where(Signal.device_id == device_id)
    )
    if strategy_id:
        query = query.where(Signal.strategy_id == strategy_id)
    if pair:
        query = query.where(Signal.pair == pair)

    query = query.order_by(Signal.triggered_at.desc()).limit(limit)
    result = await db.execute(query)
    rows = result.all()

    signals = []
    for row in rows:
        signal = row[0]
        strategy_name = row[1]
        sig_dict = {
            "id": signal.id,
            "strategy_id": signal.strategy_id,
            "strategy_name": strategy_name,
            "device_id": signal.device_id,
            "pair": signal.pair,
            "direction": signal.direction,
            "entry_price": signal.entry_price,
            "stop_loss": signal.stop_loss,
            "take_profit": signal.take_profit,
            "reason": signal.reason,
            "triggered_indicators": signal.triggered_indicators,
            "is_hit": signal.is_hit,
            "pnl_pct": signal.pnl_pct,
            "triggered_at": signal.triggered_at,
        }
        signals.append(sig_dict)

    return signals


@router.get("/{signal_id}", response_model=SignalResponse)
async def get_signal(signal_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Signal).where(Signal.id == signal_id))
    signal = result.scalar_one_or_none()
    if not signal:
        raise HTTPException(status_code=404, detail="Signal not found")
    return signal


@router.get("/stats/{device_id}")
async def get_signal_stats(device_id: str, db: AsyncSession = Depends(get_db)):
    """Get signal performance stats for dashboard."""
    result = await db.execute(
        select(Signal).where(Signal.device_id == device_id)
    )
    signals = result.scalars().all()

    total = len(signals)
    with_result = [s for s in signals if s.is_hit is not None]
    wins = [s for s in with_result if s.is_hit is True]
    losses = [s for s in with_result if s.is_hit is False]

    hit_rate = len(wins) / len(with_result) if with_result else None
    avg_pnl = sum(s.pnl_pct for s in with_result if s.pnl_pct) / len(with_result) if with_result else None

    return {
        "total_signals": total,
        "signals_with_result": len(with_result),
        "wins": len(wins),
        "losses": len(losses),
        "hit_rate": round(hit_rate, 4) if hit_rate else None,
        "avg_pnl_pct": round(avg_pnl, 4) if avg_pnl else None,
    }
