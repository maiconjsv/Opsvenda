#!/usr/bin/env bash
# Deploy OpsVenda to the production VPS (see docs/deploy.md).
#
# Deploys exactly the commit at local `main`, which must already be pushed
# to GitHub - the server pulls it from origin. Everything on the server runs
# in a single SSH session, so the password (if any) is asked once.
#
#   ./deploy.sh               tests + deploy
#   ./deploy.sh --skip-tests  deploy without running pytest locally
#
# OPSVENDA_HOST overrides the SSH target (default root@162.35.161.67).
set -euo pipefail

HOST="${OPSVENDA_HOST:-root@162.35.161.67}"
APP_DIR=/opt/opsvenda
APP_URL=https://opsvenda.montiqtech.com.br
# Other sites behind the same shared nginx - checked after the reload.
NEIGHBOR_SITES=(necasecanecas.com.br bookcase.montiqtech.com.br ofxconverter.montiqtech.com.br acervolivre.montiqtech.com.br)

RUN_TESTS=1
for arg in "$@"; do
  case "$arg" in
    --skip-tests) RUN_TESTS=0 ;;
    -h|--help) sed -n '2,11p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "Opção desconhecida: $arg (use --help)" >&2; exit 2 ;;
  esac
done

step() { printf '\n\033[1m==> %s\033[0m\n' "$*"; }
fail() { printf '\033[31mERRO:\033[0m %s\n' "$*" >&2; exit 1; }

cd "$(dirname "$0")"

step "Conferindo o repositório local"
[ "$(git rev-parse --abbrev-ref HEAD)" = "main" ] || fail "o deploy sai da branch main (atual: $(git rev-parse --abbrev-ref HEAD))."
[ -z "$(git status --porcelain)" ] || fail "há alterações não commitadas. Faça commit ou stash antes."
git fetch -q origin
SHA="$(git rev-parse HEAD)"
[ "$SHA" = "$(git rev-parse origin/main)" ] || fail "main local ($(git rev-parse --short HEAD)) difere de origin/main ($(git rev-parse --short origin/main)). Rode git push (ou git pull) antes."
echo "Commit: $(git log --oneline -1)"

if [ "$RUN_TESTS" = 1 ]; then
  step "Rodando os testes"
  python -m pytest --version >/dev/null 2>&1 || fail "pytest não encontrado. Ative o venv (source .venv/bin/activate) ou use --skip-tests."
  python -m pytest -q || fail "testes falharam; deploy cancelado."
fi

step "Deploy em $HOST"
ssh -o ConnectTimeout=15 "$HOST" bash -s -- "$SHA" "$APP_DIR" <<'REMOTE'
set -euo pipefail
SHA="$1"; APP_DIR="$2"
BACKUP_DIR=/root/backups/opsvenda
cd "$APP_DIR"

PREV="$(git rev-parse HEAD)"
echo "Versão atual no servidor: $(git log --oneline -1)"

echo "--> Backup do banco"
mkdir -p "$BACKUP_DIR"
BACKUP="$BACKUP_DIR/opsvenda-$(date +%Y%m%d%H%M%S)-pre-deploy.dump"
docker exec opsvenda-db pg_dump -U opsvenda -Fc opsvenda > "$BACKUP"
echo "$BACKUP ($(du -h "$BACKUP" | cut -f1))"
find "$BACKUP_DIR" -name '*-pre-deploy.dump' -mtime +30 -delete

echo "--> Atualizando o código"
git fetch -q origin
git merge -q --ff-only "$SHA" || { echo "O repositório do servidor divergiu de $SHA; resolva em $APP_DIR." >&2; exit 1; }
[ "$(git rev-parse HEAD)" = "$SHA" ] || { echo "O servidor está em $(git rev-parse --short HEAD), à frente de $SHA; nada foi alterado." >&2; exit 1; }

echo "--> Build e restart (migrations rodam no boot do container)"
docker compose up -d --build 2>&1 | tail -3

echo "--> Aguardando o app ficar saudável"
status=""
for _ in $(seq 1 40); do
  status="$(docker inspect -f '{{.State.Health.Status}}' opsvenda-app 2>/dev/null || true)"
  [ "$status" = "healthy" ] && break
  sleep 3
done
if [ "$status" != "healthy" ]; then
  echo "App não ficou saudável (status: ${status:-desconhecido}). Últimos logs:" >&2
  docker logs --tail 40 opsvenda-app >&2 || true
  cat >&2 <<EOF

Para voltar à versão anterior ($PREV):
  cd $APP_DIR
  # só se o deploy trouxe migration nova e ela já foi aplicada:
  #   docker exec opsvenda-app flask db downgrade
  git checkout $PREV && docker compose up -d --build
  docker exec ncas-web nginx -s reload
Backup do banco feito antes do deploy: $BACKUP
EOF
  exit 1
fi
docker logs --since 5m opsvenda-app 2>&1 | grep "alembic.runtime.migration\] Running" || echo "Nenhuma migration nova."

echo "--> Recarregando o nginx (o container novo tem outro IP)"
docker exec ncas-web nginx -t
docker exec ncas-web nginx -s reload
REMOTE

step "Conferindo os sites"
ok=1
code=""
for _ in $(seq 1 10); do
  code="$(curl -s -o /dev/null -w '%{http_code}' "$APP_URL/health" || true)"
  [ "$code" = "200" ] && break
  sleep 2
done
printf '%-34s %s\n' "opsvenda (/health)" "$code"
[ "$code" = "200" ] || ok=0
for site in "${NEIGHBOR_SITES[@]}"; do
  code="$(curl -s -o /dev/null -w '%{http_code}' "https://$site/" || true)"
  printf '%-34s %s\n' "$site" "$code"
  case "$code" in 2*|3*) ;; *) ok=0 ;; esac
done

[ "$ok" = 1 ] || fail "algum site não respondeu como esperado. Veja docs/deploy.md (rollback e nginx)."
step "Deploy concluído: $(git log --oneline -1)"
