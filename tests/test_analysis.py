"""
Unit tests for analysis.py — the detectors that drive the brief's quality.
Synthetic OHLCV is constructed so each detector has a single, unambiguous case.
"""
import numpy as np
import pandas as pd
import pytest

from analysis import (
    calc_ema,
    calc_rsi,
    detect_swing_points,
    detect_market_structure,
    detect_order_blocks,
    detect_fvg,
    detect_liquidity_pools,
    determine_trend_bias,
)


def _flat_ohlcv(n: int = 60, start: float = 100.0, step: float = 0.0) -> pd.DataFrame:
    """Build a flat or linearly drifting OHLCV with low/high spread of ±1."""
    base = np.linspace(start, start + step * (n - 1), n)
    return pd.DataFrame(
        {
            "open": base,
            "high": base + 1,
            "low": base - 1,
            "close": base,
            "volume": np.ones(n),
        },
        index=pd.date_range("2026-01-01", periods=n, freq="4h"),
    )


def test_calc_ema_converges_to_constant():
    s = pd.Series([100.0] * 50)
    ema = calc_ema(s, 21)
    assert abs(ema.iloc[-1] - 100.0) < 1e-9


def test_calc_rsi_extremes():
    # Always-rising → RSI should approach 100
    rising = pd.Series(np.linspace(100, 200, 50))
    assert calc_rsi(rising, 14).iloc[-1] > 90

    # Always-falling → RSI should approach 0
    falling = pd.Series(np.linspace(200, 100, 50))
    assert calc_rsi(falling, 14).iloc[-1] < 10


def test_detect_swing_points_finds_injected_peaks():
    df = _flat_ohlcv(n=40)
    df.iloc[15, df.columns.get_loc("high")] = 120  # swing high
    df.iloc[25, df.columns.get_loc("low")] = 80    # swing low
    highs, lows = detect_swing_points(df, lookback=3)
    assert any(sh["index"] == 15 and sh["price"] == 120 for sh in highs)
    assert any(sl["index"] == 25 and sl["price"] == 80 for sl in lows)


def test_detect_market_structure_uptrend():
    # Construct a clear uptrend with HH+HL: ramp up with two swing pairs.
    n = 60
    df = _flat_ohlcv(n=n, step=0.5)
    # Inject swings: low @ 10, high @ 20, low @ 30, high @ 40
    df.iloc[10, df.columns.get_loc("low")] = 90
    df.iloc[20, df.columns.get_loc("high")] = 115
    df.iloc[30, df.columns.get_loc("low")] = 100
    df.iloc[40, df.columns.get_loc("high")] = 130
    # Final close above last swing high → BOS bullish
    df.iloc[-1, df.columns.get_loc("close")] = 135
    res = detect_market_structure(df, lookback=3)
    assert "Uptrend" in res["structure"] or res["trend"] == "Bullish"


def test_detect_order_blocks_returns_dict():
    df = _flat_ohlcv(n=80, step=0.0)
    # Strong bearish candle followed by strong bullish move → bullish OB candidate.
    idx_open = df.columns.get_loc("open")
    idx_close = df.columns.get_loc("close")
    df.iloc[60, idx_open] = 110
    df.iloc[60, idx_close] = 100
    df.iloc[61, idx_open] = 100
    df.iloc[61, idx_close] = 130  # strong bullish
    res = detect_order_blocks(df)
    assert "bullish_ob" in res and "bearish_ob" in res


def _overlapping_ohlcv(n: int = 30, base_price: float = 100.0) -> pd.DataFrame:
    """
    Sideways series where each candle overlaps with neighbors → NO accidental
    FVGs anywhere. Used as a clean canvas for injecting exactly one gap.
    """
    base = np.full(n, base_price)
    return pd.DataFrame(
        {
            "open": base,
            "high": base + 0.5,
            "low": base - 0.5,
            "close": base,
            "volume": np.ones(n),
        },
        index=pd.date_range("2026-01-01", periods=n, freq="4h"),
    )


def _inject_bullish_fvg(df: pd.DataFrame, i: int) -> tuple:
    """
    Inject an isolated bullish FVG at index i (impulse candle).
    Returns (gap_low, gap_high) of the resulting FVG.
    Pattern: candle[i-1] flat at base, impulse[i] gaps up, candle[i+1] sits
    fully above candle[i-1].high. After idx i+1 we keep the price elevated
    so the gap is not mitigated.
    """
    high_col = df.columns.get_loc("high")
    low_col = df.columns.get_loc("low")
    close_col = df.columns.get_loc("close")
    open_col = df.columns.get_loc("open")

    # Impulse candle
    df.iloc[i, open_col] = 100.0
    df.iloc[i, low_col] = 99.5
    df.iloc[i, high_col] = 110.0
    df.iloc[i, close_col] = 109.5

    # Gap candle: low strictly above candle[i-1].high (=100.5)
    df.iloc[i + 1, open_col] = 109.0
    df.iloc[i + 1, low_col] = 107.0
    df.iloc[i + 1, high_col] = 112.0
    df.iloc[i + 1, close_col] = 111.0

    # Hold the price above the gap floor for the rest of the series.
    for k in range(i + 2, len(df)):
        df.iloc[k, open_col] = 110.0
        df.iloc[k, low_col] = 108.0
        df.iloc[k, high_col] = 111.0
        df.iloc[k, close_col] = 110.5

    return 100.5, 107.0  # gap_low (candle[i-1].high), gap_high (candle[i+1].low)


def test_detect_fvg_bullish_active():
    df = _overlapping_ohlcv(n=30)
    gap_low, gap_high = _inject_bullish_fvg(df, i=20)
    res = detect_fvg(df)
    assert any(
        f["low"] == gap_low and f["high"] == gap_high and not f["mitigated"]
        for f in res["bullish_fvg"]
    ), f"Expected unmitigated FVG {gap_low}-{gap_high}, got {res['bullish_fvg']}"


def test_detect_fvg_bullish_mitigated():
    df = _overlapping_ohlcv(n=30)
    gap_low, gap_high = _inject_bullish_fvg(df, i=20)
    # A later candle wicks back through the gap → mitigated.
    df.iloc[27, df.columns.get_loc("low")] = gap_low - 1
    res = detect_fvg(df)
    assert any(
        f["low"] == gap_low and f["high"] == gap_high and f["mitigated"]
        for f in res["bullish_fvg"]
    )


def test_detect_liquidity_pools_eqh_and_sweep():
    """
    Build an undulating series so that swing highs form ONLY at the indices we
    inject. A flat baseline would create dense "equal" swings that drown out
    the real EQH pair we want to verify.
    """
    n = 80
    # Sine-shaped backbone gives ~one local peak every 12 candles, well below
    # the levels we inject, so the injected peaks dominate.
    x = np.arange(n)
    base = 100 + np.sin(x / 4) * 0.5
    df = pd.DataFrame(
        {
            "open": base,
            "high": base + 0.2,
            "low": base - 0.2,
            "close": base,
            "volume": np.ones(n),
        },
        index=pd.date_range("2026-01-01", periods=n, freq="4h"),
    )
    # Two near-equal swing highs, well-separated.
    df.iloc[20, df.columns.get_loc("high")] = 120.0
    df.iloc[40, df.columns.get_loc("high")] = 120.05  # within 0.1% tolerance
    # Sweep in last 20 candles: wick pierces 120 but close stays below.
    sweep_i = 70
    df.iloc[sweep_i, df.columns.get_loc("high")] = 121.0
    df.iloc[sweep_i, df.columns.get_loc("close")] = 119.0
    res = detect_liquidity_pools(df, swing_lookback=3)
    assert res["equal_highs"], f"Expected EQH pair, got {res}"
    assert any(
        s["type"] == "Sell-side sweep" for s in res["sweeps"]
    ), f"Expected sell-side sweep, got {res['sweeps']}"


def test_determine_trend_bias_bullish():
    bias = determine_trend_bias(ema21=110, ema50=105, ema200=100, rsi=65, price=115)
    assert "Alcista" in bias


def test_determine_trend_bias_bearish():
    bias = determine_trend_bias(ema21=90, ema50=95, ema200=100, rsi=35, price=85)
    assert "Bajista" in bias
