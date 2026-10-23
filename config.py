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
CRYPTO_SYMBOLS = ["BTCUSDT", "ETHUSDT", "SOLUSDT"]

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
CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-5-5")
# Cap de salida: 11000 cubre el brief completo (1500–2500 palabras + tablas ≈ 10.2k tokens);
# solo se paga lo generado. Sonnet 5.5 soporta hasta 128k si hace falta subirlo por env.
CLAUDE_MAX_TOKENS = int(os.getenv("CLAUDE_MAX_TOKENS", "11000"))
# Thinking de sonnet-5-5: "between_tools" (default, cero thinking; con este pipeline sin tools
# la respuesta es 100% texto) o "adaptive" (thinking on, costo variable). "disabled" y
# "enabled"+budget_tokens devuelven 400 en este modelo.
CLAUDE_THINKING = os.getenv("CLAUDE_THINKING", "between_tools")
# Solo aplica con CLAUDE_THINKING=adaptive: acota la profundidad del thinking (limitación suave,
# sin techo estricto de costo). Sonnet 5.5 acepta between_tools solo en effort high o inferior.
CLAUDE_EFFORT = os.getenv("CLAUDE_EFFORT", "medium")
# Caché de prompt: con runs 1×/día nunca hay cache_read (TTL 5 min) y el write cuesta +25%
# sobre el precio de input. Off por defecto; on solo si se relanza varias veces seguidas.
CLAUDE_PROMPT_CACHE = os.getenv("CLAUDE_PROMPT_CACHE", "0") == "1"
# USD por MTok para el log [COST] (sonnet-5-5 a oct-2026). Actualizar si cambia el modelo.
CLAUDE_PRICES = {
    "input": 2.0,
    "output": 10.0,
    "cache_write_5m": 2.5,
    "cache_read": 0.10,
}
