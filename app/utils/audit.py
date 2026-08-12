"""
Audit logging helper - writes a row to audit_logs for
security/compliance-relevant actions (login, logout, etc).
"""
from flask import request

from app import db
from app.models import AuditLog


def record_audit(user, action: str, details: str = None) -> None:
    entry = AuditLog(
        user=user,
        action=action,
        details=details,
        ip_address=request.remote_addr if request else None,
    )
    db.session.add(entry)
    db.session.commit()
