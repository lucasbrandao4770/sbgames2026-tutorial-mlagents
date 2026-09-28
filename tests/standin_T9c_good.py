"""T9c stand-in for scripts/verify_env.py: the real output of a good check on the dev Mac."""

from __future__ import annotations

LINES = [
    "Verificação do ambiente ML-Agents, Python 3.10.12, Darwin arm64",
    "[OK]    Python 3.10.12",
    "[OK]    Ambiente virtual ativo",
    "[OK]    PyTorch 2.2.1",
    "[OK]    CUDA não disponível, uso de CPU é o esperado",
    "[OK]    mlagents 1.1.0",
    "[OK]    mlagents_envs 1.1.0",
    "[OK]    numpy 1.23.5",
    "[OK]    protobuf 3.20.3",
    "[OK]    grpcio instalado",
    "[OK]    onnx instalado",
    "[OK]    tensorboard instalado",
    "[OK]    mlagents-learn encontrado",
    "[OK]    Pasta python/configs encontrada",
    "Resumo: 13 OK, 0 AVISO, 0 FALHA",
]

if __name__ == "__main__":
    for line in LINES:
        print(line)
