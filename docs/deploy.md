# Deploy e operação

Produção: **https://opsvenda.montiqtech.com.br**

[← Voltar ao README](../README.md)

- [Infraestrutura](#infraestrutura)
- [Atualizar a produção](#atualizar-a-produção)
- [Rollback](#rollback)
- [Comandos do dia a dia](#comandos-do-dia-a-dia)
- [nginx compartilhado (leia antes de editar)](#nginx-compartilhado-leia-antes-de-editar)
- [Certificado TLS](#certificado-tls)
- [Backup do banco](#backup-do-banco)
- [Mercado Pago](#mercado-pago)
- [Deploy do zero (nova máquina)](#deploy-do-zero-nova-máquina)

## Infraestrutura

Uma VPS Ubuntu 24.04 com 2 GB de RAM, **compartilhada** com outros projetos
(necasecanecas, bookcase, ofxconverter, acervolivre). Acesso por SSH como
root; as credenciais ficam fora do repositório.

```
/opt/opsvenda/                 clone deste repositório
  .env                         segredos de produção (chmod 600, fora do git)
  docker-compose.yml           opsvenda-app + opsvenda-db

/opt/necasecanecas/nginx/default.conf    config do nginx de TODOS os sites
```

| Container | Imagem | Função |
|---|---|---|
| `opsvenda-app` | build local (`Dockerfile`) | Gunicorn + Flask, porta 5000 interna |
| `opsvenda-db` | `postgres:16-alpine` | Banco do OpsVenda (volume `opsvenda_db_data`) |
| `ncas-web` | `nginx:1.27-alpine` | Proxy e TLS de todos os sites (projeto necasecanecas) |
| `ncas-certbot` | `certbot/dns-cloudflare` | Renova os certificados a cada 12 h |

Redes: o `opsvenda-app` fica na rede interna do projeto (para falar com o
`db`) e na rede externa `necasecanecas_default` (para o nginx alcançá-lo pelo
nome `opsvenda-app`). O banco **não** fica exposto ao nginx nem à internet.

O que acontece quando o container sobe
([docker-entrypoint.sh](../docker-entrypoint.sh)):

1. O `depends_on` espera o Postgres ficar *healthy* (`pg_isready`).
2. `flask db upgrade` aplica as migrations pendentes, **uma vez**.
3. O Gunicorn sobe com 2 workers.
4. O healthcheck do Docker consulta `/health` a cada 15 s.

## Atualizar a produção

Na sua máquina: testes passando e commit enviado.

```bash
pytest
git push origin main
```

No servidor:

```bash
ssh root@162.35.161.67
cd /opt/opsvenda
git pull
docker compose up -d --build
docker compose ps                       # opsvenda-app deve ficar (healthy)
docker logs --tail 30 opsvenda-app      # confira a migration e o boot do gunicorn
curl -s https://opsvenda.montiqtech.com.br/health
```

- A troca do container leva poucos segundos de indisponibilidade só para o
  OpsVenda. Os outros sites não são afetados.
- Migrations novas rodam sozinhas no boot. Se uma migration falhar, o
  container fica reiniciando e o log mostra o erro. Veja o [rollback](#rollback).
- **Nunca** rode `docker compose down -v` em `/opt/opsvenda`: o `-v` apaga o
  banco.

## Rollback

Código sem mudança de schema:

```bash
cd /opt/opsvenda
git log --oneline -5
git checkout <commit-anterior>
docker compose up -d --build
```

Com migration: reverta o schema **antes** de voltar o código, porque o código
antigo não conhece a revisão nova.

```bash
docker exec opsvenda-app flask db downgrade
git checkout <commit-anterior>
docker compose up -d --build
```

Faça um [backup](#backup-do-banco) antes de qualquer downgrade que remova
colunas ou tabelas. Depois de resolver o problema, volte com
`git checkout main`.

## Comandos do dia a dia

```bash
cd /opt/opsvenda
docker compose ps                                   # estado
docker logs -f opsvenda-app                         # logs ao vivo
docker stats --no-stream                            # memória de todos os containers
docker exec -it opsvenda-db psql -U opsvenda        # console SQL
docker exec opsvenda-app flask db current           # revisão aplicada
docker exec -it opsvenda-app flask create-admin --company-id <id>   # suporte: senha/usuário
docker compose restart app                          # reinicia só o app
```

Consultas úteis no `psql`:

```sql
SELECT id, name, access_until FROM companies ORDER BY id;          -- empresas e vencimento
SELECT c.name, u.username FROM users u JOIN companies c ON c.id = u.company_id;
SELECT status, count(*) FROM payments GROUP BY status;
```

## nginx compartilhado (leia antes de editar)

O `default.conf` controla **todos os sites da VPS**. Um erro derruba todos.

**Armadilha do inode.** O arquivo é montado no container como *bind mount de
arquivo único*. Ferramentas que **substituem** o arquivo em vez de
reescrevê-lo, como `sed -i` e a maioria dos editores (vim, nano com backup,
VS Code remoto), criam um inode novo, e o container continua lendo o arquivo
antigo. `nginx -t` e `nginx -s reload` passam, mas **nada muda**. Isso
aconteceu entre 03/09 e 27/09/2026.

Procedimento seguro:

```bash
F=/opt/necasecanecas/nginx/default.conf
cp -p $F $F.bak-$(date +%Y%m%d%H%M%S)            # 1. backup

# 2. editar mantendo o inode: gere o novo conteúdo e grave com cat
cp $F /root/tmp/nginx.new && nano /root/tmp/nginx.new
cat /root/tmp/nginx.new > $F

# 3. confirmar que o container enxerga a mudança
docker exec ncas-web grep -c "<algo que você adicionou>" /etc/nginx/conf.d/default.conf

# 4. testar e aplicar
docker exec ncas-web nginx -t && docker exec ncas-web nginx -s reload

# 5. conferir todos os sites
for h in necasecanecas.com.br bookcase.montiqtech.com.br ofxconverter.montiqtech.com.br \
         acervolivre.montiqtech.com.br opsvenda.montiqtech.com.br; do
  echo "$h $(curl -s -o /dev/null -w '%{http_code}' https://$h/)"; done
```

Se o passo 3 mostrar o conteúdo antigo, o inode já foi trocado. Nesse caso,
teste a config nova num container descartável e reinicie o `ncas-web` (1 a 2 s
fora do ar para todos os sites):

```bash
docker run --rm --network necasecanecas_default \
  -v $F:/etc/nginx/conf.d/default.conf:ro \
  -v necasecanecas_certbot_certs:/etc/letsencrypt:ro \
  -v necasecanecas_certbot_www:/var/www/certbot:ro \
  -v /opt/necasecanecas/sites/acervolivre:/var/www/acervolivre:ro \
  nginx:1.27-alpine nginx -t
docker restart ncas-web
```

O bloco do OpsVenda no `default.conf` é o `server { listen 443 ssl; server_name
opsvenda.montiqtech.com.br; ... proxy_pass http://opsvenda-app:5000; }`, e o
domínio também aparece no `server_name` do bloco da porta 80, que redireciona
para HTTPS e responde ao desafio do certbot.

## Certificado TLS

- Emitido pelo Let's Encrypt via **webroot** (`/var/www/certbot`), no volume
  `necasecanecas_certbot_certs`.
- O `ncas-certbot` tenta renovar a cada 12 h, e a renovação acontece quando
  faltam menos de 30 dias.
- **Risco:** o nginx só carrega o certificado novo depois de um reload ou
  restart, e o certbot **não** recarrega o nginx. Se ninguém fizer reload nos
  30 dias entre a renovação e o vencimento, **todos os sites** exibem
  certificado vencido. Recomendado: um cron semanal no host.

```bash
# crontab -e (root)
0 4 * * 1 docker exec ncas-web nginx -s reload
```

- Verificar a validade:

```bash
echo | openssl s_client -connect opsvenda.montiqtech.com.br:443 -servername opsvenda.montiqtech.com.br 2>/dev/null | openssl x509 -noout -dates
```

## Backup do banco

**Ainda não há backup automático.** Configure um cron diário no host:

```bash
mkdir -p /root/backups/opsvenda
# crontab -e (root)
30 3 * * * docker exec opsvenda-db pg_dump -U opsvenda -Fc opsvenda > /root/backups/opsvenda/opsvenda-$(date +\%Y\%m\%d).dump && find /root/backups/opsvenda -name '*.dump' -mtime +14 -delete
```

Restaurar (substitui os dados atuais):

```bash
docker compose -f /opt/opsvenda/docker-compose.yml stop app
docker exec -i opsvenda-db pg_restore -U opsvenda -d opsvenda --clean --if-exists < /root/backups/opsvenda/opsvenda-AAAAMMDD.dump
docker compose -f /opt/opsvenda/docker-compose.yml start app
```

Copie os dumps periodicamente para fora da VPS: um backup na mesma máquina
não protege contra perda do servidor.

## Mercado Pago

1. Coloque o token no `.env` de produção e recrie o app:

   ```bash
   cd /opt/opsvenda
   nano .env        # MERCADO_PAGO_ACCESS_TOKEN=APP_USR-...   MP_SANDBOX=false
   docker compose up -d
   ```

2. No painel do Mercado Pago (Suas integrações → Webhooks), cadastre a URL
   `https://opsvenda.montiqtech.com.br/assinatura/webhook` para eventos de
   pedidos/pagamentos. O código **não** envia `notification_url` na criação
   da cobrança, então o webhook depende desse cadastro no painel. Sem ele, a
   confirmação ainda funciona pelo polling da tela de pagamento, mas só
   enquanto o usuário estiver com a página aberta.

## Deploy do zero (nova máquina)

Pré-requisitos: Docker com o plugin compose e um nginx com TLS na frente. Na
VPS atual isso já existe; numa máquina nova, adapte a rede externa do
`docker-compose.yml`.

```bash
git clone https://github.com/maiconjsv/Opsvenda.git /opt/opsvenda
cd /opt/opsvenda
umask 077
printf "SECRET_KEY=%s\nPOSTGRES_PASSWORD=%s\nMP_SANDBOX=false\n" \
  "$(openssl rand -hex 32)" "$(openssl rand -hex 24)" > .env
docker compose up -d --build
```

Em seguida:

1. Aponte o DNS para a máquina.
2. Adicione o domínio ao bloco da porta 80 do nginx e faça reload.
3. Emita o certificado:

   ```bash
   docker run --rm -v necasecanecas_certbot_certs:/etc/letsencrypt \
     -v necasecanecas_certbot_www:/var/www/certbot --entrypoint certbot \
     certbot/dns-cloudflare certonly --webroot -w /var/www/certbot \
     -d opsvenda.montiqtech.com.br --agree-tos -n
   ```

4. Adicione o bloco 443 seguindo o
   [procedimento seguro](#nginx-compartilhado-leia-antes-de-editar).

**Guarde o `.env`:** perder a `SECRET_KEY` desloga todos os usuários, e perder
a `POSTGRES_PASSWORD` exige resetar a senha do banco.
