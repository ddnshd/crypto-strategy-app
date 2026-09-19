from fastapi import APIRouter
from app.api.v1 import strategies, backtest, signals, scanners, ws, market

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(strategies.router)
api_router.include_router(backtest.router)
api_router.include_router(signals.router)
api_router.include_router(scanners.router)
api_router.include_router(market.router)
api_router.include_router(ws.router)
