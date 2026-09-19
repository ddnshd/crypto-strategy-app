import uuid
from datetime import datetime
from sqlalchemy import String, DateTime, JSON, Text, Float, Integer, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.core.database import Base


def generate_uuid():
    return str(uuid.uuid4())


class Strategy(Base):
    __tablename__ = "strategies"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Strategy classification
    style: Mapped[str] = mapped_column(String(50), nullable=False)  # scalp/intraday/swing/position
    pair: Mapped[str] = mapped_column(String(50), nullable=False)   # BTC/USDT
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)  # 1m, 5m, 15m, 1h, 4h, 1d

    # Strategy logic (JSON)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=False)
    is_backtested: Mapped[bool] = mapped_column(Boolean, default=False)
    backtest_score: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    backtest_results: Mapped[list["BacktestResult"]] = relationship(
        "BacktestResult", back_populates="strategy", cascade="all, delete-orphan"
    )
    versions: Mapped[list["StrategyVersion"]] = relationship(
        "StrategyVersion", back_populates="strategy", cascade="all, delete-orphan"
    )
    signals: Mapped[list["Signal"]] = relationship(
        "Signal", back_populates="strategy", cascade="all, delete-orphan"
    )
    scanner: Mapped["ActiveScanner | None"] = relationship(
        "ActiveScanner", back_populates="strategy", uselist=False, cascade="all, delete-orphan"
    )


class BacktestResult(Base):
    __tablename__ = "backtest_results"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id"), nullable=False)

    # Test period
    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    timeframe: Mapped[str] = mapped_column(String(10), nullable=False)
    start_date: Mapped[str] = mapped_column(String(30), nullable=False)
    end_date: Mapped[str] = mapped_column(String(30), nullable=False)

    # Performance metrics
    win_rate: Mapped[float] = mapped_column(Float, nullable=False)
    profit_factor: Mapped[float] = mapped_column(Float, nullable=False)
    max_drawdown: Mapped[float] = mapped_column(Float, nullable=False)
    total_return: Mapped[float] = mapped_column(Float, nullable=False)
    sharpe_ratio: Mapped[float | None] = mapped_column(Float, nullable=True)
    avg_rr: Mapped[float | None] = mapped_column(Float, nullable=True)
    total_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    winning_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    losing_trades: Mapped[int] = mapped_column(Integer, nullable=False)
    total_commission: Mapped[float | None] = mapped_column(Float, nullable=True)  # total fees paid
    direction: Mapped[str] = mapped_column(String(10), nullable=False, default="long")  # long/short

    # Score & qualification
    score: Mapped[float] = mapped_column(Float, nullable=False)  # 0-100
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Detail data (JSON)
    equity_curve: Mapped[list] = mapped_column(JSON, nullable=True)    # [{date, value}, ...]
    trade_log: Mapped[list] = mapped_column(JSON, nullable=True)        # [{entry, exit, pnl, ...}, ...]
    walk_forward: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # in-sample vs out-of-sample

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    # Relationships
    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="backtest_results")


class StrategyVersion(Base):
    __tablename__ = "strategy_versions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    definition: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="versions")


class Signal(Base):
    __tablename__ = "signals"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id"), nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)

    pair: Mapped[str] = mapped_column(String(50), nullable=False)
    direction: Mapped[str] = mapped_column(String(10), nullable=False)  # long/short
    entry_price: Mapped[float] = mapped_column(Float, nullable=False)
    stop_loss: Mapped[float | None] = mapped_column(Float, nullable=True)
    take_profit: Mapped[float | None] = mapped_column(Float, nullable=True)

    reason: Mapped[str | None] = mapped_column(Text, nullable=True)     # human-readable trigger reason
    triggered_indicators: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # indicator values at trigger

    # Paper trading tracking
    is_hit: Mapped[bool | None] = mapped_column(Boolean, nullable=True)  # None = pending, True = TP hit, False = SL hit
    close_price: Mapped[float | None] = mapped_column(Float, nullable=True)
    pnl_pct: Mapped[float | None] = mapped_column(Float, nullable=True)

    triggered_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="signals")


class ActiveScanner(Base):
    __tablename__ = "active_scanners"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_uuid)
    strategy_id: Mapped[str] = mapped_column(String(36), ForeignKey("strategies.id"), unique=True, nullable=False)
    device_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    fcm_token: Mapped[str | None] = mapped_column(String(500), nullable=True)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_signal_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    strategy: Mapped["Strategy"] = relationship("Strategy", back_populates="scanner")
