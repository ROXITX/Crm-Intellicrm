import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.audit import notify
from app.core.db import SessionLocal, get_db
from app.core.deps import Ctx, client_customer_id, require
from app.core.errors import bad_request, forbidden
from app.core.scope import customer_cond, project_cond, ticket_cond
from app.core.security import decode_access_token
from app.core.util import get_or_404, ser
from app.models import (Conversation, ConversationMember, Customer, CustomerContact, Message, OrganizationMember, Project,
                        Role, Ticket, User)

router = APIRouter(tags=["messages"])


class ConvIn(BaseModel):
    type: Literal["client", "internal"]
    title: str | None = Field(None, max_length=200)
    customer_id: uuid.UUID | None = None
    project_id: uuid.UUID | None = None
    ticket_id: uuid.UUID | None = None
    member_ids: list[uuid.UUID] = []


class MsgIn(BaseModel):
    body: str = Field(min_length=1, max_length=5000)


class Hub:
    """In-process WebSocket fan-out. For multi-instance deployments swap for Redis pub/sub."""
    def __init__(self):
        self.conns: dict[uuid.UUID, set[WebSocket]] = {}

    async def send_user(self, user_id: uuid.UUID, payload: dict):
        for ws in list(self.conns.get(user_id, ())):
            try:
                await ws.send_text(json.dumps(payload))
            except Exception:
                self.conns[user_id].discard(ws)

    def push(self, user_ids, payload: dict):
        """Sync-callable (from sync route threads): schedule onto the running loop if any."""
        loop = _loop[0]
        if loop and loop.is_running():
            for uid in set(user_ids):
                asyncio.run_coroutine_threadsafe(self.send_user(uid, payload), loop)


_loop: list = [None]
hub = Hub()


def _member(db, ctx, conv_id) -> Conversation:
    return get_or_404(db, select(Conversation).join(ConversationMember, ConversationMember.conversation_id == Conversation.id).where(
        Conversation.id == conv_id, Conversation.organization_id == ctx.org_id,
        ConversationMember.user_id == ctx.user.id), "Conversation")


@router.get("/conversations")
def list_conversations(customer_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None,
                       ctx: Ctx = Depends(require("messages.read")), db: Session = Depends(get_db)):
    last = (select(Message.body).where(Message.conversation_id == Conversation.id, Message.deleted_at.is_(None))
            .order_by(Message.created_at.desc()).limit(1).correlate(Conversation).scalar_subquery())
    last_at = (select(func.max(Message.created_at)).where(Message.conversation_id == Conversation.id).correlate(Conversation).scalar_subquery())
    unread = (select(func.count()).select_from(Message).where(
        Message.conversation_id == Conversation.id, Message.deleted_at.is_(None), Message.sender_id != ctx.user.id,
        (ConversationMember.last_read_at.is_(None)) | (Message.created_at > ConversationMember.last_read_at)
    ).correlate(Conversation, ConversationMember).scalar_subquery())
    conds = [Conversation.organization_id == ctx.org_id, ConversationMember.user_id == ctx.user.id]
    if customer_id: conds.append(Conversation.customer_id == customer_id)
    if project_id: conds.append(Conversation.project_id == project_id)
    rows = db.execute(select(Conversation, last, last_at, unread, Customer.name).join(
        ConversationMember, ConversationMember.conversation_id == Conversation.id).outerjoin(
        Customer, Customer.id == Conversation.customer_id).where(*conds
    ).order_by(func.coalesce(last_at, Conversation.created_at).desc())).all()
    return [ser(c, extra={"last_message": l, "last_message_at": la.isoformat() if la else None, "unread": u or 0,
                          "customer_name": cn}) for c, l, la, u, cn in rows]


@router.post("/conversations", status_code=201)
def create_conversation(body: ConvIn, ctx: Ctx = Depends(require("messages.write")), db: Session = Depends(get_db)):
    members = set(body.member_ids) | {ctx.user.id}
    customer_id = body.customer_id
    if ctx.is_client:
        if body.type != "client":
            raise forbidden("Clients can only start client conversations")
        customer_id = client_customer_id(db, ctx)
        owner = db.get(Customer, customer_id).account_owner_id
        members = {ctx.user.id} | ({owner} if owner else set())  # clients cannot pick arbitrary recipients
    else:
        if customer_id:
            get_or_404(db, select(Customer).where(Customer.id == customer_id, customer_cond(db, ctx)), "Customer")
        if body.type == "client" and not customer_id:
            raise bad_request("Client conversations must be linked to a customer", "VALIDATION_ERROR")
        roles = dict(db.execute(select(OrganizationMember.user_id, Role.name).join(Role, Role.id == OrganizationMember.role_id).where(
            OrganizationMember.organization_id == ctx.org_id, OrganizationMember.user_id.in_(members), OrganizationMember.status == "active")).all())
        if set(members) - set(roles):
            raise bad_request("Some members do not belong to this organization", "INVALID_MEMBERS")
        client_ids = {u for u, r in roles.items() if r == "client"}
        if body.type == "internal" and client_ids:
            raise bad_request("Internal conversations cannot include clients", "INVALID_MEMBERS")
        if client_ids:
            ok = set(db.scalars(select(CustomerContact.user_id).where(CustomerContact.customer_id == customer_id,
                                                                       CustomerContact.user_id.in_(client_ids))))
            if client_ids - ok:
                raise bad_request("Client member does not belong to this customer", "INVALID_MEMBERS")
    if body.project_id:
        get_or_404(db, select(Project).where(Project.id == body.project_id, project_cond(db, ctx)), "Project")
    if body.ticket_id:
        get_or_404(db, select(Ticket).where(Ticket.id == body.ticket_id, ticket_cond(db, ctx)), "Ticket")
    conv = Conversation(organization_id=ctx.org_id, customer_id=customer_id, project_id=body.project_id,
                        ticket_id=body.ticket_id, type="client" if ctx.is_client else body.type, title=body.title)
    db.add(conv)
    db.flush()
    for uid in members:
        db.add(ConversationMember(conversation_id=conv.id, user_id=uid, last_read_at=datetime.now(timezone.utc) if uid == ctx.user.id else None))
    return ser(conv)


@router.get("/conversations/{conv_id}/messages")
def get_messages(conv_id: uuid.UUID, q: str | None = None, limit: int = Query(100, le=200),
                 ctx: Ctx = Depends(require("messages.read")), db: Session = Depends(get_db)):
    conv = _member(db, ctx, conv_id)
    stmt = (select(Message, User.first_name).join(User, User.id == Message.sender_id)
            .where(Message.conversation_id == conv.id, Message.organization_id == ctx.org_id, Message.deleted_at.is_(None)))
    if q:
        stmt = stmt.where(Message.body.ilike(f"%{q}%"))
    rows = db.execute(stmt.order_by(Message.created_at.desc()).limit(limit)).all()
    me = db.get(ConversationMember, (conv.id, ctx.user.id))
    me.last_read_at = datetime.now(timezone.utc)
    others = db.scalars(select(ConversationMember.last_read_at).where(ConversationMember.conversation_id == conv.id,
                                                                     ConversationMember.user_id != ctx.user.id)).all()
    return {"conversation": ser(conv), "messages": [ser(m, extra={"sender_name": n,
            "read_by_all": bool(others) and all(r and r >= m.created_at for r in others)}) for m, n in reversed(rows)]}


@router.post("/conversations/{conv_id}/messages", status_code=201)
def send_message(conv_id: uuid.UUID, body: MsgIn, ctx: Ctx = Depends(require("messages.write")), db: Session = Depends(get_db)):
    conv = _member(db, ctx, conv_id)
    m = Message(organization_id=ctx.org_id, conversation_id=conv.id, sender_id=ctx.user.id, body=body.body)
    db.add(m)
    db.flush()
    others = list(db.scalars(select(ConversationMember.user_id).where(ConversationMember.conversation_id == conv.id,
                                                                     ConversationMember.user_id != ctx.user.id)))
    for uid in others:
        notify(db, ctx.org_id, uid, "message", f"New message from {ctx.user.first_name}", body.body[:120], "conversation", conv.id)
    if conv.customer_id and not ctx.is_client:
        db.get(Customer, conv.customer_id).last_interaction_at = m.created_at
    out = ser(m, extra={"sender_name": ctx.user.first_name})
    hub.push(others, {"type": "message", "conversation_id": str(conv.id), "message": out})
    return out


@router.websocket("/ws")
async def ws_endpoint(ws: WebSocket, token: str):
    """Real-time channel: message pushes, notifications, typing indicators. Auth via access token."""
    try:
        data = decode_access_token(token)
        user_id, org_id = uuid.UUID(data["sub"]), uuid.UUID(data["org"])
    except (jwt.PyJWTError, ValueError, KeyError):
        await ws.close(code=4401)
        return
    with SessionLocal() as db:
        ok = db.scalar(select(OrganizationMember.id).where(OrganizationMember.user_id == user_id,
                                                           OrganizationMember.organization_id == org_id,
                                                           OrganizationMember.status == "active"))
    if not ok:
        await ws.close(code=4401)
        return
    await ws.accept()
    _loop[0] = asyncio.get_running_loop()
    hub.conns.setdefault(user_id, set()).add(ws)
    try:
        while True:
            msg = json.loads(await ws.receive_text())
            if msg.get("type") == "typing" and msg.get("conversation_id"):
                with SessionLocal() as db:
                    cid = uuid.UUID(msg["conversation_id"])
                    members = list(db.scalars(select(ConversationMember.user_id).where(ConversationMember.conversation_id == cid)))
                if user_id in members:  # membership re-checked server-side
                    for uid in members:
                        if uid != user_id:
                            await hub.send_user(uid, {"type": "typing", "conversation_id": str(cid), "user_id": str(user_id)})
    except (WebSocketDisconnect, ValueError, KeyError):
        pass
    finally:
        hub.conns.get(user_id, set()).discard(ws)
