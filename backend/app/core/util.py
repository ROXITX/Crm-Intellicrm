import uuid
from datetime import date, datetime
from decimal import Decimal

from fastapi import Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.errors import not_found


def money(v) -> Decimal:
    return Decimal(str(v)).quantize(Decimal("0.01"))


def jsonable(v):
    if isinstance(v, Decimal):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, uuid.UUID):
        return str(v)
    return v


def ser(obj, exclude: set[str] | frozenset[str] = frozenset(), extra: dict | None = None) -> dict:
    d = {c.key: jsonable(getattr(obj, c.key)) for c in obj.__table__.columns if c.key not in exclude}
    if extra:
        d.update(extra)
    return d


class Page:
    def __init__(self, page: int = Query(1, ge=1), page_size: int = Query(25, ge=1, le=100)):
        self.page, self.page_size = page, page_size


def paginate(db: Session, stmt, p: Page, mapper, count_stmt=None) -> dict:
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    rows = db.execute(stmt.limit(p.page_size).offset((p.page - 1) * p.page_size)).all()
    items = [mapper(r) for r in rows]
    return {"items": items, "page": p.page, "page_size": p.page_size, "total": total}


def get_or_404(db: Session, stmt, what="Resource"):
    obj = db.execute(stmt).scalars().first()
    if obj is None:
        raise not_found(what)
    return obj
