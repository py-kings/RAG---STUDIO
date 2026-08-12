"""
Models package. Import every model here so Flask-Migrate's
autogenerate can discover all tables from a single entry point
(`from app.models import *` / `import app.models`).
"""
from app.models.role import Role
from app.models.user import User
from app.models.document import Document
from app.models.chat_history import ChatHistory
from app.models.query_log import QueryLog
from app.models.audit_log import AuditLog

__all__ = [
    "Role",
    "User",
    "Document",
    "ChatHistory",
    "QueryLog",
    "AuditLog",
]
