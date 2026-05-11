"""
Morning Market Brief — Daily market data cache
================================================
Cachea el resultado de collect_all_data() en disco para evitar re-pegar a las
APIs cuando se re-ejecuta el brief el mismo día (debug, regeneración, etc.).
"""
import logging
import pickle
from datetime import datetime
from pathlib import Path
from typing import Callable, Dict, Optional

import config

logger = logging.getLogger(__name__)

CACHE_DIR = config.BASE_DIR / "cache"
CACHE_DIR.mkdir(exist_ok=True)


def _cache_path_for(today: Optional[datetime] = None) -> Path:
    today = today or datetime.now()
    return CACHE_DIR / f"market_data_{today.strftime('%Y-%m-%d')}.pkl"


def load_cached(today: Optional[datetime] = None) -> Optional[Dict]:
    """Return today's cached market data dict, or None if no cache exists."""
    path = _cache_path_for(today)
    if not path.exists():
        return None
    try:
        with path.open("rb") as f:
            data = pickle.load(f)
        logger.info(f"Datos cacheados leídos desde {path.name}")
        return data
    except Exception as e:
        logger.warning(f"No pude leer caché {path.name}: {e}")
        return None


def save_cache(data: Dict, today: Optional[datetime] = None) -> None:
    """Persist today's market data dict to disk."""
    path = _cache_path_for(today)
    try:
        with path.open("wb") as f:
            pickle.dump(data, f)
        logger.info(f"Datos cacheados en {path.name}")
    except Exception as e:
        logger.warning(f"No pude escribir caché {path.name}: {e}")


def collect_with_cache(collector: Callable[[], Dict], use_cache: bool = True) -> Dict:
    """
    Run `collector()` only if today's cache is missing or use_cache=False.
    Otherwise return cached data. Always writes/refreshes the cache on a fresh run.
    """
    if use_cache:
        cached = load_cached()
        if cached is not None:
            return cached
    data = collector()
    save_cache(data)
    return data
