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
