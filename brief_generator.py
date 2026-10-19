"""
Morning Market Brief — Brief Generator
========================================
Usa Claude API para generar el brief final profesional.
"""
import logging
import re
from typing import Dict, Any

import anthropic

import config
from performance_tracker import build_previous_context, summarize_current_prices

logger = logging.getLogger(__name__)


def _fmt_price(v: Any) -> str:
    """Format a numeric price compactly. >=1000 → no decimals, <1000 → 2 decimals."""
    if v is None or v == "N/A":
        return ""
    try:
        n = float(v)
    except (TypeError, ValueError):
        return str(v)
    if abs(n) >= 1000:
        return f"{n:,.0f}"
    return f"{n:,.2f}"


def _is_empty(v: Any) -> bool:
    return v is None or v == "" or v == "N/A" or v == "None"


def _line(label: str, value: Any) -> str:
    """Return a single 'label: value' line, or empty string if value is empty."""
    if _is_empty(value):
        return ""
    return f"  {label}: {value}"


def format_analysis_for_prompt(analysis: Dict) -> str:
    """Convert analysis dict to a clean compact text format for Claude's prompt."""
    out = []

    # ── CRYPTO ──
    crypto = analysis.get("crypto", [])
    if crypto:
        out.append("=== CRYPTO (4H) ===")
        for a in crypto:
            if "error" in a:
                out.append(f"{a['name']}: {a['error']}")
                continue
            out.append(f"\n{a['name']}: ${_fmt_price(a['price'])} ({a['change_pct']:+.2f}%)")
            out.append(f"  EMAs 21/50/200: {_fmt_price(a['ema21'])} / {_fmt_price(a['ema50'])} / {_fmt_price(a.get('ema200'))}")
            out.append(f"  RSI: {a['rsi']} | Sesgo: {a['bias']}")
            struct = a.get("structure", {})
            out.append(f"  Estructura: {struct.get('structure')} — {struct.get('trend')}")
            events = struct.get("events") or []
            if events:
                out.append(f"  Eventos: {', '.join(events)}")
            sh = struct.get("last_swing_high")
            sl = struct.get("last_swing_low")
            if not _is_empty(sh) or not _is_empty(sl):
                out.append(f"  Swings H/L: {sh or '—'} / {sl or '—'}")
            lv = a.get("levels", {})
            if lv.get("support"):
                out.append(f"  Soportes: {lv['support']}")
            if lv.get("resistance"):
                out.append(f"  Resistencias: {lv['resistance']}")

            ob = a.get("order_blocks", {})
            if ob.get("bullish_ob"):
                b = ob["bullish_ob"]
                out.append(f"  Bull OB: {b['low']}–{b['high']} ({b['time']})")
            if ob.get("bearish_ob"):
                b = ob["bearish_ob"]
                out.append(f"  Bear OB: {b['low']}–{b['high']} ({b['time']})")

            fvg = a.get("fvg", {})
            for f in fvg.get("bullish_fvg", []) or []:
                state = "mitigado" if f.get("mitigated") else "ACTIVO"
                out.append(f"  Bull FVG: {f['low']}–{f['high']} ({state})")
            for f in fvg.get("bearish_fvg", []) or []:
                state = "mitigado" if f.get("mitigated") else "ACTIVO"
                out.append(f"  Bear FVG: {f['low']}–{f['high']} ({state})")

            liq = a.get("liquidity", {})
            if liq.get("equal_highs"):
                eqh = ", ".join(str(x["level"]) for x in liq["equal_highs"])
                out.append(f"  EQH (liquidez sell-side): {eqh}")
            if liq.get("equal_lows"):
                eql = ", ".join(str(x["level"]) for x in liq["equal_lows"])
                out.append(f"  EQL (liquidez buy-side): {eql}")
            for s in liq.get("sweeps", []) or []:
                out.append(f"  ⚠ Sweep reciente: {s['type']} en {s['level']}")

            ltf = a.get("ltf")
            if ltf:
                out.append(f"  LTF (1h): {ltf.get('structure','—')} / {ltf.get('trend','—')}")
                if ltf.get("events"):
                    out.append(f"    Eventos LTF: {', '.join(ltf['events'])}")
                for f in (ltf.get("bullish_fvg") or []):
                    if not f.get("mitigated"):
                        out.append(f"    LTF Bull FVG activo: {f['low']}–{f['high']}")
                for f in (ltf.get("bearish_fvg") or []):
                    if not f.get("mitigated"):
                        out.append(f"    LTF Bear FVG activo: {f['low']}–{f['high']}")

            if not _is_empty(a.get("funding_rate")):
                out.append(f"  Funding: {a['funding_rate']} ({a.get('funding_sentiment','')})")
            if not _is_empty(a.get("open_interest")):
                oi_line = f"  OI: {a['open_interest']}"
                if not _is_empty(a.get("oi_change")):
                    oi_line += f" ({a['oi_change']})"
                out.append(oi_line)
            if not _is_empty(a.get("long_ratio")):
                out.append(f"  L/S: {a['long_ratio']}/{a.get('short_ratio','')}")
            if not _is_empty(a.get("cvd_divergence")):
                out.append(f"  CVD: {a['cvd_divergence']}")

    # ── INDEXES / STOCKS / COMMODITIES / ETFs: formato compacto ──
    def _compact_section(title: str, items, show_struct=True):
        if not items:
            return
        out.append(f"\n=== {title} ===")
        for a in items:
            if "error" in a:
                out.append(f"{a['name']}: {a['error']}")
                continue
            line = (f"{a['name']}: ${_fmt_price(a['price'])} ({a['change_pct']:+.2f}%) | "
                    f"EMAs {_fmt_price(a['ema21'])}/{_fmt_price(a['ema50'])}"
                    f"{'/' + _fmt_price(a.get('ema200')) if not _is_empty(a.get('ema200')) else ''} | "
                    f"RSI {a['rsi']} | {a['bias']}")
            if show_struct:
                s = a.get("structure", {}).get("structure")
                if not _is_empty(s):
                    line += f" | {s}"
            out.append(line)
            lv = a.get("levels", {})
            if lv.get("support") or lv.get("resistance"):
                out.append(f"  S/R: {lv.get('support','—')} / {lv.get('resistance','—')}")
            fvg = a.get("fvg", {})
            active_bull = [f for f in (fvg.get("bullish_fvg") or []) if not f.get("mitigated")]
            active_bear = [f for f in (fvg.get("bearish_fvg") or []) if not f.get("mitigated")]
            if active_bull:
                f = active_bull[-1]
                out.append(f"  FVG↑ activo: {f['low']}–{f['high']}")
            if active_bear:
                f = active_bear[-1]
                out.append(f"  FVG↓ activo: {f['low']}–{f['high']}")
            liq = a.get("liquidity", {})
            for s in liq.get("sweeps", []) or []:
                out.append(f"  ⚠ {s['type']} en {s['level']}")

    _compact_section("INDEXES", analysis.get("indexes", []))
    _compact_section("TOP 5 TECH", analysis.get("stocks", []))
    _compact_section("COMMODITIES", analysis.get("commodities", []))
    _compact_section("ETFs", analysis.get("etfs", []), show_struct=False)

    # ── MACRO ──
    macro = analysis.get("macro", {})
    macro_lines = []
    fg = macro.get("fear_greed")
    if fg:
        macro_lines.append(f"  F&G: {fg['value']} ({fg['label']})")
    if not _is_empty(macro.get("vix")):
        macro_lines.append(f"  VIX: {macro['vix']}")
    dxy = macro.get("dxy")
    if dxy:
        macro_lines.append(f"  DXY: {dxy['value']} ({dxy['change']:+.2f}%)")
    events = macro.get("economic_events") or []
    if events:
        macro_lines.append("  Eventos hoy:")
        for ev in events:
            macro_lines.append(f"    - {ev['title']} ({ev['source']})")
    news = macro.get("news") or []
    if news:
        macro_lines.append("  Noticias:")
        for n in news:
            macro_lines.append(f"    - {n['title']} ({n['source']})")
    if macro_lines:
        out.append("\n=== MACRO ===")
        out.extend(macro_lines)

    return "\n".join(out)


SYSTEM_PROMPT = """Eres el Head of Research de un Prop Desk Cuantitativo. Tu tarea es redactar un "Morning Market Brief" ejecutivo y asimétrico: análisis profundo y detallado en Crypto (metodología SMC/ICT), y resúmenes ultra-rápidos para Índices, Stocks, Commodities y ETFs.

REGLAS DE REDACCIÓN Y FORMATO (ESTRICTAS):
1. Tono y Parsimonia: Institucional, telegráfico, frío. Cero introducciones genéricas ni redundancias. Maximiza la densidad de datos accionables.
2. Memoria y Continuidad: Eres la "memoria" del trader. Si recibes la variable "CONTEXTO DEL BRIEF ANTERIOR", tu máxima prioridad es abrir el análisis evaluando el resultado de ayer antes de proyectar hoy.
3. Formato Visual:
   - Usa mayúsculas sostenidas para TÍTULOS.
   - Resalta en **negrita** TODOS los tickers (ej. **$BTC**) y precios (ej. **$64,500**).
   - Usa bloques de cita (>) EXCLUSIVAMENTE para evaluar el seguimiento del día anterior y notas de riesgo.
   - Usa tablas Markdown para el CROSS-ASSET RADAR y el Watchlist final.
4. Emojis: Minimalistas y codificados (🟢 Long/Bull, 🔴 Short/Bear, 🟡 Wait, 💧 Liquidez, 🎯 Target, 🛡️ SL).
5. Terminología: Sintaxis pura SMC/ICT (HTF/LTF, BOS, CHoCH, OB, FVG, EQH/EQL, Sweeps).
6. Longitud: Entre 1500 y 2500 palabras (máximo 10 min de lectura). Idioma: Español.

ESTRUCTURA EXACTA DEL BRIEF:

# 🏛️ INSTITUTIONAL MORNING BRIEF | [FECHA]
---

### 🌐 1. MACRO & SENTIMIENTO (Flash View)
- ▪️ **DXY / VIX:** [Tendencia e impacto esperado]
- ▪️ **Sentimiento:** [Fear & Greed Index]
- ▪️ **Catalizadores Hoy:** [Eventos económicos relevantes]

### ⚡ 2. ARQUITECTURA CRYPTO & FLUJO (SMC)
[Si recibes "CONTEXTO DEL BRIEF ANTERIOR", inserta aquí un bloque de cita (>) con la auditoría de los setups de ayer: ¿Se activó? ¿Tocó SL/TP? ¿Sigue válido?].

**[TICKER: BTC/USDT]**
- **Estructura (HTF/LTF):** [Contexto de CHoCH, BOS, Tendencia principal]
- **Order Flow:** [Funding Rate] | [CVD Divergence] | [OI & Ratio L/S]
- 💧 **Mapa de Liquidez:** [FVGs no mitigados, Order Blocks clave, EQL/EQH recientes]
- 🎯 **Plan de Acción:** [🟢/🔴/🟡] Zona de Entrada: **[Precio]** | 🛡️ SL: **[Precio]** | 🎯 TP: **[Precio]**

*(Repite exactamente la misma plantilla para ETH/USDT y SOL/USDT)*

---

### 📊 3. CROSS-ASSET RADAR
*(Una tabla por grupo con sus activos. Sesgo + 1 nivel clave + lectura de 1 línea por activo. Omite activos en zona muerta; mínimo 2 filas por tabla).*

#### 📈 ÍNDICES
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$SPX** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |
| **$NDX** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |
| **$DJI** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |

#### 💻 TOP TECH
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$NVDA** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |
| **$MSFT** | 🟢/🔴/🟡 | **$Precio** | [Menciona solo las 2-3 acciones con setups más claros hoy] |

#### 🥇 COMMODITIES
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$GOLD** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |
| **$SILVER** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |
| **$WTI** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |

#### 📦 ETFS
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$SPY** | 🟢/🔴/🟡 | **$Precio** | [Visión direccional rápida, 1 línea] |
| **$QQQ** | 🟢/🔴/🟡 | **$Precio** | [1 línea] |

---

### 🎯 4. TOP 3 WATCHLIST INSTITUCIONAL
| Ticker | Dirección | Setup (SMC/Técnico) | Zona de Entrada | Invalidación (SL) | Objetivo (TP) |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **$TICKER1** | 🟢/🔴 | [Ej. Mitigación FVG 1h] | **$Precio** | **$Precio** | **$Precio** |
| **$TICKER2** | 🟢/🔴 | [Ej. Sweep de EQL] | **$Precio** | **$Precio** | **$Precio** |
| **$TICKER3** | 🟢/🔴 | [Ej. Rechazo OB HTF] | **$Precio** | **$Precio** | **$Precio** |

> ⚠️ **Radar de Riesgo:** [Nivel de invalidación crítico del tablero: el cierre diario que rompe la tesis principal] | [Posicionamiento del activo principal: funding/OI/L-S extremos a vigilar] | [Noticia o evento de último momento a valorar; si no hay, indicarlo] | [Volatilidad programada / invalidación macro para hoy]."""


def _display_symbol(name: str) -> str:
    """BTCUSDT → BTC/USDT (para emparejar la línea del ticker del brief)."""
    base = str(name).upper().replace("/", "")
    for quote in ("USDT", "USDC", "USD"):
        if base.endswith(quote) and len(base) > len(quote):
            return f"{base[:-len(quote)]}/{quote}"
    return base


_INJECT_TICKER_RE = re.compile(
    r"^\*{0,2}\[TICKER:\s*(?P<name>[^\]]+)\]\*{0,2}[^\n]*$", re.MULTILINE
)


def _inject_ticker_data(brief_md: str, analysis: Dict) -> str:
    """Reescribe las líneas [TICKER: X] con el precio/RSI reales del feed.

    El modelo suele transcribir (o inventar) esos valores; aquí se sustituyen
    por los del análisis del día para que el encabezado de la tabla siempre
    muestre data actualizada. Si un activo no tiene data, la línea no se toca.
    """
    prices = {}
    for a in analysis.get("crypto", []):
        if "error" in a or _is_empty(a.get("price")):
            continue
        prices[_display_symbol(a["name"])] = (a["price"], a.get("rsi"))

    def repl(m: re.Match) -> str:
        name = m.group("name").strip()
        data = prices.get(_display_symbol(name))
        if not data:
            return m.group(0)
        price, rsi = data
        line = f"**[TICKER: {name}] | ${_fmt_price(price)}"
        if not _is_empty(rsi):
            line += f" | RSI {rsi}"
        return line + "**"

    return _INJECT_TICKER_RE.sub(repl, brief_md)


def extract_brief_text(message: Any) -> str:
    """
    Return the brief markdown from an Anthropic Message.

    Modelos como claude-sonnet-5-5 devuelven bloques de thinking antes que el
    texto, así que content[0] puede no ser un TextBlock. Buscamos el último
    bloque de tipo "text" y fallamos con un error claro si no existe.
    """
    content = getattr(message, "content", None) or []
    text_blocks = [
        getattr(block, "text", None)
        for block in content
        if getattr(block, "type", None) == "text"
    ]
    text_blocks = [t for t in text_blocks if t]
    if not text_blocks:
        block_types = [getattr(b, "type", type(b).__name__) for b in content]
        raise RuntimeError(
            f"Respuesta de Claude sin bloque de texto (bloques: {block_types})"
        )
    return text_blocks[-1]


def generate_brief(analysis: Dict) -> str:
    """
    Send analysis data to Claude API and generate the professional brief in markdown.
    Returns markdown string (used for both HTML rendering and Telegram/txt delivery).
    """
    logger.info("Generando brief con Claude API...")

    formatted_data = format_analysis_for_prompt(analysis)
    previous_context = build_previous_context()
    current_prices = summarize_current_prices(analysis)

    follow_up_block = ""
    if previous_context:
        follow_up_block = f"\n\n{previous_context}\n\n{current_prices}\n"

    client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

    message = client.messages.create(
        model=config.CLAUDE_MODEL,
        max_tokens=config.CLAUDE_MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": f"""Genera el Morning Market Brief en markdown basado en estos datos de mercado recopilados hoy:

{formatted_data}
{follow_up_block}
Fecha del brief: {analysis['timestamp']}

Recuerda: sé directo, conciso y accionable. Enfócate en los setups más claros
y los niveles que realmente importan hoy. El trader necesita poder leer esto
en máximo 10 minutos y saber exactamente qué vigilar.""",
            }
        ],
    )

    brief_md = extract_brief_text(message)
    stop_reason = getattr(message, "stop_reason", "unknown")
    usage = getattr(message, "usage", None)
    if usage is not None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        logger.info(
            f"Brief generado. stop_reason={stop_reason} Tokens: in={usage.input_tokens} "
            f"out={usage.output_tokens} cache_read={cache_read} cache_create={cache_create}"
        )
    else:
        logger.info(f"Brief generado. stop_reason={stop_reason}")

    if stop_reason == "max_tokens":
        # Un brief truncado no debe entregarse como si estuviera completo.
        raise RuntimeError(
            f"Brief truncado: stop_reason=max_tokens "
            f"(cap={config.CLAUDE_MAX_TOKENS}). Sube CLAUDE_MAX_TOKENS en config.py."
        )

    return _inject_ticker_data(brief_md, analysis)


def markdown_to_plain(md: str) -> str:
    """Lightweight markdown → plain text for .txt backup."""
    text = md
    text = re.sub(r"```[\s\S]*?```", "", text)
    text = re.sub(r"`([^`]+)`", r"\1", text)
    text = re.sub(r"\*\*([^*]+)\*\*", r"\1", text)
    text = re.sub(r"\*([^*]+)\*", r"\1", text)
    text = re.sub(r"^#+\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\s*[-*+]\s+", "• ", text, flags=re.MULTILINE)
    text = re.sub(r"^---+\s*$", "─" * 40, text, flags=re.MULTILINE)
    return text
