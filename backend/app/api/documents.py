import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.audit import audit
from app.core.config import settings
from app.core.db import get_db
from app.core.deps import Ctx, require
from app.core.errors import bad_request, forbidden
from app.core.scope import customer_cond, document_cond, invoice_cond, project_cond, ticket_cond
from app.core.security import create_access_token  # noqa: F401
from app.core.util import Page, get_or_404, paginate, ser
from app.models import Customer, Document, Invoice, Project, Ticket

router = APIRouter(prefix="/documents", tags=["documents"])
ALLOWED = {".pdf", ".png", ".jpg", ".jpeg", ".gif", ".txt", ".csv", ".docx", ".xlsx", ".pptx", ".doc", ".xls", ".md", ".zip"}
HIDE = {"storage_key"}  # storage keys are never exposed


def _root() -> Path:
    p = Path(settings.storage_dir).resolve()
    p.mkdir(parents=True, exist_ok=True)
    return p


@router.get("")
def list_documents(customer_id: uuid.UUID | None = None, project_id: uuid.UUID | None = None, ticket_id: uuid.UUID | None = None,
                   q: str | None = None, p: Page = Depends(), ctx: Ctx = Depends(require("documents.read")), db: Session = Depends(get_db)):
    conds = [document_cond(db, ctx)]
    if customer_id: conds.append(Document.customer_id == customer_id)
    if project_id: conds.append(Document.project_id == project_id)
    if ticket_id: conds.append(Document.ticket_id == ticket_id)
    if q: conds.append(Document.file_name.ilike(f"%{q}%"))
    return paginate(db, select(Document).where(*conds).order_by(Document.created_at.desc(), Document.id), p,
                    lambda r: ser(r[0], HIDE))


@router.post("", status_code=201)
async def upload(file: UploadFile = File(...), customer_id: uuid.UUID | None = Form(None), project_id: uuid.UUID | None = Form(None),
                 ticket_id: uuid.UUID | None = Form(None), invoice_id: uuid.UUID | None = Form(None),
                 ctx: Ctx = Depends(require("documents.write")), db: Session = Depends(get_db)):
    """Binary goes to file storage under a generated key; only metadata is stored in PostgreSQL."""
    original = os.path.basename(file.filename or "file")
    ext = Path(original).suffix.lower()
    if ext not in ALLOWED:
        raise bad_request(f"File type {ext or '(none)'} is not allowed", "INVALID_FILE_TYPE")
    if not any([customer_id, project_id, ticket_id, invoice_id]):
        raise bad_request("Attach the document to a customer, project, ticket or invoice", "VALIDATION_ERROR")
    # every referenced entity must be visible to the uploader
    if customer_id: get_or_404(db, select(Customer).where(Customer.id == customer_id, customer_cond(db, ctx)), "Customer")
    if project_id: get_or_404(db, select(Project).where(Project.id == project_id, project_cond(db, ctx)), "Project")
    if ticket_id: get_or_404(db, select(Ticket).where(Ticket.id == ticket_id, ticket_cond(db, ctx)), "Ticket")
    if invoice_id: get_or_404(db, select(Invoice).where(Invoice.id == invoice_id, invoice_cond(db, ctx)), "Invoice")
    data = await file.read(settings.max_upload_bytes + 1)
    if len(data) > settings.max_upload_bytes:
        raise bad_request("File is too large", "FILE_TOO_LARGE")
    key = f"{ctx.org_id}/{uuid.uuid4().hex}{ext}"  # client filename is never used as a path
    dest = _root() / key
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(data)
    doc = Document(organization_id=ctx.org_id, uploaded_by=ctx.user.id, customer_id=customer_id, project_id=project_id,
                   ticket_id=ticket_id, invoice_id=invoice_id, file_name=original[:255], storage_key=key,
                   mime_type=mimetypes.guess_type(original)[0] or "application/octet-stream", file_size=len(data))
    db.add(doc)
    db.flush()
    audit(db, ctx, "document.upload", "document", doc.id, meta={"file_name": original})
    return ser(doc, HIDE)


@router.get("/{doc_id}/download")
def download(doc_id: uuid.UUID, ctx: Ctx = Depends(require("documents.read")), db: Session = Depends(get_db)):
    doc = get_or_404(db, select(Document).where(Document.id == doc_id, document_cond(db, ctx)), "Document")
    path = (_root() / doc.storage_key).resolve()
    if _root() not in path.parents or not path.exists():
        raise forbidden("File is unavailable")
    return FileResponse(path, media_type=doc.mime_type, filename=doc.file_name)


@router.delete("/{doc_id}", status_code=204)
def delete_document(doc_id: uuid.UUID, ctx: Ctx = Depends(require("documents.write")), db: Session = Depends(get_db)):
    doc = get_or_404(db, select(Document).where(Document.id == doc_id, document_cond(db, ctx)), "Document")
    if not ctx.is_owner and doc.uploaded_by != ctx.user.id:
        raise forbidden("Only the uploader or an owner can delete this document")
    doc.deleted_at = datetime.now(timezone.utc)
    audit(db, ctx, "document.delete", "document", doc.id)
