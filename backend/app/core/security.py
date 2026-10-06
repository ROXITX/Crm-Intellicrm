import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, InvalidHashError

from app.core.config import settings

_ph = PasswordHasher()  # Argon2id


def hash_password(pw: str) -> str:
    return _ph.hash(pw)


def verify_password(pw: str, hashed: str) -> bool:
    try:
        return _ph.verify(hashed, pw)
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(user_id: uuid.UUID, org_id: uuid.UUID) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "org": str(org_id), "typ": "access", "iat": now,
               "exp": now + timedelta(minutes=settings.access_ttl_minutes)}
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def decode_access_token(token: str) -> dict:
    data = jwt.decode(token, settings.jwt_secret, algorithms=["HS256"])
    if data.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return data


def new_refresh_token() -> tuple[str, str]:
    """Opaque random token; only its SHA-256 is stored server-side."""
    raw = secrets.token_urlsafe(48)
    return raw, hash_token(raw)


def hash_token(raw: str) -> str:
    return hashlib.sha256((raw + settings.jwt_refresh_secret).encode()).hexdigest()
