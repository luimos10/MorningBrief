"""
Morning Market Brief — Configuration
=====================================
Edita las API keys y preferencias aquí.
"""
import os
from pathlib import Path

# Load .env file if it exists
_env_file = Path(__file__).parent / ".env"
if _env_file.exists():
    for line in _env_file.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            os.environ.setdefault(key.strip(), value.strip())

# ── Directorio base del proyecto ──
BASE_DIR = Path(__file__).parent

# ── API Keys (usar variables de entorno o editar directamente) ──
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "sk-ant-XXXXXXXX")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")  # Opcional: newsapi.org free tier

# ── Activos a analizar ──
# Defaults — sobrescritos por watchlist.yaml si existe.
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT"]

STOCK_SYMBOLS = ["AAPL", "MSFT", "NVDA", "GOOGL", "AMZN"]  # Top 5 Tech

INDEX_SYMBOLS = {
    "S&P 500": "^GSPC",
    "NASDAQ": "^IXIC",
    "DOW": "^DJI",
}

COMMODITY_SYMBOLS = {
    "GOLD": "GC=F",
    "SILVER": "SI=F",
    "OIL (WTI)": "CL=F",
}

ETF_SYMBOLS = {
    "SPY": "SPY",
    "QQQ": "QQQ",
    "GLD": "GLD",
    "SLV": "SLV",
    "USO": "USO",
}

ECONOMIC_EVENTS_MANUAL: list = []

# ── Watchlist YAML override ──
_watchlist_path = BASE_DIR / "watchlist.yaml"
if _watchlist_path.exists():
    try:
        import yaml  # type: ignore
        with _watchlist_path.open("r", encoding="utf-8") as _f:
            _wl = yaml.safe_load(_f) or {}
        if isinstance(_wl.get("crypto"), list):
            CRYPTO_SYMBOLS = list(_wl["crypto"])
        if isinstance(_wl.get("stocks"), list):
            STOCK_SYMBOLS = list(_wl["stocks"])
        if isinstance(_wl.get("indexes"), dict):
            INDEX_SYMBOLS = dict(_wl["indexes"])
        if isinstance(_wl.get("commodities"), dict):
            COMMODITY_SYMBOLS = dict(_wl["commodities"])
        if isinstance(_wl.get("etfs"), dict):
            ETF_SYMBOLS = dict(_wl["etfs"])
        if isinstance(_wl.get("economic_events"), list):
            ECONOMIC_EVENTS_MANUAL = list(_wl["economic_events"])
    except Exception as _e:
        print(f"[WARN] No pude leer watchlist.yaml ({_e}); usando defaults.")

# ── Configuración de análisis técnico ──
EMA_PERIODS = [21, 50, 200]
RSI_PERIOD = 14
TIMEFRAME_CRYPTO = "4h"       # Klines de Binance
TIMEFRAME_STOCKS = "1d"       # yfinance daily
LOOKBACK_DAYS = 100           # Días de historia para cálculos

# ── Configuración de entrega ──
BRIEF_HOUR = 9                # Hora de entrega (24h format)
BRIEF_MINUTE = 0
HTML_OUTPUT_DIR = BASE_DIR / "output"
HTML_OUTPUT_DIR.mkdir(exist_ok=True)

# ── Claude API ──
CLAUDE_MODEL = "claude-sonnet-4-6"
CLAUDE_MAX_TOKENS = 8192
