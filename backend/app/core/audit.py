from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import AuditLog, Notification, User


def _clean(v):
    if isinstance(v, (Decimal, UUID)):
        return str(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def snapshot(obj, fields=None) -> dict:
    cols = fields or [c.key for c in obj.__table__.columns if c.key not in ("password_hash",)]
    return {c: _clean(getattr(obj, c, None)) for c in cols}


def audit(db: Session, ctx, action: str, entity_type: str | None = None, entity_id=None,
          before=None, after=None, meta=None):
    db.add(AuditLog(organization_id=ctx.org_id, actor_id=ctx.user.id, action=action, entity_type=entity_type,
                    entity_id=entity_id, before_data=before, after_data=after,
                    meta={**(meta or {}), "ip": ctx.ip, "user_agent": ctx.user_agent}))


def notify(db: Session, org_id, user_id, type_: str, title: str, message: str, entity_type=None, entity_id=None):
    if user_id:
        prefs = db.scalar(select(User.preferences).where(User.id == user_id)) or {}
        if prefs.get("notifications", {}).get(type_) is False:
            return  # user disabled this notification type
        db.add(Notification(organization_id=org_id, user_id=user_id, type=type_, title=title, message=message,
                            entity_type=entity_type, entity_id=entity_id))
