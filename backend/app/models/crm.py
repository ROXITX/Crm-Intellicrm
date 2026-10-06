from ._base import *


class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    source: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    estimated_value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    score_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    converted_customer_id: Mapped[uuid.UUID | None] = fk("customers.id", nullable=True)
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()
    __table_args__ = (
        CheckConstraint("score BETWEEN 0 AND 100", name="ck_leads_score"),
        CheckConstraint("score_probability BETWEEN 0 AND 1", name="ck_leads_prob"),
        CheckConstraint("estimated_value >= 0", name="ck_leads_value"),
        CheckConstraint("status IN ('new','contacted','qualified','proposal','negotiation','won','lost')", name="ck_leads_status"),
    )


class LeadInteraction(Base):
    __tablename__ = "lead_interactions"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    lead_id: Mapped[uuid.UUID] = fk("leads.id")
    type: Mapped[str] = mapped_column(String(50))
    channel: Mapped[str | None] = mapped_column(String(50))
    content: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = ts(False)
    created_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    created_at: Mapped[datetime] = now_col()


class Customer(Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    name: Mapped[str] = mapped_column(String(200))
    company_name: Mapped[str | None] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    industry: Mapped[str | None] = mapped_column(String(100))
    account_owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    source_lead_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    tags: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
    health_status: Mapped[str | None] = mapped_column(String(30))
    health_score: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    revenue: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    last_interaction_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()
    __table_args__ = (
        CheckConstraint("health_score BETWEEN 0 AND 100", name="ck_customers_health"),
        CheckConstraint("revenue >= 0", name="ck_customers_revenue"),
        Index("idx_customers_org_health", "organization_id", "health_status"),
    )


class CustomerContact(Base):
    __tablename__ = "customer_contacts"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID] = fk("customers.id")
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)  # links a client-portal login
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(255))
    phone: Mapped[str | None] = mapped_column(String(50))
    job_title: Mapped[str | None] = mapped_column(String(100))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
