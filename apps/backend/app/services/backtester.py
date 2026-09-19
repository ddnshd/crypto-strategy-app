import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging
from app.services.data_fetcher import DataFetcher
from app.services.indicators import compute_indicators, evaluate_condition

logger = logging.getLogger(__name__)


def compute_strategy_score(
    win_rate: float,
    profit_factor: float,
    max_drawdown: float,
    total_trades: int,
    sharpe: float,
) -> float:
    """
    Score 0-100. Qualified if score >= 50.
    Weights: win_rate=30%, profit_factor=30%, drawdown=20%, trades=10%, sharpe=10%
    """
    score = 0.0

    # Win rate (30 pts, target >= 50%)
    wr_score = min(win_rate / 0.6, 1.0) * 30
    score += wr_score

    # Profit factor (30 pts, target >= 1.5)
    pf_score = min((profit_factor - 1.0) / 1.0, 1.0) * 30 if profit_factor > 1.0 else 0
    score += pf_score

    # Max drawdown (20 pts, target <= 15%)
    dd_score = max(0, 1.0 - max_drawdown / 0.20) * 20
    score += dd_score

    # Trade count (10 pts, target >= 30 trades)
    trades_score = min(total_trades / 30, 1.0) * 10
    score += trades_score

    # Sharpe (10 pts, target >= 1.0)
    if sharpe and not np.isnan(sharpe):
        sharpe_score = min(sharpe / 1.5, 1.0) * 10
        score += sharpe_score

    return round(score, 2)


class Backtester:
    def __init__(self):
        self.fetcher = DataFetcher()

    async def run(
        self,
        strategy_definition: dict,
        pair: str,
        timeframe: str,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 1000.0,
        enable_walk_forward: bool = True,
    ) -> dict:
        """
        Run backtest on strategy definition.
        Returns complete metrics dict.
        """
        # Default dates: 1 year back
        if not start_date:
            start_date = (datetime.utcnow() - timedelta(days=365)).strftime("%Y-%m-%d")
        if not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")

        # Fetch OHLCV
        try:
            df = await self.fetcher.fetch_ohlcv(
                pair=pair,
                timeframe=timeframe,
                start_date=start_date,
                end_date=end_date,
            )
        finally:
            await self.fetcher.close()

        if len(df) < 50:
            raise ValueError(f"Insufficient data: only {len(df)} bars for {pair} {timeframe}")

        # Run backtest on full data
        full_result = self._run_simulation(df, strategy_definition, initial_capital)

        walk_forward_result = None
        if enable_walk_forward and len(df) >= 100:
            # 80/20 split: in-sample vs out-of-sample
            split_idx = int(len(df) * 0.8)
            df_in = df.iloc[:split_idx]
            df_out = df.iloc[split_idx:]

            in_sample = self._run_simulation(df_in, strategy_definition, initial_capital)
            out_sample = self._run_simulation(df_out, strategy_definition, initial_capital)

            walk_forward_result = {
                "in_sample": {
                    "period": f"{df_in.index[0].date()} to {df_in.index[-1].date()}",
                    "win_rate": in_sample["win_rate"],
                    "profit_factor": in_sample["profit_factor"],
                    "total_return": in_sample["total_return"],
                    "total_trades": in_sample["total_trades"],
                },
                "out_of_sample": {
                    "period": f"{df_out.index[0].date()} to {df_out.index[-1].date()}",
                    "win_rate": out_sample["win_rate"],
                    "profit_factor": out_sample["profit_factor"],
                    "total_return": out_sample["total_return"],
                    "total_trades": out_sample["total_trades"],
                },
                "degradation_pct": round(
                    (in_sample["profit_factor"] - out_sample["profit_factor"]) / max(in_sample["profit_factor"], 0.01) * 100, 2
                ),
            }

        score = compute_strategy_score(
            win_rate=full_result["win_rate"],
            profit_factor=full_result["profit_factor"],
            max_drawdown=full_result["max_drawdown"],
            total_trades=full_result["total_trades"],
            sharpe=full_result.get("sharpe_ratio", 0),
        )
        is_qualified = score >= 50 and full_result["win_rate"] >= 0.40 and full_result["profit_factor"] >= 1.2

        return {
            **full_result,
            "pair": pair,
            "timeframe": timeframe,
            "start_date": start_date,
            "end_date": end_date,
            "score": score,
            "is_qualified": is_qualified,
            "walk_forward": walk_forward_result,
        }

    def _run_simulation(
        self,
        df: pd.DataFrame,
        strategy_def: dict,
        initial_capital: float,
    ) -> dict:
        """
        Event-driven simulation on OHLCV DataFrame.
        Returns metrics dict.
        """
        entry_conditions = strategy_def.get("entry_conditions", [])
        exit_def = strategy_def.get("exit_conditions", {})
        filters = strategy_def.get("filters", [])
        position_size_pct = strategy_def.get("position_size_pct", 1.0)

        tp_pct = exit_def.get("take_profit_pct")
        sl_pct = exit_def.get("stop_loss_pct")
        trailing_pct = exit_def.get("trailing_stop_pct")
        max_bars = exit_def.get("max_bars_held")
        exit_indicator_conds = exit_def.get("exit_conditions", [])

        # Compute indicators
        all_conditions = entry_conditions + (filters or []) + (exit_indicator_conds or [])
        df = compute_indicators(df, all_conditions)
        df = df.dropna()

        if len(df) < 20:
            return self._empty_result()

        # Generate entry signals
        entry_signal = pd.Series(True, index=df.index)
        for cond in entry_conditions:
            try:
                entry_signal = entry_signal & evaluate_condition(df, cond)
            except Exception as e:
                logger.warning(f"Entry condition eval failed: {e}")
                entry_signal = pd.Series(False, index=df.index)

        # Apply filters
        for cond in (filters or []):
            try:
                entry_signal = entry_signal & evaluate_condition(df, cond)
            except Exception as e:
                logger.warning(f"Filter eval failed: {e}")

        # Simulate trades
        capital = initial_capital
        trades = []
        equity_curve = [{"date": str(df.index[0].date()), "value": capital}]

        in_trade = False
        entry_price = 0.0
        entry_idx = 0
        trailing_high = 0.0
        bars_held = 0

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        signals = entry_signal.values

        for i in range(1, len(df)):
            current_close = closes[i]
            current_high = highs[i]
            current_low = lows[i]

            if not in_trade:
                # Check entry
                if signals[i - 1]:  # signal on previous bar, enter on current open
                    in_trade = True
                    entry_price = closes[i - 1]  # enter at previous close (realistic)
                    entry_idx = i
                    trailing_high = entry_price
                    bars_held = 0
            else:
                bars_held += 1
                trailing_high = max(trailing_high, current_high)
                exit_price = None
                exit_reason = ""

                # Check TP
                if tp_pct and current_high >= entry_price * (1 + tp_pct / 100):
                    exit_price = entry_price * (1 + tp_pct / 100)
                    exit_reason = "TP"

                # Check SL
                elif sl_pct and current_low <= entry_price * (1 - sl_pct / 100):
                    exit_price = entry_price * (1 - sl_pct / 100)
                    exit_reason = "SL"

                # Check trailing stop
                elif trailing_pct and current_low <= trailing_high * (1 - trailing_pct / 100):
                    exit_price = trailing_high * (1 - trailing_pct / 100)
                    exit_reason = "TrailingStop"

                # Check max bars
                elif max_bars and bars_held >= max_bars:
                    exit_price = current_close
                    exit_reason = "MaxBars"

                # Check indicator-based exit
                elif exit_indicator_conds:
                    exit_triggered = True
                    for cond in exit_indicator_conds:
                        try:
                            cond_result = evaluate_condition(df.iloc[i:i+1], cond)
                            if not cond_result.iloc[0]:
                                exit_triggered = False
                                break
                        except Exception:
                            exit_triggered = False
                            break
                    if exit_triggered:
                        exit_price = current_close
                        exit_reason = "Signal"

                if exit_price is not None:
                    position_capital = capital * (position_size_pct / 100)
                    pnl_pct = (exit_price - entry_price) / entry_price
                    pnl_usd = position_capital * pnl_pct
                    capital += pnl_usd

                    trades.append({
                        "trade_num": len(trades) + 1,
                        "entry_date": str(df.index[entry_idx].date()),
                        "exit_date": str(df.index[i].date()),
                        "direction": "long",
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exit_price, 6),
                        "pnl_pct": round(pnl_pct * 100, 4),
                        "pnl_usd": round(pnl_usd, 4),
                        "is_win": pnl_pct > 0,
                        "exit_reason": exit_reason,
                    })

                    equity_curve.append({"date": str(df.index[i].date()), "value": round(capital, 4)})
                    in_trade = False

        if not trades:
            return self._empty_result()

        # Calculate metrics
        wins = [t for t in trades if t["is_win"]]
        losses = [t for t in trades if not t["is_win"]]

        win_rate = len(wins) / len(trades)
        gross_profit = sum(t["pnl_usd"] for t in wins) if wins else 0
        gross_loss = abs(sum(t["pnl_usd"] for t in losses)) if losses else 0.001
        profit_factor = gross_profit / gross_loss

        equity_values = [e["value"] for e in equity_curve]
        peak = initial_capital
        max_dd = 0.0
        for v in equity_values:
            if v > peak:
                peak = v
            dd = (peak - v) / peak
            max_dd = max(max_dd, dd)

        total_return = (capital - initial_capital) / initial_capital
        daily_returns = []
        for j in range(1, len(equity_values)):
            r = (equity_values[j] - equity_values[j - 1]) / equity_values[j - 1]
            daily_returns.append(r)

        sharpe = 0.0
        if daily_returns:
            arr = np.array(daily_returns)
            if arr.std() > 0:
                sharpe = float((arr.mean() / arr.std()) * np.sqrt(252))

        avg_rr = 0.0
        if wins and losses:
            avg_win = np.mean([t["pnl_pct"] for t in wins])
            avg_loss = abs(np.mean([t["pnl_pct"] for t in losses]))
            avg_rr = avg_win / avg_loss if avg_loss > 0 else 0

        return {
            "win_rate": round(win_rate, 4),
            "profit_factor": round(profit_factor, 4),
            "max_drawdown": round(max_dd, 4),
            "total_return": round(total_return, 4),
            "sharpe_ratio": round(sharpe, 4),
            "avg_rr": round(avg_rr, 4),
            "total_trades": len(trades),
            "winning_trades": len(wins),
            "losing_trades": len(losses),
            "equity_curve": equity_curve[-500:],   # limit to 500 points for response size
            "trade_log": trades,
        }

    def _empty_result(self) -> dict:
        return {
            "win_rate": 0.0,
            "profit_factor": 0.0,
            "max_drawdown": 0.0,
            "total_return": 0.0,
            "sharpe_ratio": 0.0,
            "avg_rr": 0.0,
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "equity_curve": [],
            "trade_log": [],
        }
