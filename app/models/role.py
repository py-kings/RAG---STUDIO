"""
Role model - Admin, HR, Manager, Developer, Employee.
"""
from app.utils.timeutils import utcnow
from app import db


class Role(db.Model):
    __tablename__ = "roles"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), unique=True, nullable=False)
    description = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=utcnow)

    users = db.relationship("User", back_populates="role", lazy="dynamic")

    # Canonical role names used throughout the app (RBAC checks, seed data)
    ADMIN = "Admin"
    HR = "HR"
    MANAGER = "Manager"
    DEVELOPER = "Developer"
    EMPLOYEE = "Employee"

    ALL_ROLES = [ADMIN, HR, MANAGER, DEVELOPER, EMPLOYEE]

    def __repr__(self):
        return f"<Role {self.name}>"
