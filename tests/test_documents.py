"""Tests for document management, parsing, and embedding (Phases 5-7)."""
import io

from tests.conftest import login


def test_disallowed_extension_rejected(client, employee_id):
    login(client, "bob@corp.com")
    r = client.post(
        "/documents/upload",
        data={"title": "", "file": (io.BytesIO(b"data"), "malware.exe")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"Only PDF, DOCX" in r.data


def test_upload_parses_and_indexes_txt(app, client, employee_id):
    login(client, "bob@corp.com")
    content = b"The company leave policy grants 20 days of annual leave per year."
    r = client.post(
        "/documents/upload",
        data={"title": "Leave Policy", "file": (io.BytesIO(content), "leave.txt")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"uploaded, parsed, and indexed successfully" in r.data

    with app.app_context():
        from app.models import Document
        doc = Document.query.filter_by(title="Leave Policy").first()
        assert doc.status == "indexed"
        assert doc.chunk_count == 1


def test_search_by_title(client, employee_id):
    login(client, "bob@corp.com")
    client.post(
        "/documents/upload",
        data={"title": "Handbook", "file": (io.BytesIO(b"Handbook content."), "hb.txt")},
        content_type="multipart/form-data",
    )
    r = client.get("/documents/?q=hand")
    assert b"Handbook" in r.data
    r2 = client.get("/documents/?q=zzz_no_match")
    assert b"No documents found" in r2.data


def test_delete_permissions(app, client, admin_id, employee_id):
    login(client, "bob@corp.com")
    client.post(
        "/documents/upload",
        data={"title": "Bob Doc", "file": (io.BytesIO(b"Bob's own document."), "bob.txt")},
        content_type="multipart/form-data",
    )
    with app.app_context():
        from app.models import Document
        doc_id = Document.query.filter_by(title="Bob Doc").first().id

    # owner can delete their own document
    r = client.post(f"/documents/{doc_id}/delete", follow_redirects=True)
    assert b"deleted" in r.data
    assert client.get(f"/documents/{doc_id}").status_code == 404


def test_reindex_requires_staff_role(app, client, employee_id):
    login(client, "bob@corp.com")
    client.post(
        "/documents/upload",
        data={"title": "Reindex Test", "file": (io.BytesIO(b"Some content here."), "r.txt")},
        content_type="multipart/form-data",
    )
    with app.app_context():
        from app.models import Document
        doc_id = Document.query.filter_by(title="Reindex Test").first().id

    r = client.post(f"/documents/{doc_id}/reindex")
    assert r.status_code == 403


def test_reindex_does_not_duplicate_vectors(app, client, admin_id):
    login(client, "alice@corp.com")
    client.post(
        "/documents/upload",
        data={"title": "Policy", "file": (io.BytesIO(b"Some policy content for testing."), "p.txt")},
        content_type="multipart/form-data",
    )
    with app.app_context():
        from app.models import Document
        from app.services import embedding_service
        doc = Document.query.filter_by(title="Policy").first()

        before = embedding_service.get_collection().get(where={"document_id": doc.id})
        count_before = len(before["ids"])

    client.post(f"/documents/{doc.id}/reindex")

    with app.app_context():
        after = embedding_service.get_collection().get(where={"document_id": doc.id})
        assert len(after["ids"]) == count_before
