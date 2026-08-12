"""
Auth blueprint - login, logout, session management.
"""
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user

from app import db
from app.models import User
from app.forms.auth_forms import LoginForm
from app.utils.audit import record_audit
from app.utils.timeutils import utcnow

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("main.index"))

    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data.lower().strip()).first()

        if user is None or not user.check_password(form.password.data):
            flash("Invalid email or password.", "danger")
            record_audit(
                user=user, action="LOGIN_FAILED",
                details=f"attempted email={form.email.data!r}",
            )
            return redirect(url_for("auth.login"))

        if not user.is_active_user:
            flash("This account has been deactivated. Contact an administrator.", "danger")
            return redirect(url_for("auth.login"))

        login_user(user, remember=form.remember_me.data)
        user.last_login_at = utcnow()
        db.session.commit()
        record_audit(user=user, action="LOGIN")

        next_page = request.args.get("next")
        # Only honor local, relative "next" targets (open-redirect guard)
        if not next_page or not next_page.startswith("/"):
            next_page = url_for("main.index")
        return redirect(next_page)

    return render_template("auth/login.html", form=form)


@auth_bp.route("/logout")
@login_required
def logout():
    record_audit(user=current_user, action="LOGOUT")
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))
