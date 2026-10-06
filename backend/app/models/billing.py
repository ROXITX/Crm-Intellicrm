from ._base import *


class Invoice(Base):
    __tablename__ = "invoices"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID] = fk("customers.id")
    invoice_number: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30), index=True)
    issue_date: Mapped[date] = mapped_column(Date)
    due_date: Mapped[date] = mapped_column(Date, index=True)
    subtotal: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    discount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    amount_paid: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0, server_default="0")
    currency: Mapped[str] = mapped_column(String(3), default="INR", server_default="INR")
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (
        UniqueConstraint("organization_id", "invoice_number"),
        CheckConstraint("subtotal >= 0 AND tax >= 0 AND discount >= 0 AND total >= 0 AND amount_paid >= 0", name="ck_invoices_nonneg"),
        CheckConstraint("amount_paid <= total", name="ck_invoices_paid_le_total"),
        CheckConstraint("due_date >= issue_date", name="ck_invoices_dates"),
        CheckConstraint("status IN ('draft','sent','partially_paid','paid','overdue','cancelled')", name="ck_invoices_status"),
    )


class InvoiceItem(Base):
    __tablename__ = "invoice_items"
    id: Mapped[uuid.UUID] = pk()
    invoice_id: Mapped[uuid.UUID] = fk("invoices.id")
    description: Mapped[str] = mapped_column(String(300))
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2))
    unit_price: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    tax_rate: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    position: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    __table_args__ = (CheckConstraint("quantity > 0 AND unit_price >= 0 AND tax_rate >= 0", name="ck_items_nonneg"),)


class Payment(Base):
    __tablename__ = "payments"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    invoice_id: Mapped[uuid.UUID] = fk("invoices.id")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    method: Mapped[str | None] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(30))
    transaction_reference: Mapped[str | None] = mapped_column(String(200))
    paid_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_payments_amount"),
        CheckConstraint("status IN ('pending','completed','failed','refunded')", name="ck_payments_status"),
    )


class Document(Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    uploaded_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = fk("projects.id", nullable=True)
    ticket_id: Mapped[uuid.UUID | None] = fk("tickets.id", nullable=True)
    invoice_id: Mapped[uuid.UUID | None] = fk("invoices.id", nullable=True)
    file_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(Text)
    mime_type: Mapped[str | None] = mapped_column(String(100))
    file_size: Mapped[int | None] = mapped_column(BigInteger)
    version: Mapped[int] = mapped_column(Integer, default=1, server_default="1")
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()


class Feedback(Base):
    __tablename__ = "feedback"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID] = fk("customers.id")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id", nullable=True)
    rating: Mapped[int | None] = mapped_column(Integer)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = now_col()
    __table_args__ = (CheckConstraint("rating BETWEEN 1 AND 5", name="ck_feedback_rating"),)
