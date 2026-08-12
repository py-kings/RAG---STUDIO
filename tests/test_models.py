"""Tests for core model behavior (Phase 2)."""
from app.models import Role, User


def test_password_hash_and_check(app):
    with app.app_context():
        role = Role.query.filter_by(name=Role.EMPLOYEE).first()
        user = User(full_name="Test User", email="t@corp.com", role=role)
        user.set_password("Secret123!")
        assert user.password_hash != "Secret123!"
        assert user.check_password("Secret123!")
        assert not user.check_password("wrong-password")


def test_has_role(app):
    with app.app_context():
        role = Role.query.filter_by(name=Role.ADMIN).first()
        user = User(full_name="Admin", email="a@corp.com", role=role)
        user.set_password("x")
        assert user.has_role(Role.ADMIN)
        assert user.has_role(Role.ADMIN, Role.HR)
        assert not user.has_role(Role.EMPLOYEE)


def test_all_five_roles_seeded(app):
    with app.app_context():
        names = {r.name for r in Role.query.all()}
        assert names == set(Role.ALL_ROLES)
