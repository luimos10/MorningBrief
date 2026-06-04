"""
Morning Market Brief — Data Fetcher
====================================
Recopila datos de mercado de múltiples fuentes gratuitas.
"""
import logging
import requests
import yfinance as yf
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
    before_sleep_log,
)

import config

logger = logging.getLogger(__name__)

# Common retry decorator for transient network failures.
_net_retry = retry(
    reraise=True,
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type((requests.RequestException, OSError)),
    before_sleep=before_sleep_log(logger, logging.WARNING),
)


@_net_retry
def _http_get_json(url: str, params: Optional[Dict] = None, timeout: int = 10):
    """GET a JSON endpoint with automatic retries on transient failures."""
    resp = requests.get(url, params=params, timeout=timeout)
    resp.raise_for_status()
    return resp.json()


@_net_retry
def _yf_history(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """yfinance history fetch with retry on transient failures."""
    ticker = yf.Ticker(symbol)
    return ticker.history(period=period, interval=interval)


# Spot market-data bases tried in order. `api.binance.com` está geo-bloqueado
# (HTTP 451) en IPs de EE.UU. como las de GitHub Actions; `data-api.binance.vision`
# es el mirror público de datos de mercado y NO está bloqueado, sirviendo el mismo
# JSON de /api/v3/klines (incluye taker_buy_base para el CVD).
_SPOT_BASES = ["https://api.binance.com", "https://data-api.binance.vision"]

# Mapeo de intervalos Binance → Bybit v5 (minutos como string; D/W/M para mayores).
_BYBIT_INTERVAL = {
    "1m": "1", "3m": "3", "5m": "5", "15m": "15", "30m": "30",
    "1h": "60", "2h": "120", "4h": "240", "6h": "360", "12h": "720",
    "1d": "D", "1w": "W", "1M": "M",
}


def fetch_binance_klines(symbol: str, interval: str = "4h", limit: int = 200) -> pd.DataFrame:
    """Fetch OHLCV klines, probando los mirrors spot y con fallback a Bybit."""
    params = {"symbol": symbol, "interval": interval, "limit": limit}
    columns = [
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades", "taker_buy_base",
        "taker_buy_quote", "ignore",
    ]
    num_cols = ["open", "high", "low", "close", "volume",
                "taker_buy_base", "taker_buy_quote", "quote_volume"]

    for base in _SPOT_BASES:
        url = f"{base}/api/v3/klines"
        try:
            data = _http_get_json(url, params=params, timeout=15)
            if not data:
                continue
            df = pd.DataFrame(data, columns=columns)
            for col in num_cols:
                df[col] = df[col].astype(float)
            df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
            df.set_index("open_time", inplace=True)
            return df
        except Exception as e:
            logger.warning(f"Binance klines {symbol} via {base}: {e}")

    # Fallback final: Bybit (no geo-bloqueado por API).
    df = _fetch_bybit_klines(symbol, interval=interval, limit=limit)
    if df.empty:
        logger.error(f"Klines {symbol}: sin datos en ningún proveedor (spot ni Bybit)")
    return df


def _fetch_bybit_klines(symbol: str, interval: str = "4h", limit: int = 200) -> pd.DataFrame:
    """
    Fallback de klines vía Bybit v5 (linear perp). Devuelve el mismo esquema de
    columnas que Binance; taker_buy_base no existe en Bybit, así que se aproxima
    a la mitad del volumen (CVD≈0) para no romper compute_cvd_from_klines.
    """
    bybit_interval = _BYBIT_INTERVAL.get(interval, "240")
    url = "https://api.bybit.com/v5/market/kline"
    params = {"category": "linear", "symbol": symbol,
              "interval": bybit_interval, "limit": min(limit, 1000)}
    try:
        payload = _http_get_json(url, params=params, timeout=15)
        rows = (payload.get("result") or {}).get("list") or []
        if not rows:
            return pd.DataFrame()
        # Bybit devuelve [start, open, high, low, close, volume, turnover] en orden DESC.
        rows = list(reversed(rows))
        df = pd.DataFrame(rows, columns=[
            "open_time", "open", "high", "low", "close", "volume", "quote_volume",
        ])
        for col in ["open", "high", "low", "close", "volume", "quote_volume"]:
            df[col] = df[col].astype(float)
        df["open_time"] = pd.to_datetime(df["open_time"].astype("int64"), unit="ms")
        df.set_index("open_time", inplace=True)
        # Aproximación: sin desglose taker, CVD neutro.
        df["taker_buy_base"] = df["volume"] / 2.0
        df["taker_buy_quote"] = df["quote_volume"] / 2.0
        return df
    except Exception as e:
        logger.warning(f"Bybit klines {symbol}: {e}")
        return pd.DataFrame()


def fetch_binance_funding_rate(symbol: str) -> Optional[Dict]:
    """Latest funding rate. Binance fapi → fallback Bybit (ambos geo-tolerantes)."""
    url = "https://fapi.binance.com/fapi/v1/fundingRate"
    params = {"symbol": symbol, "limit": 1}
    try:
        data = _http_get_json(url, params=params, timeout=10)
        if data:
            return {
                "rate": float(data[0]["fundingRate"]),
                "time": datetime.fromtimestamp(data[0]["fundingTime"] / 1000).strftime("%H:%M UTC"),
            }
    except Exception as e:
        logger.warning(f"Funding rate {symbol} (Binance): {e}")

    # Fallback Bybit v5.
    try:
        payload = _http_get_json(
            "https://api.bybit.com/v5/market/funding/history",
            params={"category": "linear", "symbol": symbol, "limit": 1},
            timeout=10,
        )
        rows = (payload.get("result") or {}).get("list") or []
        if rows:
            ts = int(rows[0]["fundingRateTimestamp"])
            return {
                "rate": float(rows[0]["fundingRate"]),
                "time": datetime.fromtimestamp(ts / 1000).strftime("%H:%M UTC"),
            }
    except Exception as e:
        logger.warning(f"Funding rate {symbol} (Bybit): {e}")
    return None


def fetch_binance_open_interest(symbol: str) -> Optional[Dict]:
    """Current open interest. Binance fapi → fallback Bybit."""
    url = "https://fapi.binance.com/fapi/v1/openInterest"
    params = {"symbol": symbol}
    try:
        data = _http_get_json(url, params=params, timeout=10)
        return {
            "oi": float(data["openInterest"]),
            "symbol": data["symbol"],
        }
    except Exception as e:
        logger.warning(f"Open Interest {symbol} (Binance): {e}")

    # Fallback Bybit: el más reciente del histórico 4h.
    hist = _fetch_bybit_oi_history(symbol, limit=1)
    if hist:
        return {"oi": hist[-1], "symbol": symbol}
    return None


def fetch_binance_oi_history(symbol: str, period: str = "4h", limit: int = 30) -> List[float]:
    """OI history para detectar cambios. Binance fapi → fallback Bybit."""
    url = "https://fapi.binance.com/futures/data/openInterestHist"
    params = {"symbol": symbol, "period": period, "limit": limit}
    try:
        data = _http_get_json(url, params=params, timeout=10)
        if data:
            return [float(d["sumOpenInterest"]) for d in data]
    except Exception as e:
        logger.warning(f"OI history {symbol} (Binance): {e}")

    return _fetch_bybit_oi_history(symbol, period=period, limit=limit)


def _fetch_bybit_oi_history(symbol: str, period: str = "4h", limit: int = 30) -> List[float]:
    """OI history vía Bybit v5 (devuelto ASC para emparejar el orden de Binance)."""
    interval_map = {"5m": "5min", "15m": "15min", "30m": "30min",
                    "1h": "1h", "4h": "4h", "1d": "1d"}
    url = "https://api.bybit.com/v5/market/open-interest"
    params = {"category": "linear", "symbol": symbol,
              "intervalTime": interval_map.get(period, "4h"), "limit": min(limit, 200)}
    try:
        payload = _http_get_json(url, params=params, timeout=10)
        rows = (payload.get("result") or {}).get("list") or []
        # Bybit devuelve DESC (más reciente primero); invertir a ASC.
        return [float(r["openInterest"]) for r in reversed(rows)]
    except Exception as e:
        logger.warning(f"OI history {symbol} (Bybit): {e}")
    return []


def fetch_binance_long_short_ratio(symbol: str, period: str = "4h") -> Optional[Dict]:
    """Top trader long/short ratio. Binance fapi → fallback Bybit."""
    url = "https://fapi.binance.com/futures/data/topLongShortAccountRatio"
    params = {"symbol": symbol, "period": period, "limit": 1}
    try:
        data = _http_get_json(url, params=params, timeout=10)
        if data:
            return {
                "long_account": float(data[0]["longAccount"]),
                "short_account": float(data[0]["shortAccount"]),
                "ratio": float(data[0]["longShortRatio"]),
            }
    except Exception as e:
        logger.warning(f"Long/Short ratio {symbol} (Binance): {e}")

    # Fallback Bybit v5: account-ratio devuelve buyRatio/sellRatio.
    try:
        payload = _http_get_json(
            "https://api.bybit.com/v5/market/account-ratio",
            params={"category": "linear", "symbol": symbol, "period": period, "limit": 1},
            timeout=10,
        )
        rows = (payload.get("result") or {}).get("list") or []
        if rows:
            longs = float(rows[0]["buyRatio"])
            shorts = float(rows[0]["sellRatio"])
            return {
                "long_account": longs,
                "short_account": shorts,
                "ratio": round(longs / shorts, 4) if shorts else None,
            }
    except Exception as e:
        logger.warning(f"Long/Short ratio {symbol} (Bybit): {e}")
    return None


def compute_cvd_from_klines(df: pd.DataFrame) -> pd.Series:
    """
    Approximate CVD from kline taker buy volume.
    CVD = cumulative(taker_buy - (volume - taker_buy))
    taker_buy_base = volume bought by takers (aggressive buyers)
    seller volume = total volume - taker_buy_base
    delta = taker_buy - seller = 2*taker_buy - volume
    """
    if df.empty or "taker_buy_base" not in df.columns:
        return pd.Series(dtype=float)
    delta = 2 * df["taker_buy_base"] - df["volume"]
    return delta.cumsum()


def fetch_yfinance_data(symbol: str, period: str = "6mo", interval: str = "1d") -> pd.DataFrame:
    """Fetch OHLCV data from Yahoo Finance."""
    try:
        df = _yf_history(symbol, period=period, interval=interval)
        if df.empty:
            logger.warning(f"No data for {symbol}")
        return df
    except Exception as e:
        logger.error(f"yfinance {symbol}: {e}")
        return pd.DataFrame()


def fetch_fear_greed_index() -> Optional[Dict]:
    """Fetch Crypto Fear & Greed Index from alternative.me."""
    url = "https://api.alternative.me/fng/?limit=1"
    try:
        payload = _http_get_json(url, timeout=10)
        data = payload["data"][0]
        return {
            "value": int(data["value"]),
            "label": data["value_classification"],
        }
    except Exception as e:
        logger.error(f"Fear & Greed: {e}")
    return None


def fetch_vix() -> Optional[float]:
    """Fetch current VIX level."""
    try:
        hist = _yf_history("^VIX", period="2d", interval="1d")
        if not hist.empty:
            return round(hist["Close"].iloc[-1], 2)
    except Exception as e:
        logger.error(f"VIX: {e}")
    return None


def fetch_dxy() -> Optional[Dict]:
    """Fetch US Dollar Index (DXY)."""
    try:
        hist = _yf_history("DX-Y.NYB", period="5d", interval="1d")
        if not hist.empty and len(hist) >= 2:
            current = hist["Close"].iloc[-1]
            prev = hist["Close"].iloc[-2]
            change_pct = ((current - prev) / prev) * 100
            return {"value": round(current, 2), "change": round(change_pct, 2)}
    except Exception as e:
        logger.error(f"DXY: {e}")
    return None


def fetch_economic_calendar() -> List[Dict]:
    """
    Fetch today's economic events.
    Combines:
    1. Manual events from watchlist.yaml (date matches today, by string prefix)
    2. NewsAPI keyword search for Fed/CPI/NFP if NEWSAPI_KEY is set.
    """
    events = []
    today_str = datetime.now().strftime("%Y-%m-%d")

    # ── Manual events from watchlist.yaml ──
    for ev in getattr(config, "ECONOMIC_EVENTS_MANUAL", []) or []:
        ev_date = str(ev.get("date", ""))
        if ev_date.startswith(today_str):
            events.append({
                "title": str(ev.get("title", "")),
                "source": f"manual (importance {ev.get('importance', '?')})",
                "url": ev.get("url", ""),
                "time": ev_date,
            })

    today = today_str

    # Try to get news about Fed/economic events
    if config.NEWSAPI_KEY:
        url = "https://newsapi.org/v2/everything"
        params = {
            "q": "Federal Reserve OR FOMC OR CPI OR NFP OR interest rate",
            "from": today,
            "to": today,
            "language": "en",
            "sortBy": "relevancy",
            "pageSize": 5,
            "apiKey": config.NEWSAPI_KEY,
        }
        try:
            payload = _http_get_json(url, params=params, timeout=10)
            articles = payload.get("articles", [])
            for art in articles[:3]:
                events.append({
                    "title": art.get("title", ""),
                    "source": art.get("source", {}).get("name", ""),
                    "url": art.get("url", ""),
                })
        except Exception as e:
            logger.warning(f"NewsAPI: {e}")

    return events


def fetch_market_news() -> List[Dict]:
    """Fetch top market news headlines."""
    news = []
    if config.NEWSAPI_KEY:
        url = "https://newsapi.org/v2/top-headlines"
        params = {
            "category": "business",
            "language": "en",
            "pageSize": 5,
            "apiKey": config.NEWSAPI_KEY,
        }
        try:
            payload = _http_get_json(url, params=params, timeout=10)
            articles = payload.get("articles", [])
            for art in articles[:5]:
                news.append({
                    "title": art.get("title", ""),
                    "source": art.get("source", {}).get("name", ""),
                })
        except Exception as e:
            logger.warning(f"Market news: {e}")
    return news


def collect_all_data() -> Dict:
    """
    Master function: recopila TODOS los datos necesarios para el brief.
    Returns a comprehensive dict with all market data.
    """
    logger.info("Recopilando datos del mercado...")
    data = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "crypto": {},
        "indexes": {},
        "stocks": {},
        "commodities": {},
        "etfs": {},
        "macro": {},
    }

    # ── CRYPTO ──
    for symbol in config.CRYPTO_SYMBOLS:
        logger.info(f"  → Crypto: {symbol}")
        klines = fetch_binance_klines(symbol, interval="4h", limit=200)
        klines_1h = fetch_binance_klines(symbol, interval="1h", limit=100)
        funding = fetch_binance_funding_rate(symbol)
        oi = fetch_binance_open_interest(symbol)
        oi_hist = fetch_binance_oi_history(symbol)
        ls_ratio = fetch_binance_long_short_ratio(symbol)
        cvd = compute_cvd_from_klines(klines)

        data["crypto"][symbol] = {
            "klines_4h": klines,
            "klines_1h": klines_1h,
            "funding": funding,
            "open_interest": oi,
            "oi_history": oi_hist,
            "long_short_ratio": ls_ratio,
            "cvd": cvd,
            "price": float(klines["close"].iloc[-1]) if not klines.empty else None,
            "price_24h_ago": float(klines["close"].iloc[-6]) if len(klines) >= 6 else None,
        }

    # ── INDEXES ──
    for name, symbol in config.INDEX_SYMBOLS.items():
        logger.info(f"  → Index: {name}")
        df = fetch_yfinance_data(symbol, period="6mo")
        data["indexes"][name] = {
            "ohlcv": df,
            "price": round(df["Close"].iloc[-1], 2) if not df.empty else None,
            "prev_close": round(df["Close"].iloc[-2], 2) if len(df) >= 2 else None,
        }

    # ── STOCKS (Top 5 Tech) ──
    for symbol in config.STOCK_SYMBOLS:
        logger.info(f"  → Stock: {symbol}")
        df = fetch_yfinance_data(symbol, period="6mo")
        data["stocks"][symbol] = {
            "ohlcv": df,
            "price": round(df["Close"].iloc[-1], 2) if not df.empty else None,
            "prev_close": round(df["Close"].iloc[-2], 2) if len(df) >= 2 else None,
        }

    # ── COMMODITIES ──
    for name, symbol in config.COMMODITY_SYMBOLS.items():
        logger.info(f"  → Commodity: {name}")
        df = fetch_yfinance_data(symbol, period="6mo")
        data["commodities"][name] = {
            "ohlcv": df,
            "price": round(df["Close"].iloc[-1], 2) if not df.empty else None,
            "prev_close": round(df["Close"].iloc[-2], 2) if len(df) >= 2 else None,
        }

    # ── ETFs ──
    for name, symbol in config.ETF_SYMBOLS.items():
        logger.info(f"  → ETF: {name}")
        df = fetch_yfinance_data(symbol, period="6mo")
        data["etfs"][name] = {
            "ohlcv": df,
            "price": round(df["Close"].iloc[-1], 2) if not df.empty else None,
            "prev_close": round(df["Close"].iloc[-2], 2) if len(df) >= 2 else None,
        }

    # ── MACRO ──
    logger.info("  → Macro indicators...")
    data["macro"]["fear_greed"] = fetch_fear_greed_index()
    data["macro"]["vix"] = fetch_vix()
    data["macro"]["dxy"] = fetch_dxy()
    data["macro"]["economic_events"] = fetch_economic_calendar()
    data["macro"]["news"] = fetch_market_news()

    logger.info("Datos recopilados exitosamente.")
    return data
