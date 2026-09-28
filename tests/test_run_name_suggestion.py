"""The alternative run name suggested on a conflict never takes a name the tutorial reserves."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "central_de_treino.py"


def _load_app():
    name = "central_de_treino_for_run_name_tests"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    (tmp_path / "results").mkdir()
    return tmp_path


def _make_run(repo: Path, name: str) -> None:
    (repo / "results" / name).mkdir()


def test_suggestion_after_ppo1_skips_the_module_3_name(repo: Path) -> None:
    app = _load_app()
    _make_run(repo, "ppo1")
    assert app.next_available_run_name(repo, "ppo1") == "ppo3"


def test_suggestion_after_il1_skips_the_other_imitation_runs(repo: Path) -> None:
    app = _load_app()
    _make_run(repo, "il1")
    assert app.next_available_run_name(repo, "il1") == "il4"


def test_suggestion_skips_names_that_already_exist(repo: Path) -> None:
    app = _load_app()
    for name in ("ppo1", "ppo3", "ppo4"):
        _make_run(repo, name)
    assert app.next_available_run_name(repo, "ppo1") == "ppo5"


def test_suggestion_for_a_name_without_digits(repo: Path) -> None:
    app = _load_app()
    _make_run(repo, "meu_treino")
    assert app.next_available_run_name(repo, "meu_treino") == "meu_treino2"


def test_suggestion_is_never_a_default_name_of_the_tutorial(repo: Path) -> None:
    app = _load_app()
    reserved = {name for name, _ in app.DOC_DEFAULT_RUN_SETTINGS.values()} | set(
        app.RESERVED_RUN_NAMES
    )
    for start in sorted(reserved):
        _make_run(repo, start)
        assert app.next_available_run_name(repo, start) not in reserved
