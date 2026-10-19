"""
Unit tests for html_renderer: tablas de activos (crypto/radar) y paleta ámbar.

Las tablas se generan solo en el front HTML (transformación markdown antes de
renderizar); el .txt y Telegram no se tocan.
"""
import html_renderer

from datetime import datetime


NEW_FORMAT_BRIEF = """# 🏛️ INSTITUTIONAL MORNING BRIEF | 2026-10-19

---

### 🌐 1. MACRO & SENTIMIENTO (Flash View)
- ▪️ **DXY / VIX:** DXY 101.8 plano (+0.1%).

### ⚡ 2. ARQUITECTURA CRYPTO & FLUJO (SMC)
> ⚠️ **AUDITORÍA:** el setup de ayer tocó TP1.

**[TICKER: BTC/USDT]**
- **Estructura (HTF/LTF):** CHoCH bajista en 4H.
- **Order Flow:** Funding -0.012% | OI +2.1%.
- 💧 **Mapa de Liquidez:** FVG 78,200–79,100 sin mitigar.
- 🎯 **Plan de Acción:** 🟢 Entrada: **78,900** | 🛡️ SL: **77,800**

---

### 📊 3. CROSS-ASSET RADAR (Sesión NY)
*(Lectura rápida de 1 línea por grupo.)*
- **Índices (SPX, NDX, DJI):** NDX rechazo en **25,400**.
- **Top Tech:** NVDA débil bajo **180**.
- **Commodities (Gold, Silver, WTI):** Gold en soporte **4,050**.
- **ETFs Clave:** QQQ bajo la EMA50.
"""


RADAR_TABLE_BRIEF = """# 🏛️ BRIEF | 2026-10-19

---

### 📊 3. CROSS-ASSET RADAR
*(Una tabla por grupo con sus activos).*

#### 📈 ÍNDICES
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$SPX** | 🟢 | **5,540** | Soporte de rango. |
| **$NDX** | 🔴 | **25,400** | Rechazo bajo resistencia. |

#### 📦 ETFS
| Activo | Sesgo | Nivel Clave | Lectura |
| :--- | :---: | :--- | :--- |
| **$SPY** | 🟡 | **612** | Rango. |
| **$QQQ** | 🔴 | **530** | Bajo EMA50. |

---

### 🎯 4. TOP 3 WATCHLIST INSTITUCIONAL
| Ticker | Dirección | Setup | Zona | SL | TP |
| :--- | :---: | :--- | :--- | :--- | :--- |
| **$BTC** | 🟡 | Mitigación FVG | **81,283** | **80,500** | **84,157** |
"""


def test_ticker_block_becomes_table():
    md = html_renderer._tables_for_assets(NEW_FORMAT_BRIEF)
    assert "| Métrica | BTC/USDT |" in md
    assert "| **Estructura (HTF/LTF)** | CHoCH bajista en 4H. |" in md
    assert "| 💧 **Mapa de Liquidez** | FVG 78,200–79,100 sin mitigar. |" in md
    # Los pipes dentro de celdas quedan escapados para no romper la tabla.
    assert "Funding -0.012% \\| OI +2.1%." in md
    # El bloque original ya no existe como bullets sueltos.
    assert "- **Order Flow:**" not in md


def test_radar_bullets_become_table():
    md = html_renderer._tables_for_assets(NEW_FORMAT_BRIEF)
    assert "| Grupo | Detalle |" in md
    assert "| **Índices (SPX, NDX, DJI)** | NDX rechazo en **25,400**. |" in md
    assert "| **ETFs Clave** | QQQ bajo la EMA50. |" in md
    # El hint en cursiva no se toca.
    assert "*(Lectura rápida de 1 línea por grupo.)*" in md


def test_non_radar_bullets_stay_bullets():
    md = html_renderer._tables_for_assets(NEW_FORMAT_BRIEF)
    assert "- ▪️ **DXY / VIX:** DXY 101.8 plano (+0.1%)." in md


def test_ticker_without_bold_also_converts():
    text = "**[TICKER: ETH/USDT]**\n- **Order Flow:** CVD alcista.\n- 💧 **Mapa de Liquidez:** EQH 2,739.\n"
    md = html_renderer._tables_for_assets(text.replace("**", "", 2))
    assert "| Métrica | ETH/USDT |" in md
    assert "| 💧 **Mapa de Liquidez** | EQH 2,739. |" in md


def test_ticker_sub_bullets_merge_into_cell():
    text = (
        "**[TICKER: BTC/USDT]**\n"
        "- 💧 **Mapa de Liquidez:** zona principal.\n"
        "  - Bear FVG activo **$82,083–$83,029**.\n"
        "  - Bear OB **$81,650–$82,295** como breaker.\n"
        "- 🎯 **Plan de Acción:** 🟢 Entrada: **78,900**\n"
    )
    md = html_renderer._tables_for_assets(text)
    assert (
        "| 💧 **Mapa de Liquidez** | zona principal.<br>◦ Bear FVG activo "
        "**$82,083–$83,029**.<br>◦ Bear OB **$81,650–$82,295** como breaker. |" in md
    )
    assert "| 🎯 **Plan de Acción** | 🟢 Entrada: **78,900** |" in md
    # Los sub-bullets NO deben generar filas propias con la etiqueta mal parseada.
    assert "| **$82,083–$83,029** |" not in md

    empty = "**[TICKER: SOL/USDT]**\n- 💧 **Mapa de Liquidez:**\n  - FVG 140–142.\n"
    md_empty = html_renderer._tables_for_assets(empty)
    assert "| 💧 **Mapa de Liquidez** | ◦ FVG 140–142. |" in md_empty


def test_ticker_header_con_precio_y_rsi():
    text = (
        "**[TICKER: BTC/USDT]** | **$82,496** | RSI **54.9**\n"
        "- **Estructura (HTF/LTF):** Rango transicional.\n"
        "- **Order Flow:** Funding +0.0050%.\n"
    )
    md = html_renderer._tables_for_assets(text)
    assert "| Métrica | BTC/USDT · $82,496 · RSI 54.9 |" in md
    assert "| **Estructura (HTF/LTF)** | Rango transicional. |" in md


def test_vinetas_sin_etiqueta_cuelgan_de_la_celda_anterior():
    text = (
        "**[TICKER: BTC/USDT]**\n"
        "- 💧 **Mapa de Liquidez:**\n"
        "- **Bear OB** **$81,650–$82,295** (10-18 08:00): el precio cotiza por encima.\n"
        "- **Bear FVG activo** **$82,083–$83,029**: techo inmediato.\n"
        "- 🎯 **Plan de Acción:** 🟡 **Wait**, sin ventaja.\n"
    )
    md = html_renderer._tables_for_assets(text)
    assert "| 💧 **Mapa de Liquidez** | ◦ **Bear OB** **$81,650–$82,295** (10-18 08:00): el precio cotiza por encima.<br>◦ **Bear FVG activo** **$82,083–$83,029**: techo inmediato. |" in md
    assert "| **Bear OB** |" not in md
    assert "| 🎯 **Plan de Acción** | 🟡 **Wait**, sin ventaja. |" in md
    assert md.count("| :--- | :--- |") == 1


def test_alert_paragraph_becomes_callout_but_not_inside_blockquote():
    standalone = html_renderer._wrap_callouts("<p>⚠️ Cuidado con el gap.</p>")
    assert '<p class="callout">⚠️' in standalone
    quoted = html_renderer._wrap_callouts("<blockquote>\n<p>⚠️ Radar de Riesgo.</p>\n</blockquote>")
    assert 'class="callout"' not in quoted


def test_datetime_es_no_depende_del_locale():
    dt = datetime(2026, 10, 19, 8, 45)
    assert html_renderer._format_datetime_es(dt) == "lunes 19 de octubre, 2026 · 08:45"


def test_footer_en_espanol(monkeypatch, tmp_path):
    monkeypatch.setattr(
        html_renderer, "_now_display", lambda: datetime(2026, 10, 19, 8, 45)
    )
    html = html_renderer.brief_to_html(
        "**brief**", output_path=tmp_path / "brief.html", model="claude-sonnet-5-5"
    ).read_text(encoding="utf-8")
    assert "lunes 19 de octubre, 2026 · 08:45 ET" in html
    assert "Monday" not in html
    assert "October" not in html


def test_brief_to_html_wraps_tables_and_amber_palette(tmp_path):
    out = html_renderer.brief_to_html(
        NEW_FORMAT_BRIEF,
        output_path=tmp_path / "brief.html",
        model="claude-sonnet-5-5",
    )
    html = out.read_text(encoding="utf-8")
    assert '<div class="table-wrap"><table>' in html
    assert "#ff9f1a" in html
    assert "<h1>" in html


def test_reading_time_minutes():
    assert html_renderer._reading_time_minutes(" ".join(["w"] * 2500)) == 10
    assert html_renderer._reading_time_minutes(" ".join(["w"] * 1500)) == 6
    assert html_renderer._reading_time_minutes("hola") == 1


def test_badge_lectura_dinamico(tmp_path):
    text = "**brief** " + " ".join(["dato"] * 2499)
    html = html_renderer.brief_to_html(
        text, output_path=tmp_path / "brief.html", model="claude-sonnet-5-5"
    ).read_text(encoding="utf-8")
    assert "~10 min de lectura" in html


def test_radar_tables_ya_formateadas_pasan_intactas():
    md = html_renderer._tables_for_assets(RADAR_TABLE_BRIEF)
    assert "| **$SPX** | 🟢 | **5,540** | Soporte de rango. |" in md
    assert "| **$QQQ** | 🔴 | **530** | Bajo EMA50. |" in md
    assert "| Grupo | Detalle |" not in md


def test_brief_to_html_renderiza_tablas_radar_y_h4(tmp_path):
    html = html_renderer.brief_to_html(
        RADAR_TABLE_BRIEF, output_path=tmp_path / "brief.html", model="claude-sonnet-5-5"
    ).read_text(encoding="utf-8")
    assert html.count("<table>") == 3
    assert html.count("<h4>") == 2
    assert html.count('<div class="table-wrap">') == 3
