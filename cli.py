import click

from extensions import db
from models import Company, User
from scoping import is_multi_tenant


def register(app):
    @app.cli.command("create-admin")
    @click.option("--username", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--company-id", type=int, default=None, help="Obrigatório em modo multi-tenant.")
    def create_admin(username, password, company_id):
        """Create (or update the password of) a login user."""
        user = User.query.filter_by(username=username).first()
        if user is None:
            if company_id is None:
                if is_multi_tenant():
                    raise click.UsageError("--company-id é obrigatório em modo multi-tenant.")
                company = Company.query.first()
                if company is None:
                    raise click.UsageError(
                        "Nenhuma empresa cadastrada ainda - crie a conta pelo navegador primeiro."
                    )
                company_id = company.id
            elif db.session.get(Company, company_id) is None:
                raise click.UsageError(f"Empresa com id {company_id} não existe.")

            user = User(username=username, company_id=company_id)
            db.session.add(user)
            click.echo(f"Criando usuario '{username}' (empresa {company_id}).")
        else:
            click.echo(f"Usuario '{username}' ja existe, atualizando senha.")
        user.set_password(password)
        db.session.commit()
        click.echo("Pronto.")
