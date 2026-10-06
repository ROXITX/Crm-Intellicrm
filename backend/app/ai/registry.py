import json
import threading

import joblib

from app.ai.training import VERSION, model_dir, train_one

_cache: dict[str, tuple] = {}
_lock = threading.Lock()


def get_model(name: str):
    """Returns (model, metadata). Trains on first use if no artifact for the current version exists."""
    with _lock:
        if name in _cache:
            return _cache[name]
        d = model_dir()
        mp, jp = d / f"{name}.joblib", d / f"{name}.json"
        meta = json.loads(jp.read_text()) if jp.exists() else None
        if not mp.exists() or not meta or meta.get("version") != VERSION:
            meta = train_one(name)
        _cache[name] = (joblib.load(mp), meta)
        return _cache[name]


def clear_cache():
    _cache.clear()
