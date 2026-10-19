"""
Unit tests for telegram_delivery: escaping HTML y fallback sin parse_mode.

Regresión de dos fallos reales:
- El brief contiene "<" (ej. "cierre 1h < 2,393") y parse_mode=HTML devolvía
  400. El retry sin parse_mode sí llegaba, pero el código lo marcaba como
  fallo incondicionalmente.
- format_brief_for_telegram no escapaba &, <, > antes de insertar <b>.
"""
import requests

import config
import telegram_delivery


class _FakeResponse:
    def __init__(self, status_code: int = 200, payload=None):
        self.status_code = status_code
        self._payload = payload if payload is not None else {"ok": True}
        self.text = str(self._payload)
        self.content = self.text.encode("utf-8")

    @property
    def ok(self):
        return self.status_code < 400

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")


def _configure_telegram(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "123456:FAKE")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "42")


def test_returns_false_when_not_configured(monkeypatch):
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "YOUR_BOT_TOKEN")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_ID", "YOUR_CHAT_ID")
    assert telegram_delivery.send_telegram_message("hola") is False


def test_retry_without_parse_mode_counts_as_sent(monkeypatch):
    _configure_telegram(monkeypatch)
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append(dict(json or {}))
        if len(calls) == 1:
            return _FakeResponse(400, {"ok": False, "description": "can't parse entities"})
        return _FakeResponse(200, {"ok": True})

    monkeypatch.setattr(telegram_delivery.requests, "post", fake_post)

    assert telegram_delivery.send_telegram_message("cierre 1h < 2,393") is True
    assert len(calls) == 2
    assert calls[0]["parse_mode"] == "HTML"
    assert "parse_mode" not in calls[1]


def test_returns_false_when_both_attempts_fail(monkeypatch):
    _configure_telegram(monkeypatch)

    def fake_post(url, json=None, timeout=None):
        return _FakeResponse(400, {"ok": False})

    monkeypatch.setattr(telegram_delivery.requests, "post", fake_post)

    assert telegram_delivery.send_telegram_message("hola") is False


def test_format_escapes_html_entities_and_keeps_bold_headers():
    out = telegram_delivery.format_brief_for_telegram(
        "📊 Panorama\nTrigger: cierre < 2,393 & > 1"
    )
    assert "<b>📊 Panorama</b>" in out
    assert "&lt; 2,393" in out
    assert "&amp;" in out
    assert "&gt; 1" in out


def test_format_bolds_new_header_emojis():
    out = telegram_delivery.format_brief_for_telegram(
        "🏛️ INSTITUTIONAL MORNING BRIEF | 2026-10-19\n"
        "🌐 1. MACRO & SENTIMIENTO\n"
        "⚡ 2. ARQUITECTURA CRYPTO & FLUJO"
    )
    assert "<b>🏛️ INSTITUTIONAL MORNING BRIEF | 2026-10-19</b>" in out
    assert "<b>🌐 1. MACRO &amp; SENTIMIENTO</b>" in out
    assert "<b>⚡ 2. ARQUITECTURA CRYPTO &amp; FLUJO</b>" in out


def test_split_keeps_tags_balanced_per_chunk():
    text = "\n".join(f"<b>📊 Nota {i}</b> " + "y" * 50 for i in range(20))
    chunks = telegram_delivery.split_message(text, max_length=200)
    assert len(chunks) > 1
    for chunk in chunks:
        assert len(chunk) <= 200
        assert chunk.count("<b>") == chunk.count("</b>")
