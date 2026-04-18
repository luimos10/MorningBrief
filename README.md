# Morning Market Brief

Brief matutino de mercados financieros generado automáticamente con Claude AI. Analiza crypto, índices, acciones, commodities y ETFs usando análisis técnico SMC/ICT, y entrega el resultado vía Telegram y HTML.

---

## Qué hace

Cada mañana a las 9:00 AM ejecuta un pipeline de 4 pasos:

1. **Recopila datos** de múltiples fuentes (Binance, Yahoo Finance, NewsAPI, etc.)
2. **Calcula indicadores técnicos** (EMAs, RSI, estructura SMC, Order Blocks, niveles S/R)
3. **Genera el brief** con Claude Sonnet 4.6 en formato markdown
4. **Entrega el brief** vía Telegram (texto + HTML adjunto) y guarda backup en disco

---

## Estructura del proyecto

```
morning-brief/
├── main.py              # Orquestador principal
├── config.py            # Configuración y API keys
├── data_fetcher.py      # Recopilación de datos de mercado
├── analysis.py          # Motor de análisis técnico SMC/ICT
├── brief_generator.py   # Generación del brief con Claude API
├── html_renderer.py     # Renderizado a HTML profesional
├── telegram_delivery.py # Envío a Telegram
├── setup_brief.py       # Setup interactivo para primera ejecución
├── requirements.txt     # Dependencias Python
├── .env                 # API keys (NO commitear)
├── .env.example         # Plantilla de variables de entorno
└── output/              # Briefs generados (HTML + TXT)
```

---

## Módulos paso a paso

### 1. `config.py` — Configuración central
Carga variables de entorno desde `.env` y define todos los parámetros del sistema:
- API keys (Anthropic, Telegram, NewsAPI)
- Activos a analizar: 2 cryptos, 3 índices, 5 stocks, 3 commodities, 5 ETFs
- Parámetros técnicos: periodos EMA (21/50/200), RSI (14), timeframe crypto (4h), lookback (100 días)
- Modelo Claude, max tokens, hora de ejecución del brief

### 2. `data_fetcher.py` — Recopilación de datos
Consulta fuentes públicas y gratuitas:

| Fuente | Datos |
|---|---|
| Binance API (pública) | OHLCV 4h para BTC/ETH, funding rate, open interest, long/short ratio |
| Yahoo Finance (`yfinance`) | OHLCV diario para índices, stocks, commodities y ETFs |
| alternative.me | Fear & Greed Index |
| NewsAPI | Noticias de mercado del día (opcional) |
| Stooq / Yahoo Finance | VIX, DXY |

Función principal: `collect_all_data()` → devuelve un dict con todos los datos crudos.

### 3. `analysis.py` — Motor técnico SMC/ICT
Recibe los datos crudos y calcula:
- **EMAs** (21, 50, 200) y sesgo (bullish/bearish/neutral)
- **RSI(14)** con clasificación (sobrecomprado/sobrevendido)
- **Swing points** (highs y lows) con lookback configurable
- **Estructura de mercado**: detecta BOS (Break of Structure) y CHOCH (Change of Character)
- **Order Blocks**: identifica zonas de acumulación bullish/bearish
- **CVD Divergence**: divergencia entre precio y volumen acumulado delta (crypto)
- **Niveles S/R**: soportes y resistencias basados en swings históricos

Función principal: `run_full_analysis(market_data)` → devuelve análisis completo por activo.

### 4. `brief_generator.py` — Generación con Claude
Dos responsabilidades:

- **`format_analysis_for_prompt(analysis)`**: convierte el dict de análisis a texto compacto para el prompt. Omite campos vacíos/N/A, redondea precios, compacta secciones no-crypto a 1 línea por activo para minimizar tokens de entrada.
- **`generate_brief(analysis)`**: llama a Claude Sonnet 4.6 con el system prompt de analista SMC/ICT y devuelve el brief en markdown (~2000-2500 tokens).
- **`markdown_to_plain(md)`**: convierte el markdown a texto plano para el backup .txt y Telegram.

Claude genera el brief siguiendo esta estructura:
1. Panorama Macro (DXY, VIX, Fear & Greed)
2. Crypto (BTC y ETH — análisis SMC detallado)
3. Índices (SPX, NDX, DOW)
4. Top 5 Tech stocks
5. Commodities & Metals
6. ETFs
7. Watchlist del día (top 3 setups)
8. Riesgos y alertas

### 5. `html_renderer.py` — Renderizado HTML
Convierte el markdown del brief a un archivo HTML profesional con:
- Fuentes JetBrains Mono + Inter
- Diseño oscuro optimizado para trading
- Tabla de contenidos navegable
- Guardado en `output/brief_YYYY-MM-DD.html`

### 6. `telegram_delivery.py` — Entrega
- Envía el texto del brief formateado en HTML de Telegram (soporta `<b>`, `<i>`, `<code>`)
- Si el mensaje supera 4096 caracteres, lo divide en chunks
- Adjunta el archivo HTML como documento descargable
- Fallback sin parse_mode si hay errores de formato

### 7. `main.py` — Orquestador
Punto de entrada del proyecto. Conecta todos los módulos y expone estos modos:

```
python main.py              → Ejecuta el brief ahora
python main.py --schedule   → Scheduler interno (polling cada 30s hasta las 9:00)
python main.py --test       → Solo datos + análisis, sin llamar a Claude
python main.py --setup      → Muestra comando para configurar Windows Task Scheduler
python main.py --no-telegram
python main.py --no-browser
```

### 8. `setup_brief.py` — Setup inicial
Script interactivo que guía la primera configuración: crea el archivo `.env`, verifica dependencias e imprime instrucciones para Windows Task Scheduler.

---

## Instalación

```bash
# 1. Clonar y crear entorno virtual
git clone <repo>
cd morning-brief
python -m venv venv
venv\Scripts\activate       # Windows
# source venv/bin/activate  # Mac/Linux

# 2. Instalar dependencias
pip install -r requirements.txt

# 3. Configurar variables de entorno
copy .env.example .env
# Editar .env con tus API keys

# 4. Probar sin Claude API
python main.py --test

# 5. Ejecutar brief completo
python main.py
```

---

## Variables de entorno

| Variable | Descripción | Requerido |
|---|---|---|
| `ANTHROPIC_API_KEY` | Claude API key (console.anthropic.com) | Sí |
| `TELEGRAM_BOT_TOKEN` | Token del bot de Telegram (@BotFather) | Recomendado |
| `TELEGRAM_CHAT_ID` | ID del chat donde entregar el brief | Recomendado |
| `NEWSAPI_KEY` | Noticias del día (newsapi.org — free tier) | No |

---

## Costo estimado

Solo Claude API tiene costo. Todas las demás fuentes de datos son gratuitas.

| Periodo | Costo (Sonnet 4.6) |
|---|---|
| Por ejecución | ~$0.04 |
| Mensual | ~$1.20 |
| Anual | ~$14.60 |

---

## Programación automática (Windows)

```bash
python main.py --setup
```
Imprime el comando PowerShell para registrar una tarea en Windows Task Scheduler que ejecuta el brief diariamente a las 9:00 AM.
