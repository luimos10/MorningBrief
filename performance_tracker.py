"""
Morning Market Brief — Performance Tracker
============================================
Extrae el contexto del brief anterior (setups, niveles, sesgos) y lo formatea
para inyectarlo en el prompt de hoy. Claude se encarga de la comparación
narrativa contra los precios actuales.
"""
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

import config


SETUP_HEADER_RE = re.compile(r"^[🎯⚠️📊🔥]*\s*Setup\s+([A-Z0-9 /\-]+):", re.MULTILINE)
KEY_LINE_RE = re.compile(
    r"^\s*[>•\-*]?\s*("
    r"Sesgo|Entrada|Entrada short|Entrada long|Setup|SL|Stop|Target|Target 1|"
    r"Target 2|Invalidación|Invalidacion"
    r")\s*[:：]",
    re.IGNORECASE | re.MULTILINE,
)
ASSET_LINE_RE = re.compile(
    r"^\s*(?:🟢|🔴|🟡|🟠)?\s*"
    r"(BITCOIN|ETHEREUM|BTC|ETH|S&P\s*500|NASDAQ|DOW|GOLD|SILVER|"
    r"OIL|SPY|QQQ|GLD|SLV|USO|AAPL|MSFT|NVDA|GOOGL|AMZN)"
    r"\b",
    re.IGNORECASE | re.MULTILINE,
)


def _find_previous_brief(today: datetime, max_lookback: int = 5) -> Optional[Path]:
    """Find the most recent brief .txt on disk within the last N days."""
    out_dir: Path = config.HTML_OUTPUT_DIR
    for offset in range(1, max_lookback + 1):
        candidate = out_dir / f"brief_{(today - timedelta(days=offset)).strftime('%Y-%m-%d')}.txt"
        if candidate.exists():
            return candidate
    return None


def _extract_relevant_lines(text: str, max_lines_per_asset: int = 8) -> List[str]:
    """
    Walk the previous brief and keep only lines that carry actionable context:
    asset headers, bias lines, Setup blocks, levels, invalidation.
    """
    kept: List[str] = []
    lines = text.splitlines()
    in_setup_block = False
    block_lines = 0

    for line in lines:
        stripped = line.strip()
        if not stripped:
            in_setup_block = False
            block_lines = 0
            continue

        is_asset_header = bool(ASSET_LINE_RE.search(line)) and (
            "—" in line or "$" in line or "(" in line
        )
        is_setup_header = bool(SETUP_HEADER_RE.search(line))
        is_key_line = bool(KEY_LINE_RE.search(line))

        if is_asset_header or is_setup_header:
            kept.append(stripped)
            in_setup_block = True
            block_lines = 0
            continue

        if in_setup_block and is_key_line and block_lines < max_lines_per_asset:
            kept.append(stripped)
            block_lines += 1

    return kept


def build_previous_context(today: Optional[datetime] = None) -> str:
    """
    Build a compact 'previous brief' context block for injection into today's prompt.
    Returns "" if there is no previous brief on disk.
    """
    today = today or datetime.now()
    prev_path = _find_previous_brief(today)
    if prev_path is None:
        return ""

    try:
        text = prev_path.read_text(encoding="utf-8")
    except OSError:
        return ""

    relevant = _extract_relevant_lines(text)
    if not relevant:
        return ""

    # Cap total length so we never bloat the prompt.
    joined = "\n".join(relevant)
    if len(joined) > 3000:
        joined = joined[:3000] + "\n[...truncado...]"

    header = f"=== CONTEXTO DEL BRIEF ANTERIOR ({prev_path.stem.replace('brief_', '')}) ==="
    instruction = (
        "Compara los setups y niveles de abajo con los precios actuales. "
        "En cada activo relevante, abre con una línea de SEGUIMIENTO indicando "
        "si el setup de ayer se activó, invalidó, o sigue vigente — y úsalo "
        "para dar continuidad narrativa."
    )
    return f"{header}\n{instruction}\n\n{joined}"


def summarize_current_prices(analysis: Dict) -> str:
    """Compact one-liner per asset with today's price/bias for the comparison."""
    lines: List[str] = []
    for category in ("crypto", "indexes", "stocks", "commodities", "etfs"):
        for a in analysis.get(category, []):
            if "error" in a:
                continue
            lines.append(
                f"  {a['name']}: ${a['price']:,.2f} ({a['change_pct']:+.2f}%) | "
                f"RSI {a['rsi']} | {a['bias']}"
            )
    if not lines:
        return ""
    return "=== PRECIOS / SESGOS DE HOY ===\n" + "\n".join(lines)
