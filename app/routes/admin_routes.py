"""
Admin blueprint - Admin Panel.

Provides:

- User Management
- Role Assignment
- User Activation / Deactivation
- User Creation
- Audit Logs
- System Statistics
- Human-in-the-Loop Review Queue
- AI Answer Approval / Rejection / Editing

Every route in this blueprint is Admin-only.
"""

from datetime import datetime

from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    request,
    abort,
)

from flask_login import login_required, current_user

from app import db

from app.models import (
    User,
    Role,
    AuditLog,
    Document,
    ChatHistory,
    QueryLog,
)

from app.utils.audit import record_audit

from app.services import dashboard_service


admin_bp = Blueprint(
    "admin",
    __name__,
)


PAGE_SIZE = 20


# ============================================================
# ADMIN ACCESS CONTROL
# ============================================================

@admin_bp.before_request
@login_required
def require_admin():
    """
    Allow access only to users with the Admin role.
    """

    if not current_user.has_role(Role.ADMIN):
        abort(403)


# ============================================================
# ADMIN DASHBOARD
# ============================================================

@admin_bp.route("/")
def index():
    """
    Admin dashboard with system statistics and role counts.
    """

    stats = dashboard_service.get_summary_stats()

    stats["total_chats"] = (
        ChatHistory.query.count()
    )

    stats["failed_queries"] = (
        QueryLog.query
        .filter_by(success=False)
        .count()
    )

    role_counts = (
        db.session.query(
            Role.name,
            db.func.count(User.id)
        )
        .outerjoin(
            User,
            User.role_id == Role.id
        )
        .group_by(Role.name)
        .all()
    )

    return render_template(
        "admin/index.html",
        stats=stats,
        role_counts=role_counts,
    )


# ============================================================
# USER MANAGEMENT
# ============================================================

@admin_bp.route("/users")
def users():
    """
    Display all users and available roles.
    """

    query = request.args.get(
        "q",
        ""
    ).strip()

    q = User.query

    if query:

        like = f"%{query}%"

        q = q.filter(
            db.or_(
                User.full_name.ilike(like),
                User.email.ilike(like),
            )
        )

    all_users = (
        q
        .order_by(
            User.created_at.desc()
        )
        .all()
    )

    roles = (
        Role.query
        .order_by(Role.name)
        .all()
    )

    return render_template(
        "admin/users.html",
        users=all_users,
        roles=roles,
        query=query,
    )


# ============================================================
# CREATE USER
# ============================================================

@admin_bp.route(
    "/users/create",
    methods=["POST"]
)
def create_user():
    """
    Create a new user and assign a role.
    """

    full_name = request.form.get(
        "full_name",
        ""
    ).strip()

    email = request.form.get(
        "email",
        ""
    ).strip().lower()

    password = request.form.get(
        "password",
        ""
    )

    department = request.form.get(
        "department",
        ""
    ).strip()

    role_id = request.form.get(
        "role_id",
        type=int
    )

    # --------------------------------------------------------
    # Validation
    # --------------------------------------------------------

    if (
        not full_name
        or not email
        or not password
        or not role_id
    ):

        flash(
            "Name, email, password, and role are required.",
            "danger",
        )

        return redirect(
            url_for("admin.users")
        )

    if len(password) < 6:

        flash(
            "Password must contain at least 6 characters.",
            "danger",
        )

        return redirect(
            url_for("admin.users")
        )

    # --------------------------------------------------------
    # Duplicate email check
    # --------------------------------------------------------

    existing_user = (
        User.query
        .filter_by(email=email)
        .first()
    )

    if existing_user:

        flash(
            "A user with this email already exists.",
            "danger",
        )

        return redirect(
            url_for("admin.users")
        )

    # --------------------------------------------------------
    # Validate role
    # --------------------------------------------------------

    role = db.session.get(
        Role,
        role_id
    )

    if not role:

        flash(
            "Invalid role selected.",
            "danger",
        )

        return redirect(
            url_for("admin.users")
        )

    # --------------------------------------------------------
    # Create user
    # --------------------------------------------------------

    user = User(
        full_name=full_name,
        email=email,
        department=department or None,
        role=role,
        is_active_user=True,
    )

    user.set_password(password)

    db.session.add(user)

    db.session.commit()

    # --------------------------------------------------------
    # Audit log
    # --------------------------------------------------------

    record_audit(
        user=current_user,
        action="USER_CREATED",
        details=(
            f"user_id={user.id} "
            f"email={user.email!r} "
            f"role={role.name}"
        ),
    )

    flash(
        f"{user.full_name} created successfully "
        f"as {role.name}.",
        "success",
    )

    return redirect(
        url_for("admin.users")
    )


# ============================================================
# CHANGE USER ROLE
# ============================================================

@admin_bp.route(
    "/users/<int:user_id>/role",
    methods=["POST"],
)
def change_role(user_id):
    """
    Change a user's role.
    """

    user = db.get_or_404(
        User,
        user_id
    )

    role_id = request.form.get(
        "role_id",
        type=int
    )

    new_role = (
        db.session.get(
            Role,
            role_id
        )
        if role_id
        else None
    )

    if not new_role:

        flash(
            "Invalid role selected.",
            "danger",
        )

        return redirect(
            url_for("admin.users")
        )

    old_role_name = (
        user.role.name
        if user.role
        else None
    )

    user.role = new_role

    db.session.commit()

    record_audit(
        user=current_user,
        action="USER_ROLE_CHANGE",
        details=(
            f"user_id={user.id} "
            f"email={user.email!r} "
            f"{old_role_name} -> {new_role.name}"
        ),
    )

    flash(
        f"{user.full_name}'s role changed "
        f"to {new_role.name}.",
        "success",
    )

    return redirect(
        url_for("admin.users")
    )


# ============================================================
# ACTIVATE / DEACTIVATE USER
# ============================================================

@admin_bp.route(
    "/users/<int:user_id>/toggle-active",
    methods=["POST"],
)
def toggle_active(user_id):
    """
    Activate or deactivate a user account.
    """

    user = db.get_or_404(
        User,
        user_id
    )

    # Admin cannot deactivate themselves.
    if user.id == current_user.id:

        flash(
            "You can't deactivate your own account.",
            "warning",
        )

        return redirect(
            url_for("admin.users")
        )

    user.is_active_user = (
        not user.is_active_user
    )

    db.session.commit()

    action = (
        "USER_ACTIVATED"
        if user.is_active_user
        else "USER_DEACTIVATED"
    )

    record_audit(
        user=current_user,
        action=action,
        details=(
            f"user_id={user.id} "
            f"email={user.email!r}"
        ),
    )

    status = (
        "active"
        if user.is_active_user
        else "inactive"
    )

    flash(
        f"{user.full_name} is now {status}.",
        "info",
    )

    return redirect(
        url_for("admin.users")
    )


# ============================================================
# HUMAN-IN-THE-LOOP REVIEW QUEUE
# ============================================================

@admin_bp.route("/reviews")
def reviews():
    """
    Display AI-generated answers that users have
    marked as requiring human review.
    """

    pending_reviews = (
        ChatHistory.query
        .filter_by(
            feedback_status="pending"
        )
        .order_by(
            ChatHistory.created_at.asc()
        )
        .all()
    )

    return render_template(
        "admin/reviews.html",
        reviews=pending_reviews,
    )


# ============================================================
# APPROVE AI ANSWER
# ============================================================

@admin_bp.route(
    "/reviews/<int:chat_id>/approve",
    methods=["POST"],
)
def approve_review(chat_id):
    """
    Approve an AI-generated answer after human review.
    """

    chat = db.session.get(
        ChatHistory,
        chat_id
    )

    if chat is None:
        abort(404)

    chat.feedback_status = "approved"

    chat.reviewed_by_id = (
        current_user.id
    )

    chat.reviewed_at = datetime.utcnow()

    chat.human_feedback = (
        "Answer approved by administrator."
    )

    db.session.commit()

    record_audit(
        user=current_user,
        action="AI_ANSWER_APPROVED",
        details=(
            f"chat_id={chat.id} "
            f"user_id={chat.user_id}"
        ),
    )

    flash(
        "Answer approved successfully.",
        "success",
    )

    return redirect(
        url_for("admin.reviews")
    )


# ============================================================
# REJECT AI ANSWER
# ============================================================

@admin_bp.route(
    "/reviews/<int:chat_id>/reject",
    methods=["POST"],
)
def reject_review(chat_id):
    """
    Reject an AI-generated answer after human review.
    """

    chat = db.session.get(
        ChatHistory,
        chat_id
    )

    if chat is None:
        abort(404)

    feedback = request.form.get(
        "human_feedback",
        ""
    ).strip()

    chat.feedback_status = "rejected"

    chat.reviewed_by_id = (
        current_user.id
    )

    chat.reviewed_at = datetime.utcnow()

    chat.human_feedback = (
        feedback
        or "Answer rejected by administrator."
    )

    db.session.commit()

    record_audit(
        user=current_user,
        action="AI_ANSWER_REJECTED",
        details=(
            f"chat_id={chat.id} "
            f"user_id={chat.user_id} "
            f"reason={chat.human_feedback!r}"
        ),
    )

    flash(
        "Answer rejected.",
        "warning",
    )

    return redirect(
        url_for("admin.reviews")
    )


# ============================================================
# EDIT AI ANSWER
# ============================================================

@admin_bp.route(
    "/reviews/<int:chat_id>/edit",
    methods=["POST"],
)
def edit_review(chat_id):
    """
    Edit the AI-generated answer and mark it as reviewed.
    """

    chat = db.session.get(
        ChatHistory,
        chat_id
    )

    if chat is None:
        abort(404)

    reviewed_answer = request.form.get(
        "reviewed_answer",
        ""
    ).strip()

    if not reviewed_answer:

        flash(
            "Edited answer cannot be empty.",
            "danger",
        )

        return redirect(
            url_for("admin.reviews")
        )

    chat.reviewed_answer = (
        reviewed_answer
    )

    chat.feedback_status = "edited"

    chat.reviewed_by_id = (
        current_user.id
    )

    chat.reviewed_at = datetime.utcnow()

    chat.human_feedback = (
        "AI answer edited and approved "
        "by administrator."
    )

    db.session.commit()

    record_audit(
        user=current_user,
        action="AI_ANSWER_EDITED",
        details=(
            f"chat_id={chat.id} "
            f"user_id={chat.user_id}"
        ),
    )

    flash(
        "Answer edited and approved successfully.",
        "success",
    )

    return redirect(
        url_for("admin.reviews")
    )


# ============================================================
# AUDIT LOGS
# ============================================================

@admin_bp.route("/logs")
def logs():
    """
    Display paginated audit logs.
    """

    page = request.args.get(
        "page",
        1,
        type=int
    )

    action_filter = request.args.get(
        "action",
        ""
    ).strip()

    q = AuditLog.query

    if action_filter:

        q = q.filter_by(
            action=action_filter
        )

    pagination = (
        q
        .order_by(
            AuditLog.created_at.desc()
        )
        .paginate(
            page=page,
            per_page=PAGE_SIZE,
            error_out=False,
        )
    )

    distinct_actions = [
        row[0]
        for row in (
            db.session
            .query(AuditLog.action)
            .distinct()
            .order_by(AuditLog.action)
        )
    ]

    return render_template(
        "admin/logs.html",
        pagination=pagination,
        action_filter=action_filter,
        distinct_actions=distinct_actions,
    )