"""Tests for authentication & RBAC (Phase 3)."""
from tests.conftest import login


def test_unauthenticated_redirect(client):
    r = client.get("/profile")
    assert r.status_code == 302
    assert "/auth/login" in r.headers["Location"]


def test_bad_password_shows_error(client, employee_id):
    r = login(client, "bob@corp.com", "wrong-password")
    assert b"Invalid email or password" in r.data


def test_successful_login_and_logout(client, employee_id):
    r = login(client, "bob@corp.com")
    assert r.status_code == 200

    r = client.get("/profile")
    assert r.status_code == 200
    assert b"Bob Employee" in r.data

    r = client.get("/auth/logout", follow_redirects=True)
    assert b"logged out" in r.data.lower()

    r = client.get("/profile")
    assert r.status_code == 302


def test_deactivated_user_blocked(app, client):
    from tests.conftest import make_user
    from app.models import Role
    make_user(app, "Inactive", "inactive@corp.com", Role.EMPLOYEE, is_active_user=False)

    r = login(client, "inactive@corp.com")
    assert b"deactivated" in r.data


def test_open_redirect_guarded(client, admin_id):
    r = client.post(
        "/auth/login?next=https://evil.example.com/steal",
        data={"email": "alice@corp.com", "password": "Passw0rd!"},
    )
    assert r.status_code == 302
    assert r.headers["Location"] == "/"


def test_failed_login_audit_logged(app, client, admin_id):
    login(client, "alice@corp.com", "wrong-password")
    with app.app_context():
        from app.models import AuditLog
        actions = [a.action for a in AuditLog.query.all()]
        assert "LOGIN_FAILED" in actions
