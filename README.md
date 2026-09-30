# OpsVenda

SaaS multi-tenant para pequenos vendedores de marketplace (Shopee)
descobrirem **quanto realmente lucram em cada venda**, depois de comissões,
taxas e custo do produto.

**Produção:** https://opsvenda.montiqtech.com.br. Teste grátis de 90 dias e,
depois, R$ 4,99/mês via Pix.

## Documentação

| Documento | Para quem | Conteúdo |
|---|---|---|
| [Regras de negócio](docs/regras-de-negocio.md) | Produto e dev | Empresas e acesso, produtos e estoque, perfis de margem, **fórmula de lucro**, regra do snapshot, venda manual, importação CSV, cancelamento, dashboard, assinatura Pix, limitações |
| [Arquitetura e tecnologias](docs/arquitetura.md) | Dev | Camadas do código, ciclo da requisição, **isolamento multi-tenant**, modelo de dados, papel de cada tecnologia, variáveis de ambiente, segurança |
| [Escalabilidade](docs/escalabilidade.md) | Dev e decisão | Capacidade atual, gargalos por prioridade, roteiro de crescimento por fase, segurança, dívida técnica |
| [Deploy e operação](docs/deploy.md) | Quem opera | Infra da VPS, atualizar a produção, rollback, **nginx compartilhado (armadilha do inode)**, certificado, backup, Mercado Pago |
| [Testes](docs/testes.md) | Dev | Como rodar, fixtures, o que cada arquivo garante, como escrever testes novos, lacunas |
| [Guia de desenvolvimento](docs/desenvolvimento.md) | Dev | Ambiente local, passo a passo de uma funcionalidade nova, **convenções por tecnologia**, migrations, dependências, checklist de deploy |

## Início rápido (desenvolvimento)

Requer Python 3.12+ e PostgreSQL 16+. Detalhes em
[desenvolvimento](docs/desenvolvimento.md#ambiente-local).

```bash
# banco (uma vez)
sudo -u postgres psql -c "CREATE ROLE opsvenda LOGIN PASSWORD 'opsvenda' CREATEDB;"
sudo -u postgres createdb -O opsvenda opsvenda
sudo -u postgres createdb -O opsvenda opsvenda_test

# app
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                  # defina SECRET_KEY
export FLASK_APP=wsgi:app FLASK_DEBUG=1
flask db upgrade
flask run                             # http://127.0.0.1:5000 → "Criar conta"

pytest                                # testes
```

## Stack

Python 3.12 · Flask 3 · SQLAlchemy 2 + Alembic · PostgreSQL 16 (psycopg 3) ·
Flask-Login · Flask-WTF (CSRF) · Jinja2 com CSS/JS puros · Gunicorn · Docker
Compose · nginx + Let's Encrypt · Mercado Pago (Pix) · pytest.

O papel de cada uma está em
[arquitetura → tecnologias](docs/arquitetura.md#tecnologias-e-como-cada-uma-é-aplicada).

## Três regras que não podem ser quebradas

1. **Isolamento entre empresas:** toda leitura de dado de negócio passa por
   [scoping.py](scoping.py). [Por quê](docs/arquitetura.md#multi-tenant)
2. **Vendas passadas são imutáveis:** relatórios leem os snapshots do
   `SaleItem`, nunca o preço ou custo atual.
   [Por quê](docs/regras-de-negocio.md#snapshot-vendas-passadas-nunca-mudam)
3. **Dinheiro em centavos inteiros**, e a fórmula de lucro só em
   [services/pricing.py](services/pricing.py).
   [Detalhes](docs/regras-de-negocio.md#cálculo-de-uma-venda)

## Estrutura

```
app.py              application factory: config, extensões, blueprints, bloqueio por assinatura
wsgi.py             entrada WSGI (flask run / gunicorn)
config.py           configuração via ambiente (SECRET_KEY, DATABASE_URL)
extensions.py       db, migrate, login_manager, csrf
scoping.py          isolamento multi-tenant
cli.py              flask create-admin, flask billing-reconcile
routes/             HTTP: auth, dashboard, products, margin_profiles, sales, billing
services/           regras: pricing, stock, costs, billing, mercadopago, csv_import, csv_export
models/             tabelas SQLAlchemy
templates/, static/ Jinja2, CSS e JS
migrations/         Alembic (baseline 0001_initial)
tests/              pytest contra Postgres
docs/               esta documentação
deploy.sh           deploy para a VPS (roda da sua máquina)
Dockerfile, docker-compose.yml, docker-entrypoint.sh   produção
```

## Deploy

```bash
git push origin main
./deploy.sh              # testes, backup do banco, build, reload do nginx e checagem dos sites
```

Detalhes, rollback e operação em [deploy](docs/deploy.md#atualizar-a-produção).

## Licença

[MIT](LICENSE)
