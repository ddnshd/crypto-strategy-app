import asyncio
import logging
from datetime import datetime
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from app.models.strategy import Strategy, ActiveScanner, Signal
from app.services.data_fetcher import DataFetcher
from app.services.indicators import compute_indicators, evaluate_condition
from app.services.notifications import NotificationService
from app.core.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

# Global set of active scanner tasks
_scanner_tasks: dict[str, asyncio.Task] = {}
_fetchers: dict[str, DataFetcher] = {}


class SignalScanner:
    def __init__(self):
        self.notifier = NotificationService()
        self._running = False

    async def start(self):
        """Start the main scanner loop that manages all active scanners."""
        self._running = True
        logger.info("Signal scanner started")
        while self._running:
            try:
                await self._sync_and_scan()
            except Exception as e:
                logger.error(f"Scanner loop error: {e}")
            await asyncio.sleep(60)

    async def stop(self):
        self._running = False
        for task in _scanner_tasks.values():
            task.cancel()
        _scanner_tasks.clear()
        for fetcher in _fetchers.values():
            await fetcher.close()
        _fetchers.clear()
        logger.info("Signal scanner stopped")

    async def _sync_and_scan(self):
        """Load all active scanners from DB and scan them."""
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(ActiveScanner).where(ActiveScanner.is_active == True)
            )
            scanners = result.scalars().all()

        for scanner in scanners:
            scanner_id = scanner.id
            if scanner_id not in _scanner_tasks or _scanner_tasks[scanner_id].done():
                task = asyncio.create_task(
                    self._scan_strategy(scanner),
                    name=f"scanner_{scanner_id}"
                )
                _scanner_tasks[scanner_id] = task

    async def _scan_strategy(self, scanner: ActiveScanner):
        """Scan a single strategy for signals."""
        try:
            async with AsyncSessionLocal() as session:
                strategy_result = await session.execute(
                    select(Strategy).where(Strategy.id == scanner.strategy_id)
                )
                strategy = strategy_result.scalar_one_or_none()

                if not strategy or not strategy.is_active:
                    return

                definition = strategy.definition
                pair = strategy.pair
                timeframe = strategy.timeframe
                entry_conditions = [c for c in definition.get("entry_conditions", []) if isinstance(c, dict)]
                filters = [c for c in definition.get("filters", []) if isinstance(c, dict)]
                exit_def = definition.get("exit_conditions", {})
                if not isinstance(exit_def, dict):
                    exit_def = {}

                # Detect direction
                is_short = definition.get("direction") == "short"
                if not is_short:
                    for cond in entry_conditions:
                        ind = cond.get("indicator", "").upper()
                        op = cond.get("operator", "")
                        val = cond.get("value")
                        if ind == "RSI" and op in (">", ">=") and isinstance(val, (int, float)) and val >= 65:
                            is_short = True
                            break
                        if ind == "STOCH" and op in (">", ">=") and isinstance(val, (int, float)) and val >= 75:
                            is_short = True
                            break
                direction = "short" if is_short else "long"

                # Prevent duplicate signal spam within 5 minutes
                if scanner.last_signal_at:
                    if (datetime.utcnow() - scanner.last_signal_at).total_seconds() < 300:
                        return

                # Fetch latest OHLCV
                fetcher_key = scanner.id
                if fetcher_key not in _fetchers:
                    _fetchers[fetcher_key] = DataFetcher()

                fetcher = _fetchers[fetcher_key]
                df = await fetcher.get_latest_ohlcv(pair, timeframe, bars=200)

                # Compute indicators
                all_conditions = entry_conditions + filters
                df = compute_indicators(df, all_conditions)
                df = df.dropna()

                if len(df) < 10:
                    return

                # Check last bar for signal
                signal_triggered = True
                triggered_values = {}

                for cond in entry_conditions:
                    try:
                        result_series = evaluate_condition(df, cond)
                        if not result_series.iloc[-1]:
                            signal_triggered = False
                            break
                        indicator = cond.get("indicator", "")
                        triggered_values[indicator] = float(df["close"].iloc[-1])
                    except Exception as e:
                        logger.warning(f"Condition eval error in scanner: {e}")
                        signal_triggered = False
                        break

                if signal_triggered and filters:
                    for cond in filters:
                        try:
                            result_series = evaluate_condition(df, cond)
                            if not result_series.iloc[-1]:
                                signal_triggered = False
                                break
                        except Exception as e:
                            logger.warning(f"Filter eval error in scanner: {e}")

                # Update last_checked_at regardless
                await session.execute(
                    update(ActiveScanner)
                    .where(ActiveScanner.id == scanner.id)
                    .values(last_checked_at=datetime.utcnow())
                )
                await session.commit()

                if not signal_triggered:
                    return

                # Build signal
                entry_price = float(df.iloc[-1]["close"])
                tp_pct = exit_def.get("take_profit_pct")
                sl_pct = exit_def.get("stop_loss_pct")
                if is_short:
                    tp = round(entry_price * (1 - tp_pct / 100), 6) if tp_pct else None
                    sl = round(entry_price * (1 + sl_pct / 100), 6) if sl_pct else None
                else:
                    tp = round(entry_price * (1 + tp_pct / 100), 6) if tp_pct else None
                    sl = round(entry_price * (1 - sl_pct / 100), 6) if sl_pct else None

                reason_parts = []
                for cond in entry_conditions:
                    ind = cond.get("indicator", "")
                    op = cond.get("operator", "")
                    val = cond.get("value", "")
                    reason_parts.append(f"{ind} {op} {val}")
                reason = " AND ".join(reason_parts)

                # Save signal
                new_signal = Signal(
                    strategy_id=strategy.id,
                    device_id=scanner.device_id,
                    pair=pair,
                    direction=direction,
                    entry_price=entry_price,
                    stop_loss=sl,
                    take_profit=tp,
                    reason=reason,
                    triggered_indicators=triggered_values,
                    triggered_at=datetime.utcnow(),
                )
                session.add(new_signal)

                await session.execute(
                    update(ActiveScanner)
                    .where(ActiveScanner.id == scanner.id)
                    .values(last_signal_at=datetime.utcnow())
                )
                await session.commit()

                # Notify via WebSocket if connected
                try:
                    from app.api.v1.ws import get_ws_manager
                    ws_manager = get_ws_manager()
                    await ws_manager.send_to_device(scanner.device_id, {
                        "type": "new_signal",
                        "signal": {
                            "id": new_signal.id,
                            "strategy_id": strategy.id,
                            "strategy_name": strategy.name,
                            "pair": pair,
                            "direction": direction,
                            "entry_price": entry_price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "reason": reason,
                            "triggered_at": new_signal.triggered_at.isoformat(),
                        }
                    })
                except Exception as ws_err:
                    logger.debug(f"WS notification skip: {ws_err}")

                # Send FCM notification
                if scanner.fcm_token:
                    await self.notifier.send_signal_notification(
                        fcm_token=scanner.fcm_token,
                        signal={
                            "pair": pair,
                            "direction": direction,
                            "entry_price": entry_price,
                            "stop_loss": sl,
                            "take_profit": tp,
                            "strategy_name": strategy.name,
                            "reason": reason,
                        }
                    )

                logger.info(f"Signal generated: {pair} {direction.upper()} @ {entry_price} (strategy: {strategy.name})")

        except Exception as e:
            logger.error(f"Error scanning strategy {scanner.strategy_id}: {e}", exc_info=True)


_scanner_instance: Optional[SignalScanner] = None


def get_scanner() -> SignalScanner:
    global _scanner_instance
    if _scanner_instance is None:
        _scanner_instance = SignalScanner()
    return _scanner_instance
