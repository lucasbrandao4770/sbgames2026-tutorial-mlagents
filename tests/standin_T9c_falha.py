"""T9c stand-in for scripts/verify_env.py: a check with one FALHA, exit code 1."""

from __future__ import annotations

import sys

LINES = [
    "Verificação do ambiente ML-Agents, Python 3.10.12, Windows AMD64",
    "[OK]    Python 3.10.12",
    "[FALHA] PyTorch não encontrado",
    "[OK]    mlagents 1.1.0",
    "Resumo: 2 OK, 0 AVISO, 1 FALHA",
    "Consulte docs/00-instalacao.md para corrigir os problemas acima.",
]

if __name__ == "__main__":
    for line in LINES:
        print(line)
    sys.exit(1)
