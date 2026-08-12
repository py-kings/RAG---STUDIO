"""
Document model - metadata for uploaded files. The actual file bytes
live on disk (UPLOAD_FOLDER); vector embeddings live in ChromaDB
(Phase 7). This table is the MySQL system-of-record for what exists,
who owns it, and its processing status.
"""
from app.utils.timeutils import utcnow
from app import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)

    title = db.Column(db.String(255), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), unique=True, nullable=False)
    file_type = db.Column(db.String(10), nullable=False)  # pdf, docx, txt
    file_size_bytes = db.Column(db.Integer, nullable=False)

    uploaded_by_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    uploaded_by = db.relationship(
        "User", back_populates="documents", foreign_keys=[uploaded_by_id]
    )

    # Processing pipeline status: uploaded -> parsed -> embedded -> indexed -> failed
    status = db.Column(db.String(20), default="uploaded", nullable=False)
    page_count = db.Column(db.Integer, nullable=True)
    chunk_count = db.Column(db.Integer, nullable=True)

    is_deleted = db.Column(db.Boolean, default=False, nullable=False)

    created_at = db.Column(db.DateTime, default=utcnow)
    updated_at = db.Column(
        db.DateTime, default=utcnow, onupdate=utcnow
    )

    chat_citations = db.relationship(
        "ChatHistory", back_populates="source_document", lazy="dynamic"
    )

    def __repr__(self):
        return f"<Document {self.title} ({self.status})>"
