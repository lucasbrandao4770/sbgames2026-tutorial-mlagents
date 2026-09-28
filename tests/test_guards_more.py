"""T6g: permanent proof for the guards added to tests/conftest.py after review G1-T.

G1-T-6: native file dialogs (tkinter.filedialog, which on_browse_build uses) and the
wm_deiconify()/wm_state("normal") ways of showing a window are blocked.
G1-T-5: a guard violation raised inside an app thread fails the test that started the
thread, because _guard_teardown joins that thread while the guards still apply.

Nothing here can reach the screen even if a guard were missing: Tcl's native dialog
commands are replaced by recorders for the dialog tests, and the root's Tcl interpreter
is wrapped by a recorder that swallows every "wm" call for the window tests.
"""

from __future__ import annotations

import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from pathlib import Path
from tkinter import filedialog

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app
import conftest

_REAL_POPEN_INIT = subprocess.Popen.__init__
_NATIVE_DIALOG_COMMANDS = ("tk_getOpenFile", "tk_getSaveFile", "tk_chooseDirectory")


# ----------------------------------------------------------------------------
# G1-T-6: native file dialogs
# ----------------------------------------------------------------------------


@pytest.fixture
def native_dialog_recorder(tk_root: tk.Tk) -> Iterator[Callable[[], str]]:
    """Replace Tcl's native dialog commands by a recorder for one test, then restore them.

    Yields a function that returns what the recorder saw ("" if nothing reached Tcl).
    """
    interp = tk_root.tk
    saved: list[str] = []
    for command in _NATIVE_DIALOG_COMMANDS:
        if interp.call("info", "commands", f"::{command}"):
            interp.call("rename", f"::{command}", f"::t6g_saved_{command}")
            saved.append(command)
        interp.eval(f'proc ::{command} {{args}} {{ lappend ::t6g_calls {command}; return "" }}')
    interp.eval("set ::t6g_calls {}")
    try:
        yield lambda: str(interp.eval("set ::t6g_calls"))
    finally:
        for command in _NATIVE_DIALOG_COMMANDS:
            interp.call("rename", f"::{command}", "")
        for command in saved:
            interp.call("rename", f"::t6g_saved_{command}", f"::{command}")
        interp.eval("unset -nocomplain ::t6g_calls")


def test_g1t6_procurar_cannot_open_the_native_file_dialog(
    tk_root: tk.Tk, tmp_path: Path, native_dialog_recorder: Callable[[], str]
) -> None:
    """G1-T-6: the app's Procurar... handler, on_browse_build, reaches the dialog guard
    before Tcl's native file dialog.
    """
    gui = app.CentralDeTreinoApp(tk_root, repo_root=tmp_path)
    try:
        with conftest.expect_violation("dialog-guard"):
            gui.on_browse_build()
        assert native_dialog_recorder() == ""
    finally:
        gui.container.destroy()


@pytest.mark.parametrize(
    "ask",
    [
        filedialog.askopenfilename,
        filedialog.askopenfilenames,
        filedialog.asksaveasfilename,
        filedialog.askdirectory,
    ],
    ids=lambda ask: ask.__name__,
)
def test_g1t6_every_filedialog_function_is_blocked(
    tk_root: tk.Tk, native_dialog_recorder: Callable[[], str], ask: Callable[..., object]
) -> None:
    """G1-T-6: every tkinter.filedialog function is blocked, not only the one the app uses."""
    with conftest.expect_violation("dialog-guard"):
        ask(parent=tk_root)
    assert native_dialog_recorder() == ""


# ----------------------------------------------------------------------------
# G1-T-6: wm_deiconify() and wm_state("normal")
# ----------------------------------------------------------------------------


class _WmRecorder:
    """Stands in for root.tk: records every "wm" call instead of running it."""

    def __init__(self, real: object) -> None:
        self._real = real
        self.wm_calls: list[tuple[object, ...]] = []

    def call(self, *args: object) -> object:
        if args[:1] == ("wm",):
            self.wm_calls.append(args)
            return ""
        return self._real.call(*args)  # type: ignore[attr-defined]

    def __getattr__(self, name: str) -> object:
        return getattr(self._real, name)


@pytest.mark.parametrize(
    "show",
    [
        lambda root: tk.Wm.wm_deiconify(root),
        lambda root: root.wm_deiconify(),
        lambda root: root.deiconify(),
        lambda root: root.wm_state("normal"),
        lambda root: root.state("normal"),
        lambda root: root.wm_state("zoomed"),
    ],
    ids=["Wm.wm_deiconify", "wm_deiconify", "deiconify", "wm_state", "state", "zoomed"],
)
def test_g1t6_window_guard_blocks_every_way_to_show_the_root(
    tk_root: tk.Tk, monkeypatch: pytest.MonkeyPatch, show: Callable[[tk.Tk], object]
) -> None:
    """G1-T-6: wm_deiconify() and wm_state("normal") fail like deiconify() already did."""
    recorder = _WmRecorder(tk_root.tk)
    monkeypatch.setattr(tk_root, "tk", recorder)
    with conftest.expect_violation("window-guard"):
        show(tk_root)
    assert recorder.wm_calls == []


def test_g1t6_window_guard_still_lets_the_state_be_read(tk_root: tk.Tk) -> None:
    """G1-T-6: reading the state, or withdrawing, is not a violation."""
    assert tk_root.wm_state() == "withdrawn"
    assert tk_root.state() == "withdrawn"
    tk_root.wm_state("withdrawn")
    assert conftest._GUARD_VIOLATIONS == []


# ----------------------------------------------------------------------------
# G1-T-5: a violation inside an app thread fails the test that started it
# ----------------------------------------------------------------------------


def test_g1t5_violation_in_an_app_thread_is_recorded_once_its_thread_is_joined(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G1-T-5: on_verify_env's worker thread trips the process guard; the teardown join
    step waits for it, so the violation is recorded for this test.
    """
    died_of: list[type[BaseException]] = []
    monkeypatch.setattr(threading, "excepthook", lambda args: died_of.append(args.exc_type))
    gui = app.CentralDeTreinoApp(tk_root, repo_root=tmp_path, python_bin=Path(sys.executable))
    start = len(conftest._GUARD_VIOLATIONS)
    before = set(threading.enumerate())
    try:
        gui.on_verify_env()  # runs `python scripts/verify_env.py` in a thread
        conftest._join_threads_started_since(before, conftest.THREAD_JOIN_TIMEOUT_S)
        found = conftest._GUARD_VIOLATIONS[start:]
        assert len(found) == 1
        assert found[0].startswith("process-guard") and "verify_env.py" in found[0]
        assert died_of == [conftest.GuardViolation]
    finally:
        del conftest._GUARD_VIOLATIONS[start:]  # proven above: not this test's failure
        gui.container.destroy()


_LATE_THREAD_NAME = "t6g-late-thread"
_LATE_THREAD_SAW: list[tuple[str, bool]] = []
_LATE_THREAD_STARTED: list[bool] = []


def test_g1t5_a_starts_a_thread_that_outlives_the_test_body() -> None:
    """G1-T-5 (1 of 2): starts a thread that acts 0.2 s after this test body returned.

    test_g1t5_b_..., right below, checks where and how that thread ran.
    """
    _LATE_THREAD_SAW.clear()
    _LATE_THREAD_STARTED.append(True)

    def _late() -> None:
        time.sleep(0.2)
        guarded = subprocess.Popen.__init__ is not _REAL_POPEN_INIT
        _LATE_THREAD_SAW.append((os.environ.get("PYTEST_CURRENT_TEST", ""), guarded))

    threading.Thread(target=_late, name=_LATE_THREAD_NAME, daemon=True).start()


def test_g1t5_b_the_thread_ran_inside_its_own_tests_teardown_under_the_guards() -> None:
    """G1-T-5 (2 of 2): the previous test's thread was joined in that test's teardown,
    while the guards still applied, and is gone before this test starts.
    """
    if not _LATE_THREAD_STARTED:
        pytest.skip("runs only right after test_g1t5_a_starts_a_thread_that_outlives_the_test_body")
    assert not [t for t in threading.enumerate() if t.name == _LATE_THREAD_NAME]
    assert len(_LATE_THREAD_SAW) == 1
    phase, guarded = _LATE_THREAD_SAW[0]
    assert phase.endswith("::test_g1t5_a_starts_a_thread_that_outlives_the_test_body (teardown)")
    assert guarded, "the thread ran after monkeypatch had removed the guards"
