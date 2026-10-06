"""DEMO / DEVELOPMENT seed data - never run in production (it is only invoked explicitly).

    python -m app.seed.demo            # creates the demo organization if it does not exist
    python -m app.seed.demo --reset    # deletes and recreates the demo organization

Logins (password for all: Demo@12345):
    owner@acme-demo.example  manager@acme-demo.example  staff.ananya@acme-demo.example
    staff.karthik@acme-demo.example  staff.meera@acme-demo.example  client@acme-industries.example
"""
import random
import sys
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import select, text

from app.ai import service as aisvc
from app.api.billing import ItemIn, compute_totals
from app.core.db import SessionLocal, engine
from app.core.security import hash_password
from app.models import *  # noqa
from app.services.bootstrap import ensure_system_data

PASSWORD = "Demo@12345"
DEMO_SLUG = "acme-demo"
NOW = datetime.now(timezone.utc)


def ago(days=0, hours=0):
    return NOW - timedelta(days=days, hours=hours)


def reset(db):
    org = db.scalar(select(Organization).where(Organization.slug == DEMO_SLUG))
    if not org:
        return
    ids = [r[0] for r in db.execute(text("select user_id from organization_members where organization_id = :o"), {"o": org.id})]
    for t in ["ai_recommendations", "ai_predictions", "notifications", "audit_logs", "messages", "documents", "payments"]:
        db.execute(text(f"delete from {t} where organization_id = :o"), {"o": org.id})
    db.execute(text("delete from conversation_members where conversation_id in (select id from conversations where organization_id=:o)"), {"o": org.id})
    db.execute(text("delete from invoice_items where invoice_id in (select id from invoices where organization_id=:o)"), {"o": org.id})
    db.execute(text("delete from task_dependencies where task_id in (select id from tasks where organization_id=:o)"), {"o": org.id})
    db.execute(text("delete from project_members where organization_id=:o"), {"o": org.id})
    db.execute(text("update leads set converted_customer_id=null where organization_id=:o"), {"o": org.id})
    for t in ["conversations", "ticket_comments", "tickets", "tasks", "milestones", "invoices", "feedback", "projects", "customer_contacts",
              "customers", "lead_interactions", "leads", "organization_members"]:
        db.execute(text(f"delete from {t} where organization_id = :o"), {"o": org.id})
    db.execute(text("delete from refresh_tokens where organization_id=:o"), {"o": org.id})
    if ids:
        db.execute(text("delete from users where id = any(:ids)"), {"ids": ids})
    db.execute(text("delete from organizations where id=:o"), {"o": org.id})
    db.commit()


def seed(db):
    if db.scalar(select(Organization.id).where(Organization.slug == DEMO_SLUG)):
        print("Demo organization already exists (use --reset to recreate).")
        return
    rnd = random.Random(7)
    roles = ensure_system_data(db)
    org = Organization(name="Acme Services Pvt Ltd", slug=DEMO_SLUG, email="hello@acme-demo.example", phone="+91 80 5550 0000")
    db.add(org); db.flush()
    pw = hash_password(PASSWORD)

    def mk_user(email, first, last, role, cap=40):
        u = User(email=email, password_hash=pw, first_name=first, last_name=last, weekly_capacity_hours=cap, email_verified_at=NOW)
        db.add(u); db.flush()
        db.add(OrganizationMember(organization_id=org.id, user_id=u.id, role_id=roles[role].id))
        return u

    owner = mk_user("owner@acme-demo.example", "Rohit", "Sharma", "owner")
    manager = mk_user("manager@acme-demo.example", "Priya", "Nair", "manager")
    ananya = mk_user("staff.ananya@acme-demo.example", "Ananya", "Rao", "staff")
    karthik = mk_user("staff.karthik@acme-demo.example", "Karthik", "Iyer", "staff")
    meera = mk_user("staff.meera@acme-demo.example", "Meera", "Das", "staff")
    staff = [ananya, karthik, meera]

    # ---------------- customers
    specs = [("Acme Industries", "Manufacturing", 41), ("Beta Systems", "IT Services", 6), ("Gamma Labs", "Biotech", 9),
             ("Delta Logistics", "Logistics", 3), ("Epsilon Retail", "Retail", 12), ("Zeta Finance", "Finance", 2),
             ("Eta Health", "Healthcare", 20), ("Theta Media", "Media", 5)]
    customers = {}
    for i, (name, ind, last) in enumerate(specs):
        c = Customer(organization_id=org.id, name=name, company_name=name, email=f"contact@{name.split()[0].lower()}.example", phone=f"+91 98{i}0 00{i}00",
                     industry=ind, account_owner_id=[manager, ananya, karthik, meera][i % 4].id, last_interaction_at=ago(last), created_at=ago(200 - i * 20),
                     health_status="healthy", health_score=Decimal(80))
        db.add(c); db.flush()
        customers[name] = c
        db.add(CustomerContact(organization_id=org.id, customer_id=c.id, name=f"{name.split()[0]} Contact", email=c.email, is_primary=True, job_title="Operations Head"))
    client_user = User(email="client@acme-industries.example", password_hash=pw, first_name="Vikram", last_name="Mehta", email_verified_at=NOW)
    db.add(client_user); db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=client_user.id, role_id=roles["client"].id))
    db.add(CustomerContact(organization_id=org.id, customer_id=customers["Acme Industries"].id, user_id=client_user.id, name="Vikram Mehta", email=client_user.email, job_title="COO"))
    client2 = User(email="client@beta-systems.example", password_hash=pw, first_name="Sara", last_name="Khan", email_verified_at=NOW)
    db.add(client2); db.flush()
    db.add(OrganizationMember(organization_id=org.id, user_id=client2.id, role_id=roles["client"].id))
    db.add(CustomerContact(organization_id=org.id, customer_id=customers["Beta Systems"].id, user_id=client2.id, name="Sara Khan", email=client2.email))

    # ---------------- leads (+interactions)
    sources = ["referral", "website", "linkedin", "cold_outreach", "event"]
    statuses = ["new", "contacted", "qualified", "proposal", "negotiation", "won", "lost"]
    company = ["Nimbus", "Orbit", "Pioneer", "Quanta", "Radiant", "Summit", "Tandem", "Umbra", "Vertex", "Willow", "Xenon", "Yonder"]
    for i in range(30):
        st = statuses[min(int(abs(rnd.gauss(1.8, 1.6))), 6)]
        lead = Lead(organization_id=org.id, name=f"{rnd.choice(['Aarav', 'Diya', 'Ishaan', 'Kavya', 'Rahul', 'Neha', 'Arjun', 'Sneha'])} {rnd.choice(['Patel', 'Gupta', 'Reddy', 'Singh', 'Joshi'])}",
                    company_name=f"{rnd.choice(company)} {rnd.choice(['Corp', 'Ltd', 'Labs', 'Works'])}" if rnd.random() > 0.15 else None,
                    email=f"lead{i}@prospect.example", source=rnd.choice(sources), status=st, owner_id=rnd.choice([owner.id, manager.id, ananya.id]),
                    estimated_value=Decimal(rnd.randrange(20, 400) * 1000), created_at=ago(rnd.randrange(1, 120)))
        db.add(lead); db.flush()
        n = {"new": 0, "contacted": 2, "qualified": 4, "proposal": 6, "negotiation": 8, "won": 7, "lost": 3}[st]
        for k in range(n):
            t = rnd.choice(["email", "call", "meeting", "reply", "reply", "inquiry", "pricing_page"] + (["proposal_requested"] if st in ("proposal", "negotiation") and k == 0 else []))
            db.add(LeadInteraction(organization_id=org.id, lead_id=lead.id, type=t, channel=t, content=f"{t} with lead", occurred_at=ago(rnd.randrange(0, 45 if st != "lost" else 100)), created_by=owner.id))
        db.flush()

    # ---------------- projects + tasks
    def project(cust, name, status, start, due, progress, owner_, members, budget):
        p = Project(organization_id=org.id, customer_id=customers[cust].id, name=name, description=f"{name} for {cust}", status=status,
                    owner_id=owner_.id, progress=Decimal(progress), budget=Decimal(budget), start_date=date.today() - timedelta(days=start), due_date=date.today() + timedelta(days=due))
        db.add(p); db.flush()
        for u in {owner_, *members}:
            db.add(ProjectMember(project_id=p.id, user_id=u.id, organization_id=org.id, role="lead" if u == owner_ else "member"))
        return p

    pA = project("Acme Industries", "ERP Rollout", "delayed", 120, -5, 55, manager, [ananya, meera], 1_800_000)
    pB = project("Beta Systems", "Cloud Migration", "active", 60, 50, 45, manager, [karthik, meera], 950_000)
    pC = project("Gamma Labs", "LIMS Integration", "at_risk", 90, 12, 60, manager, [ananya, karthik], 700_000)
    pD = project("Delta Logistics", "Fleet Tracking Portal", "active", 30, 70, 30, ananya, [karthik], 400_000)
    pE = project("Zeta Finance", "Compliance Dashboard", "completed", 150, -10, 100, manager, [ananya], 600_000)
    pF = project("Theta Media", "Content Workflow", "planning", 3, 120, 0, manager, [meera], 300_000)
    for p, ms in ((pA, [("Requirements", -90, "completed", 100), ("Core modules", -30, "in_progress", 60), ("Go-live", -5, "pending", 0)]),
                  (pB, [("Discovery", -30, "completed", 100), ("Migration wave 1", 15, "in_progress", 40), ("Cutover", 50, "pending", 0)]),
                  (pC, [("Design", -40, "completed", 100), ("Integration", 8, "in_progress", 55)]), (pD, [("Prototype", 20, "in_progress", 50), ("Launch", 70, "pending", 0)])):
        for nme, off, st, pr in ms:
            db.add(Milestone(organization_id=org.id, project_id=p.id, name=nme, due_date=date.today() + timedelta(days=off), status=st, progress=Decimal(pr)))
    tasks = []
    def task(p, title, assignee, status, prio, due_off, est, act=None, cust=None):
        t = Task(organization_id=org.id, project_id=p.id if p else None, customer_id=customers[cust].id if cust else None, title=title, assignee_id=assignee.id,
                 created_by=manager.id, status=status, priority=prio, due_date=ago(-due_off), estimated_hours=Decimal(est), actual_hours=Decimal(act) if act else None,
                 completed_at=ago(1) if status == "done" else None)
        db.add(t); tasks.append(t); return t
    for k, (title, st, due) in enumerate([("Data migration scripts", "in_progress", -10), ("User acceptance testing", "blocked", -4), ("Training material", "todo", -2),
                                           ("Reports module", "in_progress", -8), ("Integration with legacy billing", "blocked", -6), ("Finalize schema", "done", -40)]):
        task(pA, title, [ananya, meera][k % 2], st, "high" if k < 4 else "medium", due, 8 + k * 2, 6 if st == "done" else None)
    for k, (title, st, due) in enumerate([("Inventory servers", "done", -20), ("Provision landing zone", "in_progress", 5), ("Migrate databases", "todo", 20), ("Network cutover plan", "todo", 35), ("Security review", "review", 10)]):
        task(pB, title, [karthik, meera][k % 2], st, "high" if k == 2 else "medium", due, 6 + k * 2)
    for k, (title, st, due) in enumerate([("API mapping", "in_progress", -1), ("Sample sync tests", "todo", 4), ("Vendor sign-off", "blocked", 7), ("Data validation", "todo", 9)]):
        task(pC, title, [ananya, karthik][k % 2], st, "critical" if k == 2 else "high", due, 7 + k * 2)
    for title, assignee, est in [("Wireframes", ananya, 8), ("GPS ingestion service", karthik, 16), ("Dashboard UI", ananya, 14)]:
        task(pD, title, assignee, "todo", "medium", 25, est)
    for k in range(10):  # heavy load for Meera => overloaded
        task(pF if k % 2 else pB, f"Content migration batch {k + 1}", meera, "todo", rnd.choice(["medium", "high"]), rnd.randrange(3, 14), 9)
    task(None, "Quarterly review prep for Acme", ananya, "todo", "medium", 6, 6, cust="Acme Industries")
    db.flush()
    db.add(TaskDependency(task_id=tasks[1].id, depends_on_task_id=tasks[0].id))

    # ---------------- tickets (predictions generated by the real models)
    tdata = [("Acme Industries", "Repeated failures in the billing sync", "This is unacceptable, the billing sync has failed repeatedly and we are losing money. Nobody has responded.", "open", None),
             ("Acme Industries", "Reports are still not working", "Very disappointed, the monthly report export is still not working after three weeks.", "in_progress", None),
             ("Acme Industries", "Missed go-live deadline again", "Extremely frustrated, the project missed the deadline again and the system is down for our team.", "open", None),
             ("Gamma Labs", "Production outage on LIMS sync", "Production outage - system is down and all users blocked. Urgent!", "open", None),
             ("Gamma Labs", "Terrible turnaround on support", "Worst experience so far, completely broken data upload and nobody has responded.", "in_progress", None),
             ("Beta Systems", "How do I change my billing address?", "Question about how do I update the contact details on the account settings page.", "open", None),
             ("Beta Systems", "Invoice copy needed", "Please find the attached purchase order, can you share a copy of the invoice?", "resolved", 3),
             ("Delta Logistics", "Great work on the prototype", "Thank you so much, really happy with the service and the new dashboard. Excellent support!", "closed", 5),
             ("Epsilon Retail", "Minor typo on the dashboard", "Minor typo in the monthly report heading, cosmetic issue when convenient.", "open", None),
             ("Zeta Finance", "Intermittent error on export", "Intermittent error when exporting the compliance data, needs fixing this week.", "in_progress", None)]
    tickets = []
    for cust, subj, desc, st, resolved_days in tdata:
        a = aisvc.analyze_ticket(subj, desc)
        c = customers[cust]
        t = Ticket(organization_id=org.id, customer_id=c.id, assigned_to=c.account_owner_id, created_by=client_user.id if cust == "Acme Industries" else owner.id, subject=subj,
                   description=desc, category=a["category"], priority=a["predicted_priority"], status=st, sentiment=a["sentiment"], sentiment_confidence=a["sentiment_confidence"],
                   predicted_priority=a["predicted_priority"], priority_confidence=a["priority_confidence"], created_at=ago(rnd.randrange(2, 25)),
                   resolved_at=ago(resolved_days) if resolved_days else None)
        t.sla_due_at = t.created_at + timedelta(hours={"critical": 4, "high": 8, "medium": 24, "low": 72}[t.priority])
        db.add(t); db.flush(); aisvc.record_ticket_predictions(db, t, a); tickets.append(t)
    db.add(TicketComment(organization_id=org.id, ticket_id=tickets[0].id, author_id=manager.id, body="Looking into the sync logs now.", is_internal=False))
    db.add(TicketComment(organization_id=org.id, ticket_id=tickets[0].id, author_id=manager.id, body="INTERNAL: root cause is the legacy connector; engineering is patching.", is_internal=True))

    # ---------------- billing
    def invoice(cust, issued_days_ago, due_days, items, status, paid_ratio=0.0):
        lines, sub, tax, total = compute_totals([ItemIn(description=d, quantity=q, unit_price=u, tax_rate=18) for d, q, u in items], Decimal(0))
        n = db.scalar(select(text("count(*)")).select_from(Invoice).where(Invoice.organization_id == org.id)) + 1
        inv = Invoice(organization_id=org.id, customer_id=customers[cust].id, invoice_number=f"INV-{date.today().year}-{n:05d}", status=status,
                      issue_date=date.today() - timedelta(days=issued_days_ago), due_date=date.today() - timedelta(days=issued_days_ago) + timedelta(days=due_days),
                      subtotal=sub, tax=tax, discount=Decimal(0), total=total)
        db.add(inv); db.flush()
        for pos, (it, lt) in enumerate(lines):
            db.add(InvoiceItem(invoice_id=inv.id, description=it.description, quantity=it.quantity, unit_price=it.unit_price, tax_rate=it.tax_rate, line_total=lt, position=pos))
        paid = (total * Decimal(str(paid_ratio))).quantize(Decimal("0.01"))
        if paid:
            db.add(Payment(organization_id=org.id, invoice_id=inv.id, amount=paid, method="bank_transfer", status="completed", paid_at=ago(max(issued_days_ago - 5, 1)),
                           transaction_reference=f"TXN{rnd.randrange(10**8, 10**9)}"))
            inv.amount_paid = paid
            customers[cust].revenue += paid
        return inv
    for cust in customers:
        for m in range(3):
            invoice(cust, 60 + m * 30, 30, [("Consulting services", Decimal(rnd.randrange(20, 60)), Decimal(2500)), ("Platform subscription", Decimal(1), Decimal(45000))], "paid", 1.0)
    invoice("Acme Industries", 50, 30, [("ERP rollout milestone 2", Decimal(1), Decimal(450000))], "sent", 0.0)
    invoice("Beta Systems", 49, 30, [("Cloud migration - discovery", Decimal(1), Decimal(180000))], "sent", 0.0)
    invoice("Gamma Labs", 25, 30, [("LIMS integration phase 1", Decimal(1), Decimal(220000))], "partially_paid", 0.4)
    invoice("Delta Logistics", 5, 30, [("Prototype build", Decimal(1), Decimal(150000))], "sent", 0.0)
    invoice("Epsilon Retail", 0, 15, [("Support retainer", Decimal(1), Decimal(60000))], "draft", 0.0)

    for cust, ratings in {"Acme Industries": [2, 2, 3], "Beta Systems": [4, 5], "Gamma Labs": [2, 3], "Delta Logistics": [5, 5], "Zeta Finance": [4]}.items():
        for r in ratings:
            db.add(Feedback(organization_id=org.id, customer_id=customers[cust].id, rating=r, comment="Auto-seeded feedback"))

    # ---------------- conversations
    conv = Conversation(organization_id=org.id, customer_id=customers["Acme Industries"].id, project_id=pA.id, type="client", title="ERP Rollout - updates")
    internal = Conversation(organization_id=org.id, project_id=pA.id, type="internal", title="ERP Rollout - internal")
    db.add_all([conv, internal]); db.flush()
    for u in (client_user, manager, ananya):
        db.add(ConversationMember(conversation_id=conv.id, user_id=u.id))
    for u in (manager, ananya, meera, owner):
        db.add(ConversationMember(conversation_id=internal.id, user_id=u.id))
    db.add_all([Message(organization_id=org.id, conversation_id=conv.id, sender_id=client_user.id, body="When will the reports module be ready?", created_at=ago(2)),
                Message(organization_id=org.id, conversation_id=conv.id, sender_id=manager.id, body="We're targeting next week; I'll share a revised plan tomorrow.", created_at=ago(1, 20)),
                Message(organization_id=org.id, conversation_id=internal.id, sender_id=manager.id, body="Acme is unhappy - let's prioritise unblocking UAT.", created_at=ago(1))])
    db.flush()
    from app.workers.scheduler import refresh_once
    # backdate: ensure Acme's recency reflects the scenario (messages/tickets above touch nothing automatically)
    customers["Acme Industries"].last_interaction_at = ago(41)
    db.commit()
    refresh_once(db, org.id)
    db.commit()
    print(f"Seeded demo organization '{org.name}'. Login: owner@acme-demo.example / {PASSWORD}")


if __name__ == "__main__":
    with SessionLocal() as db:
        if "--reset" in sys.argv:
            reset(db)
        seed(db)
