"""Background worker: periodically recomputes predictions, health scores and overdue invoices.

Run:  python -m app.workers.scheduler            (loops every WORKER_INTERVAL_MINUTES, default 60)
      python -m app.workers.scheduler --once      (single pass)

If REDIS_URL is set the worker takes a short-lived Redis lock so only one worker instance runs a cycle.
"""
import logging
import os
import sys
import time

from sqlalchemy import select

from app.ai import service as ai
from app.api.billing import refresh_overdue
from app.core.config import settings
from app.core.db import SessionLocal
from app.models import Organization

log = logging.getLogger("worker")


def refresh_once(db, org_id) -> dict:
    refresh_overdue(db, org_id)
    return ai.run_all(db, org_id)


def run_cycle():
    with SessionLocal() as db:
        for org_id in list(db.scalars(select(Organization.id).where(Organization.status == "active"))):
            try:
                res = refresh_once(db, org_id)
                db.commit()
                log.info("refreshed org=%s %s", org_id, res)
            except Exception:
                db.rollback()
                log.exception("refresh failed org=%s", org_id)


def _lock():
    if not settings.redis_url:
        return True
    try:
        import redis
        return bool(redis.Redis.from_url(settings.redis_url).set("intellicrm:worker:lock", "1", nx=True, ex=300))
    except Exception:
        log.warning("Redis unavailable - running without distributed lock")
        return True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    interval = int(os.getenv("WORKER_INTERVAL_MINUTES", "60")) * 60
    while True:
        if _lock():
            run_cycle()
        if "--once" in sys.argv:
            break
        time.sleep(interval)
