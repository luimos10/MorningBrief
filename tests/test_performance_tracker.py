"""
Unit tests for performance_tracker._extract_relevant_lines.

Cubre el formato nuevo del SYSTEM_PROMPT institucional
(**[TICKER: BTC/USDT]**, Estructura/Order Flow/Mapa de Liquidez/Plan de Acción)
y mantiene la regresión del formato anterior (Sesgo/Entrada/SL/Target).
"""
from performance_tracker import _extract_relevant_lines


NEW_FORMAT_BRIEF = """# 🏛️ INSTITUTIONAL MORNING BRIEF | 2026-10-19
---

### ⚡ 2. ARQUITECTURA CRYPTO & FLUJO (SMC)
> ⚠️ **AUDITORÍA:** el setup de ayer tocó TP.

**[TICKER: BTC/USDT]**
- **Estructura (HTF/LTF):** CHoCH bajista en 4H, BOS confirmado; tendencia bajista.
- **Order Flow:** Funding -0.012% | CVD divergente | OI +2.1%, L/S 64.8% longs.
- 💧 **Mapa de Liquidez:** FVG 78,200–79,100 sin mitigar; EQL en 80,400.
- 🎯 **Plan de Acción:** 🟢 Entrada: **78,900** | 🛡️ SL: **77,800** | 🎯 TP: **81,500**

**[TICKER: ETH/USDT]**
- **Estructura (HTF/LTF):** rango LTF dentro de downtrend HTF.
"""


OLD_FORMAT_BRIEF = """BITCOIN — $64,500 (+1.2%) 🟢
Sesgo: alcista
Entrada: 63,800
SL: 62,900
Target: 66,000
Invalidación: cierre 4H < 62,500
"""


def test_extracts_crypto_headers_and_lines_new_format():
    kept = _extract_relevant_lines(NEW_FORMAT_BRIEF)
    joined = "\n".join(kept)

    assert "TICKER: BTC/USDT" in joined
    assert "TICKER: ETH/USDT" in joined
    assert "Estructura (HTF/LTF)" in joined
    assert "Order Flow" in joined
    assert "Mapa de Liquidez" in joined
    assert "Plan de Acción" in joined


def test_new_format_plan_line_keeps_entry_sl_tp():
    kept = _extract_relevant_lines(NEW_FORMAT_BRIEF)
    plan = [line for line in kept if "Plan de Acción" in line]
    assert len(plan) == 1
    assert "78,900" in plan[0]
    assert "SL" in plan[0]
    assert "TP" in plan[0]


def test_old_format_still_extracts():
    kept = _extract_relevant_lines(OLD_FORMAT_BRIEF)
    joined = "\n".join(kept)

    assert "BITCOIN" in joined
    for expected in ("Sesgo: alcista", "Entrada: 63,800", "SL: 62,900",
                     "Target: 66,000", "Invalidación: cierre 4H < 62,500"):
        assert expected in joined


MARKDOWN_FORMAT_BRIEF = """2. ₿ CRYPTO

BTCUSDT — $82,246 (-0.48%) 🔴 Bajista
• Estructura 4H: LH + LL (downtrend). Swings 84,147 / 79,800.
• EMAs: precio bajo la 21 (82,412) y la 50 (82,860).
• CVD: ⚠ confirmación bajista, sin divergencia.
• Liquidez:
• Highs barridos en 84,157 (EQH) con rechazo.
"""


def test_markdown_btcusdt_format_extracts():
    kept = _extract_relevant_lines(MARKDOWN_FORMAT_BRIEF)
    joined = "\n".join(kept)

    assert "BTCUSDT" in joined
    assert "Estructura 4H" in joined
    assert "CVD" in joined
    assert "Liquidez:" in joined


def test_watchlist_table_rows_are_not_kept_as_headers():
    brief = (
        "| Ticker | Dirección | Setup |\n"
        "| :--- | :---: | :--- |\n"
        "| **$AAPL** | 🟢 | Mitigación FVG 1h |\n"
    )
    assert _extract_relevant_lines(brief) == []
