#!/usr/bin/env bash
# Roda numa máquina de desenvolvimento (precisa de internet) para gerar o
# pacote distribuível dist/OpsVenda-linux-x64.tar.gz: um bundle autocontido
# com um Python portátil (python-build-standalone) + todas as dependências
# já instaladas, pronto para o usuário final descompactar e instalar sem
# Docker e sem privilégios de root.
#
# A raiz do pacote só expõe "Instalar OpsVenda.sh" (o resto - python,
# código, script de instalação de verdade - fica dentro de runtime/), pra
# não confundir quem for só descompactar e instalar.
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PBS_RELEASE="20260901"
PY_VERSION="3.12.14"
ASSET="cpython-${PY_VERSION}+${PBS_RELEASE}-x86_64-unknown-linux-gnu-install_only_stripped.tar.gz"
BASE_URL="https://github.com/astral-sh/python-build-standalone/releases/download/${PBS_RELEASE}"

BUILD_DIR="$REPO_ROOT/dist/linux"
RUNTIME_DIR="$BUILD_DIR/runtime"
PY_DIR="$RUNTIME_DIR/python"
DIST_TAR="$REPO_ROOT/dist/OpsVenda-linux-x64.tar.gz"

rm -rf "$BUILD_DIR"
mkdir -p "$PY_DIR"

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

echo "Baixando Python $PY_VERSION (python-build-standalone)..."
curl -fL -o "$TMP_DIR/$ASSET" "$BASE_URL/$ASSET"
curl -fL -o "$TMP_DIR/SHA256SUMS" "$BASE_URL/SHA256SUMS"
( cd "$TMP_DIR" && grep " ${ASSET}\$" SHA256SUMS | sha256sum -c - )

echo "Extraindo runtime..."
tar -xzf "$TMP_DIR/$ASSET" -C "$PY_DIR" --strip-components=1

echo "Instalando dependências do app..."
"$PY_DIR/bin/python3" -m pip install --no-warn-script-location -r "$REPO_ROOT/requirements-desktop.txt"

echo "Copiando código da aplicação..."
cp -r "$REPO_ROOT/app" "$RUNTIME_DIR/"
cp "$REPO_ROOT/wsgi.py" "$RUNTIME_DIR/"
cp "$REPO_ROOT/run_desktop.py" "$RUNTIME_DIR/"
cp "$REPO_ROOT/VERSION" "$RUNTIME_DIR/"
cp "$(dirname "${BASH_SOURCE[0]}")/templates/install-linux.sh" "$RUNTIME_DIR/"
chmod +x "$RUNTIME_DIR/install-linux.sh"

echo "Gerando o instalador visível na raiz do pacote..."
cp "$(dirname "${BASH_SOURCE[0]}")/templates/Instalar OpsVenda.sh" "$BUILD_DIR/"
chmod +x "$BUILD_DIR/Instalar OpsVenda.sh"
cat > "$BUILD_DIR/LEIA-ME.txt" <<'EOF'
OpsVenda - Instalação/Atualização (Linux)

1. Dê dois cliques em "Instalar OpsVenda.sh" (se o seu gerenciador de
   arquivos perguntar, escolha "Executar no terminal"). Se preferir, rode
   pelo terminal: bash "Instalar OpsVenda.sh"
2. Uma janela de terminal mostra o progresso e pede pra apertar Enter no
   final - é normal.
3. Um atalho "OpsVenda" aparece no menu de aplicativos. Use ele a partir de
   agora, pode apagar essa pasta descompactada depois.

Já tem o OpsVenda instalado? Sem problema: rodar esse mesmo instalador
detecta a versão atual e atualiza para a nova, sem mexer no seu banco de
dados, backups ou uploads (ficam em outra pasta). A versão anterior do
programa (só o código, não os dados) é guardada ao lado como segurança e
pode ser apagada depois de confirmar que está tudo certo.

Não precisa de internet nem de sudo/root.
EOF

echo "Gerando $DIST_TAR ..."
tar -czf "$DIST_TAR" -C "$BUILD_DIR" .

echo ""
echo "Pronto: $DIST_TAR"
