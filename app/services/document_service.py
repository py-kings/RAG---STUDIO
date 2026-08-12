"""
Document service - file storage and metadata operations backing
Document Management (Phase 5). Text extraction/chunking (Phase 6)
and embeddings (Phase 7) are separate services that will consume
what's written here.
"""
import os
import uuid

from flask import current_app
from werkzeug.utils import secure_filename
from sqlalchemy import or_

from app import db
from app.models import Document


def allowed_file(filename: str) -> bool:
    if "." not in filename:
        return False
    ext = filename.rsplit(".", 1)[1].lower()
    return ext in current_app.config["ALLOWED_EXTENSIONS"]


def _unique_stored_filename(original_filename: str) -> str:
    ext = original_filename.rsplit(".", 1)[1].lower()
    return f"{uuid.uuid4().hex}.{ext}"


def save_uploaded_document(file_storage, title: str, uploaded_by) -> Document:
    """
    Persist an uploaded file to UPLOAD_FOLDER and create its Document
    metadata row. Caller is responsible for validating allowed_file()
    and the presence of file_storage.filename beforehand.
    """
    original_filename = secure_filename(file_storage.filename)
    ext = original_filename.rsplit(".", 1)[1].lower()
    stored_filename = _unique_stored_filename(original_filename)

    upload_folder = current_app.config["UPLOAD_FOLDER"]
    os.makedirs(upload_folder, exist_ok=True)
    dest_path = os.path.join(upload_folder, stored_filename)
    file_storage.save(dest_path)

    file_size = os.path.getsize(dest_path)

    document = Document(
        title=title or original_filename,
        original_filename=original_filename,
        stored_filename=stored_filename,
        file_type=ext,
        file_size_bytes=file_size,
        uploaded_by=uploaded_by,
        status="uploaded",
    )
    db.session.add(document)
    db.session.commit()
    return document


def soft_delete_document(document: Document) -> None:
    document.is_deleted = True
    db.session.commit()


def mark_for_reindex(document: Document) -> None:
    """
    Flip a document's status back to 'uploaded' so the Phase 6/7
    parsing + embedding pipeline will pick it up again on its next
    pass. No actual re-parsing happens yet — that pipeline lands in
    later phases.
    """
    document.status = "uploaded"
    document.chunk_count = None
    db.session.commit()


def search_documents(query: str = None, file_type: str = None):
    q = Document.query.filter_by(is_deleted=False)
    if query:
        like = f"%{query.strip()}%"
        q = q.filter(
            or_(
                Document.title.ilike(like),
                Document.original_filename.ilike(like),
            )
        )
    if file_type:
        q = q.filter_by(file_type=file_type)
    return q.order_by(Document.created_at.desc()).all()


def document_file_path(document: Document) -> str:
    return os.path.join(current_app.config["UPLOAD_FOLDER"], document.stored_filename)
