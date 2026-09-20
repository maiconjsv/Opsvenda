import getpass
import sys

import click

from app.extensions import db
from app.models import User


def register(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    def create_admin(username, password):
        """Create (or update the password of) a login user."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            user = User(username=username)
            db.session.add(user)
            click.echo(f"Criando usuario '{username}'.")
        else:
            click.echo(f"Usuario '{username}' ja existe, atualizando senha.")
        user.set_password(password)
        db.session.commit()
        click.echo("Pronto.")

    @app.cli.command("ensure-admin")
    def ensure_admin():
        """Create an admin user from ADMIN_USERNAME/ADMIN_PASSWORD env vars if
        no users exist yet. Used by the Docker entrypoint for first boot.
        """
        import os

        if User.query.first() is not None:
            click.echo("Ja existe usuario cadastrado, nada a fazer.")
            return

        username = os.environ.get("ADMIN_USERNAME", "admin")
        password = os.environ.get("ADMIN_PASSWORD")
        if not password:
            if sys.stdin.isatty():
                password = getpass.getpass(f"Senha para o usuario '{username}': ")
            else:
                raise click.ClickException(
                    "ADMIN_PASSWORD nao definido. Configure essa variavel de ambiente "
                    "(veja .env.example) antes de iniciar o container."
                )

        user = User(username=username)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        click.echo(f"Usuario admin '{username}' criado.")
