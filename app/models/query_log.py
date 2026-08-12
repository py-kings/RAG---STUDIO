"""
QueryLog model - lightweight, append-only log of every AI query for
analytics (feeds Tableau dashboards in Phase 12: daily queries,
monthly trends, department-wise usage, avg response time, etc.).
Kept separate from ChatHistory so analytics queries don't compete
with the chat UI's read/write path.
"""
from app.utils.timeutils import utcnow
from app import db


class QueryLog(db.Model):
    __tablename__ = "query_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    user = db.relationship("User", back_populates="query_logs")

    department = db.Column(db.String(100), nullable=True)
    query_text = db.Column(db.Text, nullable=False)

    success = db.Column(db.Boolean, default=True, nullable=False)
    response_time_ms = db.Column(db.Integer, nullable=True)

    created_at = db.Column(db.DateTime, default=utcnow, index=True)

    def __repr__(self):
        return f"<QueryLog user={self.user_id} at={self.created_at}>"
