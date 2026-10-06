"""Fixed-window rate limiter. Uses Redis when REDIS_URL is configured (shared across instances), else process memory."""
import time
from collections import defaultdict

from app.core.config import settings
from app.core.errors import AppError

_mem: dict[str, list[float]] = defaultdict(list)
_redis = None


def _client():
    global _redis
    if _redis is None and settings.redis_url:
        try:
            import redis
            _redis = redis.Redis.from_url(settings.redis_url, socket_timeout=0.5)
            _redis.ping()
        except Exception:
            _redis = False
    return _redis or None


def hit(key: str, limit: int, window_s: int):
    r = _client()
    if r:
        try:
            k = f"rl:{key}:{int(time.time() // window_s)}"
            n = r.incr(k)
            if n == 1:
                r.expire(k, window_s)
            if n > limit:
                raise AppError(429, "RATE_LIMITED", "Too many attempts. Please try again later.")
            return
        except AppError:
            raise
        except Exception:
            pass  # fall back to memory if Redis fails
    now = time.time()
    _mem[key] = [t for t in _mem[key] if now - t < window_s]
    if len(_mem[key]) >= limit:
        raise AppError(429, "RATE_LIMITED", "Too many attempts. Please try again later.")
    _mem[key].append(now)


def reset():
    _mem.clear()
