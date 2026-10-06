from ._base import *


class AIPrediction(Base):
    __tablename__ = "ai_predictions"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True))
    prediction_type: Mapped[str] = mapped_column(String(100))
    prediction_value: Mapped[Decimal | None] = mapped_column(Numeric(10, 6))
    risk_level: Mapped[str | None] = mapped_column(String(30))
    confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    model_name: Mapped[str] = mapped_column(String(100))
    model_version: Mapped[str] = mapped_column(String(50))
    explanation: Mapped[dict | None] = mapped_column(JSONB)
    created_at: Mapped[datetime] = now_col()
    __table_args__ = (
        Index("idx_ai_pred_entity", "organization_id", "entity_type", "entity_id", "prediction_type"),
        CheckConstraint("confidence BETWEEN 0 AND 1", name="ck_ai_pred_conf"),
    )


class AIRecommendation(Base):
    __tablename__ = "ai_recommendations"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    prediction_id: Mapped[uuid.UUID | None] = fk("ai_predictions.id", nullable=True)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    recommended_action: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), default="pending")
    created_at: Mapped[datetime] = now_col()
    acted_at: Mapped[datetime | None] = ts()
    acted_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    __table_args__ = (CheckConstraint("status IN ('pending','accepted','rejected','completed','expired')", name="ck_ai_rec_status"),)


class Notification(Base):
    __tablename__ = "notifications"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    type: Mapped[str] = mapped_column(String(100))
    title: Mapped[str] = mapped_column(String(300))
    message: Mapped[str] = mapped_column(Text)
    entity_type: Mapped[str | None] = mapped_column(String(50))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    read_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
    __table_args__ = (Index("idx_notifications_unread", "user_id", postgresql_where=text("read_at IS NULL")),)


class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    actor_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    action: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str | None] = mapped_column(String(100))
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    before_data: Mapped[dict | None] = mapped_column(JSONB)
    after_data: Mapped[dict | None] = mapped_column(JSONB)
    meta: Mapped[dict | None] = mapped_column("metadata", JSONB)
    created_at: Mapped[datetime] = now_col()
    __table_args__ = (Index("idx_audit_org_created", "organization_id", "created_at"),)
