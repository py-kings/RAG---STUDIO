"""
Dashboard service - read-only aggregation queries backing the
Enterprise Dashboard (Phase 4). Kept separate from the route so the
same stats can later be reused by the Admin Panel (Phase 11) and
Tableau summary widgets (Phase 12).
"""
from datetime import timedelta

from sqlalchemy import func

from app import db
from app.models import User, Document, ChatHistory, QueryLog
from app.utils.timeutils import utcnow


def get_summary_stats() -> dict:
    """Top-line counters for the dashboard cards."""
    return {
        "total_users": User.query.count(),
        "active_users": User.query.filter_by(is_active_user=True).count(),
        "total_documents": Document.query.filter_by(is_deleted=False).count(),
        "total_ai_queries": QueryLog.query.count(),
    }


def get_recent_uploads(limit: int = 5):
    return (
        Document.query.filter_by(is_deleted=False)
        .order_by(Document.created_at.desc())
        .limit(limit)
        .all()
    )


def get_recent_chats(limit: int = 5):
    return (
        ChatHistory.query.order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )


def get_query_trend(days: int = 7) -> dict:
    """
    Daily AI query counts for the last `days` days, including days
    with zero queries, for a Chart.js line chart.
    Returns {"labels": [...], "counts": [...]}.
    """
    start = (utcnow() - timedelta(days=days - 1)).date()

    rows = (
        db.session.query(
            func.date(QueryLog.created_at).label("day"),
            func.count(QueryLog.id).label("count"),
        )
        .filter(func.date(QueryLog.created_at) >= start)
        .group_by("day")
        .all()
    )
    counts_by_day = {str(r.day): r.count for r in rows}

    labels, counts = [], []
    for i in range(days):
        day = start + timedelta(days=i)
        labels.append(day.strftime("%b %d"))
        counts.append(counts_by_day.get(str(day), 0))

    return {"labels": labels, "counts": counts}
