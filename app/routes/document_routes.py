"""
Document blueprint - Document Management (Phase 5).

Permissions:
- Any authenticated user can upload, view, and search documents.
- Delete is allowed for the uploader or Admin/HR/Manager.
- Re-index (flagging for reprocessing) is restricted to
  Admin/HR/Manager, since it triggers pipeline work, not just
  personal file cleanup.
"""
import os

from flask import (
    Blueprint, render_template, redirect, url_for, flash, request,
    send_from_directory, abort,
)
from flask_login import login_required, current_user

from app.models import Document, Role
from app.forms.document_forms import DocumentUploadForm
from app.services import document_service, parsing_service, embedding_service
from app.services.parsing_service import ParsingError
from app.services.embedding_service import EmbeddingError
from app.utils.audit import record_audit

document_bp = Blueprint("document", __name__)

STAFF_ROLES = (Role.ADMIN, Role.HR, Role.MANAGER)


def _can_manage(document: Document) -> bool:
    return current_user.has_role(*STAFF_ROLES) or document.uploaded_by_id == current_user.id


@document_bp.route("/")
@login_required
def index():
    query = request.args.get("q", "").strip()
    file_type = request.args.get("type", "").strip() or None
    documents = document_service.search_documents(query=query or None, file_type=file_type)
    return render_template(
        "documents/index.html", documents=documents, query=query, file_type=file_type
    )


@document_bp.route("/upload", methods=["GET", "POST"])
@login_required
def upload():
    form = DocumentUploadForm()
    if form.validate_on_submit():
        document = document_service.save_uploaded_document(
            file_storage=form.file.data,
            title=form.title.data,
            uploaded_by=current_user,
        )
        record_audit(
            user=current_user, action="DOCUMENT_UPLOAD",
            details=f"document_id={document.id} title={document.title!r}",
        )

        try:
            parsing_service.parse_document(
                document, document_service.document_file_path(document)
            )
        except ParsingError as exc:
            flash(
                f'"{document.title}" uploaded, but parsing failed: {exc}. '
                "You can retry from the document page.",
                "warning",
            )
            return redirect(url_for("document.index"))

        try:
            embedding_service.embed_document(document)
            flash(f'"{document.title}" uploaded, parsed, and indexed successfully.', "success")
        except EmbeddingError as exc:
            flash(
                f'"{document.title}" was parsed but indexing failed: {exc}. '
                "You can retry from the document page.",
                "warning",
            )

        return redirect(url_for("document.index"))

    return render_template("documents/upload.html", form=form)


@document_bp.route("/<int:document_id>")
@login_required
def view(document_id):
    document = Document.query.filter_by(id=document_id, is_deleted=False).first_or_404()
    return render_template("documents/view.html", document=document)


@document_bp.route("/<int:document_id>/download")
@login_required
def download(document_id):
    document = Document.query.filter_by(id=document_id, is_deleted=False).first_or_404()
    directory = os.path.dirname(document_service.document_file_path(document))
    return send_from_directory(
        directory, document.stored_filename,
        as_attachment=True, download_name=document.original_filename,
    )


@document_bp.route("/<int:document_id>/delete", methods=["POST"])
@login_required
def delete(document_id):
    document = Document.query.filter_by(id=document_id, is_deleted=False).first_or_404()
    if not _can_manage(document):
        abort(403)

    document_service.soft_delete_document(document)
    embedding_service.delete_document_embeddings(document.id)
    record_audit(
        user=current_user, action="DOCUMENT_DELETE",
        details=f"document_id={document.id} title={document.title!r}",
    )
    flash(f'"{document.title}" deleted.', "info")
    return redirect(url_for("document.index"))


@document_bp.route("/<int:document_id>/reindex", methods=["POST"])
@login_required
def reindex(document_id):
    document = Document.query.filter_by(id=document_id, is_deleted=False).first_or_404()
    if not current_user.has_role(*STAFF_ROLES):
        abort(403)

    document_service.mark_for_reindex(document)
    try:
        parsing_service.parse_document(
            document, document_service.document_file_path(document)
        )
    except ParsingError as exc:
        flash(f'Re-indexing "{document.title}" failed during parsing: {exc}', "danger")
        record_audit(
            user=current_user, action="DOCUMENT_REINDEX",
            details=f"document_id={document.id} title={document.title!r} result=parse_failed",
        )
        return redirect(url_for("document.view", document_id=document.id))

    try:
        embedding_service.embed_document(document)
        flash(f'"{document.title}" re-parsed and re-indexed.', "info")
    except EmbeddingError as exc:
        flash(f'"{document.title}" was re-parsed but embedding failed: {exc}', "warning")

    record_audit(
        user=current_user, action="DOCUMENT_REINDEX",
        details=f"document_id={document.id} title={document.title!r}",
    )
    return redirect(url_for("document.view", document_id=document.id))
