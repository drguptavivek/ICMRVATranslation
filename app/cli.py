import click
from flask import current_app
from sqlalchemy import func

from app.extensions import db
from app.models import User


def register_cli(app):
    app.cli.add_command(create_admin)


@click.command("create-admin")
def create_admin():
    username = click.prompt("Username").strip()
    email = click.prompt("Email").strip()
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)

    if "@" not in email:
        raise click.ClickException("Enter a valid email address.")

    username_exists = User.query.filter(func.lower(User.username) == username.lower()).first()
    if username_exists:
        raise click.ClickException("Username is already in use.")

    email_exists = User.query.filter(func.lower(User.email) == email.lower()).first()
    if email_exists:
        raise click.ClickException("Email is already in use.")

    user = User(
        username=username,
        email=email,
        role=User.ROLE_ADMIN,
        is_active=True,
    )
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    current_app.logger.info("Admin user created: %s", username)
    click.echo("Admin user created.")
