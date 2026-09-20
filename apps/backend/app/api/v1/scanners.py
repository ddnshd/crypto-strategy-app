import uuid
import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.deps import get_db
from app.models.strategy import Strategy, ActiveScanner
from app.schemas.strategy import ScannerActivate, ScannerResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/scanners", tags=["scanners"])


@router.post("/activate", response_model=ScannerResponse)
async def activate_scanner(
    data: ScannerActivate,
    db: AsyncSession = Depends(get_db),
):
    """Activate signal scanner for a strategy."""
    # Check strategy exists and is backtested
    result = await db.execute(select(Strategy).where(Strategy.id == data.strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if not strategy.is_backtested:
        raise HTTPException(
            status_code=400,
            detail="Strategy must be backtested before activating scanner"
        )

    if not strategy.backtest_score or strategy.backtest_score < 50:
        raise HTTPException(
            status_code=400,
            detail=f"Strategy score {strategy.backtest_score:.1f}/100 is below minimum (50). Run backtest again or refine strategy."
        )

    # Check if scanner already exists
    existing_result = await db.execute(
        select(ActiveScanner).where(ActiveScanner.strategy_id == data.strategy_id)
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        # Reactivate and update FCM token
        existing.is_active = True
        existing.fcm_token = data.fcm_token
        strategy.is_active = True
        await db.commit()
        await db.refresh(existing)
        return existing

    # Create new scanner
    strategy.is_active = True
    scanner = ActiveScanner(
        id=str(uuid.uuid4()),
        strategy_id=data.strategy_id,
        device_id=data.device_id,
        fcm_token=data.fcm_token,
        is_active=True,
    )
    db.add(scanner)
    await db.commit()
    await db.refresh(scanner)
    return scanner


@router.delete("/{scanner_id}")
async def deactivate_scanner(scanner_id: str, db: AsyncSession = Depends(get_db)):
    """Deactivate a scanner."""
    result = await db.execute(select(ActiveScanner).where(ActiveScanner.id == scanner_id))
    scanner = result.scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")

    scanner.is_active = False

    # Also deactivate strategy
    strat_result = await db.execute(
        select(Strategy).where(Strategy.id == scanner.strategy_id)
    )
    strategy = strat_result.scalar_one_or_none()
    if strategy:
        strategy.is_active = False

    await db.commit()
    return {"message": "Scanner deactivated"}


@router.get("", response_model=list[ScannerResponse])
async def list_scanners(
    device_id: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all scanners for a device, adopting legacy scanners across reinstalls."""
    result = await db.execute(select(ActiveScanner))
    scanners = result.scalars().all()
    if device_id and device_id != "all":
        adopted = False
        for s in scanners:
            if s.device_id != device_id:
                s.device_id = device_id
                adopted = True
        if adopted:
            await db.commit()
    return scanners


@router.put("/{scanner_id}/fcm-token")
async def update_fcm_token(
    scanner_id: str,
    fcm_token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Update FCM token for a scanner (called after app re-install)."""
    result = await db.execute(select(ActiveScanner).where(ActiveScanner.id == scanner_id))
    scanner = result.scalar_one_or_none()
    if not scanner:
        raise HTTPException(status_code=404, detail="Scanner not found")

    scanner.fcm_token = fcm_token
    await db.commit()
    return {"message": "FCM token updated"}
