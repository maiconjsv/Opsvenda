# Testes

[← Voltar ao README](../README.md)

- [Como rodar](#como-rodar)
- [Como a suíte funciona](#como-a-suíte-funciona)
- [O que cada arquivo garante](#o-que-cada-arquivo-garante)
- [Escrevendo testes novos](#escrevendo-testes-novos)
- [Lacunas de cobertura](#lacunas-de-cobertura)

## Como rodar

Os testes usam **Postgres de verdade**, o mesmo banco da produção, para que
diferenças entre bancos não passem despercebidas. Crie o banco de teste uma
vez (ver [desenvolvimento](desenvolvimento.md#banco-local)):

```bash
sudo -u postgres createdb -O opsvenda opsvenda_test
```

Depois:

```bash
source .venv/bin/activate
pytest                          # suíte inteira (55 testes, ~25 s)
pytest tests/test_billing.py    # um arquivo
pytest -k snapshot              # por nome
pytest -x -q                    # para no primeiro erro
```

Para usar outro banco: `TEST_DATABASE_URL=postgresql+psycopg://... pytest`.

**Nunca aponte `TEST_DATABASE_URL` para um banco com dados reais:** cada teste
apaga todas as tabelas no final.

## Como a suíte funciona

Fixtures em [tests/conftest.py](../tests/conftest.py):

| Fixture | O que entrega |
|---|---|
| `app` | App com `TestConfig`: `TESTING=True`, CSRF desligado, `SECRET_KEY` fixa, banco de teste e `instance/` num diretório temporário. Roda `create_all()` no início e `drop_all()` no fim de **cada teste**. |
| `db` | A instância do SQLAlchemy |
| `client` | `app.test_client()` para requisições HTTP |
| `company` | Uma empresa com teste grátis válido |

Com `TESTING=True`, o app cria as tabelas pelos models (`db.create_all()`) em
vez de rodar migrations. Por isso a coerência entre models e migrations é
verificada à parte, com `flask db check` (ver
[desenvolvimento](desenvolvimento.md#migrations)).

Padrão para testar logado sem passar pelo formulário (usado nos testes de
isolamento e de cobrança):

```python
with client.session_transaction() as sess:
    sess["_user_id"] = str(user.id)
    sess["_fresh"] = True
```

Chamadas ao Mercado Pago são sempre simuladas com `monkeypatch`. Nenhum teste
acessa a rede.

## O que cada arquivo garante

| Arquivo | Garante |
|---|---|
| [test_pricing.py](../tests/test_pricing.py) | Conversão reais↔centavos; fórmula de lucro; quantidade ≤ 0 rejeitada |
| [test_sale_snapshot_immutability.py](../tests/test_sale_snapshot_immutability.py) | Editar produto ou perfil **não** altera vendas passadas |
| [test_multi_tenant_isolation.py](../tests/test_multi_tenant_isolation.py) | SKU e nome de perfil podem repetir entre empresas; acesso cruzado por ID devolve 404 e não altera nada; IDs de outra empresa em formulários são rejeitados; dashboard e CSV não vazam valores de outra empresa |
| [test_billing.py](../tests/test_billing.py) | Teste grátis no cadastro; bloqueio só após a carência; renovação soma a partir do vencimento ou de agora; confirmação idempotente; webhook confirma (ID no corpo ou na query string), ignora pedido desconhecido e é idempotente; conciliação confirma cobranças recentes sem webhook e ignora as antigas; comando `flask billing-reconcile`; bloqueado vai para `/assinatura` mas ainda acessa cobrança e logout |
| [test_csv_import.py](../tests/test_csv_import.py) | Preview do upload; importação casa SKU existente e cria o que falta; SKU desconhecido é pulado quando não deve criar; reimportar o mesmo arquivo não duplica vendas nem estoque; linhas repetidas no mesmo arquivo entram uma vez; sem nº do pedido a deduplicação fica desligada; produtos criados ficam com custo pendente |
| [test_pending_cost.py](../tests/test_pending_cost.py) | Informar o custo recalcula **só** os itens pendentes; campo em branco mantém a pendência; dashboard avisa sobre custo pendente |
| [test_stock.py](../tests/test_stock.py) | Baixa atômica parte do valor real do banco, não do objeto desatualizado; venda manual baixa estoque e registra movimento; cancelar duas vezes estorna uma vez; ajuste manual de estoque |
| [test_dashboard_insights.py](../tests/test_dashboard_insights.py) | Comparação com o período anterior; período anterior com lucro zero; totais somam todas as linhas enquanto a tabela mostra 100; exportação CSV traz todas as linhas |
| [test_setup.py](../tests/test_setup.py) | Tela com login e cadastro; cadastro cria empresa e usuário e loga; validações de senha, pergunta e usuário duplicado; várias empresas podem se cadastrar |
| [test_password_recovery.py](../tests/test_password_recovery.py) | Fluxo da pergunta de segurança: usuário inexistente, resposta certa e resposta errada |

A fixture [tests/fixtures/shopee_orders_sample.csv](../tests/fixtures/shopee_orders_sample.csv)
é um export de exemplo da Shopee para os testes de importação.

## Escrevendo testes novos

Regras do projeto:

1. **Toda regra de negócio nova ganha teste** no arquivo do domínio, ou num
   arquivo novo `test_<domínio>.py`.
2. **Toda rota nova que recebe ID ganha teste de isolamento** em
   `test_multi_tenant_isolation.py`: crie duas empresas, tente acessar e
   alterar o recurso da outra, e confira o 404 **e** que nada mudou no banco.
3. Valores em centavos nos asserts (`assert item.net_profit_cents == 9400`),
   nunca `float`.
4. Integrações externas sempre simuladas com `monkeypatch.setattr(...)`.
5. Datas relativas a `billing._now()`; não dependa da data do dia.

Esqueleto:

```python
from models import Product


def test_algo_novo(client, db, company):
    product = Product(company_id=company.id, name="Caneca", current_price_cents=3000)
    db.session.add(product)
    db.session.commit()
    # ... login via session_transaction, requisição, asserts
```

## Lacunas de cobertura

Ainda sem testes; boas primeiras contribuições:

- Venda manual com preço/custo sobrescritos no formulário.
- Ativar/desativar produto e perfil.
- Concorrência real (duas transações em paralelo) na baixa de estoque; hoje
  o teste simula o objeto desatualizado numa só sessão.
- Importação: formatos de data, linhas inválidas e quantidade decimal.
- `services/mercadopago.py`: parsing das respostas da API.
- Teste de migration: `flask db upgrade` num banco vazio seguido de
  `flask db check`, para rodar em CI.
