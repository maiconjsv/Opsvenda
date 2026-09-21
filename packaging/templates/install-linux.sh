#!/usr/bin/env bash
# Instalador/atualizador OpsVenda (Linux, sem admin/sudo). Roda a partir da
# pasta descompactada do pacote (dist/OpsVenda-linux-x64.tar.gz): copia tudo
# para ~/.local/share/opsvenda e cria uma entrada no menu de aplicativos. Não
# requer Docker nem privilégios de root.
#
# Esse mesmo script serve tanto pra primeira instalação quanto pra
# atualizar uma instalação existente: ele detecta a versão já instalada
# (arquivo VERSION dentro de INSTALL_DIR) e, se for diferente da versão
# deste pacote, substitui o código/runtime só dentro de INSTALL_DIR. Os
# dados do usuário (banco de dados, backups, uploads) vivem em outra pasta
# (INSTANCE_DIR, default ~/.local/share/OpsVenda - note a diferença de
# maiúsculas em relação a INSTALL_DIR) e nunca são tocados por este script.
set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/opsvenda"
NEW_VERSION="$(cat "$SOURCE_DIR/VERSION" 2>/dev/null || echo "desconhecida")"

MODE="install"
OLD_VERSION=""
if [ -d "$INSTALL_DIR" ]; then
    MODE="update"
    OLD_VERSION="$(cat "$INSTALL_DIR/VERSION" 2>/dev/null || echo "desconhecida")"
fi

if [ "$MODE" = "update" ] && [ "$OLD_VERSION" = "$NEW_VERSION" ] && [ "$NEW_VERSION" != "desconhecida" ]; then
    echo "OpsVenda já está na versão $NEW_VERSION em $INSTALL_DIR - nada a fazer."
    exit 0
fi

BACKUP_DIR=""
if [ "$MODE" = "update" ]; then
    echo "Atualizando OpsVenda ($OLD_VERSION -> $NEW_VERSION) em $INSTALL_DIR ..."
    echo "Seus dados (banco de dados, backups, uploads) ficam em outra pasta e não são afetados."
    echo "Feche o OpsVenda antes de continuar, se ele estiver aberto."
    BACKUP_DIR="${INSTALL_DIR}.bak-${OLD_VERSION}-$(date +%Y%m%d%H%M%S)"
    mv "$INSTALL_DIR" "$BACKUP_DIR"
else
    echo "Instalando o OpsVenda em $INSTALL_DIR ..."
fi

mkdir -p "$INSTALL_DIR"
cp -r "$SOURCE_DIR"/* "$INSTALL_DIR"/
rm -f "$INSTALL_DIR/install-linux.sh"
chmod +x "$INSTALL_DIR/python/bin/python3" "$INSTALL_DIR/run_desktop.py" 2>/dev/null || true

DESKTOP_FILE="$HOME/.local/share/applications/opsvenda.desktop"
mkdir -p "$HOME/.local/share/applications"
cat > "$DESKTOP_FILE" <<EOF
[Desktop Entry]
Type=Application
Name=OpsVenda
Comment=OpsVenda - Sistema de gestão de vendas Shopee
Exec=${INSTALL_DIR}/python/bin/python3 ${INSTALL_DIR}/run_desktop.py
Terminal=false
Categories=Office;
EOF
chmod +x "$DESKTOP_FILE"

echo ""
if [ "$MODE" = "update" ]; then
    echo "Atualização concluída ($OLD_VERSION -> $NEW_VERSION)."
    echo "A versão anterior do programa (sem os dados) ficou guardada em:"
    echo "  $BACKUP_DIR"
    echo "Pode apagar essa pasta quando confirmar que está tudo certo."
else
    echo "Instalação concluída."
fi
echo "Abra 'OpsVenda' no menu de aplicativos, ou execute:"
echo "  $INSTALL_DIR/python/bin/python3 $INSTALL_DIR/run_desktop.py"
