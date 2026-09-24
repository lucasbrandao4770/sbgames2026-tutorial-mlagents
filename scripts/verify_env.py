"""Verify the pinned Unity ML-Agents Python stack for the SBGames 2026 tutorial.

Run this script inside the tutorial's virtual environment before the event to confirm
every pinned dependency is installed correctly. Output is a short checklist meant for
beginners attending the workshop.
"""

from __future__ import annotations

import argparse
import dataclasses
import importlib.metadata
import importlib.util
import json
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Literal

Status = Literal["OK", "AVISO", "FALHA"]

# mlagents 1.1.0 declares Requires-Python >=3.10.1,<=3.10.12.
MLAGENTS_PYTHON_MIN = (3, 10, 1)
MLAGENTS_PYTHON_MAX = (3, 10, 12)
PINNED_MLAGENTS = "1.1.0"
PINNED_MLAGENTS_ENVS = "1.1.0"
PINNED_TORCH = "2.2.1"
SETUPTOOLS_MAX_MAJOR = 80
GRPCIO_MACOS_ARM64 = "1.53.2"


@dataclasses.dataclass(frozen=True)
class CheckResult:
    """Outcome of a single environment check."""

    name: str
    status: Status
    detail: str


def check_python_version() -> CheckResult:
    version = platform.python_version()
    if MLAGENTS_PYTHON_MIN <= sys.version_info[:3] <= MLAGENTS_PYTHON_MAX:
        return CheckResult("python", "OK", f"Python {version}")
    detail = f"Python: encontrado {version}, o mlagents 1.1.0 aceita de 3.10.1 a 3.10.12"
    return CheckResult("python", "FALHA", detail)


def check_pinned_package(
    package: str, expected: str, allow_local_suffix: bool = False
) -> CheckResult:
    try:
        found = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return CheckResult(package, "FALHA", f"{package}: não encontrado, esperado {expected}")
    normalized = found.split("+")[0] if allow_local_suffix else found
    if normalized == expected:
        return CheckResult(package, "OK", f"{package} {found}")
    return CheckResult(package, "FALHA", f"{package}: encontrado {found}, esperado {expected}")


def check_cuda_availability() -> CheckResult:
    try:
        import torch
    except Exception:
        return CheckResult("cuda", "AVISO", "não verificado, torch não importou")
    if torch.cuda.is_available():
        return CheckResult("cuda", "OK", "CUDA disponível")
    return CheckResult("cuda", "OK", "CUDA não disponível, uso de CPU é o esperado")


def check_setuptools() -> CheckResult:
    # mlagents and tensorboard import pkg_resources, which setuptools 82 dropped.
    try:
        version: str | None = importlib.metadata.version("setuptools")
    except importlib.metadata.PackageNotFoundError:
        version = None
    label = f"setuptools {version}" if version else "setuptools não encontrado"
    if importlib.util.find_spec("pkg_resources") is None:
        detail = f'{label}: falta o módulo pkg_resources, corrija com pip install "setuptools<80"'
        return CheckResult("setuptools", "FALHA", detail)
    major = _leading_int(version) if version else None
    if major is not None and major >= SETUPTOOLS_MAX_MAJOR:
        detail = f'{label}: versão não testada, recomendado pip install "setuptools<80"'
        return CheckResult("setuptools", "AVISO", detail)
    return CheckResult("setuptools", "OK", label)


def check_grpcio() -> CheckResult:
    try:
        version = importlib.metadata.version("grpcio")
    except importlib.metadata.PackageNotFoundError:
        return CheckResult("grpcio", "AVISO", "grpcio: não encontrado")
    detail = f"grpcio {version}"
    is_macos_arm64 = platform.system() == "Darwin" and platform.machine() in {"arm64", "aarch64"}
    if is_macos_arm64 and version != GRPCIO_MACOS_ARM64:
        detail += f", versão recomendada em macOS arm64 é {GRPCIO_MACOS_ARM64}"
    return CheckResult("grpcio", "OK", detail)


def check_informational_package(package: str) -> CheckResult:
    try:
        version = importlib.metadata.version(package)
    except importlib.metadata.PackageNotFoundError:
        return CheckResult(package, "AVISO", f"{package}: não encontrado")
    return CheckResult(package, "OK", f"{package} {version}")


def check_mlagents_learn_cli() -> CheckResult:
    # A venv keeps console scripts next to its interpreter (bin/ on POSIX, Scripts\ on
    # Windows), so an unactivated venv still has the command even when PATH lacks it.
    on_path = shutil.which("mlagents-learn")
    exe_name = "mlagents-learn.exe" if os.name == "nt" else "mlagents-learn"
    beside_interpreter = Path(sys.executable).parent / exe_name
    if beside_interpreter.is_file():
        if on_path and Path(on_path).resolve() == beside_interpreter.resolve():
            return CheckResult("mlagents-learn", "OK", f"mlagents-learn encontrado em {on_path}")
        detail = (
            "mlagents-learn encontrado ao lado do interpretador, "
            "ative o ambiente virtual para usar o comando"
        )
        return CheckResult("mlagents-learn", "OK", detail)
    if on_path:
        return CheckResult("mlagents-learn", "OK", f"mlagents-learn encontrado em {on_path}")
    detail = "mlagents-learn não encontrado no PATH nem ao lado do interpretador"
    return CheckResult("mlagents-learn", "FALHA", detail)


def check_virtualenv() -> CheckResult:
    if sys.prefix != sys.base_prefix:
        return CheckResult("venv", "OK", "executando dentro de um ambiente virtual")
    detail = "não está em um ambiente virtual, ative o ambiente virtual do projeto"
    return CheckResult("venv", "AVISO", detail)


def check_import_smoke_test() -> list[CheckResult]:
    results: list[CheckResult] = []
    for module_name in ("mlagents_envs", "torch"):
        try:
            __import__(module_name)
        except Exception as exc:
            message = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
            detail = f"falha ao importar {module_name}: {message}"
            results.append(CheckResult(f"import {module_name}", "FALHA", detail))
        else:
            results.append(CheckResult(f"import {module_name}", "OK", f"{module_name} importado"))
    return results


def _leading_int(version: str) -> int | None:
    try:
        return int(version.split(".")[0])
    except (ValueError, IndexError):
        return None


def run_all_checks() -> list[CheckResult]:
    results = [
        check_python_version(),
        check_pinned_package("mlagents", PINNED_MLAGENTS),
        check_pinned_package("mlagents-envs", PINNED_MLAGENTS_ENVS),
        check_pinned_package("torch", PINNED_TORCH, allow_local_suffix=True),
        check_cuda_availability(),
        check_setuptools(),
        check_grpcio(),
        check_informational_package("protobuf"),
        check_informational_package("numpy"),
        check_mlagents_learn_cli(),
        check_virtualenv(),
    ]
    results.extend(check_import_smoke_test())
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Verifica o ambiente Python do tutorial de Unity ML-Agents."
    )
    parser.add_argument("--json", action="store_true", help="Imprime os resultados como JSON.")
    return parser.parse_args(argv)


def render_text(results: list[CheckResult]) -> int:
    version = platform.python_version()
    header = f"Verificação do ambiente ML-Agents, Python {version}, "
    header += f"{platform.system()} {platform.machine()}"
    print(header)
    for result in results:
        print(f"[{result.status}]".ljust(8) + result.detail)
    ok = sum(1 for r in results if r.status == "OK")
    aviso = sum(1 for r in results if r.status == "AVISO")
    falha = sum(1 for r in results if r.status == "FALHA")
    print(f"Resumo: {ok} OK, {aviso} AVISO, {falha} FALHA")
    if falha:
        print("Consulte docs/00-instalacao.md para corrigir os problemas acima.")
        return 1
    return 0


def render_json(results: list[CheckResult]) -> int:
    payload = [dataclasses.asdict(result) for result in results]
    print(json.dumps(payload, indent=2, ensure_ascii=False))
    return 1 if any(result.status == "FALHA" for result in results) else 0


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    results = run_all_checks()
    if args.json:
        return render_json(results)
    return render_text(results)


if __name__ == "__main__":
    sys.exit(main())
