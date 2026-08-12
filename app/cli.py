"""
CLI commands. Registered on the app in app/__init__.py.

Usage:
    flask seed-roles
    flask ask-ai "What is the leave policy?"
"""
import click
from flask.cli import with_appcontext

from app import db
from app.models import Role


@click.command("seed-roles")
@with_appcontext
def seed_roles():
    """Create the fixed Admin/HR/Manager/Developer/Employee roles if missing."""
    created = []
    for name in Role.ALL_ROLES:
        if not Role.query.filter_by(name=name).first():
            db.session.add(Role(name=name))
            created.append(name)
    db.session.commit()
    if created:
        click.echo(f"Created roles: {', '.join(created)}")
    else:
        click.echo("Roles already exist, nothing to do.")


@click.command("ask-ai")
@click.argument("question")
@click.option("--context", default="", help="Optional context text to ground the answer in.")
@with_appcontext
def ask_ai(question, context):
    """
    Manually verify the Gemini + LangChain integration (Phase 8) without
    going through the web UI. Example:

        flask ask-ai "What is the leave policy?" --context "Employees get 20 days of annual leave."
    """
    from app.services.llm_service import generate_answer, LLMError

    try:
        answer = generate_answer(question, context)
        click.echo(answer)
    except LLMError as exc:
        click.echo(f"LLM error: {exc}", err=True)
