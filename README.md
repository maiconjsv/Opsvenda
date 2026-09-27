# OpsVenda

SaaS multi-tenant de gestão de vendas (Shopee) construído em Flask: cadastro
público de empresas, autenticação, produtos, perfis de margem, vendas,
importação/exportação de CSV e assinatura via Pix (Mercado Pago). Cada
empresa só enxerga os próprios dados — o isolamento fica em
[scoping.py](scoping.py).

## Pré-requisitos

- Python 3.12+
- Git
- Docker (apenas para rodar/deployar o modo produção)

## Desenvolvimento

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt

cp .env.example .env               # defina SECRET_KEY
export FLASK_APP=wsgi:app FLASK_DEBUG=1
flask db upgrade                   # cria/atualiza o schema
flask run
```

Acesse `http://127.0.0.1:5000` e crie uma conta pela aba "Criar conta".
Sem `DATABASE_URL`, o banco é um SQLite em `instance/app.db`.

## Testes

```bash
pytest
```

## Comandos úteis do Flask CLI

Definidos em [cli.py](cli.py):

```bash
flask db upgrade                              # aplica as migrations
flask create-admin --company-id <id>          # cria um usuário numa empresa, ou troca a senha de um existente
```

## Produção (Docker)

Roda em `/opt/opsvenda` na VPS compartilhada, atrás do nginx do projeto
necasecanecas (rede Docker `necasecanecas_default`), em
https://opsvenda.montiqtech.com.br.

```bash
cd /opt/opsvenda
git pull
docker compose up -d --build   # .env: SECRET_KEY, POSTGRES_PASSWORD, Mercado Pago
```

O compose sobe o app e um Postgres próprio (`opsvenda-db`); o entrypoint
aplica as migrations (`flask db upgrade`) e sobe o Gunicorn.

## Estrutura do projeto

```
app.py              # application factory: cria o Flask app e registra tudo
config.py           # configurações (banco, chaves, uploads)
cli.py              # comandos flask CLI (create-admin)
extensions.py       # instâncias das extensões (db, login_manager, csrf, migrate)
scoping.py          # isolamento multi-tenant (toda query/lookup por empresa passa por aqui)
routes/             # rotas HTTP, um arquivo por domínio (auth, sales, products, billing, ...)
models/             # tabelas do banco (SQLAlchemy)
services/           # regras de negócio (pricing, billing, Mercado Pago, import/export de CSV)
templates/          # HTML (Jinja2)
static/             # CSS/JS
migrations/         # migrations Alembic (schema do banco)
wsgi.py             # ponto de entrada WSGI (usado por `flask run` e pelo Gunicorn)
tests/              # testes pytest
```

## Licença

Distribuído sob a licença [MIT](LICENSE).
