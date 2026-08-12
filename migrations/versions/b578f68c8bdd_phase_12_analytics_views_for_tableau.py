"""Phase 12: analytics views for Tableau

Tableau connects directly to MySQL (per project spec) rather than
through Flask. These five views cover all eight dashboards the spec
lists (Daily AI Queries, Monthly Trends, Active Users, Department-wise
Usage, Most Accessed Documents, User Activity, Average Response Time,
Query Trends) without duplicating logic across near-identical views:

  vw_query_trends_daily    -> Daily AI Queries, Query Trends, Average Response Time (daily)
  vw_query_trends_monthly  -> Monthly Trends, Average Response Time (monthly)
  vw_department_usage      -> Department-wise Usage
  vw_most_accessed_documents -> Most Accessed Documents
  vw_user_activity          -> Active Users, User Activity

Flask itself only ever shows summary counters (Phase 4 dashboard,
Phase 11 admin panel) — these views exist for Tableau to query
directly, not for the Flask app to read.

Revision ID: b578f68c8bdd
Revises: 3ae1e8661139
Create Date: 2026-07-29
"""
from alembic import op

revision = "b578f68c8bdd"
down_revision = "3ae1e8661139"
branch_labels = None
depends_on = None


VIEWS = {
    "vw_query_trends_daily": """
        CREATE VIEW vw_query_trends_daily AS
        SELECT
            DATE(created_at) AS query_date,
            COUNT(*) AS query_count,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successful_count,
            ROUND(AVG(response_time_ms)) AS avg_response_time_ms
        FROM query_logs
        GROUP BY DATE(created_at)
    """,
    "vw_query_trends_monthly": """
        CREATE VIEW vw_query_trends_monthly AS
        SELECT
            DATE_FORMAT(created_at, '%Y-%m') AS query_month,
            COUNT(*) AS query_count,
            SUM(CASE WHEN success THEN 1 ELSE 0 END) AS successful_count,
            ROUND(AVG(response_time_ms)) AS avg_response_time_ms
        FROM query_logs
        GROUP BY DATE_FORMAT(created_at, '%Y-%m')
    """,
    "vw_department_usage": """
        CREATE VIEW vw_department_usage AS
        SELECT
            COALESCE(department, 'Unspecified') AS department,
            COUNT(*) AS query_count,
            COUNT(DISTINCT user_id) AS user_count
        FROM query_logs
        GROUP BY COALESCE(department, 'Unspecified')
    """,
    "vw_most_accessed_documents": """
        CREATE VIEW vw_most_accessed_documents AS
        SELECT
            d.id AS document_id,
            d.title,
            d.file_type,
            d.status,
            COUNT(ch.id) AS times_cited
        FROM documents d
        LEFT JOIN chat_history ch ON ch.source_document_id = d.id
        WHERE d.is_deleted = FALSE
        GROUP BY d.id, d.title, d.file_type, d.status
    """,
    "vw_user_activity": """
        CREATE VIEW vw_user_activity AS
        SELECT
            u.id AS user_id,
            u.full_name,
            u.department,
            r.name AS role_name,
            u.is_active_user,
            u.last_login_at,
            COUNT(DISTINCT ql.id) AS query_count,
            COUNT(DISTINCT ch.id) AS chat_count,
            MAX(ql.created_at) AS last_query_at
        FROM users u
        JOIN roles r ON r.id = u.role_id
        LEFT JOIN query_logs ql ON ql.user_id = u.id
        LEFT JOIN chat_history ch ON ch.user_id = u.id
        GROUP BY u.id, u.full_name, u.department, r.name, u.is_active_user, u.last_login_at
    """,
}


def upgrade():
    for name, sql in VIEWS.items():
        op.execute(sql)


def downgrade():
    for name in VIEWS:
        op.execute(f"DROP VIEW IF EXISTS {name}")
