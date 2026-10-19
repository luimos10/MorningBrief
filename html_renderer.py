"""
Morning Market Brief — HTML Renderer
======================================
Genera un archivo HTML profesional a partir del brief.
"""
import re
import markdown
from datetime import datetime
from pathlib import Path

try:
    from zoneinfo import ZoneInfo  # Python 3.9+
except ImportError:  # pragma: no cover
    ZoneInfo = None  # type: ignore

import config


# Zona horaria de visualización (el runner en la nube corre en UTC).
DISPLAY_TZ = "America/New_York"
TZ_LABEL = "ET"

# Nombres amigables para los modelos de Claude.
_MODEL_NAMES = {
    "claude-opus-4-8": "Claude Opus 4.8",
    "claude-sonnet-5-5": "Claude Sonnet 5.5",
    "claude-sonnet-4-6": "Claude Sonnet 4.6",
    "claude-sonnet-4-5": "Claude Sonnet 4.5",
    "claude-haiku-4-5-20251001": "Claude Haiku 4.5",
    "claude-haiku-4-5": "Claude Haiku 4.5",
}

# Iconos de respaldo por sección (si el header llega sin emoji).
_SECTION_ICONS = [
    (("macro", "panorama"), "🌍"),
    (("crypto", "btc", "eth", "₿"), "₿"),
    (("índice", "indice", "index", "spx", "ndx", "dji"), "📈"),
    (("tech", "stock", "acciones"), "💻"),
    (("commod", "metal", "gold", "silver", "oil", "oro"), "🥇"),
    (("etf",), "📦"),
    (("watchlist", "setup"), "🎯"),
    (("riesgo", "alerta", "risk"), "⚠️"),
]


def _model_label(model_id: str) -> str:
    """Map a model id to a human-friendly label, falling back to a prettified id."""
    if model_id in _MODEL_NAMES:
        return _MODEL_NAMES[model_id]
    pretty = model_id.replace("claude-", "Claude ").replace("-", " ")
    return pretty.title()


def _now_display() -> datetime:
    """Current time in the display timezone (falls back to local if zoneinfo missing)."""
    if ZoneInfo is not None:
        try:
            return datetime.now(ZoneInfo(DISPLAY_TZ))
        except Exception:
            pass
    return datetime.now()


# Nombres en español: el runner de la nube no tiene locale es_* instalado.
_DAYS_ES = ["lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo"]
_MONTHS_ES = [
    "enero", "febrero", "marzo", "abril", "mayo", "junio",
    "julio", "agosto", "septiembre", "octubre", "noviembre", "diciembre",
]


def _format_datetime_es(dt: datetime) -> str:
    """Ej: 'lunes 19 de octubre, 2026 · 08:45' (sin depender del locale)."""
    day = _DAYS_ES[dt.weekday()]
    month = _MONTHS_ES[dt.month - 1]
    return f"{day} {dt.day:02d} de {month}, {dt.year} · {dt.strftime('%H:%M')}"


def _reading_time_minutes(text: str) -> int:
    """Estimación a 250 palabras/min (2500 palabras ≈ 10 min)."""
    words = len(re.findall(r"\S+", text))
    return max(1, round(words / 250))


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LUIMOS MORNING BRIEF — {date_file}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #050504;
  --bg-grad1: #0e0c08;
  --bg-grad2: #090806;
  --bg2: #12100c;
  --bg3: #1a1710;
  --card: #0c0b08;
  --border: #2b2517;
  --border2: #3d3521;
  --text: #f4efe4;
  --text2: #b5aa8e;
  --text3: #7d7259;
  --accent: #ff9f1a;
  --accent2: #ffc46b;
  --accent3: #ffd9a0;
  --accent-bg: rgba(255,159,26,0.12);
  --green: #3ddc84;
  --green-bg: rgba(61,220,132,0.12);
  --red: #ff5c5c;
  --red-bg: rgba(255,92,92,0.12);
  --amber: #ffb547;
  --amber-bg: rgba(255,181,71,0.12);
  --blue: #6fb3ff;
  --cyan: #ffd166;
  --purple: #ff7a00;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Inter', -apple-system, sans-serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background:
    radial-gradient(1200px 600px at 50% -10%, rgba(255,159,26,0.09), transparent 60%),
    radial-gradient(900px 500px at 90% 10%, rgba(255,122,0,0.05), transparent 55%),
    linear-gradient(180deg, var(--bg-grad1), var(--bg-grad2) 40%, var(--bg));
  background-attachment: fixed;
  color: var(--text);
  font-family: var(--sans);
  font-size: 14.5px;
  line-height: 1.72;
  min-height: 100vh;
}}
.container {{
  max-width: 880px;
  margin: 0 auto;
  padding: 24px 20px 64px;
}}
.header {{
  text-align: center;
  padding: 44px 0 30px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 30px;
  position: relative;
}}
.header h1 {{
  font-size: 34px;
  font-weight: 800;
  letter-spacing: 1.5px;
  margin: 0 0 6px;
  background: linear-gradient(92deg, var(--accent2), var(--accent) 55%, var(--purple));
  -webkit-background-clip: text;
  background-clip: text;
  -webkit-text-fill-color: transparent;
}}
.header .subtitle {{
  font-family: var(--mono);
  font-size: 11px;
  letter-spacing: 0.28em;
  text-transform: uppercase;
  color: var(--text3);
  margin-bottom: 18px;
}}
.badges {{
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  justify-content: center;
  margin-top: 16px;
}}
.badge {{
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-family: var(--mono);
  font-size: 11.5px;
  font-weight: 500;
  color: var(--text2);
  background: var(--bg2);
  border: 1px solid var(--border2);
  padding: 5px 12px;
  border-radius: 8px;
}}
.badge.accent {{ color: var(--accent2); border-color: rgba(255,159,26,0.35); background: var(--accent-bg); }}
.badge .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); }}
.brief-content {{
  background: linear-gradient(180deg, rgba(255,181,71,0.02), rgba(255,255,255,0));
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 34px 38px;
  box-shadow: 0 24px 60px -30px rgba(0,0,0,0.9);
}}
.brief-content h1 {{
  font-size: 25px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 1px;
  text-align: center;
  color: var(--accent2);
  margin: 0 0 10px;
  padding-bottom: 14px;
  border-bottom: 1px solid var(--border);
}}
.brief-content h2 {{
  font-size: 21px;
  font-weight: 800;
  text-transform: uppercase;
  color: var(--accent2);
  margin: 38px 0 16px;
  padding: 6px 0 10px 14px;
  border-bottom: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  letter-spacing: 0.8px;
}}
.brief-content h2:first-child, .brief-content h3:first-child {{ margin-top: 0; }}
.brief-content h3 {{
  font-size: 17.5px;
  font-weight: 800;
  text-transform: uppercase;
  letter-spacing: 0.9px;
  color: var(--accent3);
  margin: 34px 0 14px;
  padding: 4px 0 8px 12px;
  border-left: 3px solid var(--accent);
}}
.brief-content h4 {{
  font-family: var(--mono);
  font-size: 14.5px;
  font-weight: 700;
  text-transform: uppercase;
  letter-spacing: 1.1px;
  color: var(--accent);
  margin: 24px 0 10px;
  padding-bottom: 6px;
  border-bottom: 1px dashed var(--border2);
}}
.brief-content p {{ margin: 10px 0; color: var(--text); }}
.brief-content ul, .brief-content ol {{ margin: 10px 0; padding-left: 22px; }}
.brief-content li {{ margin: 5px 0; color: var(--text); }}
.brief-content li::marker {{ color: var(--accent); }}
.brief-content strong {{ color: #fff; font-weight: 700; }}
.brief-content em {{ color: var(--text2); font-style: italic; }}
.brief-content a {{ color: var(--accent2); text-decoration: none; border-bottom: 1px dotted var(--accent); }}
.brief-content code {{
  font-family: var(--mono);
  font-size: 12.5px;
  background: var(--bg3);
  padding: 2px 7px;
  border-radius: 5px;
  color: var(--cyan);
  border: 1px solid var(--border);
}}
.brief-content hr {{ border: none; border-top: 1px solid var(--border); margin: 26px 0; }}
.brief-content blockquote {{
  background: var(--amber-bg);
  border: 1px solid rgba(255,181,71,0.3);
  border-left: 3px solid var(--amber);
  border-radius: 10px;
  padding: 12px 16px;
  margin: 14px 0;
  color: var(--text);
}}
.brief-content blockquote p {{ margin: 0; }}
.table-wrap {{
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
  margin: 16px 0;
  border: 1px solid var(--border);
  border-radius: 10px;
}}
.brief-content table {{
  width: 100%;
  min-width: 460px;
  border-collapse: collapse;
  margin: 0;
  font-size: 13px;
}}
.brief-content th {{
  background: var(--bg3);
  color: var(--accent2);
  font-family: var(--mono);
  font-weight: 700;
  font-size: 10.5px;
  text-transform: uppercase;
  letter-spacing: 0.07em;
  padding: 10px 14px;
  text-align: left;
  border-bottom: 1px solid var(--border2);
}}
.brief-content td {{
  padding: 9px 14px;
  border-bottom: 1px solid rgba(61,53,33,0.55);
  font-family: var(--mono);
  font-size: 12.5px;
  color: var(--text2);
}}
.brief-content td strong {{ color: var(--accent3); }}
.brief-content tr:last-child td {{ border-bottom: none; }}
.brief-content tr:hover td {{ background: rgba(255,159,26,0.05); }}
/* Señales de mercado */
.pos {{ color: var(--green); font-weight: 600; }}
.neg {{ color: var(--red); font-weight: 600; }}
/* Callouts de alerta */
.callout {{
  background: var(--amber-bg);
  border: 1px solid rgba(255,181,71,0.3);
  border-left: 3px solid var(--amber);
  border-radius: 10px;
  padding: 12px 16px;
  margin: 14px 0;
}}
.callout.danger {{
  background: var(--red-bg);
  border-color: rgba(255,92,92,0.3);
  border-left-color: var(--red);
}}
.footer {{
  text-align: center;
  margin-top: 30px;
  padding-top: 22px;
  border-top: 1px solid var(--border);
}}
.footer p {{ font-size: 11.5px; color: var(--text3); font-family: var(--mono); margin: 3px 0; }}
.footer .brand {{ color: var(--accent2); letter-spacing: 0.15em; }}
@media (max-width: 640px) {{
  body {{ font-size: 14px; }}
  .container {{ padding: 14px 10px 40px; }}
  .header {{ padding: 30px 0 22px; }}
  .header h1 {{ font-size: 23px; letter-spacing: 1px; }}
  .badge {{ font-size: 10.5px; padding: 4px 9px; }}
  .brief-content {{ padding: 20px 14px; border-radius: 12px; }}
  .brief-content h1 {{ font-size: 19px; }}
  .brief-content h2 {{ font-size: 17px; }}
  .brief-content h3 {{ font-size: 15px; letter-spacing: 0.5px; }}
  .brief-content h4 {{ font-size: 13px; letter-spacing: 0.8px; }}
  .brief-content table {{ font-size: 12px; min-width: 420px; }}
  .brief-content th {{ font-size: 10px; padding: 8px 10px; }}
  .brief-content td {{ padding: 7px 10px; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="subtitle">Market Intelligence · Daily</div>
    <h1>LUIMOS MORNING BRIEF</h1>
    <div class="badges">
      <span class="badge accent"><span class="dot"></span> {datetime_str}</span>
      <span class="badge">🤖 {model_label}</span>
      <span class="badge">⏱ ~{reading_min} min de lectura</span>
    </div>
  </div>
  <div class="brief-content">
    {content}
  </div>
  <div class="footer">
    <p class="brand">LUIMOS MORNING BRIEF</p>
    <p>Generado {datetime_str} · IA: {model_label}</p>
  </div>
</div>
</body>
</html>"""


def _colorize_percentages(html: str) -> str:
    """Wrap signed percentages (+1.2% / -3.4%) in green/red spans for quick scanning."""
    pattern = re.compile(r"([+\-−])(\d+(?:[.,]\d+)?\s*%)")

    def repl(m: re.Match) -> str:
        sign = m.group(1)
        cls = "pos" if sign == "+" else "neg"
        return f'<span class="{cls}">{sign}{m.group(2)}</span>'

    return pattern.sub(repl, html)


def _add_section_icons(html: str) -> str:
    """Prepend a fallback icon to <h2> headers that don't already start with a symbol."""
    def repl(m: re.Match) -> str:
        inner = m.group(1)
        # Si ya contiene un símbolo/emoji/moneda (≥ U+2000), no añadir nada.
        # Las letras acentuadas (í, á, ñ…) están por debajo de ese umbral.
        if any(ord(c) >= 0x2000 for c in inner):
            return m.group(0)
        low = inner.lower()
        for keywords, icon in _SECTION_ICONS:
            if any(k in low for k in keywords):
                return f"<h2>{icon} {inner}</h2>"
        return m.group(0)

    return re.sub(r"<h2>(.*?)</h2>", repl, html, flags=re.DOTALL)


def _wrap_callouts(html: str) -> str:
    """Style alert paragraphs (starting with 🔴/⚠/🟡/🚨) as callout blocks."""
    def repl(m: re.Match) -> str:
        emoji = m.group(1)
        cls = "callout danger" if emoji in ("🔴", "🚨") else "callout"
        return f'<p class="{cls}">{emoji}'

    # Dentro de un <blockquote> ya hay estilo de recuadro (amber), no lo dupliques.
    return re.sub(r"(?<!<blockquote>\n)<p>(🔴|🚨|⚠️?|🟡|🟠)", repl, html)


# ── Tablas de activos (solo front HTML) ─────────────────────────────
_TICKER_LINE_RE = re.compile(
    r"^\*{0,2}\[TICKER:\s*(?P<name>[^\]]+)\]\*{0,2}\s*(?P<extra>.*)$"
)
_BULLET_LABEL_RE = re.compile(
    r"^-\s+(?P<pre>[^*]*?)\*\*(?P<label>[^*]+?):\*\*\s*(?P<val>.*)$"
)
_RADAR_HEADING_RE = re.compile(r"^#+\s.*cross-asset.*radar", re.IGNORECASE)
_SECTION_STOP_RE = re.compile(r"^(#{1,3}\s|-\s*-|─|━|═)")


def _md_cell(text: str) -> str:
    """Escapa pipes para que no rompan la tabla markdown."""
    return text.replace("|", "\\|").strip()


def _ticker_header(name: str, extra: str) -> str:
    """Nombre del ticker + datos extra de su línea (precio, RSI) para el encabezado."""
    extra = extra.strip()
    if not extra:
        return name
    extra = re.sub(r"\*\*", "", extra.replace("|", "·"))
    extra = re.sub(r"\s*·\s*", " · ", extra).strip(" ·")
    return f"{name} · {extra}" if extra else name


def _bullet_row(line: str):
    """Parsea '- [emoji] **Etiqueta:** valor' → (etiqueta_md, valor) o None."""
    m = _BULLET_LABEL_RE.match(line.strip())
    if not m:
        return None
    pre = m.group("pre").strip()
    label = m.group("label").strip()
    label_md = f"{pre} **{label}**".strip()
    return label_md, m.group("val").strip()


def _radar_section_to_table(section_lines):
    """Runs de ≥2 bullets etiquetados en la sección radar → tabla Grupo/Detalle."""
    out = []
    run_raw, run_rows = [], []

    def flush():
        if not run_rows:
            return
        if len(run_rows) < 2:
            out.extend(run_raw)
            return
        if out and out[-1].strip():
            out.append("")
        out.append("| Grupo | Detalle |")
        out.append("| :--- | :--- |")
        for label_md, val in run_rows:
            out.append(f"| {label_md} | {_md_cell(val)} |")
        out.append("")

    for line in section_lines:
        row = None if line[:1] in (" ", "\t") else _bullet_row(line)
        if row:
            run_raw.append(line)
            run_rows.append(row)
            continue
        flush()
        run_raw, run_rows = [], []
        out.append(line)
    flush()
    return out


def _tables_for_assets(md: str) -> str:
    """Convierte los bloques de activos a tablas (solo para el HTML).

    - Bloques **[TICKER: X]** (con o sin negritas) con sus bullets → tabla | Métrica | X |.
      Los sub-bullets indentados se anexan a la celda anterior.
    - Sección CROSS-ASSET RADAR → tabla | Grupo | Detalle |.
    El .txt y Telegram NO se tocan.
    """
    lines = md.split("\n")
    out = []
    i, n = 0, len(lines)

    while i < n:
        line = lines[i]

        ticker = _TICKER_LINE_RE.match(line.strip())
        if ticker:
            name = _ticker_header(ticker.group("name").strip(), ticker.group("extra"))
            rows = []
            j = i + 1
            while j < n:
                raw = lines[j]
                stripped = raw.strip()
                if not stripped or stripped[:2] not in ("- ", "• "):
                    break
                row = _bullet_row(stripped) if raw[:1] not in (" ", "\t") else None
                if row:
                    rows.append(row)
                    j += 1
                    continue
                if not rows:
                    break
                # Sub-bullet (indentado) o viñeta sin etiqueta: se anexa a la celda anterior.
                label_md, val = rows[-1]
                sep = "<br>◦ " if val else "◦ "
                rows[-1] = (label_md, f"{val}{sep}{stripped[2:].strip()}")
                j += 1
            if rows:
                if out and out[-1].strip():
                    out.append("")
                out.append(f"| Métrica | {name} |")
                out.append("| :--- | :--- |")
                for label_md, val in rows:
                    out.append(f"| {label_md} | {_md_cell(val)} |")
                out.append("")
                i = j
                continue

        if _RADAR_HEADING_RE.match(line):
            out.append(line)
            i += 1
            section = []
            while i < n and not _SECTION_STOP_RE.match(lines[i].strip()):
                section.append(lines[i])
                i += 1
            out.extend(_radar_section_to_table(section))
            continue

        out.append(line)
        i += 1

    return "\n".join(out)


def _wrap_tables(html: str) -> str:
    """Envuelve las tablas en un contenedor con scroll horizontal (mobile)."""
    html = html.replace("<table>", '<div class="table-wrap"><table>')
    return html.replace("</table>", "</table></div>")


def brief_to_html(brief_text: str, output_path: Path = None, model: str = None) -> Path:
    """
    Convert brief text/markdown to a beautiful HTML file.
    """
    now_display = _now_display()
    now_file = datetime.now()
    # Ej: "miércoles 04 de junio, 2026 · 08:45 ET"
    datetime_str = _format_datetime_es(now_display) + f" {TZ_LABEL}"
    date_file = now_file.strftime("%Y-%m-%d")

    model_id = model or getattr(config, "CLAUDE_MODEL", "")
    model_label = _model_label(model_id)
    reading_min = _reading_time_minutes(brief_text)

    # Convert markdown to HTML if it contains markdown syntax
    if any(marker in brief_text for marker in ["##", "**", "```", "| "]):
        content_html = markdown.markdown(
            _tables_for_assets(brief_text),
            extensions=["tables", "fenced_code", "nl2br"],
        )
    else:
        # Plain text: preserve formatting
        lines = brief_text.split("\n")
        html_lines = []
        for line in lines:
            line = line.strip()
            if not line:
                html_lines.append("<br>")
            elif line.startswith("━") or line.startswith("═") or line.startswith("─"):
                html_lines.append("<hr>")
            elif line.startswith("📊") or line.startswith("🌍") or line.startswith("₿") or \
                 line.startswith("📈") or line.startswith("💻") or line.startswith("🥇") or \
                 line.startswith("📦") or line.startswith("🎯") or line.startswith("⚠"):
                html_lines.append(f"<h2>{line}</h2>")
            elif line.startswith("•") or line.startswith("-") or line.startswith("  -"):
                html_lines.append(f"<li>{line.lstrip('•- ')}</li>")
            else:
                html_lines.append(f"<p>{line}</p>")
        content_html = "\n".join(html_lines)

    # Post-procesado visual
    content_html = _wrap_tables(content_html)
    content_html = _add_section_icons(content_html)
    content_html = _wrap_callouts(content_html)
    content_html = _colorize_percentages(content_html)

    # Build full HTML
    html = HTML_TEMPLATE.format(
        datetime_str=datetime_str,
        date_file=date_file,
        model_label=model_label,
        reading_min=reading_min,
        content=content_html,
    )

    # Save file
    if output_path is None:
        output_path = config.HTML_OUTPUT_DIR / f"brief_{date_file}.html"

    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] HTML brief guardado: {output_path}")
    return output_path
