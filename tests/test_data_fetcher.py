"""
Unit tests para los fallbacks geo-tolerantes de data_fetcher.

fapi.binance.com (451) y api.bybit.com (403) fallan desde GitHub Actions
(IPs de EE.UU.); los payloads imitan las respuestas reales de OKX público
y del CSV de metrics diarios de binance.vision, verificados por sonda
el 22/10/2026.
"""
import io
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

import data_fetcher


_OKX_FUNDING = {
    "code": "0",
    "data": [{
        "fundingRate": "0.0000745756007660",
        "fundingTime": 1792713600000,
        "realizedRate": "0.0000668879046611",
        "instId": "BTC-USDT-SWAP",
        "instType": "SWAP",
        "method": "current_period",
    }],
    "msg": "",
}

_OKX_OI = {
    "code": "0",
    "data": [{
        "instId": "BTC-USDT-SWAP",
        "instType": "SWAP",
        "oi": "3114185.8500000144",
        "oiCcy": "31141.858500000144",
        "oiUsd": "2535591918.3709617",
        "ts": "1792719133532",
    }],
    "msg": "",
}

_BINANCE_FUNDING_OK = [{"fundingRate": "0.0001", "fundingTime": 1792713600000}]

_BINANCE_LS_OK = [{
    "longAccount": "0.5243",
    "shortAccount": "0.4757",
    "longShortRatio": "1.1023",
}]


def _install_http_fake(monkeypatch, handler):
    urls = []

    def fake_get_json(url, params=None, timeout=10):
        urls.append(url)
        return handler(url, params)

    monkeypatch.setattr(data_fetcher, "_http_get_json", fake_get_json)
    return urls


# ── _okx_inst_id ──


def test_okx_inst_id_mapea_perps_usdt():
    assert data_fetcher._okx_inst_id("BTCUSDT") == "BTC-USDT-SWAP"
    assert data_fetcher._okx_inst_id("SOLUSDT") == "SOL-USDT-SWAP"


def test_okx_inst_id_rechaza_no_usdt():
    assert data_fetcher._okx_inst_id("BTC-USD") is None
    assert data_fetcher._okx_inst_id("BTCUSDC") is None
    assert data_fetcher._okx_inst_id("") is None


# ── funding: cadena Binance → Bybit → OKX ──


def test_funding_falla_binance_y_bybit_pasa_a_okx(monkeypatch):
    def handler(url, params):
        if "fapi.binance.com" in url:
            raise RuntimeError("451")
        if "bybit" in url:
            raise RuntimeError("403")
        return _OKX_FUNDING

    urls = _install_http_fake(monkeypatch, handler)
    result = data_fetcher.fetch_binance_funding_rate("BTCUSDT")
    assert result["rate"] == pytest.approx(0.0000668879046611)
    assert result["time"].endswith("UTC")
    assert any("okx.com" in u for u in urls)


def test_funding_binance_ok_no_toca_okx(monkeypatch):
    urls = _install_http_fake(monkeypatch, lambda u, p: _BINANCE_FUNDING_OK)
    result = data_fetcher.fetch_binance_funding_rate("BTCUSDT")
    assert result["rate"] == 0.0001
    assert all("okx" not in u for u in urls)


# ── open interest: cadena Binance → Bybit → OKX ──


def test_oi_falla_binance_y_bybit_pasa_a_okx(monkeypatch):
    def handler(url, params):
        if "fapi.binance.com" in url:
            raise RuntimeError("451")
        if "bybit" in url:
            raise RuntimeError("403")
        return _OKX_OI

    urls = _install_http_fake(monkeypatch, handler)
    result = data_fetcher.fetch_binance_open_interest("BTCUSDT")
    # okxCcy viene en base asset (BTC): comparable con openInterest de Binance.
    assert result["oi"] == pytest.approx(31141.8585)
    assert result["symbol"] == "BTCUSDT"
    assert any("okx.com" in u for u in urls)


def test_oi_binance_ok_no_toca_okx(monkeypatch):
    urls = _install_http_fake(
        monkeypatch, lambda u, p: {"openInterest": "94759.3", "symbol": "BTCUSDT"}
    )
    result = data_fetcher.fetch_binance_open_interest("BTCUSDT")
    assert result["oi"] == pytest.approx(94759.3)
    assert all("okx" not in u for u in urls)


# ── metrics CSV de binance.vision: parse, resample y L/S del cierre previo ──

_METRICS_HEADER = (
    b"create_time,symbol,sum_open_interest,sum_open_interest_value,"
    b"count_toptrader_long_short_ratio,sum_toptrader_long_short_ratio,"
    b"count_long_short_ratio,sum_taker_long_short_vol_ratio\n"
)


def _metrics_row(ts: str, oi: str, count: str, pos: str) -> bytes:
    return f"{ts},BTCUSDT,{oi},7859415730.59,{count},{pos},1.49,0.60\n".encode()


def test_parse_metrics_csv():
    raw = (
        _METRICS_HEADER
        + _metrics_row("2026-10-21 00:00:00", "94759.308", "1.58560282", "1.84273700")
        + _metrics_row("2026-10-21 00:55:00", "94816.677", "1.57791751", "1.83416400")
    )
    rows = data_fetcher._parse_metrics_csv(raw)
    assert len(rows) == 2
    assert rows[0]["ts"] == datetime(2026, 10, 21, 0, 0)
    assert rows[0]["oi"] == pytest.approx(94759.308)
    assert rows[0]["count_ratio"] == pytest.approx(1.58560282)
    assert rows[0]["position_ratio"] == pytest.approx(1.84273700)


def test_metrics_rows_descarga_y_parsea_dias(monkeypatch):
    data_fetcher._metrics_cache.clear()
    # Publicado a día siguiente: el archivo vigente es el de hace 2 días (UTC).
    disponible = (datetime.now(timezone.utc).date() - timedelta(days=2)).isoformat()
    day_csv = (
        _METRICS_HEADER
        + _metrics_row(f"{disponible} 10:00:00", "94000.0", "1.5", "1.8")
    )
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"BTCUSDT-metrics-{disponible}.csv", day_csv.decode("utf-8"))

    def fake_get(url, timeout=15):
        class R:
            status_code = 200 if disponible in url else 404
            content = buf.getvalue()

        return R()

    monkeypatch.setattr(data_fetcher.requests, "get", fake_get)
    rows = data_fetcher._fetch_metrics_rows("BTCUSDT", days=6)
    assert len(rows) == 1
    assert rows[0]["oi"] == pytest.approx(94000.0)


def test_metrics_oi_history_resample_ventana_4h(monkeypatch):
    rows = [
        {"ts": datetime(2026, 10, 21, 0, 10), "oi": 1.0, "count_ratio": None, "position_ratio": None},
        {"ts": datetime(2026, 10, 21, 1, 30), "oi": 2.0, "count_ratio": None, "position_ratio": None},
        {"ts": datetime(2026, 10, 21, 5, 0), "oi": 3.0, "count_ratio": None, "position_ratio": None},
        {"ts": datetime(2026, 10, 21, 6, 0), "oi": 4.0, "count_ratio": None, "position_ratio": None},
        {"ts": datetime(2026, 10, 21, 9, 15), "oi": 5.0, "count_ratio": None, "position_ratio": None},
        {"ts": datetime(2026, 10, 21, 10, 0), "oi": 6.0, "count_ratio": None, "position_ratio": None},
    ]
    monkeypatch.setattr(data_fetcher, "_fetch_metrics_rows", lambda s, days=6: rows)
    hist = data_fetcher._metrics_oi_history("BTCUSDT", period="4h", limit=3)
    # Última fila de cada ventana 4h ([0,4),[4,8),[8,12)), ASC y limitada a las últimas 3.
    assert hist == [2.0, 4.0, 6.0]


def test_metrics_oi_history_periodo_invalido(monkeypatch):
    monkeypatch.setattr(data_fetcher, "_fetch_metrics_rows", lambda s, days=6: [])
    assert data_fetcher._metrics_oi_history("BTCUSDT", period="4x") == []


def test_metrics_ls_ratio_ultima_fila(monkeypatch):
    rows = [
        {"ts": datetime(2026, 10, 21, 12, 0), "oi": 1.0, "count_ratio": 1.5, "position_ratio": 1.8},
        {"ts": datetime(2026, 10, 21, 22, 55), "oi": 2.0, "count_ratio": 1.58560282, "position_ratio": 1.8427},
    ]
    monkeypatch.setattr(data_fetcher, "_fetch_metrics_rows", lambda s, days=6: rows)
    out = data_fetcher._metrics_long_short_ratio("BTCUSDT")
    ratio = 1.58560282
    assert out["ratio"] == pytest.approx(ratio, rel=1e-4)
    assert out["long_account"] == pytest.approx(ratio / (1.0 + ratio))
    assert out["short_account"] == pytest.approx(1.0 / (1.0 + ratio))


def test_ls_binance_ok_no_toca_metrics(monkeypatch):
    _install_http_fake(monkeypatch, lambda u, p: _BINANCE_LS_OK)
    llamadas = []
    monkeypatch.setattr(data_fetcher, "_fetch_metrics_rows", lambda s, days=6: llamadas.append(1))
    result = data_fetcher.fetch_binance_long_short_ratio("BTCUSDT")
    assert result["ratio"] == pytest.approx(1.1023)
    assert result["long_account"] == pytest.approx(0.5243)
    assert not llamadas


def test_oi_history_cadena_baja_a_metrics(monkeypatch):
    def handler(url, params):
        if "fapi.binance.com" in url or "bybit" in url:
            raise RuntimeError("geo-block")

    _install_http_fake(monkeypatch, handler)
    monkeypatch.setattr(
        data_fetcher, "_metrics_oi_history", lambda s, period="4h", limit=30: [1.0, 2.0]
    )
    assert data_fetcher.fetch_binance_oi_history("BTCUSDT") == [1.0, 2.0]


def test_fallbacks_no_aplican_a_no_usdt(monkeypatch):
    urls = _install_http_fake(
        monkeypatch, lambda u, p: (_ for _ in ()).throw(RuntimeError("geo"))
    )
    assert data_fetcher.fetch_binance_funding_rate("BTC-USD") is None
    assert data_fetcher.fetch_binance_open_interest("BTC-USD") is None
    # OKX ni se llama porque no es un perp USDT.
    assert urls  # hubo intentos de Binance/Bybit
