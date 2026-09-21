from pydantic import BaseModel, Field
from typing import Optional, Any, Dict, List
from datetime import datetime
from enum import Enum


class TradingStyle(str, Enum):
    SCALP = "scalp"
    INTRADAY = "intraday"
    SWING = "swing"
    POSITION = "position"


class IndicatorCondition(BaseModel):
    indicator: str = Field(..., description="e.g. RSI, EMA, MACD, BBANDS, VOLUME")
    params: Dict[str, Any] = Field(default_factory=dict)
    operator: str = Field(..., description="<, >, ==, cross_above, cross_below, >=, <=")
    value: Optional[float] = None
    compare_to: Optional[str] = None


class ExitConditions(BaseModel):
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    take_profit_r: Optional[float] = None
    trailing_stop_pct: Optional[float] = None
    max_bars_held: Optional[int] = None
    exit_conditions: Optional[List[IndicatorCondition]] = None


class StrategyDefinition(BaseModel):
    name: str
    style: TradingStyle
    pair: str
    timeframe: str
    entry_conditions: List[IndicatorCondition]
    exit_conditions: ExitConditions
    filters: Optional[List[IndicatorCondition]] = None
    position_size_pct: float = 1.0
    notes: Optional[str] = None


class StrategyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    style: str
    pair: str
    timeframe: str
    definition: Dict[str, Any]
    device_id: str


class StrategyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    definition: Optional[Dict[str, Any]] = None
    change_note: Optional[str] = None


class StrategyResponse(BaseModel):
    id: str
    device_id: str
    name: str
    description: Optional[str]
    style: str
    pair: str
    timeframe: str
    definition: Dict[str, Any]
    is_active: bool
    is_backtested: bool
    backtest_score: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class AIStrategyRequest(BaseModel):
    user_input: str
    device_id: str
    refine_strategy_id: Optional[str] = None


class AIStrategyResponse(BaseModel):
    strategy: Dict[str, Any]
    explanation: str
    suggestions: List[str]
    warnings: List[str]


# Backtest schemas
class BacktestRequest(BaseModel):
    strategy_id: str
    pair: Optional[str] = None
    timeframe: Optional[str] = None
    period: Optional[str] = None  # "1m","3m","6m","1y","2y" — overrides start_date/end_date
    start_date: Optional[str] = None
    end_date: Optional[str] = None
    initial_capital: float = 1000.0
    position_size_pct: Optional[float] = None  # overrides strategy position_size_pct if provided
    enable_walk_forward: bool = True


class BacktestOptimizeRequest(BaseModel):
    user_goal: Optional[str] = None  # e.g. "Tingkatkan win rate", "Perkecil drawdown"


class BacktestOptimizeResponse(BaseModel):
    diagnosis: str
    weaknesses: List[str]
    improvements: List[str]
    optimized_strategy: Dict[str, Any]
    explanation: str


class BacktestResponse(BaseModel):
    id: str
    strategy_id: str
    pair: str
    timeframe: str
    start_date: str
    end_date: str
    win_rate: float
    profit_factor: float
    max_drawdown: float
    total_return: float
    sharpe_ratio: Optional[float]
    avg_rr: Optional[float]
    total_trades: int
    winning_trades: int
    losing_trades: int
    total_commission: Optional[float] = 0.0
    direction: Optional[str] = "long"
    score: float
    is_qualified: bool
    equity_curve: List[Dict]
    trade_log: List[Dict]
    walk_forward: Optional[Dict]
    created_at: datetime

    class Config:
        orm_mode = True


# Signal schemas
class SignalResponse(BaseModel):
    id: str
    strategy_id: str
    strategy_name: Optional[str] = None
    device_id: str
    pair: str
    direction: str
    entry_price: float
    stop_loss: Optional[float]
    take_profit: Optional[float]
    reason: Optional[str]
    triggered_indicators: Optional[Dict]
    is_hit: Optional[bool]
    close_price: Optional[float] = None
    pnl_pct: Optional[float]
    triggered_at: datetime
    closed_at: Optional[datetime] = None

    class Config:
        orm_mode = True


# Scanner schemas
class ScannerActivate(BaseModel):
    strategy_id: str
    device_id: str
    fcm_token: Optional[str] = None


class ScannerResponse(BaseModel):
    id: str
    strategy_id: str
    device_id: str
    fcm_token: Optional[str]
    is_active: bool
    last_checked_at: Optional[datetime]
    last_signal_at: Optional[datetime]
    created_at: datetime

    class Config:
        orm_mode = True
