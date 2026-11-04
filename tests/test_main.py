"""Tests for main.run_brief delivery resilience.

A failed delivery must not short-circuit the remaining channels: every
configured delivery gets a chance, the brief stays saved on disk, and the
pipeline still signals failure (exit != 0 in CI) after the summary.
"""
import pytest

import main


def _stub_pipeline(monkeypatch, tmp_path):
    monkeypatch.setattr(main, "collect_with_cache", lambda *a, **k: {})
    monkeypatch.setattr(main, "run_full_analysis", lambda data: {})
    monkeypatch.setattr(main, "generate_brief", lambda analysis: "brief md")
    monkeypatch.setattr(main, "markdown_to_plain", lambda md: "brief text")

    html_path = tmp_path / "brief.html"
    html_path.write_text("<html></html>", encoding="utf-8")
    monkeypatch.setattr(main, "brief_to_html", lambda *a, **k: html_path)
    monkeypatch.setattr(main.config, "HTML_OUTPUT_DIR", tmp_path)
    return html_path


def test_telegram_failure_still_attempts_discord(monkeypatch, tmp_path):
    _stub_pipeline(monkeypatch, tmp_path)
    calls = []

    monkeypatch.setattr(
        main, "deliver_to_telegram",
        lambda *a, **k: calls.append("telegram") or False,
    )
    monkeypatch.setattr(
        main, "deliver_to_discord",
        lambda *a, **k: calls.append("discord") or True,
    )

    with pytest.raises(RuntimeError, match="Telegram"):
        main.run_brief(open_browser=False, send_telegram=True)

    assert calls == ["telegram", "discord"]


def test_discord_failure_still_attempts_telegram(monkeypatch, tmp_path):
    _stub_pipeline(monkeypatch, tmp_path)
    calls = []

    monkeypatch.setattr(
        main, "deliver_to_telegram",
        lambda *a, **k: calls.append("telegram") or True,
    )
    monkeypatch.setattr(
        main, "deliver_to_discord",
        lambda *a, **k: calls.append("discord") or False,
    )

    with pytest.raises(RuntimeError, match="Discord"):
        main.run_brief(open_browser=False, send_telegram=True)

    assert calls == ["telegram", "discord"]


def test_all_deliveries_succeed(monkeypatch, tmp_path):
    _stub_pipeline(monkeypatch, tmp_path)
    calls = []

    monkeypatch.setattr(
        main, "deliver_to_telegram",
        lambda *a, **k: calls.append("telegram") or True,
    )
    monkeypatch.setattr(
        main, "deliver_to_discord",
        lambda *a, **k: calls.append("discord") or True,
    )

    main.run_brief(open_browser=False, send_telegram=True)

    assert calls == ["telegram", "discord"]
