import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete
from app.core.deps import get_db
from app.models.strategy import Strategy, StrategyVersion
from app.schemas.strategy import (
    StrategyCreate, StrategyUpdate, StrategyResponse,
    AIStrategyRequest, AIStrategyResponse
)
from app.services.ai_client import AIClient
from typing import Optional

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/strategies", tags=["strategies"])
ai_client = AIClient()


@router.post("/generate", response_model=AIStrategyResponse)
async def generate_strategy(request: AIStrategyRequest, db: AsyncSession = Depends(get_db)):
    """Generate a strategy from natural language using AI."""
    existing_def = None

    if request.refine_strategy_id:
        result = await db.execute(
            select(Strategy).where(Strategy.id == request.refine_strategy_id)
        )
        existing = result.scalar_one_or_none()
        if existing:
            existing_def = existing.definition

    try:
        ai_result = await ai_client.generate_strategy(
            user_input=request.user_input,
            existing_strategy=existing_def,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"AI generation failed: {e}")
        raise HTTPException(status_code=503, detail="AI service unavailable")

    return AIStrategyResponse(**ai_result)


@router.post("/chat")
async def chat_about_strategy(
    messages: list[dict],
):
    """General chat endpoint for strategy discussion."""
    try:
        reply = await ai_client.chat(messages)
        return {"reply": reply}
    except Exception as e:
        raise HTTPException(status_code=503, detail="AI service unavailable")


@router.post("", response_model=StrategyResponse)
async def create_strategy(data: StrategyCreate, db: AsyncSession = Depends(get_db)):
    """Save a strategy (AI-generated or manual)."""
    strategy = Strategy(
        id=str(uuid.uuid4()),
        device_id=data.device_id,
        name=data.name,
        description=data.description,
        style=data.style,
        pair=data.pair,
        timeframe=data.timeframe,
        definition=data.definition,
    )
    db.add(strategy)

    # Save initial version
    version = StrategyVersion(
        id=str(uuid.uuid4()),
        strategy_id=strategy.id,
        version=1,
        definition=data.definition,
        change_note="Initial version",
    )
    db.add(version)
    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.get("", response_model=list[StrategyResponse])
async def list_strategies(
    device_id: Optional[str] = Query(None),
    style: Optional[str] = Query(None),
    pair: Optional[str] = Query(None),
    timeframe: Optional[str] = Query(None),
    is_backtested: Optional[bool] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """List all strategies with optional filters. Automatically preserves all strategies across reinstalls."""
    query = select(Strategy)
    if style:
        query = query.where(Strategy.style == style)
    if pair:
        query = query.where(Strategy.pair == pair)
    if timeframe:
        query = query.where(Strategy.timeframe == timeframe)
    if is_backtested is not None:
        query = query.where(Strategy.is_backtested == is_backtested)

    query = query.order_by(Strategy.created_at.desc())
    result = await db.execute(query)
    strategies = result.scalars().all()

    # Automatically adopt strategies to current device_id so user never loses their strategies on app reinstall
    if device_id and device_id != "all":
        adopted = False
        for s in strategies:
            if s.device_id != device_id:
                s.device_id = device_id
                adopted = True
        if adopted:
            await db.commit()

    return strategies


@router.get("/{strategy_id}", response_model=StrategyResponse)
async def get_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    return strategy


@router.put("/{strategy_id}", response_model=StrategyResponse)
async def update_strategy(
    strategy_id: str,
    data: StrategyUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update strategy and save new version."""
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")

    if data.name:
        strategy.name = data.name
    if data.description is not None:
        strategy.description = data.description
    if data.definition:
        # Save new version
        versions_result = await db.execute(
            select(StrategyVersion)
            .where(StrategyVersion.strategy_id == strategy_id)
            .order_by(StrategyVersion.version.desc())
        )
        latest = versions_result.scalars().first()
        next_version = (latest.version + 1) if latest else 1

        new_version = StrategyVersion(
            id=str(uuid.uuid4()),
            strategy_id=strategy_id,
            version=next_version,
            definition=data.definition,
            change_note=data.change_note,
        )
        db.add(new_version)
        strategy.definition = data.definition
        strategy.is_backtested = False  # reset backtest status when definition changes
        strategy.backtest_score = None

    await db.commit()
    await db.refresh(strategy)
    return strategy


@router.post("/{strategy_id}/duplicate", response_model=StrategyResponse)
async def duplicate_strategy(
    strategy_id: str,
    device_id: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """Duplicate a strategy for parameter testing."""
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    original = result.scalar_one_or_none()
    if not original:
        raise HTTPException(status_code=404, detail="Strategy not found")

    new_strategy = Strategy(
        id=str(uuid.uuid4()),
        device_id=device_id,
        name=f"{original.name} (copy)",
        description=original.description,
        style=original.style,
        pair=original.pair,
        timeframe=original.timeframe,
        definition=original.definition,
    )
    db.add(new_strategy)

    version = StrategyVersion(
        id=str(uuid.uuid4()),
        strategy_id=new_strategy.id,
        version=1,
        definition=original.definition,
        change_note=f"Duplicated from {original.name}",
    )
    db.add(version)
    await db.commit()
    await db.refresh(new_strategy)
    return new_strategy


@router.delete("/{strategy_id}")
async def delete_strategy(strategy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Strategy).where(Strategy.id == strategy_id))
    strategy = result.scalar_one_or_none()
    if not strategy:
        raise HTTPException(status_code=404, detail="Strategy not found")
    await db.delete(strategy)
    await db.commit()
    return {"message": "Strategy deleted"}


@router.get("/{strategy_id}/versions")
async def get_strategy_versions(strategy_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(StrategyVersion)
        .where(StrategyVersion.strategy_id == strategy_id)
        .order_by(StrategyVersion.version.desc())
    )
    versions = result.scalars().all()
    return [
        {
            "id": v.id,
            "version": v.version,
            "change_note": v.change_note,
            "created_at": v.created_at,
            "definition": v.definition,
        }
        for v in versions
    ]
