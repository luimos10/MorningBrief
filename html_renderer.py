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


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>LUIMOS MORNING BRIEF — {date_file}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700;800&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #07070c;
  --bg-grad1: #0d0d18;
  --bg-grad2: #0a0a12;
  --bg2: #101019;
  --bg3: #181826;
  --card: #0f0f18;
  --border: #23233a;
  --border2: #2e2e4a;
  --text: #ececf5;
  --text2: #9a9ab5;
  --text3: #61617e;
  --accent: #7c83ff;
  --accent2: #a5acff;
  --accent-bg: rgba(124,131,255,0.12);
  --green: #2ee676;
  --green-bg: rgba(46,230,118,0.12);
  --red: #ff5c6c;
  --red-bg: rgba(255,92,108,0.12);
  --amber: #ffb547;
  --amber-bg: rgba(255,181,71,0.12);
  --blue: #4aa8ff;
  --cyan: #2fe0d6;
  --purple: #c06bff;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Inter', -apple-system, sans-serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background:
    radial-gradient(1200px 600px at 50% -10%, rgba(124,131,255,0.10), transparent 60%),
    radial-gradient(900px 500px at 90% 10%, rgba(47,224,214,0.06), transparent 55%),
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
  background: linear-gradient(92deg, var(--accent2), var(--cyan) 55%, var(--purple));
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
.badge.accent {{ color: var(--accent2); border-color: rgba(124,131,255,0.35); background: var(--accent-bg); }}
.badge .dot {{ width: 7px; height: 7px; border-radius: 50%; background: var(--green); box-shadow: 0 0 8px var(--green); }}
.brief-content {{
  background: linear-gradient(180deg, rgba(255,255,255,0.018), rgba(255,255,255,0));
  background-color: var(--card);
  border: 1px solid var(--border);
  border-radius: 16px;
  padding: 34px 38px;
  box-shadow: 0 24px 60px -30px rgba(0,0,0,0.8);
}}
.brief-content h2 {{
  font-size: 19px;
  font-weight: 700;
  color: var(--text);
  margin: 36px 0 16px;
  padding: 6px 0 10px 14px;
  border-bottom: 1px solid var(--border);
  border-left: 3px solid var(--accent);
  letter-spacing: 0.2px;
}}
.brief-content h2:first-child {{ margin-top: 0; }}
.brief-content h3 {{
  font-size: 15.5px;
  font-weight: 600;
  color: var(--accent2);
  margin: 22px 0 8px;
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
.brief-content table {{
  width: 100%;
  border-collapse: collapse;
  margin: 16px 0;
  font-size: 13px;
  border: 1px solid var(--border);
  border-radius: 10px;
  overflow: hidden;
}}
.brief-content th {{
  background: var(--bg3);
  color: var(--accent2);
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
  border-bottom: 1px solid rgba(42,42,58,0.5);
  font-family: var(--mono);
  font-size: 12.5px;
}}
.brief-content tr:last-child td {{ border-bottom: none; }}
.brief-content tr:hover td {{ background: rgba(124,131,255,0.05); }}
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
  border-color: rgba(255,92,108,0.3);
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
@media (max-width: 600px) {{
  .container {{ padding: 14px 12px 40px; }}
  .brief-content {{ padding: 22px 18px; }}
  .header h1 {{ font-size: 25px; }}
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
      <span class="badge">⏱ ~8 min de lectura</span>
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

    return re.sub(r"<p>(🔴|🚨|⚠️?|🟡|🟠)", repl, html)


def brief_to_html(brief_text: str, output_path: Path = None, model: str = None) -> Path:
    """
    Convert brief text/markdown to a beautiful HTML file.
    """
    now_display = _now_display()
    now_file = datetime.now()
    # Ej: "miércoles 04 de junio, 2026 · 08:45 ET"
    datetime_str = now_display.strftime("%A %d de %B, %Y · %H:%M") + f" {TZ_LABEL}"
    date_file = now_file.strftime("%Y-%m-%d")

    model_id = model or getattr(config, "CLAUDE_MODEL", "")
    model_label = _model_label(model_id)

    # Convert markdown to HTML if it contains markdown syntax
    if any(marker in brief_text for marker in ["##", "**", "```", "| "]):
        content_html = markdown.markdown(
            brief_text,
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
    content_html = _add_section_icons(content_html)
    content_html = _wrap_callouts(content_html)
    content_html = _colorize_percentages(content_html)

    # Build full HTML
    html = HTML_TEMPLATE.format(
        datetime_str=datetime_str,
        date_file=date_file,
        model_label=model_label,
        content=content_html,
    )

    # Save file
    if output_path is None:
        output_path = config.HTML_OUTPUT_DIR / f"brief_{date_file}.html"

    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] HTML brief guardado: {output_path}")
    return output_path
