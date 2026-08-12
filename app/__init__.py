"""
Enterprise KnowledgeOS
Application factory for the Flask app.

Extension wiring, logging, error handlers, and blueprints are added
incrementally per project phase. As of Phase 11: models (Phase 2),
authentication/RBAC (Phase 3), the Enterprise Dashboard (Phase 4),
Document Management (Phase 5), Document Parsing (Phase 6), Embeddings
& ChromaDB (Phase 7), Gemini + LangChain (Phase 8), the complete RAG
pipeline / AI Knowledge Assistant (Phase 9), full paginated chat
history with citations (Phase 10), and the Admin Panel (Phase 11)
are all wired in.
"""
import os
import logging
from logging.handlers import RotatingFileHandler

import markdown
import bleach

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager
from flask_migrate import Migrate

from config import config_by_name

# --- Extensions (instantiated here, bound to app in create_app) ---
db = SQLAlchemy()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_name: str = None) -> Flask:
    """Application factory."""
    config_name = config_name or os.getenv("FLASK_ENV", "development")

    app = Flask(__name__, instance_relative_config=True)
    app.config.from_object(config_by_name[config_name])

    # config.py's class attributes are evaluated once, at first import of
    # that module - fine for a normal process, but stale in a long-lived
    # process that changes env vars between app instances (e.g. the test
    # suite, or a REPL). Re-apply anything env-driven here so every
    # create_app() call reflects the *current* environment.
    if os.getenv("DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL")
    elif config_name == "testing" and os.getenv("TEST_DATABASE_URL"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("TEST_DATABASE_URL")

    # --- Init extensions ---
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    login_manager.login_view = "auth.login"
    login_manager.login_message = "Please sign in to access this page."
    login_manager.login_message_category = "warning"

    # --- Models ---
    # Imported (not used directly) so Flask-Migrate's autogenerate can see
    # every table from this single entry point.
    from app import models  # noqa: F401
    from app.models.user import User

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # --- Logging ---
    _configure_logging(app)

    # --- Blueprints ---
    from app.routes.main_routes import main_bp
    from app.routes.auth_routes import auth_bp
    from app.routes.dashboard_routes import dashboard_bp
    from app.routes.document_routes import document_bp
    from app.routes.chat_routes import assistant_bp
    from app.routes.admin_routes import admin_bp

    app.register_blueprint(main_bp)
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(dashboard_bp, url_prefix="/dashboard")
    app.register_blueprint(document_bp, url_prefix="/documents")
    app.register_blueprint(assistant_bp, url_prefix="/assistant")
    app.register_blueprint(admin_bp, url_prefix="/admin")

    # --- Error handlers ---
    _register_error_handlers(app)

    # --- CLI commands ---
    from app.cli import seed_roles, ask_ai

    app.cli.add_command(seed_roles)
    app.cli.add_command(ask_ai)

    @app.template_filter("render_markdown")
    def render_markdown(text):
        if not text:
            return ""

        html = markdown.markdown(
            text,
            extensions=[
                "extra",
                "fenced_code",
                "tables",
                "nl2br",
                "sane_lists",
            ],
        )

        allowed_tags = [
            "p", "br",
            "strong", "em",
            "h1", "h2", "h3", "h4", "h5", "h6",
            "ul", "ol", "li",
            "blockquote",
            "pre", "code",
            "table", "thead", "tbody", "tr", "th", "td",
            "a",
        ]

        allowed_attrs = {
            "a": ["href", "title", "target", "rel"],
        }

        return bleach.clean(
            html,
            tags=allowed_tags,
            attributes=allowed_attrs,
            protocols=["http", "https", "mailto"],
        )

    return app


def _configure_logging(app: Flask) -> None:
    log_dir = os.path.join(app.root_path, "..", "logs")
    os.makedirs(log_dir, exist_ok=True)

    handler = RotatingFileHandler(
        os.path.join(log_dir, "app.log"),
        maxBytes=1_000_000,
        backupCount=5
    )

    handler.setFormatter(
        logging.Formatter(
            "[%(asctime)s] %(levelname)s in %(module)s: %(message)s"
        )
    )

    handler.setLevel(logging.INFO)
    app.logger.addHandler(handler)
    app.logger.setLevel(logging.INFO)


def _register_error_handlers(app: Flask) -> None:
    from flask import render_template

    @app.errorhandler(404)
    def not_found(e):
        return render_template("errors/404.html"), 404

    @app.errorhandler(403)
    def forbidden(e):
        return render_template("errors/403.html"), 403

    @app.errorhandler(500)
    def server_error(e):
        app.logger.exception("Server error")
        return render_template("errors/500.html"), 500