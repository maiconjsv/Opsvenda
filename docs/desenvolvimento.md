# Guia de desenvolvimento

Como preparar o ambiente e continuar o projeto mantendo os padrões atuais.

[← Voltar ao README](../README.md)

- [Ambiente local](#ambiente-local)
- [Banco local](#banco-local)
- [Fluxo de trabalho](#fluxo-de-trabalho)
- [Adicionando uma funcionalidade (passo a passo)](#adicionando-uma-funcionalidade-passo-a-passo)
- [Convenções por tecnologia](#convenções-por-tecnologia)
- [Migrations](#migrations)
- [Dependências](#dependências)
- [Checklist antes do deploy](#checklist-antes-do-deploy)

## Ambiente local

Pré-requisitos: Python 3.12+, Git e PostgreSQL 16+. Docker **não** é
necessário para desenvolver.

```bash
git clone https://github.com/maiconjsv/Opsvenda.git && cd Opsvenda
python3 -m venv .venv
source .venv/bin/activate              # Windows: .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
cp .env.example .env                   # defina SECRET_KEY
```

`SECRET_KEY` para dev:
`python -c "import secrets; print(secrets.token_hex(32))"`.

```bash
export FLASK_APP=wsgi:app FLASK_DEBUG=1
flask db upgrade
flask run                              # http://127.0.0.1:5000
```

O `flask run` lê o `.env` automaticamente (python-dotenv). Com
`FLASK_DEBUG=1`, o servidor recarrega a cada mudança no código.

## Banco local

Uma vez só (Ubuntu/Debian):

```bash
sudo apt install postgresql
sudo -u postgres psql -c "CREATE ROLE opsvenda LOGIN PASSWORD 'opsvenda' CREATEDB;"
sudo -u postgres createdb -O opsvenda opsvenda        # desenvolvimento
sudo -u postgres createdb -O opsvenda opsvenda_test   # testes
```

A `DATABASE_URL` do `.env.example` já aponta para
`postgresql+psycopg://opsvenda:opsvenda@localhost:5432/opsvenda`.

Recomeçar o banco de dev do zero:

```bash
sudo -u postgres dropdb opsvenda && sudo -u postgres createdb -O opsvenda opsvenda
flask db upgrade
```

## Fluxo de trabalho

1. Crie um branch: `git checkout -b feature/nome-curto`.
2. Implemente seguindo o [passo a passo](#adicionando-uma-funcionalidade-passo-a-passo).
3. Rode `pytest` e `flask db check`.
4. Faça commits pequenos, com mensagem no imperativo e dizendo o porquê.
5. Faça merge em `main`, `git push` e [deploy](deploy.md#atualizar-a-produção).

## Adicionando uma funcionalidade (passo a passo)

Exemplo: cadastrar **despesas fixas** da empresa (aluguel, internet...) para
descontar no dashboard.

### 1. Model: `models/expense.py`

```python
from datetime import datetime, timezone

from extensions import db


class Expense(db.Model):
    __tablename__ = "expenses"

    id = db.Column(db.Integer, primary_key=True)
    company_id = db.Column(db.Integer, db.ForeignKey("companies.id"), nullable=False, index=True)
    description = db.Column(db.String(200), nullable=False)
    amount_cents = db.Column(db.Integer, nullable=False)
    active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
```

- `company_id` NOT NULL e indexado, porque todo dado de negócio pertence a
  uma empresa.
- Dinheiro em `*_cents` inteiro.
- `active` em vez de apagar.
- Registre o model em [models/\_\_init\_\_.py](../models/__init__.py), para o
  Alembic enxergá-lo.

### 2. Migration

```bash
flask db migrate -m "add expenses"
# revise o arquivo gerado em migrations/versions/
flask db upgrade
flask db check                         # deve dizer "No new upgrade operations detected."
```

### 3. Regra de negócio: `services/expenses.py`

Cálculos e regras ficam aqui, sem `request` nem `current_user`: recebem
`company_id` por parâmetro. Assim podem ser testados diretamente e,
futuramente, rodar em background.

### 4. Rotas: `routes/expenses.py`

```python
from flask import Blueprint, render_template
from flask_login import login_required

from models import Expense
from scoping import get_scoped_or_404, scoped_query

bp = Blueprint("expenses", __name__, url_prefix="/despesas")


@bp.route("/")
@login_required
def index():
    expenses = scoped_query(Expense).order_by(Expense.description).all()
    return render_template("expenses/index.html", expenses=expenses)


@bp.route("/<int:expense_id>/editar", methods=["GET", "POST"])
@login_required
def edit(expense_id):
    expense = get_scoped_or_404(Expense, expense_id)
    ...
```

- **Sempre** use `scoped_query` / `get_scoped_or_404` / `scoped_get_or_none`.
- Ao criar um registro, use `company_id=current_user.company_id`.
- URLs em português (`/despesas`, `/novo`, `/editar`), código em inglês.
- Registre o blueprint em `create_app()` ([app.py](../app.py)).

### 5. Templates: `templates/expenses/index.html`

```html
{% extends "base.html" %}
{% block title %}Despesas{% endblock %}
{% block content %}
  <form method="post">
    {% include "_csrf_field.html" %}
    ...
  </form>
{% endblock %}
```

- Todo `<form method="post">` inclui `_csrf_field.html`.
- Ações destrutivas usam `data-confirm="Tem certeza?"` no form; o
  `static/js/app.js` pede confirmação.
- Adicione o link no menu lateral de [templates/base.html](../templates/base.html).

### 6. Testes

Um arquivo `tests/test_expenses.py` com a regra de negócio e **testes de
isolamento** em `test_multi_tenant_isolation.py` (ver [testes](testes.md#escrevendo-testes-novos)).

### 7. Documentação

Atualize [regras-de-negocio.md](regras-de-negocio.md) com a regra nova.

## Convenções por tecnologia

### Flask

- Uma responsabilidade por blueprint; rotas finas, com a lógica em
  `services/`.
- Mensagens ao usuário via `flash(msg, categoria)` com as categorias
  `success`, `danger`, `warning` e `info`, em português.
- Depois de um POST bem-sucedido, **redirecione** (padrão
  Post/Redirect/Get). Com erro de validação, renderize de novo com
  `form=request.form` para não perder o que foi digitado.
- Rotas que não devem ser bloqueadas por assinatura vencida entram em
  `_BLOCKED_ALLOWED_ENDPOINTS` em [app.py](../app.py).

### SQLAlchemy

- Leitura de negócio só pelo [scoping.py](../scoping.py).
- Para somas e contagens, agregue no banco (`query.with_entities(func.sum(...))`)
  em vez de `.all()` e somar em Python; veja `routes/dashboard.py`. Para
  listas longas, use `LIMIT` na tela e `yield_per()` em exportações.
- **Estoque só muda por `services.stock.adjust_stock()`**, que faz o
  `UPDATE` atômico e registra o movimento. Nunca faça
  `product.stock_qty -= q`.
- Transições de estado que não podem acontecer duas vezes (ex.: cancelar)
  usam `UPDATE ... WHERE <estado atual>` e conferem o `rowcount`, como
  `sales.cancel`.
- Cuidado para não dar a uma rota o mesmo nome de uma função importada:
  o blueprint sobrescreve o nome no módulo. Prefira importar o módulo
  (`from services import stock` → `stock.adjust_stock(...)`).
- Um `db.session.commit()` por operação de negócio; em lote, use `flush()`
  para obter IDs e commit no fim.
- Datas: grave UTC e compare com `billing._now()` (UTC naive).

### Postgres

- Único banco suportado: não escreva código com fallback para SQLite.
- Índice em toda coluna usada em filtro frequente; pense em índices
  compostos começando por `company_id`.
- Unicidade por empresa com `UniqueConstraint("company_id", ...)`.

### Alembic / Flask-Migrate

Ver [Migrations](#migrations). O `render_as_batch` (modo de compatibilidade
com SQLite, padrão no Flask-Migrate 4) está desligado em `app.py`, então as
migrations geradas usam `op.add_column` etc. direto.

### Flask-Login e autenticação

- `@login_required` em toda rota que não seja pública.
- `current_user.company_id` é a fonte do tenant; nunca aceite `company_id`
  vindo do formulário ou da URL.

### Flask-WTF (CSRF)

- CSRF é global. Só webhooks de terceiros usam `@csrf.exempt`, e nesse caso
  **não confie no conteúdo recebido**: reconsulte a origem, como o webhook do
  Mercado Pago faz.

### Jinja2, CSS e JS

- Templates por blueprint em `templates/<blueprint>/`; parciais com
  prefixo `_`.
- Área logada: `{% block content %}`. Páginas públicas:
  `{% block content_guest %}`.
- CSS e JS puros, sem build. Estilos do app em `static/css/style.css` e da
  landing/login em `static/css/landing.css`.
- JS mínimo e progressivo: a página deve funcionar sem ele, exceto o polling
  do Pix.

### Dinheiro e cálculos

- Sempre inteiro em centavos; `to_cents()` na entrada e `from_cents()` na
  exibição.
- Qualquer valor de uma venda passada vem do snapshot do `SaleItem`
  ([regra do snapshot](regras-de-negocio.md#snapshot-vendas-passadas-nunca-mudam)).
- Fórmula de lucro só em `services/pricing.py`.

### Integrações externas (Mercado Pago)

- Isoladas em um módulo por provedor (`services/mercadopago.py`).
- Timeout em toda chamada; nunca propagam exceção (devolvem
  `{"erro": ...}` ou `None`) e registram o erro com `logging`.
- Chave de idempotência nas criações.

### Docker e Gunicorn

- Mudou dependência: rebuild (`docker compose up -d --build`).
- Workers e timeout ficam em [docker-entrypoint.sh](../docker-entrypoint.sh).
  Aumentar workers exige olhar a memória (`mem_limit` no compose) e a VPS
  compartilhada.
- Arquivos novos na raiz precisam de `COPY` no [Dockerfile](../Dockerfile).
  Pastas novas também: ele copia pasta por pasta.

## Migrations

- Gere com `flask db migrate -m "descrição"` e **sempre revise** o arquivo.
  O autogenerate não detecta renomeações (vira drop + add, perdendo dados)
  nem mudanças de tipo em alguns casos.
- **Nunca edite uma migration já aplicada em produção**; crie outra.
- Coluna nova `NOT NULL` em tabela com dados: crie como nullable,
  preencha com `op.execute(...)` e só depois altere para NOT NULL, ou use
  `server_default`.
- Teste `upgrade` e `downgrade` localmente antes do deploy:

```bash
flask db upgrade && flask db downgrade && flask db upgrade && flask db check
```

- O histórico começa em `0001_initial`, a baseline só-Postgres que substituiu
  a cadeia antiga da era SQLite/desktop.
- `flask db downgrade` sem argumento volta uma revisão.

## Dependências

- Produção em [requirements.txt](../requirements.txt), dev em
  [requirements-dev.txt](../requirements-dev.txt), com versões fixadas
  (`==`).
- O **SQLAlchemy não está fixado** (vem pelo Flask-SQLAlchemy). Recomendado
  fixar, ex. `SQLAlchemy==2.0.x`, depois de testar, para builds
  reproduzíveis.
- Ao atualizar uma dependência: suba a versão, rode `pytest` e
  `flask db check`, e faça o rebuild do container.

## Checklist antes do deploy

- [ ] `pytest` passando
- [ ] `flask db check` sem diferenças entre models e migrations
- [ ] Migration nova revisada e testada com upgrade/downgrade
- [ ] Rota nova usa o `scoping` e tem teste de isolamento
- [ ] Nenhum segredo no código ou no git
- [ ] Documentação de regra de negócio atualizada
- [ ] `git push` e depois o [deploy](deploy.md#atualizar-a-produção)
