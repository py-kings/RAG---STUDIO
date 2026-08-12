"""
Shared pytest fixtures.

The app is configured against an isolated SQLite database and
temp directories per test session, with CSRF disabled for form
posts. The embedding and Gemini calls are stubbed (deterministic
pseudo-embeddings, a canned chat model) since this test suite must
run without HuggingFace/Google network access - the same approach
used throughout manual verification in earlier phases.
"""
import hashlib
import os
import tempfile

import pytest

from app import create_app, db as _db
from app.models import Role, User, Document


@pytest.fixture()
def app():
    tmp_dir = tempfile.mkdtemp()
    db_path = os.path.join(tmp_dir, "test.db")

    os.environ["SECRET_KEY"] = "test-secret"
    os.environ["TEST_DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["GEMINI_API_KEY"] = "test-key"

    flask_app = create_app("testing")
    flask_app.config.update(
        WTF_CSRF_ENABLED=False,
        UPLOAD_FOLDER=os.path.join(tmp_dir, "uploads"),
        PARSED_CACHE_DIR=os.path.join(tmp_dir, "parsed_cache"),
        CHROMA_PERSIST_DIR=os.path.join(tmp_dir, "chroma_store"),
    )

    # Stub the embedding model call - deterministic pseudo-vectors so
    # semantically-different chunks land in different places without
    # needing the real (network-downloaded) BGE model.
    from app.services import embedding_service

    def fake_embed_texts(texts):
        import numpy as np
        vectors = []
        for text in texts:
            digest = int(hashlib.sha256(text.encode()).hexdigest(), 16)
            rng = np.random.default_rng(digest % (2**32))
            vec = rng.normal(size=32)
            vectors.append((vec / (vec**2).sum() ** 0.5).tolist())
        return vectors

    embedding_service.embed_texts = fake_embed_texts

    with flask_app.app_context():
        _db.create_all()
        for name in Role.ALL_ROLES:
            _db.session.add(Role(name=name))
        _db.session.commit()

    yield flask_app

    with flask_app.app_context():
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def stub_llm(app):
    """Swap in a canned chat model in place of Gemini for a test."""
    from app.services import llm_service
    from langchain_core.language_models.fake_chat_models import FakeListChatModel

    def _set(responses):
        llm_service._llm = FakeListChatModel(responses=responses)

    yield _set
    llm_service._llm = None


def make_user(app, full_name, email, role_name, password="Passw0rd!", **kwargs):
    with app.app_context():
        role = Role.query.filter_by(name=role_name).first()
        user = User(full_name=full_name, email=email, role=role, **kwargs)
        user.set_password(password)
        _db.session.add(user)
        _db.session.commit()
        return user.id


@pytest.fixture()
def admin_id(app):
    return make_user(app, "Alice Admin", "alice@corp.com", Role.ADMIN)


@pytest.fixture()
def employee_id(app):
    return make_user(app, "Bob Employee", "bob@corp.com", Role.EMPLOYEE, department="HR")


def login(client, email, password="Passw0rd!"):
    return client.post("/auth/login", data={"email": email, "password": password}, follow_redirects=True)
