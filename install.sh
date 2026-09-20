#!/usr/bin/env bash
# Instalador Linux: sobe o backend via Docker e cria um atalho para o
# launcher desktop (pywebview).
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if ! command -v docker >/dev/null 2>&1; then
  echo "Docker não encontrado. Instale o Docker antes de continuar: https://docs.docker.com/engine/install/"
  exit 1
fi

if ! docker compose version >/dev/null 2>&1; then
  echo "O plugin 'docker compose' não foi encontrado. Instale-o antes de continuar."
  exit 1
fi

if [ ! -f .env ]; then
  echo "Criando .env a partir de .env.example..."
  cp .env.example .env
  RANDOM_SECRET=$(python3 -c "import secrets; print(secrets.token_hex(32))" 2>/dev/null || echo "$(date +%s)-troque-esta-chave")
  sed -i "s/^SECRET_KEY=.*/SECRET_KEY=${RANDOM_SECRET}/" .env
  echo ""
  echo "Defina a senha do usuário administrador (usuário: admin, editável em .env):"
  read -r -s -p "Senha: " ADMIN_PW
  echo ""
  sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=${ADMIN_PW}/" .env
fi

echo "Subindo o backend com Docker Compose..."
docker compose up -d --build

echo "Aguardando o backend responder..."
for i in $(seq 1 30); do
  if curl -fs http://localhost:"$(grep '^APP_PORT=' .env | cut -d= -f2 || echo 5000)"/health >/dev/null 2>&1; then
    break
  fi
  sleep 2
done

echo "Preparando o launcher desktop..."
if [ ! -d .venv-desktop ]; then
  python3 -m venv .venv-desktop
fi
./.venv-desktop/bin/pip install --quiet --upgrade pip
./.venv-desktop/bin/pip install --quiet -r requirements-desktop.txt

DESKTOP_FILE="$HOME/.local/share/applications/opsvenda.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=OpsVenda
Comment=OpsVenda - Sistema de gestão de vendas Shopee
Exec=${SCRIPT_DIR}/.venv-desktop/bin/python ${SCRIPT_DIR}/run_desktop.py
Terminal=false
Categories=Office;
EOF
chmod +x "$DESKTOP_FILE"

echo ""
echo "Instalação concluída."
echo "Abra 'OpsVenda' no menu de aplicativos, ou execute:"
echo "  ./.venv-desktop/bin/python run_desktop.py"
