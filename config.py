"""
Enterprise KnowledgeOS - Configuration
Environment-based config classes. Values are read from environment
variables (see .env.example) so no secrets live in source control.

Note: these are class attributes, so os.getenv() calls below run once,
at first import of this module - fine for a normal process lifetime.
A long-lived process that changes env vars between app instances
(the test suite, a REPL) should not rely on re-importing this module;
app/__init__.py's create_app() re-applies DATABASE_URL/TEST_DATABASE_URL
on every call specifically to handle that case.
"""
import os
from dotenv import load_dotenv

load_dotenv()

basedir = os.path.abspath(os.path.dirname(__file__))


def _mysql_uri() -> str:
    user = os.getenv("DB_USER", "eakms_user")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME", "eakms_db")
    # PyMySQL as the DBAPI driver for MySQL 8
    return f"mysql+pymysql://{user}:{password}@{host}:{port}/{name}?charset=utf8mb4"


class BaseConfig:
    SECRET_KEY = os.getenv("SECRET_KEY", "change-this-in-production")

    # DATABASE_URL, if set, takes priority (CI/migration tooling convenience).
    # Normal local/production use builds the MySQL 8 URI from DB_* parts.
    SQLALCHEMY_DATABASE_URI = os.getenv("DATABASE_URL") or _mysql_uri()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    UPLOAD_FOLDER = os.path.join(basedir, "uploads")
    MAX_CONTENT_LENGTH = 25 * 1024 * 1024  # 25 MB per upload
    ALLOWED_EXTENSIONS = {"pdf", "docx", "txt"}

    # Chunking config for RAG pipeline (used from Phase 6+)
    CHUNK_SIZE = 500
    CHUNK_OVERLAP = 100

    # Phase 6: parsed chunk JSON cache (consumed by Phase 7 embeddings)
    PARSED_CACHE_DIR = os.path.join(basedir, "parsed_cache")

    CHROMA_PERSIST_DIR = os.path.join(basedir, "chroma_store")
    EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "BAAI/bge-small-en-v1.5")
    RERANKER_MODEL_NAME = os.getenv(
    "RERANKER_MODEL_NAME",
    "cross-encoder/ms-marco-MiniLM-L-6-v2",
    )

    TAVILY_API_KEY = os.getenv("TAVILY_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
    GEMINI_MODEL_NAME = os.getenv("GEMINI_MODEL_NAME", "gemini-3.6-flash")
    GEMINI_TEMPERATURE = float(os.getenv("GEMINI_TEMPERATURE", "0.2"))


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_ECHO = False


class TestingConfig(BaseConfig):
    TESTING = True
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = os.getenv(
        "TEST_DATABASE_URL", "mysql+pymysql://root:root@localhost:3306/eakms_test_db"
    )
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
        "pool_size": 10,
        "max_overflow": 20,
    }


config_by_name = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
