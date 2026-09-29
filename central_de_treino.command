#!/bin/bash
# Opens Central de treino on macOS and Linux. Double-click this file.
#
# Finds .venv next to this script and the repo root (this script's own folder),
# then runs scripts/central_de_treino.py with that virtual environment's Python,
# so results/, Demos/ and the relative paths in commands behave exactly as in
# the docs.
set -u

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR" || exit 1

PYTHON_BIN="$DIR/.venv/bin/python3"

if [ ! -x "$PYTHON_BIN" ]; then
    echo "=============================================================="
    echo "Ambiente virtual não encontrado em .venv."
    echo "Siga docs/00-instalacao.md para instalar o ambiente do tutorial"
    echo "antes de abrir a Central de treino."
    echo "=============================================================="
    read -r -p "Pressione Enter para fechar."
    exit 1
fi

echo "Não feche esta janela enquanto a Central de treino estiver aberta."

"$PYTHON_BIN" scripts/central_de_treino.py
STATUS=$?

if [ $STATUS -ne 0 ]; then
    echo "A Central de treino fechou com um erro (código $STATUS)."
    read -r -p "Pressione Enter para fechar."
fi

exit $STATUS
