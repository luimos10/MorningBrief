"""
Morning Market Brief — Logging configuration
==============================================
Configura logging estructurado a archivo (logs/) y a stdout.
"""
import logging
import sys
from datetime import datetime
from pathlib import Path

import config

LOGS_DIR = config.BASE_DIR / "logs"
LOGS_DIR.mkdir(exist_ok=True)


def configure_logging(level: int = logging.INFO) -> Path:
    """
    Configure root logger to write to a daily file plus stdout.
    Returns the path of the active log file.
    """
    log_path = LOGS_DIR / f"morning_brief_{datetime.now().strftime('%Y-%m-%d')}.log"

    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt, datefmt="%Y-%m-%d %H:%M:%S")

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)

    # Force UTF-8 on stdout where possible (Windows cp1252 chokes on emoji).
    stream = sys.stdout
    try:
        stream.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    stream_handler = logging.StreamHandler(stream)
    stream_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    # Reset any handlers already attached (e.g. on re-import in tests).
    root.handlers = [file_handler, stream_handler]

    # Quiet noisy third-party loggers.
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("peewee").setLevel(logging.WARNING)

    return log_path
