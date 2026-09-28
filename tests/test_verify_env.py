"""T9c: the button "Verificar instalação", pressed through the widget itself.

Every test presses the real button with invoke() on the shared withdrawn root. The app runs
a stand-in (tests/standin_T9c_*.py) instead of scripts/verify_env.py: only
resolve_for_execution is replaced, so the command shown in the log area stays the one the
guides teach. The ids T9c-1 to T9c-6 are the numbered problems of the T9c brief.

The tests for the FALHA, the bad byte and the start failure run the app's worker thread
inline (as tests/test_wiring.py does for the TensorBoard probe), so the problem each one
covers shows up even on code whose worker cannot reach the Tk thread under update().
"""

from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app
import conftest
import standin_T9c_falha
import standin_T9c_good

TESTS_DIR = Path(__file__).resolve().parent
STANDIN_GOOD = TESTS_DIR / "standin_T9c_good.py"
STANDIN_FALHA = TESTS_DIR / "standin_T9c_falha.py"
STANDIN_SLOW = TESTS_DIR / "standin_T9c_slow.py"
STANDIN_BAD_BYTES = TESTS_DIR / "standin_T9c_bad_bytes.py"
COMMAND_LINE = "$ python scripts/verify_env.py"
RESUMO_OK = "Resumo: 13 OK, 0 AVISO, 0 FALHA"
STATUS_MAX_CHARS = 110


class _InlineThread:
    """Runs the target at start(), on the calling (Tk) thread."""

    def __init__(
        self,
        target: Callable[..., None],
        args: tuple[object, ...] = (),
        daemon: bool | None = None,
        **_kwargs: object,
    ) -> None:
        del daemon
        self._target = target
        self._args = args

    def start(self) -> None:
        self._target(*self._args)


def _buttons(widget: tk.Misc) -> list[ttk.Button]:
    found: list[ttk.Button] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            found.append(child)
        found.extend(_buttons(child))
    return found


def _verify_button(gui: app.CentralDeTreinoApp) -> ttk.Button:
    """The button the attendee clicks, found by its label."""
    found = [b for b in _buttons(gui.container) if str(b.cget("text")) == "Verificar instalação"]
    assert len(found) == 1
    return found[0]


def _log_lines(gui: app.CentralDeTreinoApp) -> list[str]:
    return gui.log_text.get("1.0", "end").rstrip("\n").split("\n")


def _pump_until(root: tk.Tk, condition: Callable[[], bool], timeout: float) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        root.update()
        if condition():
            return True
        time.sleep(0.02)
    root.update()
    return condition()


def _use_standin(monkeypatch: pytest.MonkeyPatch, script: Path) -> None:
    monkeypatch.setattr(app, "resolve_for_execution", lambda *_args: [sys.executable, str(script)])


def _build(root: tk.Tk, repo_root: Path) -> app.CentralDeTreinoApp:
    return app.CentralDeTreinoApp(root, repo_root=repo_root, python_bin=Path(sys.executable))


def _cleanup(gui: app.CentralDeTreinoApp) -> None:
    """Never leave a stand-in behind, even when the test failed."""
    for proc in list(conftest._LIVE_PROCESSES):
        if proc.poll() is None:
            proc.kill()
            proc.wait(timeout=5)
    job = getattr(gui, "_verify_job", None)
    if job is not None:
        gui.root.after_cancel(job)
    gui.container.destroy()


def test_click_disables_the_button_and_says_at_once_that_the_check_runs(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-1, T9c-2: right after the click the button is disabled and the log and the status
    line say that the check runs; a second click meanwhile starts nothing.
    """
    _use_standin(monkeypatch, STANDIN_GOOD)
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        assert button.instate(["disabled"]), "the button stays enabled while the check runs"
        lines = _log_lines(gui)
        assert lines[-2] == COMMAND_LINE
        assert lines[-1].startswith("Verificando a instalação") and "minuto" in lines[-1]
        assert gui.status_var.get().startswith("Verificando a instalação")
        button.invoke()
        assert _pump_until(tk_root, lambda: button.instate(["!disabled"]), 20)
        lines = _log_lines(gui)
        assert lines.count(COMMAND_LINE) == 1
        assert lines.count(RESUMO_OK) == 1
    finally:
        _cleanup(gui)


def test_good_check_ends_the_log_with_the_script_output_and_shows_the_summary(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-5, T9c-6: the output reaches the log area through the Tk thread exactly as the
    script printed it, its Resumo line last, and the status line shows the Resumo line.
    """
    _use_standin(monkeypatch, STANDIN_GOOD)
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        arrived = _pump_until(
            tk_root,
            lambda: RESUMO_OK in _log_lines(gui) and button.instate(["!disabled"]),
            20,
        )
        assert arrived, "the check's output never reached the log area"
        lines = _log_lines(gui)
        assert lines[-len(standin_T9c_good.LINES) :] == standin_T9c_good.LINES
        assert lines[-1] == RESUMO_OK
        assert gui.status_var.get() == RESUMO_OK
    finally:
        _cleanup(gui)


def test_failing_check_keeps_the_script_lines_last_and_asks_for_an_instructor(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-6: with a FALHA (exit code 1) the log area ends with the script's own lines and
    the status line says that the check found a failure and to call an instructor.
    """
    _use_standin(monkeypatch, STANDIN_FALHA)
    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=_InlineThread))
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        last = standin_T9c_falha.LINES[-1]
        assert _pump_until(tk_root, lambda: _log_lines(gui)[-1] == last, 5)
        assert button.instate(["!disabled"])
        assert _log_lines(gui)[-len(standin_T9c_falha.LINES) :] == standin_T9c_falha.LINES
        status = gui.status_var.get()
        assert "falha" in status.lower() and "instrutor" in status, status
        assert len(status) <= STATUS_MAX_CHARS
    finally:
        _cleanup(gui)


def test_check_that_takes_too_long_is_stopped_with_a_pt_br_message(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-3: past the limit the check is stopped, the log area and the status line say in
    PT-BR that it took too long, to click once more and to call an instructor if it repeats,
    and the button comes back.
    """
    monkeypatch.setattr(app, "VERIFY_ENV_TIMEOUT_S", 1.0, raising=False)
    _use_standin(monkeypatch, STANDIN_SLOW)
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        stopped = _pump_until(
            tk_root,
            lambda: button.instate(["!disabled"]) and "demorou" in _log_lines(gui)[-1],
            12,
        )
        assert stopped, f"no PT-BR timeout message, log ends with {_log_lines(gui)[-1]!r}"
        message = _log_lines(gui)[-1]
        assert "mais uma vez" in message and "instrutor" in message
        assert gui.status_var.get() == message
        assert len(message) <= STATUS_MAX_CHARS
        assert all(proc.poll() is not None for proc in conftest._LIVE_PROCESSES)
    finally:
        _cleanup(gui)


def test_undecodable_byte_is_replaced_not_raised(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-4: a byte that cannot be decoded is replaced; the rest of the output still shows."""
    _use_standin(monkeypatch, STANDIN_BAD_BYTES)
    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=_InlineThread))
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        _pump_until(tk_root, lambda: RESUMO_OK in _log_lines(gui), 5)
        lines = _log_lines(gui)
        assert lines[-1] == RESUMO_OK, f"log ends with {lines[-1]!r}"
        assert lines[-2].startswith("[OK]    byte ruim: ") and "�" in lines[-2]
        assert button.instate(["!disabled"])
    finally:
        _cleanup(gui)


def test_check_that_cannot_start_says_what_to_do_and_gives_the_button_back(
    tk_root: tk.Tk, repo_root: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-1: when the check cannot be started at all, the log area gets a PT-BR line that
    says what to do, and the button is enabled again.
    """
    missing = tmp_path / "sem-python" / "python"
    monkeypatch.setattr(
        app, "resolve_for_execution", lambda *_args: [str(missing), str(STANDIN_GOOD)]
    )
    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=_InlineThread))
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    try:
        button.invoke()
        _pump_until(tk_root, lambda: len(_log_lines(gui)) > 2, 5)
        lines = _log_lines(gui)
        assert any(
            line.startswith("Não consegui iniciar a verificação") and "instrutor" in line
            for line in lines
        ), lines
        assert button.instate(["!disabled"])
    finally:
        _cleanup(gui)


def test_closing_the_window_during_the_check_stops_its_process(
    tk_root: tk.Tk, repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """T9c-5: the window's close button, pressed while the check runs, raises nothing and
    leaves no process behind.
    """
    destroyed: list[bool] = []
    errors: list[object] = []
    monkeypatch.setattr(tk_root, "destroy", lambda: destroyed.append(True))
    monkeypatch.setattr(tk_root, "report_callback_exception", lambda *a: errors.append(a))
    _use_standin(monkeypatch, STANDIN_SLOW)
    gui = _build(tk_root, repo_root)
    button = _verify_button(gui)
    close_command = ""
    try:
        button.invoke()
        assert _pump_until(
            tk_root, lambda: any(p.poll() is None for p in conftest._LIVE_PROCESSES), 10
        )
        proc = next(p for p in conftest._LIVE_PROCESSES if p.poll() is None)
        tk_root.protocol("WM_DELETE_WINDOW", gui.on_close)
        close_command = str(tk_root.protocol("WM_DELETE_WINDOW"))
        tk_root.tk.call(close_command)
        assert destroyed == [True]
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pytest.fail("closing the window left the check's process running")
        tk_root.update()
        assert errors == []
    finally:
        tk_root.protocol("WM_DELETE_WINDOW", "")
        if close_command:
            tk_root.deletecommand(close_command)
        _cleanup(gui)
