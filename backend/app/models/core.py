from ._base import *


class Organization(Base):
    __tablename__ = "organizations"
    id: Mapped[uuid.UUID] = pk()
    name: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    logo_url: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="active")
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()


class User(Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True)
    password_hash: Mapped[str] = mapped_column(Text)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str | None] = mapped_column(String(100))
    avatar_url: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    email_verified_at: Mapped[datetime | None] = ts()
    last_login_at: Mapped[datetime | None] = ts()
    preferences: Mapped[dict | None] = mapped_column(JSONB)
    weekly_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(6, 2), default=40, server_default="40")
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (CheckConstraint("email = lower(email)", name="ck_users_email_lower"),)


class Role(Base):
    __tablename__ = "roles"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID | None] = fk("organizations.id", nullable=True)
    name: Mapped[str] = mapped_column(String(50))
    description: Mapped[str | None] = mapped_column(Text)
    is_system_role: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()


class Permission(Base):
    __tablename__ = "permissions"
    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(100), unique=True)
    description: Mapped[str | None] = mapped_column(Text)


class RolePermission(Base):
    __tablename__ = "role_permissions"
    role_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True)
    permission_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("permissions.id", ondelete="CASCADE"), primary_key=True)


class OrganizationMember(Base):
    __tablename__ = "organization_members"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    role_id: Mapped[uuid.UUID] = fk("roles.id")
    status: Mapped[str] = mapped_column(String(30), default="active")
    joined_at: Mapped[datetime] = now_col()
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (UniqueConstraint("organization_id", "user_id"),)


class RefreshToken(Base):
    """Server-side refresh token record enabling rotation and revocation."""
    __tablename__ = "refresh_tokens"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = ts(False)
    revoked_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
