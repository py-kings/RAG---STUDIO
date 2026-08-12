"""
RBAC helpers - route decorators enforcing role-based access control
on top of Flask-Login's session handling.
"""
from functools import wraps

from flask import abort
from flask_login import current_user


def role_required(*role_names: str):
    """
    Restrict a view to users whose Role.name is in role_names.
    Must be stacked *under* @login_required (auth check happens first).

        @auth_bp.route("/admin-only")
        @login_required
        @role_required(Role.ADMIN)
        def admin_only(): ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                abort(401)
            if not current_user.has_role(*role_names):
                abort(403)
            return view_func(*args, **kwargs)
        return wrapped
    return decorator
