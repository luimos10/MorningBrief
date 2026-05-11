"""
Morning Market Brief — Analysis Engine
========================================
Calcula indicadores técnicos y estructura de mercado SMC/ICT.
"""
import pandas as pd
import numpy as np
from typing import Dict, List, Optional, Tuple
import config


def calc_ema(series: pd.Series, period: int) -> pd.Series:
    """Calculate EMA for a given period."""
    return series.ewm(span=period, adjust=False).mean()


def calc_rsi(series: pd.Series, period: int = 14) -> pd.Series:
    """Calculate RSI."""
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


def detect_swing_points(df: pd.DataFrame, lookback: int = 5) -> Tuple[List, List]:
    """
    Detect swing highs and swing lows.
    A swing high = high[i] > high[i-n:i] and high[i] > high[i+1:i+n]
    """
    highs = df["high"] if "high" in df.columns else df["High"]
    lows = df["low"] if "low" in df.columns else df["Low"]

    swing_highs = []
    swing_lows = []

    for i in range(lookback, len(df) - lookback):
        # Swing High
        if highs.iloc[i] == highs.iloc[i - lookback:i + lookback + 1].max():
            swing_highs.append({
                "index": i,
                "price": float(highs.iloc[i]),
                "time": df.index[i],
            })
        # Swing Low
        if lows.iloc[i] == lows.iloc[i - lookback:i + lookback + 1].min():
            swing_lows.append({
                "index": i,
                "price": float(lows.iloc[i]),
                "time": df.index[i],
            })

    return swing_highs, swing_lows


def detect_market_structure(df: pd.DataFrame, lookback: int = 5) -> Dict:
    """
    Detect BOS (Break of Structure) and CHOCH (Change of Character).

    BOS = price breaks a previous swing high (bullish) or swing low (bearish)
          in the DIRECTION of the existing trend.
    CHOCH = price breaks structure in the OPPOSITE direction of the existing trend,
            signaling a potential reversal.
    """
    close_col = "close" if "close" in df.columns else "Close"
    swing_highs, swing_lows = detect_swing_points(df, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return {"structure": "Undefined", "events": [], "trend": "Neutral"}

    current_price = float(df[close_col].iloc[-1])

    # Determine trend from swing structure
    last_2_highs = swing_highs[-2:]
    last_2_lows = swing_lows[-2:]

    higher_highs = last_2_highs[-1]["price"] > last_2_highs[-2]["price"]
    higher_lows = last_2_lows[-1]["price"] > last_2_lows[-2]["price"]
    lower_highs = last_2_highs[-1]["price"] < last_2_highs[-2]["price"]
    lower_lows = last_2_lows[-1]["price"] < last_2_lows[-2]["price"]

    events = []

    if higher_highs and higher_lows:
        trend = "Bullish"
        structure = "HH + HL (Uptrend)"
        # Check for BOS: current price broke above last swing high
        if current_price > last_2_highs[-1]["price"]:
            events.append("BOS Bullish (rompió último swing high)")
    elif lower_highs and lower_lows:
        trend = "Bearish"
        structure = "LH + LL (Downtrend)"
        if current_price < last_2_lows[-1]["price"]:
            events.append("BOS Bearish (rompió último swing low)")
    else:
        trend = "Transitional"
        structure = "Mixed structure"

    # CHOCH detection
    if higher_highs and lower_lows:
        events.append("CHOCH potencial — estructura mixta")
    if lower_highs and higher_lows:
        events.append("CHOCH potencial — compresión / rango")

    # Check for recent CHOCH: was bullish but broke below last swing low
    if trend == "Bullish" and current_price < last_2_lows[-1]["price"]:
        events.append("⚠ CHOCH Bearish — rompió swing low en uptrend")
        trend = "Bearish Reversal"
    elif trend == "Bearish" and current_price > last_2_highs[-1]["price"]:
        events.append("⚠ CHOCH Bullish — rompió swing high en downtrend")
        trend = "Bullish Reversal"

    return {
        "structure": structure,
        "trend": trend,
        "events": events,
        "last_swing_high": last_2_highs[-1]["price"],
        "last_swing_low": last_2_lows[-1]["price"],
        "prev_swing_high": last_2_highs[-2]["price"],
        "prev_swing_low": last_2_lows[-2]["price"],
    }


def detect_order_blocks(df: pd.DataFrame, lookback: int = 50) -> Dict:
    """
    Detect Order Blocks (OB) — ICT concept.

    Bullish OB = last bearish candle before a strong bullish move (impulse up).
    Bearish OB = last bullish candle before a strong bearish move (impulse down).

    We look for:
    1. A candle that is opposite to the subsequent impulse
    2. The impulse must be strong (> 1.5x ATR)
    """
    close_col = "close" if "close" in df.columns else "Close"
    open_col = "open" if "open" in df.columns else "Open"
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"

    recent = df.iloc[-lookback:].copy()
    if len(recent) < 10:
        return {"bullish_ob": None, "bearish_ob": None}

    # Calculate ATR for threshold
    tr = pd.DataFrame({
        "hl": recent[high_col] - recent[low_col],
        "hc": abs(recent[high_col] - recent[close_col].shift(1)),
        "lc": abs(recent[low_col] - recent[close_col].shift(1)),
    }).max(axis=1)
    atr = tr.rolling(14).mean().iloc[-1]

    bullish_ob = None
    bearish_ob = None

    # Scan recent candles for OBs
    for i in range(len(recent) - 3, max(0, len(recent) - 30), -1):
        candle_close = recent[close_col].iloc[i]
        candle_open = recent[open_col].iloc[i]
        next_close = recent[close_col].iloc[i + 1]

        is_bearish_candle = candle_close < candle_open
        is_bullish_candle = candle_close > candle_open

        move_after = next_close - candle_close

        # Bullish OB: bearish candle followed by strong bullish impulse
        if is_bearish_candle and move_after > atr * 1.5 and bullish_ob is None:
            bullish_ob = {
                "high": round(float(recent[high_col].iloc[i]), 2),
                "low": round(float(recent[low_col].iloc[i]), 2),
                "time": str(recent.index[i]),
                "type": "Bullish OB (demand zone)",
            }

        # Bearish OB: bullish candle followed by strong bearish impulse
        if is_bullish_candle and move_after < -atr * 1.5 and bearish_ob is None:
            bearish_ob = {
                "high": round(float(recent[high_col].iloc[i]), 2),
                "low": round(float(recent[low_col].iloc[i]), 2),
                "time": str(recent.index[i]),
                "type": "Bearish OB (supply zone)",
            }

        if bullish_ob and bearish_ob:
            break

    return {"bullish_ob": bullish_ob, "bearish_ob": bearish_ob}


def detect_fvg(df: pd.DataFrame, lookback: int = 50, max_results: int = 3) -> Dict:
    """
    Detect Fair Value Gaps (ICT concept) in the most recent candles.

    Bullish FVG: candle[i+1].low > candle[i-1].high (gap exists between them).
    Bearish FVG: candle[i+1].high < candle[i-1].low.

    A FVG is "mitigated" once price has traded back into the gap range
    on any later candle. Returns the most recent up to `max_results` of each side.
    """
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"

    recent = df.iloc[-lookback:]
    if len(recent) < 3:
        return {"bullish_fvg": [], "bearish_fvg": []}

    highs = recent[high_col].values
    lows = recent[low_col].values
    times = recent.index

    bullish: List[Dict] = []
    bearish: List[Dict] = []

    # i is the middle (impulsive) candle; gap is between i-1 and i+1.
    for i in range(1, len(recent) - 1):
        prev_high = highs[i - 1]
        prev_low = lows[i - 1]
        next_high = highs[i + 1]
        next_low = lows[i + 1]

        # Bullish FVG
        if next_low > prev_high:
            gap_low = float(prev_high)
            gap_high = float(next_low)
            future_lows = lows[i + 2:]
            mitigated = bool(len(future_lows) and future_lows.min() <= gap_low)
            bullish.append({
                "high": round(gap_high, 2),
                "low": round(gap_low, 2),
                "time": str(times[i]),
                "mitigated": mitigated,
            })

        # Bearish FVG
        if next_high < prev_low:
            gap_high = float(prev_low)
            gap_low = float(next_high)
            future_highs = highs[i + 2:]
            mitigated = bool(len(future_highs) and future_highs.max() >= gap_high)
            bearish.append({
                "high": round(gap_high, 2),
                "low": round(gap_low, 2),
                "time": str(times[i]),
                "mitigated": mitigated,
            })

    return {
        "bullish_fvg": bullish[-max_results:],
        "bearish_fvg": bearish[-max_results:],
    }


def detect_liquidity_pools(df: pd.DataFrame, swing_lookback: int = 5,
                           tolerance: float = 0.001, max_results: int = 3) -> Dict:
    """
    Detect Equal Highs / Equal Lows (liquidity pools) and recent sweeps.

    EQH/EQL: pairs of swing points within `tolerance` (default 0.1%) of each other.
    Sweep: a candle whose wick crosses the EQH/EQL level but closes back inside.
    """
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"
    close_col = "close" if "close" in df.columns else "Close"

    swing_highs, swing_lows = detect_swing_points(df, swing_lookback)

    eq_highs: List[Dict] = []
    eq_lows: List[Dict] = []

    # Compare each swing against any of the previous N swings, not only its
    # immediate neighbor — flat zones produce dense neighbor pairs that crowd
    # out genuine equal levels far apart in time.
    pairing_window = 8

    for j in range(1, len(swing_highs)):
        b = swing_highs[j]["price"]
        for k in range(max(0, j - pairing_window), j):
            a = swing_highs[k]["price"]
            if a <= 0:
                continue
            if abs(b - a) / a <= tolerance and abs(b - a) > 1e-9:
                eq_highs.append({
                    "level": round((a + b) / 2, 2),
                    "time": str(swing_highs[j]["time"]),
                })
                break

    for j in range(1, len(swing_lows)):
        b = swing_lows[j]["price"]
        for k in range(max(0, j - pairing_window), j):
            a = swing_lows[k]["price"]
            if a <= 0:
                continue
            if abs(b - a) / a <= tolerance and abs(b - a) > 1e-9:
                eq_lows.append({
                    "level": round((a + b) / 2, 2),
                    "time": str(swing_lows[j]["time"]),
                })
                break

    # Detect sweeps in the last N candles against any EQH/EQL.
    sweeps: List[Dict] = []
    sweep_window = df.iloc[-20:]
    for level_info in eq_highs[-max_results:]:
        lvl = level_info["level"]
        for ts, row in sweep_window.iterrows():
            if row[high_col] > lvl and row[close_col] < lvl:
                sweeps.append({
                    "type": "Sell-side sweep",
                    "level": lvl,
                    "time": str(ts),
                })
                break
    for level_info in eq_lows[-max_results:]:
        lvl = level_info["level"]
        for ts, row in sweep_window.iterrows():
            if row[low_col] < lvl and row[close_col] > lvl:
                sweeps.append({
                    "type": "Buy-side sweep",
                    "level": lvl,
                    "time": str(ts),
                })
                break

    return {
        "equal_highs": eq_highs[-max_results:],
        "equal_lows": eq_lows[-max_results:],
        "sweeps": sweeps[-max_results:],
    }


def calc_support_resistance(df: pd.DataFrame, n_levels: int = 3) -> Dict:
    """Calculate key support and resistance levels from recent price action."""
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"
    close_col = "close" if "close" in df.columns else "Close"

    recent = df.iloc[-60:]
    current_price = float(recent[close_col].iloc[-1])

    swing_highs, swing_lows = detect_swing_points(df.iloc[-100:], lookback=3)

    # Resistance = swing highs above current price
    resistance_levels = sorted(
        [sh["price"] for sh in swing_highs if sh["price"] > current_price],
        key=lambda x: x - current_price
    )[:n_levels]

    # Support = swing lows below current price
    support_levels = sorted(
        [sl["price"] for sl in swing_lows if sl["price"] < current_price],
        key=lambda x: current_price - x
    )[:n_levels]

    return {
        "resistance": [round(r, 2) for r in resistance_levels],
        "support": [round(s, 2) for s in support_levels],
    }


def determine_trend_bias(ema21: float, ema50: float, ema200: float, rsi: float, price: float) -> str:
    """Determine the day's bias based on EMAs and RSI."""
    bullish_signals = 0
    bearish_signals = 0

    if price > ema21:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if ema21 > ema50:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if price > ema200:
        bullish_signals += 1
    else:
        bearish_signals += 1

    if rsi > 55:
        bullish_signals += 1
    elif rsi < 45:
        bearish_signals += 1

    if bullish_signals >= 3:
        return "🟢 Alcista"
    elif bearish_signals >= 3:
        return "🔴 Bajista"
    else:
        return "🟡 Neutro"


def analyze_cvd_divergence(cvd: pd.Series, close: pd.Series, window: int = 20) -> str:
    """Detect CVD divergence vs price."""
    if cvd.empty or len(cvd) < window:
        return "Sin datos suficientes"

    recent_cvd = cvd.iloc[-window:]
    recent_close = close.iloc[-window:]

    price_trend = "up" if recent_close.iloc[-1] > recent_close.iloc[0] else "down"
    cvd_trend = "up" if recent_cvd.iloc[-1] > recent_cvd.iloc[0] else "down"

    if price_trend == "up" and cvd_trend == "down":
        return "⚠ Divergencia bajista (precio sube, CVD baja)"
    elif price_trend == "down" and cvd_trend == "up":
        return "⚠ Divergencia alcista (precio baja, CVD sube)"
    elif price_trend == cvd_trend:
        direction = "alcista" if price_trend == "up" else "bajista"
        return f"✅ Confirmación {direction} (precio y CVD alineados)"
    return "Neutral"


def analyze_asset(name: str, df: pd.DataFrame, is_crypto: bool = False,
                  extra_data: Optional[Dict] = None) -> Dict:
    """
    Full analysis for a single asset.
    Returns a dict with all technical data ready for the brief.
    """
    if df.empty:
        return {"name": name, "error": "Sin datos disponibles"}

    close_col = "close" if "close" in df.columns else "Close"
    high_col = "high" if "high" in df.columns else "High"
    low_col = "low" if "low" in df.columns else "Low"

    close = df[close_col]
    price = float(close.iloc[-1])

    # EMAs
    ema21 = float(calc_ema(close, 21).iloc[-1])
    ema50 = float(calc_ema(close, 50).iloc[-1])
    ema200 = float(
        calc_ema(close, 200).iloc[-1]) if len(close) >= 200 else None

    # RSI
    rsi = float(calc_rsi(close, config.RSI_PERIOD).iloc[-1])

    # Market structure
    structure = detect_market_structure(df)

    # Order Blocks
    obs = detect_order_blocks(df)

    # Fair Value Gaps
    fvg = detect_fvg(df)

    # Liquidity pools (EQH/EQL + sweeps)
    liquidity = detect_liquidity_pools(df)

    # Support / Resistance
    levels = calc_support_resistance(df)

    # Trend bias
    bias = determine_trend_bias(ema21, ema50, ema200 or ema50, rsi, price)

    # Price change
    if len(close) >= 2:
        prev = float(close.iloc[-2])
        change_pct = round(((price - prev) / prev) * 100, 2)
    else:
        change_pct = 0

    result = {
        "name": name,
        "price": round(price, 2),
        "change_pct": change_pct,
        "ema21": round(ema21, 2),
        "ema50": round(ema50, 2),
        "ema200": round(ema200, 2) if ema200 else "N/A",
        "rsi": round(rsi, 1),
        "structure": structure,
        "order_blocks": obs,
        "fvg": fvg,
        "liquidity": liquidity,
        "levels": levels,
        "bias": bias,
    }

    # Multi-timeframe refinement: if a lower-timeframe df is provided
    # (e.g. 1h klines for a 4h asset), surface its most recent FVG and swings
    # so the brief can suggest entry refinement.
    df_ltf = None
    if extra_data:
        df_ltf = extra_data.get("df_ltf") or extra_data.get("klines_1h")
    if isinstance(df_ltf, pd.DataFrame):
        if not df_ltf.empty and len(df_ltf) >= 10:
            ltf_struct = detect_market_structure(df_ltf)
            ltf_fvg = detect_fvg(df_ltf, lookback=40, max_results=2)
            result["ltf"] = {
                "structure": ltf_struct.get("structure"),
                "trend": ltf_struct.get("trend"),
                "events": ltf_struct.get("events", []),
                "last_swing_high": ltf_struct.get("last_swing_high"),
                "last_swing_low": ltf_struct.get("last_swing_low"),
                "bullish_fvg": ltf_fvg.get("bullish_fvg", []),
                "bearish_fvg": ltf_fvg.get("bearish_fvg", []),
            }

    # Extra crypto data
    if is_crypto and extra_data:
        funding = extra_data.get("funding")
        oi = extra_data.get("open_interest")
        oi_hist = extra_data.get("oi_history", [])
        ls_ratio = extra_data.get("long_short_ratio")
        cvd = extra_data.get("cvd", pd.Series(dtype=float))

        if funding:
            result["funding_rate"] = f"{funding['rate'] * 100:.4f}%"
            result["funding_sentiment"] = "Longs pagan" if funding["rate"] > 0 else "Shorts pagan"

        if oi:
            result["open_interest"] = f"{oi['oi']:,.0f}"

        if len(oi_hist) >= 2:
            oi_change = ((oi_hist[-1] - oi_hist[-2]) / oi_hist[-2]) * 100
            result["oi_change"] = f"{oi_change:+.2f}%"

        if ls_ratio:
            result["long_ratio"] = f"{ls_ratio['long_account'] * 100:.1f}%"
            result["short_ratio"] = f"{ls_ratio['short_account'] * 100:.1f}%"

        if not cvd.empty:
            result["cvd_divergence"] = analyze_cvd_divergence(cvd, close)

    return result


def run_full_analysis(market_data: Dict) -> Dict:
    """
    Run full analysis on all collected market data.
    Returns structured analysis ready for the brief generator.
    """
    print("[INFO] Ejecutando análisis técnico completo...")
    analysis = {
        "timestamp": market_data["timestamp"],
        "crypto": [],
        "indexes": [],
        "stocks": [],
        "commodities": [],
        "etfs": [],
        "macro": market_data["macro"],
    }

    # ── Crypto ──
    for symbol, data in market_data["crypto"].items():
        result = analyze_asset(
            symbol,
            data["klines_4h"],
            is_crypto=True,
            extra_data=data,
        )
        analysis["crypto"].append(result)

    # ── Indexes ──
    for name, data in market_data["indexes"].items():
        result = analyze_asset(name, data["ohlcv"])
        analysis["indexes"].append(result)

    # ── Stocks ──
    for symbol, data in market_data["stocks"].items():
        result = analyze_asset(symbol, data["ohlcv"])
        analysis["stocks"].append(result)

    # ── Commodities ──
    for name, data in market_data["commodities"].items():
        result = analyze_asset(name, data["ohlcv"])
        analysis["commodities"].append(result)

    # ── ETFs ──
    for name, data in market_data["etfs"].items():
        result = analyze_asset(name, data["ohlcv"])
        analysis["etfs"].append(result)

    print("[OK] Análisis técnico completado.")
    return analysis
