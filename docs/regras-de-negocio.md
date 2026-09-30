# Regras de negócio

O OpsVenda responde a uma pergunta do pequeno vendedor de marketplace: **quanto
eu realmente lucrei em cada venda, depois de taxas e custo do produto?**

[← Voltar ao README](../README.md)

- [Conceitos](#conceitos)
- [Empresas, usuários e acesso](#empresas-usuários-e-acesso)
- [Produtos e estoque](#produtos-e-estoque)
- [Perfis de margem](#perfis-de-margem)
- [Cálculo de uma venda](#cálculo-de-uma-venda)
- [Snapshot: vendas passadas nunca mudam](#snapshot-vendas-passadas-nunca-mudam)
- [Venda manual](#venda-manual)
- [Importação de CSV (Shopee)](#importação-de-csv-shopee)
- [Cancelamento](#cancelamento)
- [Dashboard e exportação](#dashboard-e-exportação)
- [Assinatura e cobrança (Pix)](#assinatura-e-cobrança-pix)
- [Recuperação de senha](#recuperação-de-senha)
- [Limitações conhecidas](#limitações-conhecidas)

## Conceitos

| Conceito | O que é | Onde está |
|---|---|---|
| Empresa (tenant) | A conta que assina o serviço. Todo dado de negócio pertence a uma empresa. | [models/company.py](../models/company.py) |
| Usuário | Login de uma empresa. Hoje cada cadastro cria uma empresa com um usuário. | [models/user.py](../models/user.py) |
| Produto | Item vendido, com preço e custo **atuais** e estoque. | [models/product.py](../models/product.py) |
| Movimento de estoque | Histórico de toda alteração de estoque (venda, estorno, ajuste...). | [models/product.py](../models/product.py) |
| Perfil de margem | Modelo reutilizável de taxas (ex.: "Shopee Padrão", "Shopee Frete Grátis"). | [models/margin_profile.py](../models/margin_profile.py) |
| Venda / item de venda | Pedido e suas linhas, com todos os valores congelados no momento da venda. | [models/sale.py](../models/sale.py) |
| Pagamento | Uma cobrança Pix da assinatura. | [models/payment.py](../models/payment.py) |

**Dinheiro é sempre inteiro em centavos** (`*_cents`). Conversão só na borda
(`to_cents` / `from_cents` em [services/pricing.py](../services/pricing.py)).
Percentuais são guardados como fração (`0.12` = 12%); a tela mostra e recebe em %.

## Empresas, usuários e acesso

- **Cadastro público** (`/auth/cadastro`): nome da empresa, usuário, senha
  (mín. 6 caracteres, com confirmação) e pergunta de segurança obrigatória.
  Cria a empresa, com **90 dias de teste grátis**, e o usuário, e já faz login.
- **Nome de usuário é único no sistema inteiro**, não por empresa: duas
  empresas não podem ter um usuário `admin`.
- **Isolamento total entre empresas:** um usuário nunca vê nem altera dados de
  outra empresa. Acessar por ID um registro de outra empresa devolve 404
  (detalhes em [arquitetura → multi-tenant](arquitetura.md#multi-tenant)).
- **Login** aceita `?next=` apenas para caminhos internos (`/...`), o que
  impede redirecionar para sites de fora (open redirect).
- **Suporte:** `flask create-admin --company-id <id>` cria um usuário numa
  empresa existente ou troca a senha de um usuário.

## Produtos e estoque

- Campos: SKU (opcional, **único dentro da empresa**; empresas diferentes
  podem repetir), nome, preço atual, custo atual e estoque.
- **Produto não é apagado, é desativado.** Produtos inativos somem da lista
  (há o filtro "mostrar inativos") e do formulário de venda, mas continuam nas
  vendas antigas.
- **Toda alteração de estoque gera um movimento** (`StockMovement`) com o
  delta e o motivo:

| Motivo | Quando |
|---|---|
| `estoque_inicial` | Produto criado com estoque > 0 |
| `venda` | Venda manual (delta negativo) |
| `venda_import` | Venda importada por CSV (delta negativo) |
| `estorno` | Cancelamento de venda (delta positivo) |
| `ajuste` / outro | Ajuste manual na tela do produto (delta ≠ 0, com observação opcional) |

- **O estoque pode ficar negativo.** Nenhuma venda é bloqueada por falta de
  estoque; o saldo negativo indica que é preciso repor ou corrigir.
- **Baixas simultâneas não se perdem:** toda alteração passa por
  `adjust_stock()` em [services/stock.py](../services/stock.py), que manda o
  Postgres calcular `stock_qty = stock_qty + delta`. Duas vendas ao mesmo
  tempo do mesmo produto baixam as duas quantidades.
- **Custo pendente:** produtos criados automaticamente pela importação
  aparecem com o selo "custo pendente" até o usuário informar o custo (ver
  [exceção do snapshot](#exceção-custo-pendente)).

## Perfis de margem

Um perfil reúne as taxas de um canal de venda:

| Campo | Significado |
|---|---|
| `platform_fee_pct` | Comissão da plataforma, % sobre a receita bruta da linha |
| `fixed_fee_cents` | Taxa fixa **por linha de venda** (não por unidade) |
| `other_fee_pct` | Outras taxas percentuais (ex.: imposto, antecipação) |

- O nome é único dentro da empresa.
- Os perfis também são desativados em vez de apagados.
- Toda venda exige um perfil ativo.

## Cálculo de uma venda

A fórmula existe em **um único lugar**, `calculate_sale_item()` em
[services/pricing.py](../services/pricing.py), e é usada tanto pela venda
manual quanto pela importação:

```
receita_bruta  = preço_unitário × quantidade
taxa_plataforma = arred(receita_bruta × platform_fee_pct) + taxa_fixa
outras_taxas   = arred(receita_bruta × other_fee_pct)
taxas_totais   = taxa_plataforma + outras_taxas
custo_total    = custo_unitário × quantidade + taxas_totais
lucro_líquido  = receita_bruta − custo_total
margem         = lucro_líquido / receita_bruta
```

**Exemplo:** 2 unidades a R$ 100,00, custo de R$ 30,00, perfil com 20% de
comissão, taxa fixa de R$ 4,00 e 1% de outras taxas.

| | Valor |
|---|---|
| Receita bruta | R$ 200,00 |
| Taxa da plataforma | R$ 40,00 + R$ 4,00 = R$ 44,00 |
| Outras taxas | R$ 2,00 |
| Custo total | R$ 60,00 + R$ 46,00 = R$ 106,00 |
| **Lucro líquido** | **R$ 94,00 (margem de 47%)** |

- Quantidade precisa ser > 0.
- Frete **não** entra no cálculo. As colunas `shipping_cost_*` existem no
  banco, mas não são usadas (ver [limitações](#limitações-conhecidas)).

## Snapshot: vendas passadas nunca mudam

**Esta é a regra mais importante do sistema.** Cada `SaleItem` guarda uma
cópia de tudo o que existia no momento da venda: nome e SKU do produto, preço,
custo, as três taxas e os totais calculados.

- Editar o preço ou custo de um produto **não** altera vendas já registradas.
- Editar um perfil de margem **não** altera vendas já registradas.
- Relatórios e dashboard leem **somente** os snapshots, sem recalcular nada.

Os testes em
[tests/test_sale_snapshot_immutability.py](../tests/test_sale_snapshot_immutability.py)
garantem essa regra. Qualquer código novo que precise de valores de uma venda
passada deve ler do `SaleItem`, nunca do `Product` ou do `MarginProfile`.

### Exceção: custo pendente

A única situação em que um snapshot é recalculado é quando o **custo era
desconhecido** no momento da venda:

- Um produto criado pela importação nasce com `cost_pending = True` e custo
  R$ 0,00. As vendas dele também são marcadas com `cost_pending`, e o lucro
  delas fica superestimado.
- O dashboard avisa: "N venda(s) de produtos com custo pendente: o lucro está
  superestimado".
- Na edição do produto, o campo de custo aparece vazio. **Ao preencher**
  (mesmo com 0), o produto sai da pendência e **só** os itens marcados como
  pendentes são recalculados com o custo informado
  ([services/costs.py](../services/costs.py)). Preço, taxas e demais
  snapshots continuam como estavam.
- Deixar o campo em branco mantém a pendência.
- Uma venda manual de produto pendente também fica pendente, a menos que o
  custo seja informado no próprio formulário da venda.

Coberto por [tests/test_pending_cost.py](../tests/test_pending_cost.py).

## Venda manual

`/vendas/nova`: escolhe produto ativo, quantidade e perfil de margem ativo.

- Preço e custo unitários são opcionais no formulário. Se vierem vazios, o
  sistema usa o preço e o custo atuais do produto; preenchidos, sobrescrevem
  os do produto só naquela venda (ex.: promoção).
- Nº do pedido e observações são opcionais.
- A venda nasce `completed`, com origem `manual`. O estoque é baixado e um
  movimento `venda` é registrado.

## Importação de CSV (Shopee)

Assistente em três passos (`/vendas/importar`):

1. **Upload:** qualquer CSV em UTF-8 (com ou sem BOM). O arquivo fica salvo
   no servidor com um token aleatório.
2. **Mapeamento:** o usuário vê as 5 primeiras linhas e indica qual coluna
   corresponde a cada campo. Os nomes das colunas **não** são fixos, porque o
   export da Shopee muda por região e versão.
   - Obrigatórios: SKU, quantidade, preço unitário.
   - Opcionais: nº do pedido, nome do produto, data da venda.
   - Também escolhe o perfil de margem e se deve **criar produtos que não
     existem**.
3. **Resultado:** vendas criadas, produtos criados, duplicadas ignoradas,
   linhas com erro (com o número da linha), a lista de produtos com custo
   pendente e, se o nº do pedido não foi mapeado, um aviso de que reimportar
   vai duplicar.

Regras da importação ([services/csv_import.py](../services/csv_import.py)):

- **Cada linha do CSV vira uma venda** com um item. Um pedido da Shopee com 3
  produtos vira 3 vendas com o mesmo nº de pedido.
- O produto é localizado pelo SKU dentro da empresa. Se não existir:
  - com "criar produtos" marcado, é criado com o preço da linha, estoque 0
    e **custo pendente**;
  - sem essa opção, a linha é rejeitada ("SKU não encontrado").
- **O custo vem do custo atual do produto**, e não do CSV. Para produtos
  criados pela importação, as vendas ficam com custo pendente até o usuário
  informar o custo; aí elas são recalculadas
  ([exceção do snapshot](#exceção-custo-pendente)).
- **Deduplicação:** com a coluna do nº do pedido mapeada, uma linha cujo par
  **nº do pedido + SKU** já existe na empresa (de uma importação anterior,
  de uma venda manual ou de uma linha anterior do mesmo arquivo) é ignorada e
  contada como duplicada. Importar o mesmo arquivo duas vezes não duplica
  vendas nem baixa o estoque de novo. Isso vale inclusive se a venda original
  foi cancelada: ela continua registrada.
- Datas aceitas: `AAAA-MM-DD`, `AAAA-MM-DD HH:MM:SS`, `DD/MM/AAAA` e
  `DD/MM/AAAA HH:MM:SS`. Sem data válida, vale o momento da importação.
- Quantidade decimal é truncada (`"2.0"` vira 2).
- Linhas inválidas são puladas e listadas; as válidas são gravadas juntas num
  único commit no final.
- **Sem a coluna do nº do pedido não há como deduplicar:** a tela recomenda
  mapeá-la e o resultado avisa quando ela não foi mapeada.

## Cancelamento

`/vendas/<id>/cancelar` muda o status para `cancelled` e **devolve ao
estoque** a quantidade de cada item (movimento `estorno`). Cancelar de novo
não tem efeito, inclusive com dois cliques simultâneos: a troca de status é
um `UPDATE ... WHERE status != 'cancelled'`, e só quem de fato mudou a venda
devolve o estoque. Vendas canceladas não entram no dashboard nem na exportação.

O status `refunded` (reembolsada) existe no modelo, mas ainda não há tela que
o use. Se for usado, hoje **ele conta** no dashboard, porque o filtro só exclui
`cancelled`.

## Dashboard e exportação

`/` (dashboard) aceita os filtros data inicial, data final e produto.

- **KPIs:** receita bruta, taxas, custo total, lucro líquido, unidades
  vendidas e margem média (lucro ÷ receita).
- **Insights:**
  - quantas vendas têm custo pendente (lucro superestimado);
  - quantos itens deram prejuízo e o valor total perdido;
  - produto que mais lucrou;
  - produto que mais deu prejuízo (só aparece se algum teve lucro negativo);
  - com as duas datas preenchidas, comparação com o **período anterior de
    mesma duração** (ex.: 8–14/jan é comparado com 1–7/jan) e a variação em %.
- A tabela mostra os 100 itens mais recentes, com o total de linhas
  encontradas.
- Todos os totais e insights são calculados pelo Postgres (`SUM`, `COUNT`,
  `GROUP BY`), sobre todas as linhas do filtro, e não só sobre as 100
  exibidas.
- **Exportar CSV** (`/exportar.csv`) usa os mesmos filtros e traz todas as
  linhas, enviadas em streaming, com colunas em português (`data_venda`, `pedido`, `sku`, ...,
  `lucro_liquido`, `margem_pct`, `status`, `origem`).

## Assinatura e cobrança (Pix)

Regras em [services/billing.py](../services/billing.py):

| Constante | Valor | Efeito |
|---|---|---|
| `TRIAL_DAYS` | 90 | Teste grátis a partir do cadastro |
| `PRICE_CENTS` | 499 | R$ 4,99 por período |
| `SUBSCRIPTION_DAYS` | 30 | Dias somados por pagamento |
| `GRACE_DAYS` | 3 | Tolerância após o vencimento |

- Cada empresa tem `access_until`, a data até a qual o acesso está pago (ou
  em teste).
- **Bloqueio:** depois de `access_until + 3 dias`, qualquer página redireciona
  para `/assinatura`. Continuam liberados: login, logout, a página de
  assinatura, gerar e verificar cobrança, webhook, arquivos estáticos e
  `/health`. Nenhum dado é apagado; ao pagar, tudo volta.
- **Pagamento:**
  1. O usuário clica em gerar cobrança. O Mercado Pago cria um pedido Pix e o
     sistema salva um `Payment` pendente com QR code e copia-e-cola. Se a API
     falhar, nada é salvo e aparece uma mensagem de erro.
  2. A página consulta `/assinatura/verificar/<id>` a cada 5 segundos, que
     pergunta o status ao Mercado Pago.
  3. O Mercado Pago também avisa pelo webhook `/assinatura/webhook`, se ele
     estiver cadastrado no painel.
  4. **Conciliação:** o comando `flask billing-reconcile`, rodado por um timer a
     cada 5 minutos no servidor, confere no Mercado Pago todas as cobranças
     pendentes das últimas 48 h. O pagamento é confirmado mesmo sem webhook
     e com a página fechada.
- **Confirmação:** soma 30 dias a partir de `access_until` se ainda estiver
  no futuro, ou a partir de agora se já venceu. Pagar adiantado não perde
  dias.
- **Idempotência:** confirmar um pagamento já pago não faz nada. O Mercado
  Pago reenvia webhooks, e sem isso o acesso seria estendido duas vezes.
- **Segurança do webhook:** o conteúdo recebido **não é confiável**. O
  sistema usa só o ID do pedido e consulta o status real na API do Mercado
  Pago antes de confirmar, então um webhook forjado não libera acesso.

## Recuperação de senha

Não há e-mail. A recuperação usa a pergunta de segurança escolhida no
cadastro:

- A resposta é guardada como hash e comparada sem diferenciar maiúsculas nem
  espaços nas pontas.
- Com a resposta certa, o usuário define uma nova senha (mín. 6 caracteres).
- Sem pergunta cadastrada, ou com usuário inexistente, a tela orienta a falar
  com o suporte, que usa o `flask create-admin`.

## Limitações conhecidas

Pontos de regra que ainda não estão resolvidos e merecem decisão de produto:

- Uma empresa tem na prática um único usuário (não há convite nem papéis).
- Status `refunded` sem fluxo próprio.
- Frete fora do cálculo (colunas `shipping_cost_*` mortas).
- Recuperação de senha só por pergunta de segurança, sem e-mail. É fraca para
  um SaaS.
- A plataforma de toda venda importada é fixa em `"Shopee"`.
