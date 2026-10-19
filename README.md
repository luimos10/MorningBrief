# Morning Market Brief

Brief matutino de mercados financieros generado automáticamente con Claude AI y **desplegado en la nube con GitHub Actions**. Cada día laborable, antes de la apertura de Wall Street, analiza crypto, índices, acciones, commodities y ETFs con análisis técnico SMC/ICT (BOS/CHOCH, Order Blocks, **Fair Value Gaps**, **liquidity sweeps**, multi-timeframe), incorpora el contexto del brief del día anterior y entrega el resultado vía Telegram, Discord y HTML.

---

## 1. Objetivo

Tener cada mañana, **sin encender la computadora ni intervención manual**, un informe profesional de mercados listo en el teléfono (Telegram) antes de que abra la bolsa de Nueva York (9:30 AM ET).

El proyecto resuelve tres cosas:

1. **Análisis técnico automatizado** de calidad institucional (metodología SMC/ICT) sobre ~20 activos.
2. **Redacción del brief** con Claude, con un tono consistente y continuidad narrativa día a día (cada brief "recuerda" los setups del anterior y les da SEGUIMIENTO).
3. **Ejecución 100% en la nube**: GitHub Actions lo corre solo, de lunes a viernes, ~9:00 AM ET, sin depender de tu PC.

El único costo es la Claude API (~$1/mes). Todas las demás fuentes de datos son gratuitas.

---

## 2. Cómo funciona (el pipeline de 4 pasos)

Cada ejecución corre `main.py`, que orquesta:

1. **Recopila datos** de múltiples fuentes (Binance 4h+1h, Yahoo Finance, alternative.me, NewsAPI) con retries y caché diario en disco.
2. **Calcula indicadores SMC/ICT**: EMAs, RSI, BOS/CHOCH, Order Blocks, FVG (con flag de mitigación), Equal Highs/Lows + sweeps de liquidez, niveles S/R, refinamiento multi-timeframe (1h dentro de 4h).
3. **Genera el brief** con Claude Sonnet 5.5 (cap de salida 16.000 tokens) — el system prompt va con `cache_control: ephemeral`. Si Claude devuelve `stop_reason=max_tokens`, el pipeline **falla** en vez de entregar un brief incompleto.
4. **Entrega el brief** vía Telegram (texto + HTML adjunto), Discord (si hay webhook), HTML local, y backup `.txt` en disco. El `.txt` se guarda **antes** de entregar, y una entrega fallida termina el proceso con exit ≠ 0 (job en rojo).

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
├── tests/                  # Tests pytest (analysis, brief_generator, telegram_delivery)
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
Carga variables de entorno (desde `.env` en local, o desde el entorno en la nube) y, si existe, sobrescribe los símbolos con `watchlist.yaml`. Define API keys, activos por defecto, parámetros técnicos (EMAs 21/50/200, RSI 14, timeframe crypto 4h, lookback 100 días), modelo Claude (`claude-sonnet-5-5`), cap de salida (`CLAUDE_MAX_TOKENS = 16000`) y hora de ejecución (`BRIEF_HOUR = 9`).

### `watchlist.yaml` — Watchlist configurable
Editar para añadir/quitar tickers sin tocar código:
```yaml
crypto: [BTCUSDT, ETHUSDT, SOLUSDT]
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
| Binance API (pública) | OHLCV 4h **y 1h** para BTC/ETH/SOL, funding rate, open interest, long/short ratio |
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
`format_analysis_for_prompt()` serializa el análisis a texto compacto. `generate_brief()` llama a Claude Sonnet 5.5 (cap de salida 16.000 tokens) con el `SYSTEM_PROMPT` envuelto en `cache_control: {"type": "ephemeral"}` y loguea tokens y uso de caché en cada run. `extract_brief_text()` toma el último bloque `type=text` de la respuesta (claude-sonnet-5-5 devuelve bloques `thinking` antes del texto) y falla con error claro si no hay ninguno. Si `stop_reason == "max_tokens"`, `generate_brief()` lanza `RuntimeError`: **nunca se entrega un brief truncado**. `markdown_to_plain()` convierte a texto plano para `.txt` y Telegram.

> Nota: el caché de prompt es efímero (TTL ~5 min), así que entre ejecuciones diarias lo normal es ver `cache_read=0`; se mantiene por si hay reintentos dentro de la ventana.

### `html_renderer.py`, `telegram_delivery.py`, `discord_delivery.py` — Entrega
- HTML: tema oscuro, JetBrains Mono + Inter, tabla de contenidos → `output/brief_YYYY-MM-DD.html`.
- Telegram: texto en HTML, split a 4096 chars, HTML adjunto como documento. Escapa `&`, `<` y `>` (el brief contiene comparaciones como "cierre 1h < 2,393" que rompían `parse_mode=HTML`), y si Telegram rechaza el HTML de un chunk reintenta **ese chunk** sin `parse_mode`, marcando fallo solo si el reintento también falla.
- Discord: webhook, split a 1900 chars, adjunto HTML. No-op (éxito) si `DISCORD_WEBHOOK_URL` no está configurado.
- Fallos visibles: `main.py` verifica el retorno de cada entrega y termina con exit ≠ 0 si algo falló → job en rojo en Actions.

### `market_cache.py`, `logging_setup.py`, `tests/`
- Caché diario del dict de `collect_all_data()` en `cache/market_data_<fecha>.pkl` (bypass con `--fresh`).
- Logging a `logs/morning_brief_<fecha>.log` + stdout en UTF-8.
- 23 tests pytest: detectores SMC/ICT, extracción de texto y truncación en `brief_generator`, y escape/fallback de entrega en `telegram_delivery` (`pytest tests/`).

### `main.py` — Orquestador (CLI)
```
python main.py              → Ejecuta el brief ahora (con caché del día si existe)
python main.py --fresh      → Ignora la caché y baja todo de las APIs
python main.py --schedule   → Scheduler interno por polling (uso local)
python main.py --test       → Solo datos + análisis, sin llamar a Claude
python main.py --no-telegram
python main.py --no-browser → No abre el navegador (obligatorio en la nube)
```

En cualquier modo, un fallo del pipeline (truncación de Claude o entrega fallida) sale con exit ≠ 0, para que GitHub Actions marque el job en rojo.

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
pytest tests/                  # Correr la suite completa (23 tests)
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

- **Horario / puntualidad:** el workflow **solo** acepta `workflow_dispatch` (no tiene `schedule`). Lo dispara un **cron externo (cron-job.org)** que llama a la API de GitHub a las ~8:45 America/New_York; el servicio externo resuelve el DST. Se abandonó el scheduler de GitHub porque es best-effort (runs con horas de retraso o descartados) y el viejo *guard* de ventana horaria terminaba salteando el envío dejando el job en verde.
- **Fallos visibles:** `python main.py --no-browser --fresh` sale con exit ≠ 0 si Claude trunca el brief (`stop_reason=max_tokens`) o si una entrega configurada (Telegram/Discord) falla → el job queda en rojo en Actions en vez de pasar desapercibido.
- **Continuidad:** como cada ejecución corre en una VM nueva, el `.txt` se escribe en disco **antes** de entregar y el último paso del workflow commitea `output/brief_<fecha>.txt` de vuelta al repo con `if: always()` (corre aunque la entrega haya fallado; el job igual queda rojo). Al día siguiente el `checkout` lo trae y `performance_tracker.py` lo encuentra → el SEGUIMIENTO funciona en la nube.
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

En la pestaña **Actions** → workflow **"Morning Market Brief"** → botón **Run workflow** (`workflow_dispatch`). Ya no hay *guard* horario: puedes probar a cualquier hora y el run ejecuta de punta a punta.

Para el disparo diario, configura en cron-job.org un job que haga `POST` a:

```
https://api.github.com/repos/<owner>/<repo>/actions/workflows/morning-brief.yml/dispatches
body: {"ref": "main"}
```

con un token fine-grained de GitHub con permiso **Actions: write**, programado a las 8:45 America/New_York.

### Paso 4 — Verificar

- En **Actions** revisa que el job termine en verde (rojo = truncación de Claude o entrega fallida) y mira los logs del paso "Generate & deliver brief".
- Confirma que llegó el mensaje a **Telegram** (y Discord si lo configuraste).
- Verifica que aparece un commit automático `brief: <fecha> [skip ci]` con el `.txt` del día (se commitea incluso si el run quedó rojo).

A partir de ahí, el brief llega solo cada mañana laborable.

### Costo

~22 ejecuciones/mes ≈ **~$1/mes** (solo Claude API). Un run típico usa ~3.6k tokens de entrada y ~11.5k de salida (el cap de 16k es un techo, solo se paga lo que se genera). GitHub Actions entra dentro del free tier (ilimitado en repos públicos; 2000 min/mes en privados).

---

## 7. Tests

```bash
pytest tests/ -v
```
23 tests en <2s, sin red ni API (todo mockeado):
- **SMC/ICT** con OHLCV sintético: EMAs, RSI, swings, BOS/CHOCH, Order Blocks, FVG (activo + mitigado), Equal Highs/Lows + sweeps, sesgo de tendencia.
- **`brief_generator`**: `extract_brief_text()` con bloques `thinking` (regresión del fallo del 12/10) y truncación (`stop_reason=max_tokens` → `RuntimeError`).
- **`telegram_delivery`**: escape de HTML y fallback sin `parse_mode` (400 → retry ok cuenta como enviado).

Deben pasar antes de cualquier cambio en `analysis.py`.
