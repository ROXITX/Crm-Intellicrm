"""Idempotent seeding of the permission catalog and system roles (required in every environment)."""
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.permissions import PERMISSIONS, ROLE_DESCRIPTIONS, ROLE_PERMISSIONS
from app.models import Permission, Role, RolePermission


def ensure_system_data(db: Session) -> dict[str, Role]:
    perms = {p.code: p for p in db.scalars(select(Permission))}
    for code, desc in PERMISSIONS.items():
        if code not in perms:
            perms[code] = Permission(code=code, description=desc)
            db.add(perms[code])
    db.flush()
    roles = {r.name: r for r in db.scalars(select(Role).where(Role.is_system_role.is_(True)))}
    for name, codes in ROLE_PERMISSIONS.items():
        role = roles.get(name)
        if not role:
            role = roles[name] = Role(name=name, description=ROLE_DESCRIPTIONS[name], is_system_role=True)
            db.add(role)
            db.flush()
        have = set(db.scalars(select(RolePermission.permission_id).where(RolePermission.role_id == role.id)))
        for code in codes:
            if perms[code].id not in have:
                db.add(RolePermission(role_id=role.id, permission_id=perms[code].id))
        # remove permissions no longer granted
        for pid in have - {perms[c].id for c in codes}:
            db.query(RolePermission).filter_by(role_id=role.id, permission_id=pid).delete()
    db.flush()
    return roles
