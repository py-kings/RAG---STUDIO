"""
ChatHistory model - stores every AI Knowledge Assistant Q&A turn,
including internal document citations, external web sources,
and Human-in-the-Loop review/feedback.
"""

from app.utils.timeutils import utcnow
from app import db


class ChatHistory(db.Model):
    __tablename__ = "chat_history"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    # ---------------------------------------------------------
    # User who asked the question
    # ---------------------------------------------------------

    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=False
    )

    user = db.relationship(
        "User",
        back_populates="chat_history",
        foreign_keys=[user_id]
    )

    # ---------------------------------------------------------
    # Question & AI response
    # ---------------------------------------------------------

    question = db.Column(
        db.Text,
        nullable=False
    )

    response = db.Column(
        db.Text,
        nullable=True
    )

    # ---------------------------------------------------------
    # Internal document citation
    # ---------------------------------------------------------

    source_document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id"),
        nullable=True
    )

    source_document = db.relationship(
        "Document",
        back_populates="chat_citations"
    )

    source_page = db.Column(
        db.Integer,
        nullable=True
    )

    # ---------------------------------------------------------
    # External web citations
    #
    # Example:
    #
    # [
    #     {
    #         "title": "Data Analyst Skills",
    #         "url": "https://example.com",
    #         "score": 0.91
    #     }
    # ]
    # ---------------------------------------------------------

    web_sources = db.Column(
        db.JSON,
        nullable=True
    )

    # ---------------------------------------------------------
    # Human-in-the-Loop
    # ---------------------------------------------------------

    # Current review state.
    #
    # Possible values:
    #   pending
    #   approved
    #   rejected
    #   edited
    #
    # NULL means no human review has been requested yet.

    feedback_status = db.Column(
        db.String(20),
        nullable=True,
        default=None
    )

    # Feedback/comment provided by the user or reviewer.

    human_feedback = db.Column(
        db.Text,
        nullable=True
    )

    # Final answer after human editing.
    #
    # If NULL, the original AI response remains the answer.

    reviewed_answer = db.Column(
        db.Text,
        nullable=True
    )

    # ---------------------------------------------------------
    # Human reviewer
    # ---------------------------------------------------------

    reviewed_by_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id"),
        nullable=True
    )

    reviewed_by = db.relationship(
        "User",
        foreign_keys=[reviewed_by_id],
        backref="reviewed_chat_history"
    )

    # When the human review actually happened.

    reviewed_at = db.Column(
        db.DateTime,
        nullable=True
    )

    # ---------------------------------------------------------
    # Performance
    # ---------------------------------------------------------

    response_time_ms = db.Column(
        db.Integer,
        nullable=True
    )

    created_at = db.Column(
        db.DateTime,
        default=utcnow
    )

    # ---------------------------------------------------------
    # Representation
    # ---------------------------------------------------------

    def __repr__(self):
        return (
            f"<ChatHistory "
            f"user={self.user_id} "
            f"q={self.question[:30]!r}>"
        )