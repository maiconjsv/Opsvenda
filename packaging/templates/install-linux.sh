#!/usr/bin/env bash
# Instalador OpsVenda (Linux, sem admin/sudo). Roda a partir da pasta
# descompactada do pacote (dist/OpsVenda-linux-x64.tar.gz): copia tudo para
# ~/.local/share/opsvenda e cria uma entrada no menu de aplicativos. Não
# requer Docker nem privilégios de root.
set -e

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/opsvenda"

echo "Instalando o OpsVenda em $INSTALL_DIR ..."
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
echo "Instalação concluída."
echo "Abra 'OpsVenda' no menu de aplicativos, ou execute:"
echo "  $INSTALL_DIR/python/bin/python3 $INSTALL_DIR/run_desktop.py"
