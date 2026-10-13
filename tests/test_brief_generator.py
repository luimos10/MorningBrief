"""
Unit tests for brief_generator.extract_brief_text.

Modelos como claude-sonnet-5-5 devuelven bloques de thinking antes que el
texto: content[0] puede no ser un TextBlock. Regresión del fallo del
12/10/2026 ('ThinkingBlock' object has no attribute 'text').
"""
from types import SimpleNamespace

import pytest

from brief_generator import extract_brief_text


def _block(type_: str, text: str = None) -> SimpleNamespace:
    b = SimpleNamespace(type=type_)
    if text is not None:
        b.text = text
    return b


def _message(*blocks) -> SimpleNamespace:
    return SimpleNamespace(content=list(blocks))


def test_extracts_text_when_it_is_the_only_block():
    msg = _message(_block("text", "# Brief"))
    assert extract_brief_text(msg) == "# Brief"


def test_skips_thinking_block_before_text():
    # Forma de respuesta real de claude-sonnet-5-5: [thinking, text].
    msg = _message(_block("thinking"), _block("text", "## Panorama"))
    assert extract_brief_text(msg) == "## Panorama"


def test_uses_last_text_block():
    msg = _message(
        _block("thinking"),
        _block("text", "parcial"),
        _block("text", "final"),
    )
    assert extract_brief_text(msg) == "final"


def test_ignores_empty_text_blocks():
    msg = _message(_block("text", ""), _block("text", "contenido"))
    assert extract_brief_text(msg) == "contenido"


def test_raises_when_no_text_block():
    msg = _message(_block("thinking"), _block("tool_use"))
    with pytest.raises(RuntimeError, match="sin bloque de texto"):
        extract_brief_text(msg)


def test_raises_on_empty_content():
    with pytest.raises(RuntimeError, match="sin bloque de texto"):
        extract_brief_text(_message())
