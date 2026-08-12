"""
Main blueprint - Phase 1 placeholder routes plus a Phase 3
login-protected profile route to prove session handling works.
"""
from flask import Blueprint, render_template, jsonify
from flask_login import login_required, current_user

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    return render_template("index.html")


@main_bp.route("/health")
def health():
    return jsonify(status="ok", service="Enterprise KnowledgeOS"), 200


@main_bp.route("/profile")
@login_required
def profile():
    return render_template("profile.html", user=current_user)
