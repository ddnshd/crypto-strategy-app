import pandas as pd
import numpy as np
import ta
from typing import Any
import logging

logger = logging.getLogger(__name__)


def compute_indicators(df: pd.DataFrame, conditions: list[dict]) -> pd.DataFrame:
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
        indicator = cond.get("indicator", "").upper()
        params = cond.get("params", {})
        compare_to = cond.get("compare_to")

        # Also compute compare_to indicator if present
        if compare_to:
            _compute_single(df, compare_to.upper(), {}, close, high, low, volume)

        _compute_single(df, indicator, params, close, high, low, volume)

    return df


def _compute_single(df, indicator, params, close, high, low, volume):
    """Compute a single indicator and add to df."""
    try:
        if indicator == "RSI":
            period = params.get("period", 14)
            col = f"RSI_{period}"
            if col not in df.columns:
                df[col] = ta.momentum.RSIIndicator(close, window=period).rsi()

        elif indicator == "EMA":
            period = params.get("period", 20)
            col = f"EMA_{period}"
            if col not in df.columns:
                df[col] = ta.trend.EMAIndicator(close, window=period).ema_indicator()

        elif indicator == "SMA":
            period = params.get("period", 20)
            col = f"SMA_{period}"
            if col not in df.columns:
                df[col] = ta.trend.SMAIndicator(close, window=period).sma_indicator()

        elif indicator == "EMA_CROSS":
            fast = params.get("fast", 9)
            slow = params.get("slow", 21)
            fast_col = f"EMA_{fast}"
            slow_col = f"EMA_{slow}"
            if fast_col not in df.columns:
                df[fast_col] = ta.trend.EMAIndicator(close, window=fast).ema_indicator()
            if slow_col not in df.columns:
                df[slow_col] = ta.trend.EMAIndicator(close, window=slow).ema_indicator()

        elif indicator == "SMA_CROSS":
            fast = params.get("fast", 9)
            slow = params.get("slow", 21)
            fast_col = f"SMA_{fast}"
            slow_col = f"SMA_{slow}"
            if fast_col not in df.columns:
                df[fast_col] = ta.trend.SMAIndicator(close, window=fast).sma_indicator()
            if slow_col not in df.columns:
                df[slow_col] = ta.trend.SMAIndicator(close, window=slow).sma_indicator()

        elif indicator == "MACD":
            fast = params.get("fast", 12)
            slow = params.get("slow", 26)
            signal = params.get("signal", 9)
            macd = ta.trend.MACD(close, window_slow=slow, window_fast=fast, window_sign=signal)
            if "MACD_line" not in df.columns:
                df["MACD_line"] = macd.macd()
            if "MACD_signal" not in df.columns:
                df["MACD_signal"] = macd.macd_signal()
            if "MACD_hist" not in df.columns:
                df["MACD_hist"] = macd.macd_diff()

        elif indicator == "BBANDS":
            period = params.get("period", 20)
            std = params.get("std", 2)
            bb = ta.volatility.BollingerBands(close, window=period, window_dev=std)
            if f"BB_upper_{period}" not in df.columns:
                df[f"BB_upper_{period}"] = bb.bollinger_hband()
                df[f"BB_lower_{period}"] = bb.bollinger_lband()
                df[f"BB_mid_{period}"] = bb.bollinger_mavg()
                df[f"BB_width_{period}"] = bb.bollinger_wband()

        elif indicator == "ATR":
            period = params.get("period", 14)
            col = f"ATR_{period}"
            if col not in df.columns:
                df[col] = ta.volatility.AverageTrueRange(high, low, close, window=period).average_true_range()

        elif indicator == "STOCH":
            k_period = params.get("k", 14)
            d_period = params.get("d", 3)
            stoch = ta.momentum.StochasticOscillator(high, low, close, window=k_period, smooth_window=d_period)
            if "STOCH_k" not in df.columns:
                df["STOCH_k"] = stoch.stoch()
                df["STOCH_d"] = stoch.stoch_signal()

        elif indicator == "VOLUME_SMA":
            period = params.get("period", 20)
            col = f"VOLUME_SMA_{period}"
            if col not in df.columns:
                df[col] = volume.rolling(window=period).mean()

        elif indicator in ("PRICE", "CLOSE"):
            pass  # use df["close"] directly

        elif indicator == "VOLUME":
            pass  # use df["volume"] directly

    except Exception as e:
        logger.warning(f"Failed to compute indicator {indicator}: {e}")

    return df


def evaluate_condition(df: pd.DataFrame, cond: dict) -> pd.Series:
    """
    Evaluate a single condition and return boolean Series.
    """
    indicator = cond.get("indicator", "").upper()
    params = cond.get("params", {})
    operator = cond.get("operator", "")
    value = cond.get("value")
    compare_to = cond.get("compare_to")

    close = df["close"]

    # Get the left-hand side series
    lhs = _get_indicator_series(df, indicator, params)

    # Get the right-hand side (value or another series)
    if compare_to:
        rhs = _get_indicator_series(df, compare_to.upper(), {})
    else:
        rhs = value

    # Evaluate operator
    if operator in ("cross_above", "cross_below"):
        # For cross operators: default rhs to 0 if None (for EMA_CROSS etc.)
        if rhs is None:
            rhs_series = pd.Series(0.0, index=df.index)
        elif isinstance(rhs, (int, float)):
            rhs_series = pd.Series(rhs, index=df.index)
        elif isinstance(rhs, pd.Series):
            rhs_series = rhs
        else:
            rhs_series = pd.Series(0.0, index=df.index)
        if operator == "cross_above":
            prev_below = lhs.shift(1) <= rhs_series.shift(1)
            curr_above = lhs > rhs_series
            return prev_below & curr_above
        else:
            prev_above = lhs.shift(1) >= rhs_series.shift(1)
            curr_below = lhs < rhs_series
            return prev_above & curr_below
    elif operator == "<":
        return lhs < rhs
    elif operator == ">":
        return lhs > rhs
    elif operator == "<=":
        return lhs <= rhs
    elif operator == ">=":
        return lhs >= rhs
    elif operator == "==":
        return lhs == rhs
    else:
        logger.warning(f"Unknown operator '{operator}', returning all False")
        return pd.Series(False, index=df.index)


def _get_indicator_series(df: pd.DataFrame, indicator: str, params: dict) -> pd.Series:
    """Map indicator name to the correct DataFrame column."""
    if indicator in ("PRICE", "CLOSE"):
        return df["close"]
    elif indicator == "OPEN":
        return df["open"]
    elif indicator == "HIGH":
        return df["high"]
    elif indicator == "LOW":
        return df["low"]
    elif indicator == "VOLUME":
        return df["volume"]
    elif indicator == "RSI":
        period = params.get("period", 14)
        return df[f"RSI_{period}"]
    elif indicator == "EMA":
        period = params.get("period", 20)
        return df[f"EMA_{period}"]
    elif indicator == "SMA":
        period = params.get("period", 20)
        return df[f"SMA_{period}"]
    elif indicator == "EMA_CROSS":
        fast = params.get("fast", 9)
        slow = params.get("slow", 21)
        return df[f"EMA_{fast}"] - df[f"EMA_{slow}"]  # positive = fast above slow
    elif indicator == "SMA_CROSS":
        fast = params.get("fast", 9)
        slow = params.get("slow", 21)
        return df[f"SMA_{fast}"] - df[f"SMA_{slow}"]
    elif indicator == "MACD":
        return df["MACD_line"]
    elif indicator == "MACD_SIGNAL":
        return df["MACD_signal"]
    elif indicator == "MACD_HIST":
        return df["MACD_hist"]
    elif indicator == "STOCH_K":
        return df["STOCH_k"]
    elif indicator == "STOCH_D":
        return df["STOCH_d"]
    elif indicator == "ATR":
        period = params.get("period", 14)
        return df[f"ATR_{period}"]
    elif indicator.startswith("BB_UPPER"):
        period = params.get("period", 20)
        return df[f"BB_upper_{period}"]
    elif indicator.startswith("BB_LOWER"):
        period = params.get("period", 20)
        return df[f"BB_lower_{period}"]
    elif indicator.startswith("BB_MID"):
        period = params.get("period", 20)
        return df[f"BB_mid_{period}"]
    elif indicator == "VOLUME_SMA":
        period = params.get("period", 20)
        return df[f"VOLUME_SMA_{period}"]
    else:
        raise ValueError(f"Unknown indicator for series lookup: {indicator}")
