"""
Assistant blueprint - the employee-facing AI Knowledge Assistant
(Phase 9: Complete RAG Pipeline), full chat history with citations
(Phase 10), and Human-in-the-Loop feedback/review (Phase 12).
"""

from app.utils.timeutils import utcnow

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
from app.forms.chat_forms import AskForm
from app.models import ChatHistory
from app.services import rag_service


assistant_bp = Blueprint("assistant", __name__)

PAGE_SIZE = 10


# ============================================================
# AI ASSISTANT
# ============================================================

@assistant_bp.route("/", methods=["GET", "POST"])
@login_required
def index():

    form = AskForm()

    if form.validate_on_submit():

        result = rag_service.ask_question(
            current_user,
            form.question.data.strip()
        )

        if "error" in result:
            flash(
                f"Couldn't get an answer: {result['error']}",
                "danger"
            )

        return redirect(url_for("assistant.index"))

    history = (
        ChatHistory.query
        .filter_by(user_id=current_user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(5)
        .all()
    )

    return render_template(
        "assistant/index.html",
        form=form,
        history=history
    )


# ============================================================
# CHAT HISTORY
# ============================================================

@assistant_bp.route("/history")
@login_required
def history():

    query = request.args.get("q", "").strip()
    page = request.args.get("page", 1, type=int)

    q = ChatHistory.query.filter_by(
        user_id=current_user.id
    )

    if query:
        q = q.filter(
            ChatHistory.question.ilike(
                f"%{query}%"
            )
        )

    pagination = (
        q.order_by(
            ChatHistory.created_at.desc()
        )
        .paginate(
            page=page,
            per_page=PAGE_SIZE,
            error_out=False
        )
    )

    return render_template(
        "assistant/history.html",
        pagination=pagination,
        query=query
    )

# ============================================================
# HUMAN-IN-THE-LOOP FEEDBACK
# ============================================================

@assistant_bp.route(
    "/feedback/<int:chat_id>",
    methods=["POST"]
)
@login_required
def feedback(chat_id):

    chat = db.session.get(
        ChatHistory,
        chat_id
    )

    if chat is None:
        abort(404)

    # Users can only provide feedback
    # on their own conversations.
    if chat.user_id != current_user.id:
        abort(403)

    feedback_value = request.form.get(
        "feedback"
    )

    # Only allow valid user feedback states.
    if feedback_value not in {
        "approved",
        "pending"
    }:
        flash(
            "Invalid feedback option.",
            "danger"
        )

        return redirect(
            request.referrer
            or url_for("assistant.index")
        )

    # --------------------------------------------------------
    # APPROVED
    # --------------------------------------------------------

    if feedback_value == "approved":

        chat.feedback_status = "approved"

        chat.human_feedback = (
            "User approved the AI-generated answer."
        )

        chat.reviewed_by_id = current_user.id

        chat.reviewed_at = utcnow()

        flash(
            "Thank you! Your feedback has been recorded.",
            "success"
        )

    # --------------------------------------------------------
    # NEEDS HUMAN REVIEW
    # --------------------------------------------------------

    elif feedback_value == "pending":

        chat.feedback_status = "pending"

        chat.human_feedback = (
            "User requested human review."
        )

        # IMPORTANT:
        # reviewed_by_id and reviewed_at remain NULL
        # because a human has not reviewed it yet.

        flash(
            "This answer has been sent for human review.",
            "warning"
        )

    db.session.commit()

    return redirect(
        request.referrer
        or url_for("assistant.index")
    )
