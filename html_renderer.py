"""
Morning Market Brief — HTML Renderer
======================================
Genera un archivo HTML profesional a partir del brief.
"""
import re
import markdown
from datetime import datetime
from pathlib import Path
import config


HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Morning Brief — {date}</title>
<link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600;700&display=swap" rel="stylesheet">
<style>
:root {{
  --bg: #0a0a0f;
  --bg2: #12121a;
  --bg3: #1a1a26;
  --card: #15151f;
  --border: #2a2a3a;
  --text: #e4e4ed;
  --text2: #8b8ba0;
  --text3: #5a5a70;
  --accent: #6366f1;
  --accent2: #818cf8;
  --green: #22c55e;
  --green-bg: rgba(34,197,94,0.08);
  --red: #ef4444;
  --red-bg: rgba(239,68,68,0.08);
  --amber: #f59e0b;
  --amber-bg: rgba(245,158,11,0.08);
  --blue: #3b82f6;
  --cyan: #06b6d4;
  --mono: 'JetBrains Mono', monospace;
  --sans: 'Inter', -apple-system, sans-serif;
}}
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
  background: var(--bg);
  color: var(--text);
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.7;
  min-height: 100vh;
}}
.container {{
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 20px 60px;
}}
.header {{
  text-align: center;
  padding: 40px 0 32px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 32px;
}}
.header-tag {{
  display: inline-block;
  font-family: var(--mono);
  font-size: 11px;
  font-weight: 500;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--accent2);
  background: rgba(99,102,241,0.1);
  padding: 4px 14px;
  border-radius: 20px;
  border: 1px solid rgba(99,102,241,0.2);
  margin-bottom: 16px;
}}
.header h1 {{
  font-size: 28px;
  font-weight: 700;
  color: var(--text);
  margin: 12px 0 6px;
  letter-spacing: -0.5px;
}}
.header .date {{
  font-family: var(--mono);
  font-size: 13px;
  color: var(--text2);
}}
.header .reading-time {{
  font-size: 12px;
  color: var(--text3);
  margin-top: 6px;
}}
.brief-content {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 32px 36px;
}}
.brief-content h2 {{
  font-size: 18px;
  font-weight: 600;
  color: var(--accent2);
  margin: 32px 0 14px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border);
}}
.brief-content h2:first-child {{
  margin-top: 0;
}}
.brief-content h3 {{
  font-size: 15px;
  font-weight: 600;
  color: var(--text);
  margin: 20px 0 8px;
}}
.brief-content p {{
  margin: 8px 0;
  color: var(--text);
}}
.brief-content ul, .brief-content ol {{
  margin: 8px 0;
  padding-left: 20px;
}}
.brief-content li {{
  margin: 4px 0;
  color: var(--text);
}}
.brief-content strong {{
  color: var(--text);
  font-weight: 600;
}}
.brief-content em {{
  color: var(--text2);
  font-style: italic;
}}
.brief-content code {{
  font-family: var(--mono);
  font-size: 12px;
  background: var(--bg3);
  padding: 2px 6px;
  border-radius: 4px;
  color: var(--cyan);
}}
.brief-content hr {{
  border: none;
  border-top: 1px solid var(--border);
  margin: 24px 0;
}}
.brief-content table {{
  width: 100%;
  border-collapse: collapse;
  margin: 12px 0;
  font-size: 13px;
}}
.brief-content th {{
  background: var(--bg3);
  color: var(--text2);
  font-weight: 600;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.06em;
  padding: 8px 12px;
  text-align: left;
  border-bottom: 1px solid var(--border);
}}
.brief-content td {{
  padding: 8px 12px;
  border-bottom: 1px solid rgba(42,42,58,0.5);
  font-family: var(--mono);
  font-size: 12px;
}}
.brief-content tr:hover td {{
  background: rgba(99,102,241,0.04);
}}
.footer {{
  text-align: center;
  margin-top: 32px;
  padding-top: 20px;
  border-top: 1px solid var(--border);
}}
.footer p {{
  font-size: 12px;
  color: var(--text3);
  font-family: var(--mono);
}}
@media (max-width: 600px) {{
  .container {{ padding: 12px 12px 40px; }}
  .brief-content {{ padding: 20px 16px; }}
  .header h1 {{ font-size: 22px; }}
}}
</style>
</head>
<body>
<div class="container">
  <div class="header">
    <div class="header-tag">Luimos Trading Terminal</div>
    <h1>Morning Market Brief</h1>
    <div class="date">{date}</div>
    <div class="reading-time">~8 min de lectura</div>
  </div>
  <div class="brief-content">
    {content}
  </div>
  <div class="footer">
    <p>Generado por Luimos Morning Brief System v1.0</p>
    <p>Powered by Claude API + Python</p>
  </div>
</div>
</body>
</html>"""


def brief_to_html(brief_text: str, output_path: Path = None) -> Path:
    """
    Convert brief text/markdown to a beautiful HTML file.
    """
    today = datetime.now()
    date_str = today.strftime("%A %d de %B, %Y — %H:%M hrs")
    date_file = today.strftime("%Y-%m-%d")

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

    # Build full HTML
    html = HTML_TEMPLATE.format(
        date=date_str,
        content=content_html,
    )

    # Save file
    if output_path is None:
        output_path = config.HTML_OUTPUT_DIR / f"brief_{date_file}.html"

    output_path.write_text(html, encoding="utf-8")
    print(f"[OK] HTML brief guardado: {output_path}")
    return output_path
