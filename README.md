# Morning Market Brief

Brief matutino de mercados financieros generado automáticamente con Claude AI. Analiza crypto, índices, acciones, commodities y ETFs usando análisis técnico SMC/ICT (BOS/CHOCH, Order Blocks, **Fair Value Gaps**, **liquidity sweeps**, multi-timeframe), incorpora el contexto del brief del día anterior y entrega el resultado vía Telegram, Discord y HTML.

---

## Qué hace

Cada mañana a las 9:00 AM ejecuta un pipeline de 4 pasos:

1. **Recopila datos** de múltiples fuentes (Binance 4h+1h, Yahoo Finance, alternative.me, NewsAPI) con retries y caché diario en disco
2. **Calcula indicadores SMC/ICT**: EMAs, RSI, BOS/CHOCH, Order Blocks, FVG (con flag de mitigación), Equal Highs/Lows + sweeps de liquidez, niveles S/R, refinamiento multi-timeframe (1h dentro de 4h)
3. **Genera el brief** con Claude Sonnet 4.6 — el system prompt va con `cache_control: ephemeral` para reducir coste
4. **Entrega el brief** vía Telegram (texto + HTML adjunto), Discord (si hay webhook), HTML local en navegador, y backup `.txt` en disco

Cada brief incluye una línea de **SEGUIMIENTO** que compara los setups del día anterior con los precios actuales (¿se activó la entrada? ¿saltó el SL? ¿llegó al target?), dando continuidad narrativa día a día.

---

## Estructura del proyecto

```
morning-brief/
├── main.py                 # Orquestador principal (CLI)
├── config.py               # Configuración + carga de watchlist.yaml
├── watchlist.yaml          # Símbolos editables sin tocar código
├── data_fetcher.py         # Recopilación de datos (con retries tenacity)
├── analysis.py             # Motor SMC/ICT (BOS/CHOCH, OB, FVG, liquidity)
├── performance_tracker.py  # Inyecta contexto del brief anterior
├── brief_generator.py      # Genera brief con Claude (prompt caching)
├── html_renderer.py        # Renderizado HTML profesional
├── telegram_delivery.py    # Envío a Telegram
├── discord_delivery.py     # Envío a Discord (webhook)
├── market_cache.py         # Caché diario de market_data
├── logging_setup.py        # Logging estructurado a logs/
├── setup_brief.py          # Setup interactivo
├── tests/                  # Tests pytest de analysis.py
├── requirements.txt
├── .env                    # API keys (NO commitear)
├── cache/                  # Cachés diarios de market data (.pkl)
├── logs/                   # Logs diarios
└── output/                 # Briefs generados (HTML + TXT)
```

---

## Módulos paso a paso

### 1. `config.py` — Configuración central
Carga variables de entorno desde `.env` y, si existe, sobrescribe los símbolos de activos con `watchlist.yaml`. Define:
- API keys (Anthropic, Telegram, NewsAPI, opcional Discord)
- Activos por defecto (cryptos, índices, stocks, commodities, ETFs)
- Eventos económicos manuales (`ECONOMIC_EVENTS_MANUAL`) cargados del YAML
- Parámetros técnicos: EMAs (21/50/200), RSI (14), timeframe crypto (4h), lookback (100 días)
- Modelo Claude, max tokens, hora de ejecución

### 2. `watchlist.yaml` — Watchlist configurable
Editar este archivo para añadir/quitar tickers sin tocar código. Estructura:
```yaml
crypto: [BTCUSDT, ETHUSDT]
stocks: [AAPL, MSFT, NVDA, GOOGL, AMZN]
indexes: {S&P 500: ^GSPC, NASDAQ: ^IXIC, DOW: ^DJI}
commodities: {GOLD: GC=F, SILVER: SI=F, OIL (WTI): CL=F}
etfs: {SPY: SPY, QQQ: QQQ, GLD: GLD, SLV: SLV, USO: USO}
economic_events:
  - {date: "2026-05-14 14:00 UTC", title: "FOMC Minutes", importance: 3}
```

### 3. `data_fetcher.py` — Recopilación de datos (con retries)

| Fuente | Datos |
|---|---|
| Binance API (pública) | OHLCV 4h **y 1h** para BTC/ETH, funding rate, open interest, long/short ratio |
| Yahoo Finance (`yfinance`) | OHLCV diario para índices, stocks, commodities y ETFs |
| alternative.me | Fear & Greed Index |
| NewsAPI | Noticias de mercado del día (opcional) |
| Yahoo Finance | VIX, DXY |

Todas las llamadas HTTP pasan por `_http_get_json()` decorado con **tenacity** (3 intentos, backoff exponencial 1–8s) para sobrevivir a fallos transitorios. El calendario económico combina eventos manuales del YAML del día actual con keywords de NewsAPI.

Función principal: `collect_all_data()` → dict con todos los datos crudos (incluye `klines_1h` para crypto).

### 4. `analysis.py` — Motor técnico SMC/ICT
Detectores:
- **EMAs** (21, 50, 200) → `determine_trend_bias()`
- **RSI(14)**
- **Swing points** (`detect_swing_points`)
- **Estructura de mercado** (`detect_market_structure`): BOS y CHOCH
- **Order Blocks** (`detect_order_blocks`): zonas de demanda/oferta
- **Fair Value Gaps** (`detect_fvg`): bullish/bearish con flag `mitigated`
- **Liquidity pools + sweeps** (`detect_liquidity_pools`): EQH/EQL detectadas con tolerancia 0.1%, sweeps detectados cuando el wick perfora un EQH/EQL pero el cierre vuelve dentro del rango
- **CVD Divergence** (crypto)
- **Niveles S/R** (`calc_support_resistance`)
- **Multi-timeframe**: cuando `extra_data["klines_1h"]` está disponible, `analyze_asset` añade un bloque `ltf` con estructura, eventos y FVGs activos del 1h para refinar entradas

Función principal: `run_full_analysis(market_data)`.

### 5. `performance_tracker.py` — Continuidad día a día
- `build_previous_context()`: localiza el brief de ayer en `output/brief_<fecha>.txt`, extrae líneas relevantes (Sesgo, Setup, Entrada, SL, Target, Invalidación) y construye un bloque `=== CONTEXTO DEL BRIEF ANTERIOR ===` con instrucción para Claude de abrir cada activo con una línea de SEGUIMIENTO
- `summarize_current_prices(analysis)`: resumen compacto precio/sesgo/RSI de hoy

Esto convierte el brief en una serie con memoria, no en piezas sueltas.

### 6. `brief_generator.py` — Generación con Claude
- `format_analysis_for_prompt(analysis)`: serializa el análisis a texto compacto. Para crypto incluye OB, FVG (activos vs mitigados), EQH/EQL, sweeps, bloque LTF (1h). Para los demás surface el FVG activo más reciente y sweeps relevantes.
- `generate_brief(analysis)`: llama a Claude Sonnet 4.6 con el `SYSTEM_PROMPT` envuelto en `cache_control: {"type": "ephemeral"}`. Loguea `cache_read_input_tokens` / `cache_creation_input_tokens` para medir el ahorro.
- `markdown_to_plain(md)`: convierte el markdown a texto plano para `.txt` y Telegram.

Estructura del brief generado:
1. Panorama Macro (DXY, VIX, Fear & Greed, eventos económicos)
2. Crypto (BTC y ETH — análisis SMC detallado, incluye seguimiento del brief anterior)
3. Índices, 4. Top 5 Tech, 5. Commodities & Metals, 6. ETFs
7. Watchlist del día (top 3 setups), 8. Riesgos y alertas

### 7. `html_renderer.py` — Renderizado HTML
Markdown → HTML con JetBrains Mono + Inter, tema oscuro, tabla de contenidos. Guardado en `output/brief_YYYY-MM-DD.html`.

### 8. `telegram_delivery.py` y `discord_delivery.py` — Entrega
- **Telegram**: texto formateado en HTML (`<b>`, `<i>`, `<code>`), split a chunks de 4096 chars, HTML adjunto como documento.
- **Discord**: webhook con split a 1900 chars y adjunto HTML. No-op silencioso si `DISCORD_WEBHOOK_URL` no está configurado.

### 9. `market_cache.py` — Caché diario
Persiste el dict completo de `collect_all_data()` en `cache/market_data_<YYYY-MM-DD>.pkl`. Permite re-ejecutar el brief el mismo día sin volver a pegar a las APIs (debug, regeneración tras un fix). Bypass con `--fresh`.

### 10. `logging_setup.py` — Logging estructurado
Configura logging a archivo `logs/morning_brief_<fecha>.log` y stdout (forzando UTF-8 para evitar el `UnicodeEncodeError cp1252` típico de Windows). Sustituye los `print` previos.

### 11. `tests/test_analysis.py` — Tests pytest
10 tests sobre los detectores críticos (EMAs, RSI, swing points, market structure, order blocks, FVG activo y mitigado, liquidity pools + sweeps, trend bias). `pytest tests/` debe pasar antes de cualquier cambio en `analysis.py`.

### 12. `main.py` — Orquestador
```
python main.py              → Ejecuta el brief ahora (con caché del día si existe)
python main.py --fresh      → Ignora la caché y baja todo de las APIs
python main.py --schedule   → Scheduler interno (polling cada 30s hasta las 9:00)
python main.py --test       → Solo datos + análisis, sin llamar a Claude
python main.py --setup      → Muestra comando para Windows Task Scheduler
python main.py --no-telegram
python main.py --no-browser
```

---

## Instalación

```bash
git clone <repo>
cd morning-brief
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

pip install -r requirements.txt

copy .env.example .env
# Editar .env con tus API keys

python main.py --test       # Probar sin Claude API
python main.py              # Ejecutar brief completo
pytest tests/               # Verificar detectores SMC/ICT
```

---

## Variables de entorno

| Variable | Descripción | Requerido |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (console.anthropic.com) | Sí |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (@BotFather) | Recomendado |
| `TELEGRAM_CHAT_ID` | ID del chat donde entregar el brief | Recomendado |
| `DISCORD_WEBHOOK_URL` | Webhook de canal Discord (Server Settings → Integrations) | No |
| `NEWSAPI_KEY` | Noticias del día (newsapi.org — free tier) | No |

---

## Costo estimado

Solo Claude API tiene costo. Todas las demás fuentes de datos son gratuitas.

| Periodo | Costo (Sonnet 4.6) | Notas |
|---|---|---|
| Por ejecución | ~$0.04 | El system prompt va cacheado (`cache_read_input_tokens` ~10% del precio normal) |
| Mensual | ~$1.20 | |
| Anual | ~$14.60 | |

---

## Programación automática (Windows)

```bash
python main.py --setup
```
Imprime el comando PowerShell para registrar una tarea en Windows Task Scheduler que ejecuta el brief diariamente a las 9:00 AM.

---

## Tests

```bash
pytest tests/ -v
```
Cubre los detectores SMC/ICT con OHLCV sintético: EMAs, RSI, swings, BOS/CHOCH, Order Blocks, FVG (activo + mitigado), Equal Highs/Lows + sweeps, sesgo de tendencia. Diez tests, ejecutan en <1s.
