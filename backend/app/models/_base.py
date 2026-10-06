import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import (BigInteger, Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index,
                        Integer, Numeric, String, Text, UniqueConstraint, func, text)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base



def pk():
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def fk(target, nullable=False, ondelete="RESTRICT", index=True):
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=index)


def now_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


def upd_col():
    return mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)


def ts(nullable=True):
    return mapped_column(DateTime(timezone=True), nullable=nullable)
