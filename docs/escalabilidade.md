# Escalabilidade

Onde o sistema está hoje, onde vai quebrar primeiro e em que ordem atacar.

[← Voltar ao README](../README.md)

- [Capacidade atual](#capacidade-atual)
- [Por que a base escala](#por-que-a-base-escala)
- [Gargalos conhecidos (por prioridade)](#gargalos-conhecidos-por-prioridade)
- [Roteiro de crescimento](#roteiro-de-crescimento)
- [Segurança](#segurança)
- [Dívida técnica](#dívida-técnica)

## Capacidade atual

| Recurso | Configuração |
|---|---|
| App | 1 container, Gunicorn com 2 workers síncronos, limite de 300 MB (uso ~130 MB) |
| Banco | Postgres 16 próprio, limite de 200 MB, `shared_buffers=32MB`, `max_connections=30` |
| Máquina | VPS de 2 GB **compartilhada** com bookcase, ofxconverter e necasecanecas |

Com 2 workers síncronos, o app atende **2 requisições ao mesmo tempo**; as
demais esperam na fila. Para telas rápidas isso dá conta de dezenas de
usuários simultâneos, mas uma requisição lenta (importação grande, dashboard
sem filtro ou Mercado Pago lento, que pode levar até 10 s) ocupa um worker
inteiro.

## Por que a base escala

As decisões estruturais já estão corretas para crescer sem reescrever:

- **Stateless:** a sessão fica no cookie assinado e não há estado em memória
  entre requisições. Dá para subir mais workers ou réplicas.
- **Postgres desde o início**, com índices em todo `company_id`, em
  `sku`, `order_number` e `mp_order_id`.
- **Multi-tenant por coluna** num banco só: operar 10 ou 10.000 empresas
  custa o mesmo em migrations e backup.
- **Snapshots imutáveis:** relatórios nunca recalculam o histórico, então
  somar é sempre barato e previsível.
- **Regras isoladas em `services/`**, sem depender do HTTP. Mover importação
  ou cobrança para uma fila de background é trocar quem chama, não reescrever.
- **Migrations aplicadas uma vez no entrypoint**, e não por worker, o que
  permite subir réplicas sem corrida no schema.

## Gargalos conhecidos (por prioridade)

Já resolvidos (29/09/2026): o **dashboard** agrega no Postgres
(`SUM`/`COUNT`/`GROUP BY`), carrega só as 100 linhas exibidas e exporta o CSV
em streaming; a **baixa de estoque** é atômica (`UPDATE ... SET stock_qty =
stock_qty + delta`) e o cancelamento usa `UPDATE` condicional; a
**importação** busca os produtos numa consulta só (sem N+1). Os testes em
[test_dashboard_insights.py](../tests/test_dashboard_insights.py) e
[test_stock.py](../tests/test_stock.py) seguram esse comportamento.

### 1. Dashboard sem período padrão
Sem filtro de data, as agregações percorrem todo o histórico da empresa. Com
o índice por `company_id` isso é rápido até algumas centenas de milhares de
itens. **Próximo passo:** índice composto `(company_id, sale_date)` em
`sales` e, se necessário, um período padrão (ex.: últimos 30 dias).

### 2. Importação de CSV síncrona
O arquivo inteiro é lido em memória e processado dentro da requisição, com um
commit único no final. Arquivos grandes estouram o `timeout` de 60 s do
Gunicorn e prendem um worker. Ainda há um `UPDATE` de estoque por linha.

**Correção, em ordem:** commits em lotes; depois, mover para um worker em
background (RQ ou Celery com Redis) com uma tela de progresso.

### 3. Uploads em disco local
Os CSVs em importação ficam em `instance/uploads/` e **nunca são apagados**.
Além de crescer para sempre, o disco local impede rodar réplicas do app em
máquinas diferentes.

**Correção:** apagar o arquivo ao final da importação e um job que limpe
arquivos com mais de 24 h. Com múltiplas máquinas, usar storage de objetos
(S3 ou compatível).

### 4. Listagens sem paginação
`/vendas` limita a 200 registros e `/produtos` carrega todos. **Correção:**
paginação com `LIMIT/OFFSET` ou cursor.

### 5. Workers síncronos e chamadas externas
Chamadas ao Mercado Pago (timeout de 10 s) bloqueiam um dos 2 workers. O
polling a cada 5 s na tela de Pix também consome workers (a conciliação por
cron roda fora do Gunicorn, via `docker exec`). **Correção:**
aumentar os workers conforme a RAM permitir (`--workers` no
`docker-entrypoint.sh`) ou usar `--worker-class gthread --threads 4`, que
atende I/O melhor com pouca memória.

### 6. Máquina compartilhada
Os limites de memória protegem os vizinhos, mas CPU e disco são disputados.
Quando o OpsVenda tiver receita relevante, a primeira mudança de
infraestrutura é **separá-lo em uma VPS própria**, ou pelo menos o banco num
Postgres gerenciado.

## Roteiro de crescimento

| Fase | Sinal para agir | Ações |
|---|---|---|
| **1. Agora (barato)** | — | Backup diário do banco ([deploy](deploy.md#backup-do-banco)); limpeza de uploads; fixar versão do SQLAlchemy |
| **2. Dezenas de empresas ativas** | Lentidão perceptível, fila no Gunicorn | `gthread` + mais workers; paginação; importação em lotes; índice composto `(company_id, sale_date)` em `sales` |
| **3. Centenas de empresas** | Importações > 30 s, RAM da VPS no limite | VPS própria; fila (Redis + RQ) para importação e cobrança; Sentry/logs centralizados; métricas de uso |
| **4. Milhares de empresas** | Banco como gargalo | Postgres gerenciado com réplica de leitura para relatórios; várias réplicas do app atrás do nginx; storage de objetos; tabelas de resumo diário por empresa para o dashboard |

Não é preciso mudar o modelo multi-tenant (coluna `company_id`) em nenhuma
dessas fases. Se um dia um cliente grande exigir isolamento físico, o
Row-Level Security do Postgres pode reforçar o `scoping` sem mudar o schema.

## Segurança

Itens para endurecer conforme o número de usuários cresce:

- **Rate limit** em `/auth/login`, `/auth/recuperar-senha` e na resposta de
  segurança (ex.: Flask-Limiter). Hoje dá para testar respostas sem limite.
- **Recuperação por e-mail** no lugar de, ou além de, a pergunta de
  segurança.
- `SESSION_COOKIE_SECURE=True` e `SESSION_COOKIE_SAMESITE="Lax"` explícitos
  em produção.
- Validar a assinatura (`x-signature`) do webhook do Mercado Pago. Hoje ele
  já é seguro porque reconsulta a API, mas validar evita chamadas
  desnecessárias disparadas por terceiros.
- Vários usuários por empresa, com papéis (dono/operador).

## Dívida técnica

- Colunas `shipping_cost_cents` (perfil) e `shipping_cost_snapshot_cents`
  (item) não são usadas. Remover com uma migration ou reativar o frete no
  cálculo.
- Nome de usuário único global. Ao permitir vários usuários por empresa,
  considere login por e-mail.
- `services/mercadopago.py` tem dados fixos de pagador (CPF zerado e e-mail
  genérico).
- Formulários validados à mão em cada rota. Com o crescimento, vale adotar
  formulários do Flask-WTF ou schemas (pydantic/marshmallow).
