"""
AuditLog model - records security/compliance-relevant actions
(login, logout, document upload/delete, role changes, admin
actions) for the Admin Panel's Logs view (Phase 11).
"""
from app.utils.timeutils import utcnow
from app import db


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", back_populates="audit_logs")

    action = db.Column(db.String(100), nullable=False)  # e.g. "LOGIN", "DOCUMENT_DELETE"
    details = db.Column(db.Text, nullable=True)
    ip_address = db.Column(db.String(45), nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    def __repr__(self):
        return f"<AuditLog {self.action} user={self.user_id}>"
