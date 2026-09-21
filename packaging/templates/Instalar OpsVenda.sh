#!/usr/bin/env bash
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
bash "$DIR/runtime/install-linux.sh"
echo ""
read -r -p "Pressione Enter para fechar..." _
