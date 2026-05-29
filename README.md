# Morning Market Brief

Brief matutino de mercados financieros generado automáticamente con Claude AI y **desplegado en la nube con GitHub Actions**. Cada día laborable, antes de la apertura de Wall Street, analiza crypto, índices, acciones, commodities y ETFs con análisis técnico SMC/ICT (BOS/CHOCH, Order Blocks, **Fair Value Gaps**, **liquidity sweeps**, multi-timeframe), incorpora el contexto del brief del día anterior y entrega el resultado vía Telegram, Discord y HTML.

---

## 1. Objetivo

Tener cada mañana, **sin encender la computadora ni intervención manual**, un informe profesional de mercados listo en el teléfono (Telegram) antes de que abra la bolsa de Nueva York (9:30 AM ET).

El proyecto resuelve tres cosas:

1. **Análisis técnico automatizado** de calidad institucional (metodología SMC/ICT) sobre ~20 activos.
2. **Redacción del brief** con Claude, con un tono consistente y continuidad narrativa día a día (cada brief "recuerda" los setups del anterior y les da SEGUIMIENTO).
3. **Ejecución 100% en la nube**: GitHub Actions lo corre solo, de lunes a viernes, ~9:00 AM ET, sin depender de tu PC.

El único costo es la Claude API (~$0.90/mes). Todas las demás fuentes de datos son gratuitas.

---

## 2. Cómo funciona (el pipeline de 4 pasos)

Cada ejecución corre `main.py`, que orquesta:

1. **Recopila datos** de múltiples fuentes (Binance 4h+1h, Yahoo Finance, alternative.me, NewsAPI) con retries y caché diario en disco.
2. **Calcula indicadores SMC/ICT**: EMAs, RSI, BOS/CHOCH, Order Blocks, FVG (con flag de mitigación), Equal Highs/Lows + sweeps de liquidez, niveles S/R, refinamiento multi-timeframe (1h dentro de 4h).
3. **Genera el brief** con Claude Sonnet 4.6 — el system prompt va con `cache_control: ephemeral` para reducir coste.
4. **Entrega el brief** vía Telegram (texto + HTML adjunto), Discord (si hay webhook), HTML local, y backup `.txt` en disco.

Cada brief incluye una línea de **SEGUIMIENTO** que compara los setups del día anterior con los precios actuales (¿se activó la entrada? ¿saltó el SL? ¿llegó al target?), dando continuidad narrativa día a día.

---

## 3. Arquitectura del proyecto

```
morning-brief/
├── .github/workflows/
│   └── morning-brief.yml   # ★ Despliegue en la nube (GitHub Actions)
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
├── .env.example            # Plantilla de variables (copiar a .env en local)
├── cache/                  # Cachés diarios (ignorado por git)
├── logs/                   # Logs diarios (ignorado por git)
└── output/                 # Briefs generados — solo los .txt se versionan
```

> **Nota git:** `cache/`, `logs/`, `.env` y `output/*.html` están en `.gitignore`. Los `output/brief_*.txt` **sí** se versionan: son livianos y son los que dan continuidad día a día en la nube (ver sección 6).

---

## 4. Módulos paso a paso

### `config.py` — Configuración central
Carga variables de entorno (desde `.env` en local, o desde el entorno en la nube) y, si existe, sobrescribe los símbolos con `watchlist.yaml`. Define API keys, activos por defecto, parámetros técnicos (EMAs 21/50/200, RSI 14, timeframe crypto 4h, lookback 100 días), modelo Claude (`claude-sonnet-4-6`), max tokens (8192) y hora de ejecución (`BRIEF_HOUR = 9`).

### `watchlist.yaml` — Watchlist configurable
Editar para añadir/quitar tickers sin tocar código:
```yaml
crypto: [BTCUSDT, ETHUSDT]
stocks: [AAPL, MSFT, NVDA, GOOGL, AMZN]
indexes: {S&P 500: ^GSPC, NASDAQ: ^IXIC, DOW: ^DJI}
commodities: {GOLD: GC=F, SILVER: SI=F, OIL (WTI): CL=F}
etfs: {SPY: SPY, QQQ: QQQ, GLD: GLD, SLV: SLV, USO: USO}
economic_events:
  - {date: "2026-05-14 14:00 UTC", title: "FOMC Minutes", importance: 3}
```

### `data_fetcher.py` — Recopilación de datos (con retries)

| Fuente | Datos |
|---|---|
| Binance API (pública) | OHLCV 4h **y 1h** para BTC/ETH, funding rate, open interest, long/short ratio |
| Yahoo Finance (`yfinance`) | OHLCV diario para índices, stocks, commodities y ETFs; VIX y DXY |
| alternative.me | Fear & Greed Index |
| NewsAPI | Noticias de mercado del día (opcional) |

Todas las llamadas HTTP pasan por `_http_get_json()` decorado con **tenacity** (3 intentos, backoff exponencial 1–8s). Función principal: `collect_all_data()`.

### `analysis.py` — Motor técnico SMC/ICT
Detectores: EMAs → `determine_trend_bias()`, RSI(14), swing points, BOS/CHOCH (`detect_market_structure`), Order Blocks, Fair Value Gaps (con flag `mitigated`), liquidity pools + sweeps (EQH/EQL con tolerancia 0.1%), CVD divergence (crypto), niveles S/R, y refinamiento multi-timeframe (1h dentro de 4h). Función principal: `run_full_analysis(market_data)`.

### `performance_tracker.py` — Continuidad día a día
- `build_previous_context()`: localiza el brief de ayer en `output/brief_<fecha>.txt`, extrae líneas relevantes (Sesgo, Setup, Entrada, SL, Target, Invalidación) y arma el bloque `=== CONTEXTO DEL BRIEF ANTERIOR ===`.
- `summarize_current_prices(analysis)`: resumen compacto precio/sesgo/RSI de hoy.

> Este módulo es la razón por la que versionamos `output/brief_*.txt`: en la nube cada ejecución arranca en una VM limpia, así que el brief de ayer tiene que venir del repositorio (ver sección 6).

### `brief_generator.py` — Generación con Claude
`format_analysis_for_prompt()` serializa el análisis a texto compacto. `generate_brief()` llama a Claude Sonnet 4.6 con el `SYSTEM_PROMPT` envuelto en `cache_control: {"type": "ephemeral"}` y loguea `cache_read_input_tokens` para medir el ahorro. `markdown_to_plain()` convierte a texto plano para `.txt` y Telegram.

### `html_renderer.py`, `telegram_delivery.py`, `discord_delivery.py` — Entrega
- HTML: tema oscuro, JetBrains Mono + Inter, tabla de contenidos → `output/brief_YYYY-MM-DD.html`.
- Telegram: texto en HTML, split a 4096 chars, HTML adjunto como documento.
- Discord: webhook, split a 1900 chars, adjunto HTML. No-op silencioso si `DISCORD_WEBHOOK_URL` no está.

### `market_cache.py`, `logging_setup.py`, `tests/`
- Caché diario del dict de `collect_all_data()` en `cache/market_data_<fecha>.pkl` (bypass con `--fresh`).
- Logging a `logs/morning_brief_<fecha>.log` + stdout en UTF-8.
- 10 tests pytest sobre los detectores SMC/ICT (`pytest tests/`).

### `main.py` — Orquestador (CLI)
```
python main.py              → Ejecuta el brief ahora (con caché del día si existe)
python main.py --fresh      → Ignora la caché y baja todo de las APIs
python main.py --schedule   → Scheduler interno por polling (uso local)
python main.py --test       → Solo datos + análisis, sin llamar a Claude
python main.py --no-telegram
python main.py --no-browser → No abre el navegador (obligatorio en la nube)
```

---

## 5. Instalación y uso en local

```bash
git clone <repo>
cd morning-brief
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # Mac/Linux

pip install -r requirements.txt

copy .env.example .env         # Windows  (cp en Mac/Linux)
# Editar .env con tus API keys

python main.py --test          # Probar sin gastar Claude API
python main.py                 # Ejecutar brief completo
pytest tests/                  # Verificar detectores SMC/ICT
```

### Variables de entorno

| Variable | Descripción | Requerido |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (console.anthropic.com) | Sí |
| `TELEGRAM_BOT_TOKEN` | Token del bot (@BotFather) | Recomendado |
| `TELEGRAM_CHAT_ID` | Chat donde entregar el brief | Recomendado |
| `DISCORD_WEBHOOK_URL` | Webhook de canal Discord | No |
| `NEWSAPI_KEY` | Noticias del día (newsapi.org free tier) | No |

En local estas variables viven en `.env` (que **nunca** se commitea). En la nube se configuran como GitHub Secrets (sección 6).

---

## 6. Despliegue en la nube con GitHub Actions (paso a paso)

El objetivo: que GitHub corra el brief solo, de **lunes a viernes ~9:00 AM ET** (antes de la apertura), sin tu PC.

### Cómo está resuelto

- **Horario / DST:** el cron de GitHub es UTC y no respeta el horario de verano de EE.UU. (ET = UTC-4 en verano, UTC-5 en invierno). Por eso el workflow dispara **dos crons** (13:00 y 14:00 UTC) y un paso *guard* en Python usa `zoneinfo("America/New_York")` para continuar solo si en Nueva York son ~9 AM. El run "equivocado" aborta en segundos sin gastar API. Resultado: **9:00 ET exacto todo el año, sin mantenimiento**.
- **Continuidad:** como cada ejecución corre en una VM nueva, el último paso del workflow hace `commit` del `output/brief_<fecha>.txt` de vuelta al repo. Al día siguiente el `checkout` lo trae y `performance_tracker.py` lo encuentra → el SEGUIMIENTO funciona en la nube.
- **Sin navegador:** se ejecuta con `--no-browser` (el `webbrowser.open()` no aplica en CI).
- **Secretos:** se inyectan como variables de entorno desde GitHub Secrets; `config.py` los lee directamente, sin necesidad de `.env`.

### Paso 1 — Configurar los Secrets

En GitHub: **Settings → Secrets and variables → Actions → New repository secret**. Crear:

| Secret | Requerido |
|---|---|
| `ANTHROPIC_API_KEY` | Sí |
| `TELEGRAM_BOT_TOKEN` | Recomendado |
| `TELEGRAM_CHAT_ID` | Recomendado |
| `NEWSAPI_KEY` | Opcional |
| `DISCORD_WEBHOOK_URL` | Opcional |

### Paso 2 — Subir el repo

```bash
git add .
git commit -m "Deploy: GitHub Actions + limpieza de artefactos"
git push
```

El workflow ya vive en `.github/workflows/morning-brief.yml`, así que GitHub lo detecta automáticamente al hacer push.

### Paso 3 — Probar manualmente

En la pestaña **Actions** → workflow **"Morning Market Brief"** → botón **Run workflow** (`workflow_dispatch`). Esto permite probar sin esperar a las 9 ET.

> En disparo manual fuera de la ventana 8:30–9:30 ET el *guard* abortará el run (es lo esperado). Para una prueba real de extremo a extremo, córrelo dentro de esa franja o ajusta temporalmente el guard.

### Paso 4 — Verificar

- En **Actions** revisa que el job termine en verde y mira los logs del paso "Generate & deliver brief".
- Confirma que llegó el mensaje a **Telegram** (y Discord si lo configuraste).
- Verifica que aparece un commit automático `brief: <fecha>` con el `.txt` del día.

A partir de ahí, el brief llega solo cada mañana laborable.

### Costo

~22 ejecuciones/mes × ~$0.04 ≈ **$0.90/mes** (solo Claude API). Los runs que aborta el guard son gratis. GitHub Actions entra dentro del free tier (ilimitado en repos públicos; 2000 min/mes en privados).

---

## 7. Tests

```bash
pytest tests/ -v
```
Cubre los detectores SMC/ICT con OHLCV sintético: EMAs, RSI, swings, BOS/CHOCH, Order Blocks, FVG (activo + mitigado), Equal Highs/Lows + sweeps, sesgo de tendencia. Diez tests, ejecutan en <1s. Deben pasar antes de cualquier cambio en `analysis.py`.
