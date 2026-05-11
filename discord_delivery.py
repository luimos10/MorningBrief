"""
Morning Market Brief — Discord delivery
=========================================
Envía el brief a un canal Discord vía webhook.
Configura DISCORD_WEBHOOK_URL en .env para activar.
"""
import logging
import os
from pathlib import Path
from typing import Optional

import requests

logger = logging.getLogger(__name__)

DISCORD_MAX_LEN = 1900  # margen sobre el 2000 oficial


def _split_for_discord(text: str, max_len: int = DISCORD_MAX_LEN):
    """Split text into chunks that fit Discord's 2000-char message limit."""
    if len(text) <= max_len:
        yield text
        return
    buf = []
    size = 0
    for line in text.splitlines(keepends=True):
        if size + len(line) > max_len and buf:
            yield "".join(buf)
            buf, size = [], 0
        buf.append(line)
        size += len(line)
    if buf:
        yield "".join(buf)


def deliver_to_discord(brief_text: str, html_path: Optional[Path] = None) -> bool:
    """
    Send the brief to Discord via webhook. Returns True on success.
    Silently no-ops (returns False) if DISCORD_WEBHOOK_URL is not set.
    """
    webhook = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
    if not webhook:
        logger.info("DISCORD_WEBHOOK_URL no configurado; salto Discord delivery.")
        return False

    try:
        for chunk in _split_for_discord(brief_text):
            resp = requests.post(webhook, json={"content": chunk}, timeout=15)
            resp.raise_for_status()

        if html_path is not None and html_path.exists():
            with html_path.open("rb") as f:
                resp = requests.post(
                    webhook,
                    files={"file": (html_path.name, f, "text/html")},
                    timeout=30,
                )
                resp.raise_for_status()

        logger.info("Brief entregado a Discord.")
        return True
    except Exception as e:
        logger.error(f"Discord delivery falló: {e}")
        return False
