from ._base import *


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID] = fk("customers.id")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(30), index=True)
    owner_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    progress: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0, server_default="0")
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    start_date: Mapped[date | None] = mapped_column(Date)
    due_date: Mapped[date | None] = mapped_column(Date, index=True)
    delay_probability: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    risk_level: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()
    __table_args__ = (
        CheckConstraint("progress BETWEEN 0 AND 100", name="ck_projects_progress"),
        CheckConstraint("budget >= 0", name="ck_projects_budget"),
        CheckConstraint("delay_probability BETWEEN 0 AND 1", name="ck_projects_delay"),
        CheckConstraint("status IN ('planning','active','at_risk','delayed','completed','archived')", name="ck_projects_status"),
    )


class ProjectMember(Base):
    __tablename__ = "project_members"
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    role: Mapped[str | None] = mapped_column(String(50))
    created_at: Mapped[datetime] = now_col()


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    project_id: Mapped[uuid.UUID] = fk("projects.id")
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    due_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str | None] = mapped_column(String(30))
    progress: Mapped[Decimal | None] = mapped_column(Numeric(5, 2))
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (CheckConstraint("progress BETWEEN 0 AND 100", name="ck_milestones_progress"),)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id", nullable=True)
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id", nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    assignee_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    created_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30), index=True)
    due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    estimated_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    actual_hours: Mapped[Decimal | None] = mapped_column(Numeric(8, 2))
    completed_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()
    __table_args__ = (
        CheckConstraint("estimated_hours >= 0", name="ck_tasks_est"),
        CheckConstraint("actual_hours >= 0", name="ck_tasks_act"),
        CheckConstraint("status IN ('todo','in_progress','blocked','review','done','cancelled')", name="ck_tasks_status"),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="ck_tasks_priority"),
        Index("idx_tasks_org_assignee_status", "organization_id", "assignee_id", "status"),
    )


class TaskDependency(Base):
    __tablename__ = "task_dependencies"
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    depends_on_task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    __table_args__ = (CheckConstraint("task_id <> depends_on_task_id", name="ck_task_dep_self"),)


class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID] = fk("customers.id")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id", nullable=True)
    assigned_to: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    created_by: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    subject: Mapped[str] = mapped_column(String(300))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str | None] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(30))
    sentiment: Mapped[str | None] = mapped_column(String(30))
    sentiment_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    predicted_priority: Mapped[str | None] = mapped_column(String(20))
    priority_confidence: Mapped[Decimal | None] = mapped_column(Numeric(5, 4))
    sla_due_at: Mapped[datetime | None] = ts()
    resolved_at: Mapped[datetime | None] = ts()
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    deleted_at: Mapped[datetime | None] = ts()
    __table_args__ = (
        CheckConstraint("sentiment_confidence BETWEEN 0 AND 1", name="ck_tickets_sc"),
        CheckConstraint("priority_confidence BETWEEN 0 AND 1", name="ck_tickets_pc"),
        CheckConstraint("status IN ('open','in_progress','waiting_customer','waiting_internal','resolved','closed')", name="ck_tickets_status"),
        CheckConstraint("priority IN ('low','medium','high','critical')", name="ck_tickets_priority"),
        Index("idx_tickets_org_status", "organization_id", "status"),
    )


class TicketComment(Base):
    __tablename__ = "ticket_comments"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    ticket_id: Mapped[uuid.UUID] = fk("tickets.id")
    author_id: Mapped[uuid.UUID] = fk("users.id")
    body: Mapped[str] = mapped_column(Text)
    is_internal: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id", nullable=True)
    project_id: Mapped[uuid.UUID | None] = fk("projects.id", nullable=True)
    ticket_id: Mapped[uuid.UUID | None] = fk("tickets.id", nullable=True)
    title: Mapped[str | None] = mapped_column(String(200))
    type: Mapped[str] = mapped_column(String(30))  # client | internal
    created_at: Mapped[datetime] = now_col()
    updated_at: Mapped[datetime] = upd_col()
    __table_args__ = (CheckConstraint("type IN ('client','internal')", name="ck_conv_type"),)


class ConversationMember(Base):
    __tablename__ = "conversation_members"
    conversation_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    joined_at: Mapped[datetime] = now_col()
    last_read_at: Mapped[datetime | None] = ts()


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[uuid.UUID] = pk()
    organization_id: Mapped[uuid.UUID] = fk("organizations.id")
    conversation_id: Mapped[uuid.UUID] = fk("conversations.id")
    sender_id: Mapped[uuid.UUID] = fk("users.id")
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = now_col()
    edited_at: Mapped[datetime | None] = ts()
    deleted_at: Mapped[datetime | None] = ts()
