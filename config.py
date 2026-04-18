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
CLAUDE_MAX_TOKENS = 2800
