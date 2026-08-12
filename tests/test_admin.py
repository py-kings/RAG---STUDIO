"""Tests for the Admin Panel (Phase 11)."""
from tests.conftest import login


def test_admin_panel_requires_admin_role(client, employee_id, admin_id):
    r = client.get("/admin/")
    assert r.status_code == 302  # unauthenticated

    login(client, "bob@corp.com")
    r = client.get("/admin/")
    assert r.status_code == 403


def test_admin_can_change_role_and_deactivate(app, client, admin_id, employee_id):
    login(client, "alice@corp.com")

    with app.app_context():
        from app.models import Role
        hr_role_id = Role.query.filter_by(name=Role.HR).first().id

    r = client.post(f"/admin/users/{employee_id}/role", data={"role_id": hr_role_id}, follow_redirects=True)
    assert b"role changed to HR" in r.data

    r = client.post(f"/admin/users/{employee_id}/toggle-active", follow_redirects=True)
    assert b"now inactive" in r.data

    with app.app_context():
        from app.models import User
        from app import db
        user = db.session.get(User, employee_id)
        assert user.role.name == "HR"
        assert user.is_active_user is False


def test_admin_cannot_deactivate_self(app, client, admin_id):
    login(client, "alice@corp.com")
    client.post(f"/admin/users/{admin_id}/toggle-active")
    with app.app_context():
        from app.models import User
        from app import db
        assert db.session.get(User, admin_id).is_active_user is True


def test_audit_log_filter(app, client, admin_id, employee_id):
    login(client, "alice@corp.com")
    with app.app_context():
        from app.models import Role
        hr_role_id = Role.query.filter_by(name=Role.HR).first().id
    client.post(f"/admin/users/{employee_id}/role", data={"role_id": hr_role_id})

    r = client.get("/admin/logs?action=USER_ROLE_CHANGE")
    body = r.data.decode()
    table = body.split("<tbody>")[1].split("</tbody>")[0]
    assert "USER_ROLE_CHANGE" in table
    assert "LOGIN" not in table
