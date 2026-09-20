import re
import logging
from typing import Any
import numpy as np
import pandas as pd
import ta

logger = logging.getLogger(__name__)


def _extract_period(indicator: str, params: dict, default: int = 14) -> int:
    """Extract numeric period from params or from indicator name (e.g. EMA_200 -> 200)."""
    if params and "period" in params and isinstance(params["period"], (int, float)):
        return int(params["period"])
    m = re.search(r"(\d+)$", indicator)
    if m:
        try:
            return int(m.group(1))
        except (ValueError, TypeError):
            pass
    return default


def compute_indicators(df: pd.DataFrame, conditions: list) -> pd.DataFrame:
    """
    Compute all required indicators from strategy conditions and add to df.
    Returns augmented DataFrame.
    """
    df = df.copy()
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    for cond in conditions:
        if not isinstance(cond, dict):
            continue
        indicator = cond.get("indicator", "")
        params = cond.get("params", {}) or {}
        compare_to = cond.get("compare_to")

        # Also compute compare_to indicator if present
        if compare_to and isinstance(compare_to, str):
            _compute_single(df, compare_to.upper(), params, close, high, low, volume)

        if indicator and isinstance(indicator, str):
            _compute_single(df, indicator.upper(), params, close, high, low, volume)

    return df


def _compute_single(df: pd.DataFrame, indicator: str, params: dict, close, high, low, volume):
    """Compute a single indicator and add to df."""
    if not indicator:
        return
    params = params or {}
    try:
        # Cross indicators (MUST be checked before EMA/SMA)
        if indicator in ("EMA_CROSS", "EMA_CROSSING"):
            fast = params.get("fast", 9)
            slow = params.get("slow", 21)
            fast_col = f"EMA_{fast}"
            slow_col = f"EMA_{slow}"
            if fast_col not in df.columns:
                df[fast_col] = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
            if slow_col not in df.columns:
                df[slow_col] = ta.trend.EMAIndicator(close, window=slow).ema_indicator()
            return

        if indicator in ("SMA_CROSS", "SMA_CROSSING"):
            fast = params.get("fast", 9)
            slow = params.get("slow", 21)
            fast_col = f"SMA_{fast}"
            slow_col = f"SMA_{slow}"
            if fast_col not in df.columns:
                df[fast_col] = ta.trend.SMAIndicator(close, window=fast).sma_indicator()
            if slow_col not in df.columns:
                df[slow_col] = ta.trend.SMAIndicator(close, window=slow).sma_indicator()
            return

        # Bollinger Bands
        if indicator in ("BBANDS", "BOLLINGER", "BOLLINGER_BANDS", "BB") or indicator.startswith("BB_") or indicator.startswith("BBANDS_") or indicator.startswith("BOLLINGER_"):
            period = _extract_period(indicator, params, default=20)
            std = params.get("std", 2)
            if f"BB_upper_{period}" not in df.columns:
                bb = ta.volatility.BollingerBands(close, window=period, window_dev=std)
                df[f"BB_upper_{period}"] = bb.bollinger_hband()
                df[f"BB_lower_{period}"] = bb.bollinger_lband()
                df[f"BB_mid_{period}"] = bb.bollinger_mavg()
                df[f"BB_width_{period}"] = bb.bollinger_wband()
            return

        # RSI
        if indicator in ("RSI",) or indicator.startswith("RSI_"):
            period = _extract_period(indicator, params, default=14)
            col = f"RSI_{period}"
            if col not in df.columns:
                df[col] = ta.momentum.RSIIndicator(close, window=period).rsi()
            return

        # MACD
        if indicator in ("MACD", "MACD_LINE", "MACD_SIGNAL", "MACD_HIST", "MACD_DIFF", "MACD_HISTOGRAM"):
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal = params.get("signal", 9)
            if "MACD_line" not in df.columns:
                macd = ta.trend.MACD(close, window_slow=slow, window_fast=fast, window_sign=signal)
                df["MACD_line"] = macd.macd()
                df["MACD_signal"] = macd.macd_signal()
                df["MACD_hist"] = macd.macd_diff()
            return

        # Stochastic
        if indicator in ("STOCH", "STOCHASTIC", "STOCH_K", "STOCH_D"):
            k_period = params.get("k", 14)
            d_period = params.get("d", 3)
            if "STOCH_k" not in df.columns:
                stoch = ta.momentum.StochasticOscillator(high, low, close, window=k_period, smooth_window=d_period)
                df["STOCH_k"] = stoch.stoch()
                df["STOCH_d"] = stoch.stoch_signal()
            return

        # Volume Moving Average
        if indicator in ("VOLUME_SMA", "VOL_SMA", "VOLUME_MA", "VOL_MA") or indicator.startswith("VOLUME_SMA_") or indicator.startswith("VOL_SMA_"):
            period = _extract_period(indicator, params, default=20)
            col = f"VOLUME_SMA_{period}"
            if col not in df.columns:
                df[col] = volume.rolling(window=period).mean()
            return

        # ATR
        if indicator in ("ATR",) or indicator.startswith("ATR_"):
            period = _extract_period(indicator, params, default=14)
            col = f"ATR_{period}"
            if col not in df.columns:
                df[col] = ta.volatility.AverageTrueRange(high, low, close, window=period).average_true_range()
            return

        # EMA
        if indicator == "EMA" or (indicator.startswith("EMA_") and indicator[4:].isdigit()) or (indicator.startswith("EMA") and indicator[3:].isdigit()):
            period = _extract_period(indicator, params, default=20)
            col = f"EMA_{period}"
            if col not in df.columns:
                df[col] = ta.trend.EMAIndicator(close, window=period).ema_indicator()
            return

        # SMA
        if indicator == "SMA" or (indicator.startswith("SMA_") and indicator[4:].isdigit()) or (indicator.startswith("SMA") and indicator[3:].isdigit()):
            period = _extract_period(indicator, params, default=20)
            col = f"SMA_{period}"
            if col not in df.columns:
                df[col] = ta.trend.SMAIndicator(close, window=period).sma_indicator()
            return

        # Simple price/volume fields
        if indicator in ("PRICE", "CLOSE", "OPEN", "HIGH", "LOW", "VOLUME", "VOL"):
            return

    except Exception as e:
        logger.warning(f"Failed to compute indicator {indicator}: {e}")


def evaluate_condition(df: pd.DataFrame, cond: dict) -> pd.Series:
    """
    Evaluate a single condition and return boolean Series.
    Always safe: never throws exception, returns boolean series.
    """
    if not isinstance(cond, dict):
        return pd.Series(True, index=df.index)

    indicator = cond.get("indicator", "")
    if not indicator or not isinstance(indicator, str):
        return pd.Series(True, index=df.index)

    params = cond.get("params", {}) or {}
    operator = cond.get("operator", "")
    value = cond.get("value")
    compare_to = cond.get("compare_to")

    try:
        # Get LHS
        lhs = _get_indicator_series(df, indicator.upper(), params, operator=operator, is_rhs=False)

        # Get RHS
        if compare_to and isinstance(compare_to, str):
            rhs = _get_indicator_series(df, compare_to.upper(), params, operator=operator, is_rhs=True)
        else:
            rhs = value

        # Evaluate cross operators
        if operator in ("cross_above", "cross_below"):
            if rhs is None:
                rhs_series = pd.Series(0.0, index=df.index)
            elif isinstance(rhs, (int, float)):
                rhs_series = pd.Series(float(rhs), index=df.index)
            elif isinstance(rhs, pd.Series):
                rhs_series = rhs
            else:
                rhs_series = pd.Series(0.0, index=df.index)

            if operator == "cross_above":
                prev_below = lhs.shift(1) <= rhs_series.shift(1)
                curr_above = lhs > rhs_series
                return (prev_below & curr_above).fillna(False)
            else:
                prev_above = lhs.shift(1) >= rhs_series.shift(1)
                curr_below = lhs < rhs_series
                return (prev_above & curr_below).fillna(False)

        # For comparison operators, if rhs is None, default to 0.0
        if rhs is None:
            rhs = 0.0

        if operator == "<":
            return (lhs < rhs).fillna(False)
        elif operator == ">":
            return (lhs > rhs).fillna(False)
        elif operator == "<=":
            return (lhs <= rhs).fillna(False)
        elif operator == ">=":
            return (lhs >= rhs).fillna(False)
        elif operator == "==":
            return (lhs == rhs).fillna(False)
        else:
            logger.warning(f"Unknown operator '{operator}', returning all False")
            return pd.Series(False, index=df.index)

    except Exception as e:
        logger.warning(f"Error evaluating condition {cond}: {e}")
        return pd.Series(True, index=df.index)


def _get_indicator_series(df: pd.DataFrame, indicator: str, params: dict, operator: str = "", is_rhs: bool = False) -> pd.Series:
    """Map indicator name to the correct DataFrame column. Computes on-the-fly if missing."""
    indicator = (indicator or "").upper().strip()
    params = params or {}
    close = df["close"]
    high = df["high"]
    low = df["low"]
    volume = df["volume"]

    # Basic price/volume
    if indicator in ("PRICE", "CLOSE", "C"):
        return close
    elif indicator in ("OPEN", "O"):
        return df["open"]
    elif indicator in ("HIGH", "H"):
        return high
    elif indicator in ("LOW", "L"):
        return low
    elif indicator in ("VOLUME", "VOL", "V"):
        return volume

    # Cross indicators (MUST be checked before EMA/SMA)
    elif indicator in ("EMA_CROSS", "EMA_CROSSING"):
        fast = params.get("fast", 9)
        slow = params.get("slow", 21)
        fast_col = f"EMA_{fast}"
        slow_col = f"EMA_{slow}"
        if fast_col not in df.columns:
            df[fast_col] = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
        if slow_col not in df.columns:
            df[slow_col] = ta.trend.EMAIndicator(close, window=slow).ema_indicator()
        return df[fast_col] - df[slow_col]

    elif indicator in ("SMA_CROSS", "SMA_CROSSING"):
        fast = params.get("fast", 9)
        slow = params.get("slow", 21)
        fast_col = f"SMA_{fast}"
        slow_col = f"SMA_{slow}"
        if fast_col not in df.columns:
            df[fast_col] = ta.trend.SMAIndicator(close, window=fast).sma_indicator()
        if slow_col not in df.columns:
            df[slow_col] = ta.trend.SMAIndicator(close, window=slow).sma_indicator()
        return df[fast_col] - df[slow_col]

    # Bollinger Bands
    elif indicator in ("BBANDS", "BOLLINGER", "BOLLINGER_BANDS", "BB") or indicator.startswith("BB_") or indicator.startswith("BBANDS_") or indicator.startswith("BOLLINGER_"):
        period = _extract_period(indicator, params, default=20)
        std = params.get("std", 2)
        if f"BB_upper_{period}" not in df.columns:
            bb = ta.volatility.BollingerBands(close, window=period, window_dev=std)
            df[f"BB_upper_{period}"] = bb.bollinger_hband()
            df[f"BB_lower_{period}"] = bb.bollinger_lband()
            df[f"BB_mid_{period}"] = bb.bollinger_mavg()
            df[f"BB_width_{period}"] = bb.bollinger_wband()

        if "UPPER" in indicator or "TOP" in indicator:
            return df[f"BB_upper_{period}"]
        elif "LOWER" in indicator or "BOTTOM" in indicator:
            return df[f"BB_lower_{period}"]
        elif "MID" in indicator or "MIDDLE" in indicator:
            return df[f"BB_mid_{period}"]
        elif "WIDTH" in indicator:
            return df[f"BB_width_{period}"]
        else:
            # Generic BBANDS: pick band based on operator
            if operator in (">", ">=", "cross_above"):
                return df[f"BB_upper_{period}"]
            elif operator in ("<", "<=", "cross_below"):
                return df[f"BB_lower_{period}"]
            else:
                return df[f"BB_mid_{period}"]

    # RSI
    elif indicator in ("RSI",) or indicator.startswith("RSI_"):
        period = _extract_period(indicator, params, default=14)
        col = f"RSI_{period}"
        if col not in df.columns:
            df[col] = ta.momentum.RSIIndicator(close, window=period).rsi()
        return df[col]

    # MACD
    elif indicator in ("MACD", "MACD_LINE"):
        if "MACD_line" not in df.columns:
            _compute_single(df, "MACD", params, close, high, low, volume)
        return df["MACD_line"]
    elif indicator in ("MACD_SIGNAL",):
        if "MACD_signal" not in df.columns:
            _compute_single(df, "MACD", params, close, high, low, volume)
        return df["MACD_signal"]
    elif indicator in ("MACD_HIST", "MACD_HISTOGRAM", "MACD_DIFF"):
        if "MACD_hist" not in df.columns:
            _compute_single(df, "MACD", params, close, high, low, volume)
        return df["MACD_hist"]

    # Stochastic
    elif indicator in ("STOCH", "STOCHASTIC", "STOCH_K"):
        if "STOCH_k" not in df.columns:
            _compute_single(df, "STOCH", params, close, high, low, volume)
        return df["STOCH_k"]
    elif indicator in ("STOCH_D",):
        if "STOCH_d" not in df.columns:
            _compute_single(df, "STOCH", params, close, high, low, volume)
        return df["STOCH_d"]

    # Volume Moving Average
    elif indicator in ("VOLUME_SMA", "VOL_SMA", "VOLUME_MA", "VOL_MA") or indicator.startswith("VOLUME_SMA_") or indicator.startswith("VOL_SMA_"):
        period = _extract_period(indicator, params, default=20)
        col = f"VOLUME_SMA_{period}"
        if col not in df.columns:
            df[col] = volume.rolling(window=period).mean()
        return df[col]

    # ATR
    elif indicator in ("ATR",) or indicator.startswith("ATR_"):
        period = _extract_period(indicator, params, default=14)
        col = f"ATR_{period}"
        if col not in df.columns:
            df[col] = ta.volatility.AverageTrueRange(high, low, close, window=period).average_true_range()
        return df[col]

    # EMA
    elif indicator == "EMA" or (indicator.startswith("EMA_") and indicator[4:].isdigit()) or (indicator.startswith("EMA") and indicator[3:].isdigit()):
        period = _extract_period(indicator, params, default=20)
        col = f"EMA_{period}"
        if col not in df.columns:
            df[col] = ta.trend.EMAIndicator(close, window=period).ema_indicator()
        return df[col]

    # SMA
    elif indicator == "SMA" or (indicator.startswith("SMA_") and indicator[4:].isdigit()) or (indicator.startswith("SMA") and indicator[3:].isdigit()):
        period = _extract_period(indicator, params, default=20)
        col = f"SMA_{period}"
        if col not in df.columns:
            df[col] = ta.trend.SMAIndicator(close, window=period).sma_indicator()
        return df[col]

    else:
        # Check direct column in df
        if indicator in df.columns:
            return df[indicator]
        logger.warning(f"Unknown indicator '{indicator}', fallback to close")
        return close
