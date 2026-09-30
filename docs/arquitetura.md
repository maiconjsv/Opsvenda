# Arquitetura e tecnologias

[← Voltar ao README](../README.md)

- [Visão geral](#visão-geral)
- [Camadas do código](#camadas-do-código)
- [Ciclo de uma requisição](#ciclo-de-uma-requisição)
- [Multi-tenant](#multi-tenant)
- [Modelo de dados](#modelo-de-dados)
- [Tecnologias e como cada uma é aplicada](#tecnologias-e-como-cada-uma-é-aplicada)
- [Configuração (variáveis de ambiente)](#configuração-variáveis-de-ambiente)
- [Segurança](#segurança)

## Visão geral

O OpsVenda é um **monólito Flask renderizado no servidor**: não há SPA nem API
JSON pública, e o HTML sai pronto do Jinja2. Isso mantém o projeto pequeno,
rápido de mudar e barato de hospedar. O único JavaScript é para confirmações
de formulário, abas da tela de login e polling do Pix.

```mermaid
flowchart LR
    U[Navegador] -->|HTTPS| N[nginx ncas-web<br/>TLS + proxy]
    N -->|HTTP :5000| G[Gunicorn<br/>2 workers]
    G --> F[Flask app<br/>routes → services → models]
    F -->|psycopg 3| P[(Postgres 16<br/>opsvenda-db)]
    F -->|uploads CSV| V[(volume<br/>app_instance)]
    F -->|Orders API| MP[Mercado Pago]
    MP -->|webhook| N
```

## Camadas do código

```
app.py              application factory: config, extensões, blueprints, gate de assinatura
wsgi.py             ponto de entrada WSGI (flask run / gunicorn)
config.py           classe Config lida do ambiente
extensions.py       instâncias únicas: db, migrate, login_manager, csrf
scoping.py          isolamento multi-tenant (obrigatório em toda query de negócio)
cli.py              comandos `flask ...` de suporte
routes/             HTTP: um blueprint por domínio
services/           regras de negócio e integrações, sem dependência de request
models/             tabelas (SQLAlchemy)
templates/          Jinja2, uma pasta por blueprint
static/             CSS e JS sem build
migrations/         Alembic (schema versionado)
tests/              pytest contra Postgres
```

Responsabilidade de cada camada:

| Camada | Pode | Não deve |
|---|---|---|
| `routes/` | ler `request`, validar formulário, chamar services, `flash`, renderizar/redirecionar | conter fórmula de negócio, pular o `scoping` |
| `services/` | regras e cálculos, integrações externas, gravar no banco | depender de `request`/`current_user` (recebem `company_id` por parâmetro) |
| `models/` | colunas, relacionamentos, propriedades derivadas simples | chamar APIs, conhecer HTTP |

Serviços existentes:

| Módulo | Responsabilidade |
|---|---|
| [pricing.py](../services/pricing.py) | Fórmula de lucro e conversão de centavos (única fonte) |
| [stock.py](../services/stock.py) | Toda alteração de estoque, com `UPDATE` atômico + movimento |
| [costs.py](../services/costs.py) | Aplicar o custo informado às vendas com custo pendente |
| [csv_import.py](../services/csv_import.py) | Upload, preview e importação com deduplicação |
| [csv_export.py](../services/csv_export.py) | CSV de vendas gerado linha a linha (streaming) |
| [billing.py](../services/billing.py) | Teste grátis, bloqueio, cobrança, confirmação e conciliação |
| [mercadopago.py](../services/mercadopago.py) | Único ponto que fala com a API do Mercado Pago |

Blueprints e prefixos:

| Blueprint | Prefixo | Arquivo |
|---|---|---|
| `auth` | `/auth` | [routes/auth.py](../routes/auth.py) |
| `dashboard` | `/` | [routes/dashboard.py](../routes/dashboard.py) |
| `products` | `/produtos` | [routes/products.py](../routes/products.py) |
| `margin_profiles` | `/margens` | [routes/margin_profiles.py](../routes/margin_profiles.py) |
| `sales` | `/vendas` | [routes/sales.py](../routes/sales.py) |
| `billing` | `/assinatura` | [routes/billing.py](../routes/billing.py) |

Além deles, `/health` (em `app.py`) responde `{"status":"ok"}` e é usado pelo
healthcheck do Docker.

## Ciclo de uma requisição

1. O nginx termina o TLS e repassa para `opsvenda-app:5000` com
   `X-Forwarded-For/Proto/Host`.
2. O `ProxyFix` (em `app.py`) confia em **um** proxy e corrige o IP e o esquema
   (`https`) vistos pelo Flask.
3. O Flask-Login carrega o usuário da sessão (cookie assinado com
   `SECRET_KEY`).
4. `_enforce_billing_gate` (em `app.py`), para usuários logados, redireciona
   para `/assinatura` se a empresa estiver bloqueada, exceto nas rotas
   liberadas.
5. O CSRFProtect valida o token em todo POST (menos no webhook).
6. A rota usa o `scoping` para ler e gravar só dados da empresa do usuário.
7. O template é renderizado a partir de `base.html`.

## Multi-tenant

O modelo é **banco compartilhado, schema compartilhado, coluna
`company_id`**. É o mais simples e barato de operar: um banco, uma migration e
um backup para todas as empresas.

- `Company` é o tenant.
- `User`, `Product`, `MarginProfile`, `Sale` e `Payment` têm `company_id`
  (NOT NULL e indexado).
- `SaleItem` e `StockMovement` **não têm** `company_id`: pertencem à empresa
  através de `Sale` e `Product`. Toda consulta sobre eles precisa de JOIN com o
  pai filtrado, como faz `_items_query` no dashboard.
- Unicidade é por empresa: `(company_id, sku)` em produtos e
  `(company_id, name)` em perfis.

**A regra de ouro é que toda leitura de dado de negócio passa por
[scoping.py](../scoping.py):**

| Função | Uso |
|---|---|
| `scoped_query(Model)` | listagens; já filtra por `company_id` do usuário |
| `get_scoped_or_404(Model, id)` | rota com ID na URL; outra empresa → 404 |
| `scoped_get_or_none(Model, id)` | IDs vindos de formulário; outra empresa → tratado como inexistente |

Nunca use `Model.query.get(id)` ou `db.session.get(Model, id)` direto numa
rota. Em services, receba `company_id` e filtre explicitamente, como faz
`csv_import.run_import`. A suíte
[tests/test_multi_tenant_isolation.py](../tests/test_multi_tenant_isolation.py)
cobre acesso cruzado por ID, adivinhação de IDs em formulários e vazamento no
dashboard e no CSV. **Todo blueprint novo precisa de testes equivalentes.**

## Modelo de dados

```mermaid
erDiagram
    COMPANY ||--o{ USER : tem
    COMPANY ||--o{ PRODUCT : tem
    COMPANY ||--o{ MARGIN_PROFILE : tem
    COMPANY ||--o{ SALE : tem
    COMPANY ||--o{ PAYMENT : tem
    PRODUCT ||--o{ STOCK_MOVEMENT : registra
    SALE ||--|{ SALE_ITEM : contém
    PRODUCT ||--o{ SALE_ITEM : referencia
    MARGIN_PROFILE |o--o{ SALE : aplicado_em
```

Convenções:

- **Dinheiro em centavos** (`Integer`), percentuais como fração (`Float`).
- **Datas em UTC "naive"**: o Postgres guarda `timestamp without time zone`.
  Para comparar, use `billing._now()` (UTC sem tzinfo), porque misturar datas
  com e sem fuso gera `TypeError`.
- Nada é apagado de verdade: produtos e perfis usam `active`, vendas usam
  `status`.
- O schema está versionado a partir de
  [migrations/versions/0001_initial.py](../migrations/versions/0001_initial.py).

## Tecnologias e como cada uma é aplicada

| Tecnologia | Versão | Papel no OpsVenda |
|---|---|---|
| Python | 3.12 | Linguagem (imagem `python:3.12-slim`) |
| Flask | 3.0 | App factory `create_app()`, blueprints por domínio, `before_request` para o bloqueio por assinatura, `stream_with_context` na exportação CSV, comandos CLI (`create-admin`, `billing-reconcile`) |
| Jinja2 | (Flask) | Templates server-side; `base.html` com sidebar para logado e `content_guest` para a landing/login |
| Flask-SQLAlchemy / SQLAlchemy | 3.1 / 2.x | ORM; `db.Model` em `models/`, sessão por request |
| psycopg | 3.2 | Driver do Postgres (URL `postgresql+psycopg://`) |
| PostgreSQL | 16 | Único banco suportado (dev, testes e produção) |
| Flask-Migrate / Alembic | 4.0 | `flask db upgrade` aplica migrations; o entrypoint do container roda uma vez antes do Gunicorn; `render_as_batch` desligado (só Postgres) |
| Flask-Login | 0.6 | Sessão do usuário, `@login_required`, `current_user.company_id` alimenta o scoping |
| Flask-WTF (CSRFProtect) | 1.2 | CSRF global; formulários incluem `_csrf_field.html`; webhook isento com `@csrf.exempt` |
| Werkzeug | (Flask) | Hash de senha e da resposta de segurança; `ProxyFix` atrás do nginx; `secure_filename` no upload |
| requests | 2.32 | Chamadas HTTP ao Mercado Pago, com timeout de 10 s |
| Mercado Pago Orders API | v1 | Cobrança Pix, consulta de status, webhook |
| Gunicorn | 22 | Servidor WSGI em produção, 2 workers síncronos e timeout de 60 s |
| Docker / Compose | — | `opsvenda-app` + `opsvenda-db`, limites de memória, healthchecks |
| nginx | 1.27 | Proxy reverso e TLS compartilhado com outros sites da VPS |
| Certbot (Let's Encrypt) | — | Certificado por webroot, renovado pelo container `ncas-certbot` |
| pytest | 8.3 | Testes, cada um com tabelas recriadas no Postgres |
| CSS/JS puros | — | Sem bundler: `static/css/style.css` (app), `landing.css` (login/landing), `static/js/app.js` |
| python-dotenv | 1.0 | `flask run` lê o `.env` automaticamente em dev |

**Atenção:** o `SQLAlchemy` não está fixado no `requirements.txt` (vem como
dependência do Flask-SQLAlchemy). A versão 2.1 mudou o driver padrão do
Postgres para o psycopg 3, e por isso a URL usa `postgresql+psycopg://` de
forma explícita. Considere fixar a versão (ver
[desenvolvimento](desenvolvimento.md#dependências)).

## Configuração (variáveis de ambiente)

| Variável | Obrigatória | Uso |
|---|---|---|
| `SECRET_KEY` | sim | Assina sessão e CSRF. Trocar desloga todo mundo. O app não sobe sem ela. |
| `DATABASE_URL` | sim | `postgresql+psycopg://usuario:senha@host:5432/banco`. O app não sobe sem ela. Em produção, o compose monta a URL a partir de `POSTGRES_PASSWORD`. |
| `POSTGRES_PASSWORD` | produção | Senha do container `opsvenda-db` |
| `MERCADO_PAGO_ACCESS_TOKEN` | não | Sem ela, gerar cobrança mostra erro e o resto funciona |
| `MP_SANDBOX` | não | `true`/`false` |
| `TEST_DATABASE_URL` | não | Banco dos testes (padrão: `opsvenda_test` local) |

Arquivos em disco ficam em `instance/` (volume `app_instance` em produção):
hoje só `instance/uploads/` (CSVs em importação).

## Segurança

- Senhas e respostas de segurança com hash (Werkzeug, PBKDF2/scrypt).
- CSRF em todos os formulários.
- Isolamento por empresa via `scoping` com testes dedicados.
- `?next=` do login restrito a caminhos internos.
- Upload: nome do arquivo gerado por UUID, `secure_filename` no token e
  limite de 16 MB (`MAX_CONTENT_LENGTH`).
- Webhook não confia no conteúdo recebido e reconsulta o Mercado Pago.
- Segredos só no `.env` do servidor (permissão 600), nunca no git.

Faltam, para um SaaS maduro: limite de tentativas no login e na recuperação,
cookie de sessão com `Secure` explícito, validação de assinatura do webhook e
recuperação de senha por e-mail. Veja a lista completa em
[escalabilidade](escalabilidade.md#segurança).
