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


SYSTEM_PROMPT = """Eres un analista de mercados financieros profesional. Tu tarea es generar un brief matutino
conciso y accionable para un trader que opera perpetual futures en crypto (SMC/ICT) y también monitorea
stocks, índices, commodities y ETFs.

REGLAS DEL BRIEF:
1. Máximo 7-10 minutos de lectura (aprox 1500-2000 palabras)
2. Usa terminología SMC/ICT: BOS, CHOCH, Order Blocks, Fair Value Gap, Liquidity
3. Para cada activo incluye: sesgo del día, niveles clave a vigilar, y posible setup
4. Sé directo y conciso — el trader necesita info accionable, no teoría
5. Incluye una sección de "Watchlist del día" con los 3 mejores setups
6. Escribe en español
7. Usa emojis moderadamente para escaneo rápido (🟢🔴🟡⚠📊)
8. Genera markdown: headers ##, **bold**, listas, tablas, separadores --- (se renderiza a HTML)

ESTRUCTURA DEL BRIEF:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 MORNING BRIEF — [FECHA]
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. 🌍 PANORAMA MACRO (breve: DXY, VIX, Fear&Greed, eventos Fed)
2. ₿ CRYPTO (BTC y ETH detallado: estructura, OB, CVD, funding, OI, niveles)
3. 📈 ÍNDICES (SPX, NDX, DJI: tendencia + niveles clave)
4. 💻 TOP TECH (5 stocks: sesgo rápido)
5. 🥇 COMMODITIES & METALS (Gold, Silver, Oil)
6. 📦 ETFs (SPY, QQQ, GLD, SLV, USO)
7. 🎯 WATCHLIST DEL DÍA (top 3 setups más interesantes de todos los mercados)
8. ⚠ RIESGOS Y ALERTAS (factores a vigilar hoy)

Para la sección CRYPTO, incluye análisis detallado SMC:
- Estructura del mercado (BOS/CHOCH detectados)
- Order Blocks activos (zonas de demanda/oferta)
- Fair Value Gaps activos (no mitigados) — son targets de magnetismo de precio
- Equal Highs / Equal Lows como pools de liquidez y SWEEPS recientes (señal SMC clave)
- CVD divergence si existe
- Funding rate y su implicación
- Open Interest y cambios
- Ratio Long/Short
- Si hay datos LTF (1h), úsalos para refinar la entrada (no para cambiar el sesgo HTF)
- Niveles exactos de entrada/invalidación si hay setup

SI EL PROMPT INCLUYE "CONTEXTO DEL BRIEF ANTERIOR":
- Abre cada activo crypto con una línea breve de SEGUIMIENTO comparando los setups
  de ayer con el precio de hoy: ¿se activó la entrada? ¿saltó el SL? ¿llegó al target?
  ¿sigue vigente?
- Mantén continuidad narrativa: el trader está siguiendo la misma idea día a día.

Para las demás secciones, sé más conciso pero incluye:
- Tendencia (EMAs)
- RSI y sesgo
- 1-2 niveles clave"""


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

    brief_md = message.content[0].text
    stop_reason = getattr(message, "stop_reason", "unknown")
    if stop_reason == "max_tokens":
        logger.warning(
            f"Brief truncado: alcanzó max_tokens={config.CLAUDE_MAX_TOKENS}. "
            f"Considera subir el cap."
        )
    usage = getattr(message, "usage", None)
    if usage is not None:
        cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        cache_create = getattr(usage, "cache_creation_input_tokens", 0) or 0
        logger.info(
            f"Brief generado. stop_reason={stop_reason} Tokens: in={usage.input_tokens} "
            f"out={usage.output_tokens} cache_read={cache_read} cache_create={cache_create}"
        )
    else:
        logger.info(f"Brief generado exitosamente. stop_reason={stop_reason}")
    return brief_md


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
