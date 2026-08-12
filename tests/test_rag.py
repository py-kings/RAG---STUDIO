"""Tests for the complete RAG pipeline (Phases 8-10)."""
import io

from tests.conftest import login


def test_ask_question_returns_answer_with_citation(app, client, employee_id, stub_llm):
    login(client, "bob@corp.com")
    content = b"The IT security policy requires passwords of at least 12 characters."
    client.post(
        "/documents/upload",
        data={"title": "IT Policy", "file": (io.BytesIO(content), "it.txt")},
        content_type="multipart/form-data",
    )

    stub_llm(["Passwords must be at least 12 characters long."])
    r = client.post("/assistant/", data={"question": "What are the password requirements?"}, follow_redirects=True)
    assert b"12 characters" in r.data
    assert b"IT Policy" in r.data

    with app.app_context():
        from app.models import ChatHistory, QueryLog
        chat = ChatHistory.query.order_by(ChatHistory.id.desc()).first()
        assert chat.source_document is not None
        assert chat.source_document.title == "IT Policy"

        qlog = QueryLog.query.order_by(QueryLog.id.desc()).first()
        assert qlog.success is True


def test_missing_api_key_fails_gracefully(app, client, employee_id):
    login(client, "bob@corp.com")
    app.config["GEMINI_API_KEY"] = ""
    from app.services import llm_service
    llm_service._llm = None

    r = client.post("/assistant/", data={"question": "Anything?"}, follow_redirects=True)
    assert r.status_code == 200  # no crash

    with app.app_context():
        from app.models import QueryLog, ChatHistory
        assert QueryLog.query.filter_by(success=False).count() >= 1
        assert ChatHistory.query.count() == 0


def test_history_pagination_and_search(app, client, employee_id, stub_llm):
    login(client, "bob@corp.com")
    for i in range(12):
        stub_llm([f"Answer {i}"])
        client.post("/assistant/", data={"question": f"Question number {i}"})

    r = client.get("/assistant/history")
    assert b"Page 1 of 2" in r.data

    r2 = client.get("/assistant/history?q=number 7")
    assert b"Question number 7" in r2.data
    assert b"Question number 3" not in r2.data
