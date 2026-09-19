import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional
import logging
from app.services.data_fetcher import DataFetcher
from app.services.indicators import compute_indicators, evaluate_condition

logger = logging.getLogger(__name__)

# Binance spot taker fee = 0.1% per side
DEFAULT_COMMISSION_PCT = 0.1
DEFAULT_SLIPPAGE_PCT = 0.02


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

    wr_score = min(win_rate / 0.6, 1.0) * 30
    score += wr_score

    pf_score = min((profit_factor - 1.0) / 1.0, 1.0) * 30 if profit_factor > 1.0 else 0
    score += pf_score

    dd_score = max(0, 1.0 - max_drawdown / 0.20) * 20
    score += dd_score

    trades_score = min(total_trades / 30, 1.0) * 10
    score += trades_score

    if sharpe and not np.isnan(sharpe):
        sharpe_score = max(0, min(sharpe / 1.5, 1.0)) * 10
        score += sharpe_score

    return round(score, 2)


def _annualization_factor(timeframe: str) -> float:
    """Return sqrt(N) where N = number of bars per year for a given timeframe."""
    tf_minutes = {
        "1m": 1, "3m": 3, "5m": 5, "15m": 15, "30m": 30,
        "1h": 60, "2h": 120, "4h": 240, "6h": 360, "8h": 480,
        "12h": 720, "1d": 1440, "3d": 4320, "1w": 10080,
    }
    minutes = tf_minutes.get(timeframe, 60)
    bars_per_year = (365 * 24 * 60) / minutes
    return np.sqrt(bars_per_year)


class Backtester:
    def __init__(self):
        self.fetcher = DataFetcher()

    async def run(
        self,
        strategy_definition: dict,
        pair: str,
        timeframe: str,
        period: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        initial_capital: float = 1000.0,
        enable_walk_forward: bool = True,
        commission_pct: float = DEFAULT_COMMISSION_PCT,
        slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    ) -> dict:
        PERIOD_DAYS = {"1m": 30, "3m": 90, "6m": 180, "1y": 365, "2y": 730}
        if not start_date and not end_date:
            days = PERIOD_DAYS.get(period or "1y", 365)
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
            end_date = datetime.utcnow().strftime("%Y-%m-%d")
        elif not start_date:
            days = PERIOD_DAYS.get(period or "1y", 365)
            start_date = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
        elif not end_date:
            end_date = datetime.utcnow().strftime("%Y-%m-%d")

        try:
            df = await self.fetcher.fetch_ohlcv(
                pair=pair, timeframe=timeframe,
                start_date=start_date, end_date=end_date,
            )
        finally:
            await self.fetcher.close()

        if len(df) < 50:
            raise ValueError(f"Data tidak cukup: hanya {len(df)} bar untuk {pair} {timeframe} (minimal 50)")

        full_result = self._run_simulation(
            df, strategy_definition, initial_capital,
            timeframe, commission_pct, slippage_pct,
        )

        walk_forward_result = None
        if enable_walk_forward and len(df) >= 200:
            walk_forward_result = self._walk_forward(
                df, strategy_definition, initial_capital,
                timeframe, commission_pct, slippage_pct,
            )

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

    def _walk_forward(self, df, strategy_def, capital, timeframe, commission, slippage):
        """Rolling walk-forward with 5 folds."""
        n = len(df)
        fold_size = n // 5
        folds = []
        for i in range(5):
            start = i * fold_size
            end = min(start + fold_size, n)
            if end - start < 30:
                continue
            chunk = df.iloc[start:end]
            res = self._run_simulation(chunk, strategy_def, capital, timeframe, commission, slippage)
            folds.append({
                "period": f"{chunk.index[0].date()} to {chunk.index[-1].date()}",
                "win_rate": res["win_rate"],
                "profit_factor": res["profit_factor"],
                "total_return": res["total_return"],
                "total_trades": res["total_trades"],
                "score": compute_strategy_score(
                    res["win_rate"], res["profit_factor"],
                    res["max_drawdown"], res["total_trades"],
                    res.get("sharpe_ratio", 0),
                ),
            })

        if len(folds) < 2:
            return None

        # Out-of-sample = last 2 folds, in-sample = first 3
        split = max(1, len(folds) - 2)
        in_folds = folds[:split]
        out_folds = folds[split:]

        in_pf = np.mean([f["profit_factor"] for f in in_folds]) if in_folds else 0
        out_pf = np.mean([f["profit_factor"] for f in out_folds]) if out_folds else 0
        degradation = round((in_pf - out_pf) / max(in_pf, 0.01) * 100, 2)

        in_wr = np.mean([f["win_rate"] for f in in_folds]) if in_folds else 0
        out_wr = np.mean([f["win_rate"] for f in out_folds]) if out_folds else 0
        in_ret = np.mean([f["total_return"] for f in in_folds]) if in_folds else 0
        out_ret = np.mean([f["total_return"] for f in out_folds]) if out_folds else 0
        in_trades = sum(f["total_trades"] for f in in_folds)
        out_trades = sum(f["total_trades"] for f in out_folds)
        in_score = np.mean([f["score"] for f in in_folds]) if in_folds else 0
        out_score = np.mean([f["score"] for f in out_folds]) if out_folds else 0

        return {
            "folds": folds,
            "in_sample": {
                "period": f"{in_folds[0]['period'].split(' to ')[0]} to {in_folds[-1]['period'].split(' to ')[-1]}",
                "win_rate": round(in_wr, 4),
                "profit_factor": round(in_pf, 4),
                "total_return": round(in_ret, 4),
                "total_trades": in_trades,
                "avg_score": round(in_score, 2),
            },
            "out_of_sample": {
                "period": f"{out_folds[0]['period'].split(' to ')[0]} to {out_folds[-1]['period'].split(' to ')[-1]}",
                "win_rate": round(out_wr, 4),
                "profit_factor": round(out_pf, 4),
                "total_return": round(out_ret, 4),
                "total_trades": out_trades,
                "avg_score": round(out_score, 2),
            },
            "degradation_pct": degradation,
            "consistency": round(out_wr, 4) if out_folds else 0,
        }

    def _run_simulation(
        self,
        df: pd.DataFrame,
        strategy_def: dict,
        initial_capital: float,
        timeframe: str = "1h",
        commission_pct: float = DEFAULT_COMMISSION_PCT,
        slippage_pct: float = DEFAULT_SLIPPAGE_PCT,
    ) -> dict:
        entry_conditions = strategy_def.get("entry_conditions", [])
        exit_def = strategy_def.get("exit_conditions", {})
        filters = strategy_def.get("filters", [])
        position_size_pct = strategy_def.get("position_size_pct", 1.0)

        tp_pct = exit_def.get("take_profit_pct")
        sl_pct = exit_def.get("stop_loss_pct")
        trailing_pct = exit_def.get("trailing_stop_pct")
        max_bars = exit_def.get("max_bars_held")
        exit_indicator_conds = exit_def.get("exit_conditions", [])

        # Detect short from definition: if short_conditions exist or style is short
        is_short = strategy_def.get("direction") == "short"
        if not is_short:
            # Heuristic: if entry condition says RSI > 70 or similar overbought, treat as short
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

        all_conditions = [c for c in entry_conditions if isinstance(c, dict)] + \
                         [c for c in (filters or []) if isinstance(c, dict)] + \
                         [c for c in (exit_indicator_conds or []) if isinstance(c, dict)]
        df = compute_indicators(df, all_conditions)
        df = df.dropna()

        if len(df) < 20:
            return self._empty_result("Data terlalu sedikit setelah compute indikator")

        # Generate entry signals
        entry_signal = pd.Series(True, index=df.index)
        for cond in entry_conditions:
            try:
                entry_signal = entry_signal & evaluate_condition(df, cond)
            except Exception as e:
                logger.warning(f"Entry condition eval failed: {e}")
                entry_signal = pd.Series(False, index=df.index)

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
        trailing_extreme = 0.0
        bars_held = 0

        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        opens = df["open"].values
        signals = entry_signal.values

        for i in range(1, len(df)):
            current_open = opens[i]
            current_close = closes[i]
            current_high = highs[i]
            current_low = lows[i]

            if not in_trade:
                if signals[i - 1]:
                    in_trade = True
                    # FIX: enter at current bar open + slippage (realistic)
                    slip = current_open * (slippage_pct / 100)
                    entry_price = current_open + slip if not is_short else current_open - slip
                    entry_idx = i
                    trailing_extreme = entry_price
                    bars_held = 0
            else:
                bars_held += 1
                if is_short:
                    trailing_extreme = min(trailing_extreme, current_low)
                else:
                    trailing_extreme = max(trailing_extreme, current_high)

                exit_price = None
                exit_reason = ""

                if is_short:
                    # Short: TP when price drops, SL when price rises
                    if tp_pct and current_low <= entry_price * (1 - tp_pct / 100):
                        exit_price = entry_price * (1 - tp_pct / 100) - current_open * (slippage_pct / 100)
                        exit_reason = "TP"
                    elif sl_pct and current_high >= entry_price * (1 + sl_pct / 100):
                        exit_price = entry_price * (1 + sl_pct / 100) + current_open * (slippage_pct / 100)
                        exit_reason = "SL"
                    elif trailing_pct and current_high >= trailing_extreme * (1 + trailing_pct / 100):
                        exit_price = trailing_extreme * (1 + trailing_pct / 100) + current_open * (slippage_pct / 100)
                        exit_reason = "TrailingStop"
                else:
                    # Long: TP when price rises, SL when price drops
                    if tp_pct and current_high >= entry_price * (1 + tp_pct / 100):
                        exit_price = entry_price * (1 + tp_pct / 100) - current_open * (slippage_pct / 100)
                        exit_reason = "TP"
                    elif sl_pct and current_low <= entry_price * (1 - sl_pct / 100):
                        exit_price = entry_price * (1 - sl_pct / 100) + current_open * (slippage_pct / 100)
                        exit_reason = "SL"
                    elif trailing_pct and current_low <= trailing_extreme * (1 - trailing_pct / 100):
                        exit_price = trailing_extreme * (1 - trailing_pct / 100) + current_open * (slippage_pct / 100)
                        exit_reason = "TrailingStop"

                if not exit_price and max_bars and bars_held >= max_bars:
                    exit_price = current_close
                    exit_reason = "MaxBars"

                if not exit_price and exit_indicator_conds:
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

                    # Commission: entry + exit
                    commission_cost = position_capital * (commission_pct / 100) * 2

                    if is_short:
                        pnl_pct = (entry_price - exit_price) / entry_price
                    else:
                        pnl_pct = (exit_price - entry_price) / entry_price

                    pnl_usd = position_capital * pnl_pct - commission_cost
                    capital += pnl_usd

                    trades.append({
                        "trade_num": len(trades) + 1,
                        "entry_date": str(df.index[entry_idx].date()),
                        "exit_date": str(df.index[i].date()),
                        "direction": "short" if is_short else "long",
                        "entry_price": round(entry_price, 6),
                        "exit_price": round(exit_price, 6),
                        "pnl_pct": round(pnl_pct * 100, 4),
                        "pnl_usd": round(pnl_usd, 4),
                        "commission": round(commission_cost, 4),
                        "is_win": pnl_pct > 0,
                        "exit_reason": exit_reason,
                    })

                    equity_curve.append({"date": str(df.index[i].date()), "value": round(capital, 4)})
                    in_trade = False

        if not trades:
            return self._empty_result("Tidak ada trade yang terbentuk dari kondisi entry/exit")

        # Metrics
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
            dd = (peak - v) / peak if peak > 0 else 0
            max_dd = max(max_dd, dd)

        total_return = (capital - initial_capital) / initial_capital

        # Sharpe: use actual returns between equity points, annualized by timeframe
        daily_returns = []
        for j in range(1, len(equity_values)):
            prev = equity_values[j - 1]
            if prev > 0:
                r = (equity_values[j] - prev) / prev
                daily_returns.append(r)

        ann_factor = _annualization_factor(timeframe)
        sharpe = 0.0
        if daily_returns and len(daily_returns) > 1:
            arr = np.array(daily_returns)
            std = arr.std(ddof=1)  # sample std
            if std > 0:
                sharpe = float((arr.mean() / std) * ann_factor)

        avg_rr = 0.0
        if wins and losses:
            avg_win = np.mean([t["pnl_pct"] for t in wins])
            avg_loss = abs(np.mean([t["pnl_pct"] for t in losses]))
            avg_rr = avg_win / avg_loss if avg_loss > 0 else 0

        total_commission = sum(t.get("commission", 0) for t in trades)

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
            "total_commission": round(total_commission, 4),
            "direction": "short" if is_short else "long",
            "equity_curve": equity_curve,
            "trade_log": trades,
        }

    def _empty_result(self, reason: str = "") -> dict:
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
            "total_commission": 0.0,
            "direction": "long",
            "equity_curve": [],
            "trade_log": [],
            "error": reason,
        }
