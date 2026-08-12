"""
Dashboard blueprint - Enterprise Dashboard (Phase 4).
Login-required for any authenticated role; no RBAC restriction here
since all roles are allowed to see the overview (per-role scoping,
if ever needed, is an Admin Panel concern in Phase 11).
"""
from flask import Blueprint, render_template
from flask_login import login_required

from app.services import dashboard_service

dashboard_bp = Blueprint("dashboard", __name__)


@dashboard_bp.route("/")
@login_required
def index():
    stats = dashboard_service.get_summary_stats()
    recent_uploads = dashboard_service.get_recent_uploads()
    recent_chats = dashboard_service.get_recent_chats()
    trend = dashboard_service.get_query_trend()

    return render_template(
        "dashboard/index.html",
        stats=stats,
        recent_uploads=recent_uploads,
        recent_chats=recent_chats,
        trend=trend,
    )
