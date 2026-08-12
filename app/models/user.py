"""
User model. Integrates with Flask-Login (UserMixin) for session
management; password hashing via werkzeug.security.
"""
from app.utils.timeutils import utcnow

from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

from app import db


class User(db.Model, UserMixin):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)

    department = db.Column(db.String(100), nullable=True)
    is_active_user = db.Column(db.Boolean, default=True, nullable=False)

    role_id = db.Column(db.Integer, db.ForeignKey("roles.id"), nullable=False)
    role = db.relationship("Role", back_populates="users")

    created_at = db.Column(db.DateTime, default=utcnow)
    last_login_at = db.Column(db.DateTime, nullable=True)

    # --- Relationships to other modules (added as those models land) ---
    documents = db.relationship(
        "Document", back_populates="uploaded_by", lazy="dynamic",
        foreign_keys="Document.uploaded_by_id",
    )
    chat_history = db.relationship(
    "ChatHistory",
    back_populates="user",
    lazy="dynamic",
    foreign_keys="ChatHistory.user_id"
)
    query_logs = db.relationship(
        "QueryLog", back_populates="user", lazy="dynamic"
    )
    audit_logs = db.relationship(
        "AuditLog", back_populates="user", lazy="dynamic"
    )

    # --- Password helpers ---
    def set_password(self, raw_password: str) -> None:
        self.password_hash = generate_password_hash(raw_password)

    def check_password(self, raw_password: str) -> bool:
        return check_password_hash(self.password_hash, raw_password)

    # --- Flask-Login required overrides ---
    def get_id(self) -> str:
        return str(self.id)

    @property
    def is_active(self) -> bool:
        return self.is_active_user

    # --- RBAC convenience ---
    def has_role(self, *role_names: str) -> bool:
        return self.role is not None and self.role.name in role_names

    def __repr__(self):
        return f"<User {self.email}>"
