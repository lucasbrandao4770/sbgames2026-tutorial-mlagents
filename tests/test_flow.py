"""T6a, batch F ("train, then watch"): regression tests for B1, B2, M3 and m14.

Drives scripts/central_de_treino.py's real methods (the ones the buttons call) on a
withdrawn Tk root, with a fake ManagedProcess injected through the app's own
gui._process_factory test seam instead of a real mlagents-learn subprocess: B1/B2/M3
are about GUI orchestration (when a refresh happens, what a dialog choice does, which
file a preview points at), not about subprocess mechanics, and the fake process makes
the timing of "a training just ended" deterministic instead of racing a real child.
No test starts a real process, maps a window/dialog, or opens a socket.
"""

from __future__ import annotations

import sys
import tkinter as tk
from collections.abc import Callable
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """Stub every tkinter.messagebox call so no test can ever show a real window."""
    calls: list[tuple[str, str, str]] = []

    def _record(kind: str) -> Callable[..., None]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> None:
            calls.append((kind, title, message))

        return _fn

    def _yes(title: str = "", message: str = "", **_kwargs: object) -> bool:
        calls.append(("askyesno", title, message))
        return True

    monkeypatch.setattr(app.messagebox, "showerror", _record("showerror"))
    monkeypatch.setattr(app.messagebox, "showwarning", _record("showwarning"))
    monkeypatch.setattr(app.messagebox, "showinfo", _record("showinfo"))
    monkeypatch.setattr(app.messagebox, "askyesno", _yes)
    return calls


# tk_root comes from tests/conftest.py: one withdrawn Tk root for the whole session.


# ----------------------------------------------------------------------------
# Fake repo and fake process helpers
# ----------------------------------------------------------------------------


def _behavior_config(*, max_steps: int) -> str:
    return (
        "behaviors:\n"
        "  FlappyAgent:\n"
        "    trainer_type: ppo\n"
        f"    max_steps: {max_steps}\n"
        "    hyperparameters:\n"
        "      batch_size: 256\n"
    )


def _repo_with_configs(tmp_path: Path) -> Path:
    """A fake repo with the tutorial's three documented configs, plus a build."""
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "imitation").mkdir(parents=True)
    (root / "python" / "configs" / "desafio").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(
        _behavior_config(max_steps=50000)
    )
    (root / "python" / "configs" / "imitation" / "FlappyBird_run1.yaml").write_text(
        _behavior_config(max_steps=50000)
    )
    (root / "python" / "configs" / "desafio" / "FlappyBird_desafio.yaml").write_text(
        _behavior_config(max_steps=50000)
    )
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    return root


def _stub_python_bin(tmp_path: Path) -> Path:
    """A venv-shaped bin dir that only needs to satisfy resolve_for_execution.

    Never actually run: tests that use this also inject a fake process factory, so
    ManagedProcess never spawns a real child from these placeholder files.
    """
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.touch()
    (bin_dir / "mlagents-learn").touch()
    return python_bin


def _make_run(base: Path, name: str, *, max_steps: int = 50000) -> Path:
    """Create a results-shaped, fully trained run: checkpoint, onnx, configuration.yaml."""
    run_dir = base / name
    behavior_dir = run_dir / "FlappyAgent"
    behavior_dir.mkdir(parents=True)
    (run_dir / "configuration.yaml").write_text(_behavior_config(max_steps=max_steps))
    (run_dir / "FlappyAgent.onnx").touch()
    (behavior_dir / "checkpoint.pt").touch()
    return run_dir


class _FakeProcess:
    """Stand-in for ManagedProcess, injected through gui._process_factory.

    Lets a test drive _launch/_poll_process/_finish_process deterministically: no
    real subprocess, no sleep, is_running() only flips when the test says so.
    """

    def __init__(self) -> None:
        self.graceful_timeout_s = 30.0
        self.running = True
        self._lines: list[str] = [
            "[INFO] Connected to Unity environment with package version 4.1.0"
        ]

    def start(self) -> None:
        return None

    def poll_output(self) -> list[str]:
        lines, self._lines = self._lines, []
        return lines

    def is_running(self) -> bool:
        return self.running

    @property
    def returncode(self) -> int | None:
        return None if self.running else 0

    def finish_reading(self, timeout: float = 2.0) -> list[str]:
        del timeout
        return self.poll_output()

    def request_graceful_stop(self) -> None:
        self.running = False

    def graceful_timeout_elapsed(self) -> bool:
        return False

    def force_kill(self) -> None:
        self.running = False


def _build_app(
    tk_root: tk.Tk, repo_root: Path, python_bin: Path | None = None
) -> app.CentralDeTreinoApp:
    return app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=python_bin)


def _label_for(gui: app.CentralDeTreinoApp, filename: str) -> str:
    return next(label for label, path in gui._config_by_label.items() if path.name == filename)


def _finish_fake_process(
    gui: app.CentralDeTreinoApp, tk_root: tk.Tk, process: _FakeProcess
) -> None:
    """Mark the fake process finished and let the app's own poll loop reap it, now."""
    process.running = False
    if gui._poll_job is not None:
        tk_root.after_cancel(gui._poll_job)
        gui._poll_job = None
    if gui._process is not None:
        gui._poll_process()


# ----------------------------------------------------------------------------
# B1: the Assistir list refreshes after a training ends, on tab switch, and
# keeps whatever the attendee already picked.
# ----------------------------------------------------------------------------


def test_b1_training_run_appears_and_is_preselected_after_it_ends(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """B1: a run trained in this session shows up in Assistir, preselected, no restart."""
    repo_root = _repo_with_configs(tmp_path)
    python_bin = _stub_python_bin(tmp_path)
    gui = _build_app(tk_root, repo_root, python_bin)
    process = _FakeProcess()
    gui._process_factory = lambda args, cwd: process
    gui.run_name_var.set("ppo1")
    tk_root.update()
    try:
        assert gui._runs_by_label == {}
        gui.on_start()
        assert gui._process is process
        _make_run(repo_root / "results", "ppo1")
        _finish_fake_process(gui, tk_root, process)
        assert gui._process is None
        assert "ppo1" in gui._run_combo.cget("values")
        assert gui.watch_run_var.get() == "ppo1"
    finally:
        _finish_fake_process(gui, tk_root, process)
        gui.container.destroy()


def test_b1_showing_assistir_tab_refreshes_the_list(tk_root: tk.Tk, tmp_path: Path) -> None:
    """B1: opening the Assistir tab refreshes the list, not only the end of a run."""
    repo_root = _repo_with_configs(tmp_path)
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        assert gui._runs_by_label == {}
        _make_run(repo_root / "results", "il1")
        gui.notebook.select(1)
        tk_root.update()
        assert "il1" in gui._run_combo.cget("values")
        assert gui.watch_run_var.get() == "il1"
    finally:
        gui.container.destroy()


def test_b1_refresh_keeps_the_choice_the_user_already_made(tk_root: tk.Tk, tmp_path: Path) -> None:
    """B1: a run the attendee already picked survives a later refresh."""
    repo_root = _repo_with_configs(tmp_path)
    _make_run(repo_root / "results", "ppo1")
    _make_run(repo_root / "results", "ppo2")
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        assert gui.watch_run_var.get() == "ppo1"  # sorted first, the initial default
        gui.watch_run_var.set("ppo2")
        gui._refresh_trained_runs()
        assert gui.watch_run_var.get() == "ppo2"
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# B2: config selection applies the documented defaults unless the user typed a
# name, and the conflict dialog's first choice renames instead of only
# resuming/overwriting.
# ----------------------------------------------------------------------------


def test_b2_selecting_each_documented_config_applies_its_own_default(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """B2: choosing a config applies that config's own doc run name and window default."""
    repo_root = _repo_with_configs(tmp_path)
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        cases = [
            ("FlappyBird_ppo.yaml", "ppo1", True),
            ("FlappyBird_run1.yaml", "il1", False),
            ("FlappyBird_desafio.yaml", "ppo2", False),
        ]
        for filename, expected_name, expected_window in cases:
            gui.config_var.set(_label_for(gui, filename))
            gui._on_config_selected()
            assert gui.run_name_var.get() == expected_name
            assert gui.show_window_var.get() is expected_window
    finally:
        gui.container.destroy()


def test_b2_custom_run_name_survives_switching_to_another_config(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """B2: a name the attendee already typed is not clobbered by a later config change."""
    repo_root = _repo_with_configs(tmp_path)
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        gui.config_var.set(_label_for(gui, "FlappyBird_ppo.yaml"))
        gui._on_config_selected()
        assert (gui.run_name_var.get(), gui.show_window_var.get()) == ("ppo1", True)
        gui.run_name_var.set("meu_treino")  # the attendee typed a name by hand
        gui.config_var.set(_label_for(gui, "FlappyBird_desafio.yaml"))
        gui._on_config_selected()
        assert gui.run_name_var.get() == "meu_treino"
        assert gui.show_window_var.get() is True  # desafio's own default (False) must not apply
    finally:
        gui.container.destroy()


def test_b2_conflict_dialogs_first_choice_renames_and_starts_fresh(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """B2: the dialog's first choice renames to a free name and starts clean under it."""
    repo_root = _repo_with_configs(tmp_path)
    python_bin = _stub_python_bin(tmp_path)
    (repo_root / "results" / "ppo1").mkdir()
    gui = _build_app(tk_root, repo_root, python_bin)
    process = _FakeProcess()
    gui._process_factory = lambda args, cwd: process
    expected_name = app.next_available_run_name(repo_root, "ppo1")
    # Stand in for the dialog itself (never mapped - see module docstring), but use
    # the app's own real next_available_run_name, exactly as _ask_run_conflict does,
    # so this test still exercises the production "first choice" computation.
    gui._ask_run_conflict = lambda run_name: (
        "rename",
        app.next_available_run_name(repo_root, run_name),
    )
    gui.run_name_var.set("ppo1")
    tk_root.update()
    try:
        gui.on_start()
        assert gui._process is process
        assert gui.run_name_var.get() == expected_name
        command = gui.command_var.get()
        assert f"--run-id={expected_name}" in command
        assert "--resume" not in command
        assert "--force" not in command
    finally:
        _finish_fake_process(gui, tk_root, process)
        gui.container.destroy()


# ----------------------------------------------------------------------------
# M3: the Assistir preview points at a config file that already exists on
# disk, one file per run, before Iniciar is ever pressed.
# ----------------------------------------------------------------------------


def test_m3_previewed_watch_config_exists_on_disk_before_iniciar(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M3: the config the Assistir preview points to already exists before Iniciar."""
    repo_root = _repo_with_configs(tmp_path)
    _make_run(repo_root / "results", "ppo1")
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        gui.notebook.select(1)
        gui.watch_run_var.set("ppo1")
        gui._on_watch_run_selected()
        tk_root.update()
        run = gui._runs_by_label["ppo1"]
        watch_config = repo_root / gui._watch_config_path(run)
        assert watch_config.is_file()  # exists before Iniciar was ever pressed
        expected = app.build_watch_command(
            repo_root=repo_root,
            watch_config=watch_config,
            build=gui._build_path,
            trained_run_id="ppo1",
        )
        assert gui.command_var.get() == app.format_command_for_display(expected)
    finally:
        gui.container.destroy()


def test_m3_each_run_gets_its_own_watch_config_file(tk_root: tk.Tk, tmp_path: Path) -> None:
    """M3: one watch config file per run, not a single file overwritten by the last watch."""
    repo_root = _repo_with_configs(tmp_path)
    _make_run(repo_root / "results", "ppo1", max_steps=50000)
    _make_run(repo_root / "results", "il1", max_steps=999999)
    gui = _build_app(tk_root, repo_root)
    tk_root.update()
    try:
        run_a = gui._runs_by_label["ppo1"]
        run_b = gui._runs_by_label["il1"]
        path_a = repo_root / gui._watch_config_path(run_a)
        path_b = repo_root / gui._watch_config_path(run_b)
        assert path_a != path_b
        assert path_a.is_file()
        assert path_b.is_file()
        content_a = yaml.safe_load(path_a.read_text())
        content_b = yaml.safe_load(path_b.read_text())
        assert content_a["behaviors"]["FlappyAgent"]["max_steps"] == 50000
        assert content_b["behaviors"]["FlappyAgent"]["max_steps"] == 999999
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# m14 (OPEN): Basic_ppo.yaml, an Editor-only config, must not be offered.
# ----------------------------------------------------------------------------


def test_m14_treinar_config_list_excludes_basic_ppo(tk_root: tk.Tk, tmp_path: Path) -> None:
    """m14: Basic_ppo.yaml (an Editor-only config, behavior "Basic") must not be offered."""
    repo_root = _repo_with_configs(tmp_path)
    (repo_root / "python" / "configs" / "ppo" / "Basic_ppo.yaml").write_text(
        "behaviors:\n  Basic:\n    trainer_type: ppo\n    max_steps: 500000\n"
    )
    gui = _build_app(tk_root, repo_root)
    try:
        offered = {path.name for path in gui._config_by_label.values()}
        assert "Basic_ppo.yaml" not in offered
    finally:
        gui.container.destroy()
