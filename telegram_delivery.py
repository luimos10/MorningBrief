"""
Morning Market Brief — Telegram Delivery
==========================================
Envía el brief diario vía Telegram bot.

SETUP:
1. Habla con @BotFather en Telegram → /newbot → obtén el token
2. Envía un mensaje a tu bot, luego visita:
   https://api.telegram.org/bot<TOKEN>/getUpdates
   para obtener tu chat_id
3. Guarda ambos en config.py o como variables de entorno
"""
import logging
import requests
from typing import Optional
from pathlib import Path

from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception,
    before_sleep_log,
)

import config


logger = logging.getLogger(__name__)

MAX_TELEGRAM_MSG_LENGTH = 4096


def _is_transient_error(exc: BaseException) -> bool:
    """True for network errors, timeouts, 429 and 5xx; False for other 4xx.

    A 400 from Telegram (p.ej. HTML inválido) debe caer de inmediato al
    fallback sin parse_mode en vez de gastar 4 reintentos con backoff.
    """
    if isinstance(exc, requests.HTTPError):
        response = getattr(exc, "response", None)
        if response is None:
            return False
        return response.status_code == 429 or response.status_code >= 500
    return isinstance(exc, (requests.RequestException, OSError))


# Retry-wrapped helper for Telegram HTTP POST calls.
@retry(
    stop=stop_after_attempt(4),
    wait=wait_exponential(multiplier=2, min=2, max=30),
    retry=retry_if_exception(_is_transient_error),
    before_sleep=before_sleep_log(logger, logging.WARNING),
    reraise=True,
)
def _telegram_post(url: str, *, json: dict = None, data: dict = None,
                   files: dict = None, timeout: int = 30) -> requests.Response:
    """Execute a single POST to the Telegram Bot API with tenacity retry."""
    resp = requests.post(url, json=json, data=data, files=files, timeout=timeout)
    resp.raise_for_status()
    return resp


def send_telegram_message(text: str, chat_id: str = None, parse_mode: str = "HTML") -> bool:
    """Send a text message via Telegram bot."""
    token = config.TELEGRAM_BOT_TOKEN
    cid = chat_id or config.TELEGRAM_CHAT_ID

    if token == "YOUR_BOT_TOKEN" or cid == "YOUR_CHAT_ID":
        print("[WARN] Telegram no configurado. Configura TELEGRAM_BOT_TOKEN y TELEGRAM_CHAT_ID.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"

    # Split long messages
    chunks = split_message(text, MAX_TELEGRAM_MSG_LENGTH)

    success = True
    for i, chunk in enumerate(chunks):
        payload = {
            "chat_id": cid,
            "text": chunk,
            "parse_mode": parse_mode,
            "disable_web_page_preview": True,
        }
        try:
            resp = _telegram_post(url, json=payload, timeout=30)
            if not resp.json().get("ok"):
                print(f"[ERROR] Telegram chunk {i+1}: {resp.json()}")
                success = False
        except Exception as e:
            print(f"[ERROR] Telegram chunk {i+1} con parse_mode={parse_mode}: {e}")
            # Retry without parse_mode in case of formatting issues
            try:
                payload.pop("parse_mode", None)
                resp = _telegram_post(url, json=payload, timeout=30)
                data = resp.json() if resp.content else {}
                if not (resp.ok and data.get("ok")):
                    print(
                        f"[ERROR] Telegram chunk {i+1} (retry sin parse_mode): "
                        f"{resp.status_code} {resp.text[:200]}"
                    )
                    success = False
            except Exception as e2:
                print(f"[ERROR] Telegram chunk {i+1} (retry sin parse_mode): {e2}")
                success = False

    return success


def send_telegram_document(file_path: Path, caption: str = "", chat_id: str = None) -> bool:
    """Send an HTML file as a document via Telegram."""
    token = config.TELEGRAM_BOT_TOKEN
    cid = chat_id or config.TELEGRAM_CHAT_ID

    if token == "YOUR_BOT_TOKEN" or cid == "YOUR_CHAT_ID":
        print("[WARN] Telegram no configurado.")
        return False

    url = f"https://api.telegram.org/bot{token}/sendDocument"

    try:
        with open(file_path, "rb") as f:
            files = {"document": (file_path.name, f, "text/html")}
            payload = {
                "chat_id": cid,
                "caption": caption[:1024] if caption else "",
            }
            resp = _telegram_post(url, data=payload, files=files, timeout=60)
            if resp.json().get("ok"):
                print(f"[OK] Documento enviado a Telegram: {file_path.name}")
                return True
            else:
                print(f"[ERROR] Telegram document: {resp.json()}")
    except Exception as e:
        print(f"[ERROR] Telegram document send: {e}")

    return False


def split_message(text: str, max_length: int = 4096) -> list:
    """Split a long message into chunks for Telegram."""
    if len(text) <= max_length:
        return [text]

    chunks = []
    lines = text.split("\n")
    current_chunk = ""

    for line in lines:
        if len(current_chunk) + len(line) + 1 > max_length:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = line
        else:
            current_chunk += ("\n" + line) if current_chunk else line

    if current_chunk:
        chunks.append(current_chunk)

    return chunks


def format_brief_for_telegram(brief_text: str) -> str:
    """
    Format the brief text for Telegram (clean up markdown, use simple formatting).
    Telegram supports limited HTML: <b>, <i>, <code>, <pre>, <a>.
    """
    text = brief_text

    # Convert markdown bold to HTML bold
    text = text.replace("**", "")  # Remove markdown bold (we'll keep it clean)

    # Clean up any triple backticks
    text = text.replace("```", "")

    # Escape entities para que <, > y & del brief no rompan parse_mode=HTML
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    # Limit line length for mobile readability
    lines = text.split("\n")
    formatted_lines = []
    for line in lines:
        # Make section headers bold
        if line.strip().startswith(("📊", "🌍", "₿", "📈", "💻", "🥇", "📦",
                                    "🎯", "⚠", "🏛️", "🌐", "⚡")):
            formatted_lines.append(f"\n<b>{line.strip()}</b>")
        elif "━" in line or "═" in line:
            formatted_lines.append("─" * 30)
        else:
            formatted_lines.append(line)

    return "\n".join(formatted_lines)


def deliver_to_telegram(brief_text: str, html_path: Path = None) -> bool:
    """
    Full delivery: send text brief + HTML file to Telegram.
    """
    print("[INFO] Enviando brief a Telegram...")

    # Send text version (formatted)
    formatted = format_brief_for_telegram(brief_text)
    text_sent = send_telegram_message(formatted, parse_mode="HTML")

    # Send HTML file as document
    doc_sent = False
    if html_path and html_path.exists():
        doc_sent = send_telegram_document(
            html_path,
            caption="📊 Morning Brief — abre en tu browser para la versión completa"
        )

    if text_sent:
        print("[OK] Brief enviado a Telegram exitosamente.")
    elif doc_sent:
        print("[OK] Documento HTML enviado a Telegram.")
    else:
        print("[WARN] No se pudo enviar a Telegram.")

    return text_sent or doc_sent
