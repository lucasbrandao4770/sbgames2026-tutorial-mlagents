"""The alternative run name suggested on a conflict never takes a name the tutorial reserves."""

from __future__ import annotations

import importlib.util
import os
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


def test_suggestion_after_ppo1_is_ppo1_plus_a_letter(repo: Path) -> None:
    """G1-U-4: ppo1 is followed by ppo1b, which the slides' filter ppo1|ppo2 still matches."""
    app = _load_app()
    _make_run(repo, "ppo1")
    assert app.next_available_run_name(repo, "ppo1") == "ppo1b"


def test_suggestion_after_il1_is_il1_plus_a_letter(repo: Path) -> None:
    """G1-U-4: il1 is followed by il1b, never by il2 or il3, the other imitation runs."""
    app = _load_app()
    _make_run(repo, "il1")
    assert app.next_available_run_name(repo, "il1") == "il1b"


def test_suggestion_skips_names_that_already_exist(repo: Path) -> None:
    """G1-U-4: the letters go on past every name already in results/."""
    app = _load_app()
    for name in ("ppo1", "ppo1b", "ppo1c"):
        _make_run(repo, name)
    assert app.next_available_run_name(repo, "ppo1") == "ppo1d"


def test_suggestion_for_a_lettered_name_goes_on_from_its_base(repo: Path) -> None:
    """G1-U-4: a conflict on ppo1b suggests ppo1c, not ppo1bb."""
    app = _load_app()
    for name in ("ppo1", "ppo1b"):
        _make_run(repo, name)
    assert app.next_available_run_name(repo, "ppo1b") == "ppo1c"


def test_suggestion_for_a_name_without_digits(repo: Path) -> None:
    """G1-U-4: a name of the attendee's own gets a letter too."""
    app = _load_app()
    _make_run(repo, "meu_treino")
    assert app.next_available_run_name(repo, "meu_treino") == "meu_treinob"


def test_an_existing_run_is_found_in_any_letter_case(
    repo: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G1-W-5: Windows folders ignore letter case, so with results/ppo1 in place "PPO1"
    already exists, even on a file system that tells the two apart (simulated here by an
    is_dir that matches the exact name only)."""
    app = _load_app()
    _make_run(repo, "ppo1")
    results = repo / "results"
    real_is_dir = Path.is_dir

    def _case_sensitive_is_dir(self: Path) -> bool:
        if self.parent == results:
            return self.name in os.listdir(results) and real_is_dir(self)
        return real_is_dir(self)

    monkeypatch.setattr(Path, "is_dir", _case_sensitive_is_dir)
    assert app.run_exists(repo, "PPO1") is True
    assert app.run_exists(repo, "ppo1") is True
    assert app.run_exists(repo, "ppo2") is False
    assert app.next_available_run_name(repo, "PPO1") not in {"PPO1", "ppo1"}


def test_suggestion_is_never_a_default_name_of_the_tutorial(repo: Path) -> None:
    """G1-U-4: no suggestion is a run name the tutorial gives to its own steps."""
    app = _load_app()
    reserved = {name for name, _ in app.DOC_DEFAULT_RUN_SETTINGS.values()} | set(
        app.RESERVED_RUN_NAMES
    )
    for start in sorted(reserved):
        _make_run(repo, start)
        assert app.next_available_run_name(repo, start) not in reserved
