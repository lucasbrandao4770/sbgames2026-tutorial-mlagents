"""Permanent proof for every autouse safety guard defined in tests/conftest.py.

T4: test hygiene and safety guards (see local_files/build/launcher/agent_rules.md
and finding m25 in local_files/build/launcher/review_launcher.md). Each test below
calls the exact function/method a guard patches and asserts conftest.py's
GuardViolation fires with that guard's name in the message, via
conftest.expect_violation. None of these tests really opens a window, a browser
tab or a socket: every guarded call here is intercepted before the real
implementation ever runs (see each guard's docstring in conftest.py), so nothing
observable happens on screen or on the network.

Docstrings below name the guard they prove instead of a review finding id
(agent_rules.md's "every docstring starts with the finding id it covers" is about
tests covering the review's B/M/m findings; these tests instead cover this task's
own brief, step 6).
"""

from __future__ import annotations

import socket
import subprocess
import sys
import tkinter as tk
import webbrowser
from pathlib import Path

import conftest

FAKE_TRAINER = Path(__file__).resolve().parent / "fake_trainer.py"


# ----------------------------------------------------------------------------
# window-guard
# ----------------------------------------------------------------------------


def test_window_guard_blocks_deiconify(tk_root: tk.Tk) -> None:
    """window-guard: deiconify()/wm_deiconify() on any Tk root or Toplevel fails
    the test immediately instead of letting the window become viewable.
    """
    dialog = tk.Toplevel(tk_root)
    try:
        with conftest.expect_violation("window-guard"):
            dialog.deiconify()
    finally:
        dialog.destroy()


def test_window_guard_blocks_wait_visibility(tk_root: tk.Tk) -> None:
    """window-guard: wait_visibility() - the call scripts/central_de_treino.py's
    own dialogs use to pump the loop until mapped - fails immediately too, so it
    can never actually block waiting for (or produce) a real mapped window.
    """
    dialog = tk.Toplevel(tk_root)
    try:
        with conftest.expect_violation("window-guard"):
            dialog.wait_visibility()
    finally:
        dialog.destroy()


# ----------------------------------------------------------------------------
# browser-guard
# ----------------------------------------------------------------------------


def test_browser_guard_blocks_webbrowser_open() -> None:
    """browser-guard: webbrowser.open() never reaches the real implementation,
    so no browser tab can open.
    """
    with conftest.expect_violation("browser-guard"):
        webbrowser.open("http://localhost:6006")


# ----------------------------------------------------------------------------
# socket-guard
# ----------------------------------------------------------------------------


def test_socket_guard_blocks_connect() -> None:
    """socket-guard: socket.connect() fails before any real connect() syscall."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with conftest.expect_violation("socket-guard"):
            sock.connect(("127.0.0.1", 6006))
    finally:
        sock.close()


def test_socket_guard_blocks_bind() -> None:
    """socket-guard: socket.bind() fails before any real bind() syscall."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        with conftest.expect_violation("socket-guard"):
            sock.bind(("127.0.0.1", 0))
    finally:
        sock.close()


def test_socket_guard_blocks_create_connection() -> None:
    """socket-guard: socket.create_connection() - what is_tensorboard_up() and
    urllib both end up calling - fails before it can reach the network.
    """
    with conftest.expect_violation("socket-guard"):
        socket.create_connection(("127.0.0.1", 6006), timeout=0.1)


# ----------------------------------------------------------------------------
# process-guard (the start-time allowlist)
# ----------------------------------------------------------------------------


def test_process_guard_blocks_disallowed_program() -> None:
    """process-guard: a program that is neither `ps` nor sys.executable running a
    tests/ file is refused before subprocess.Popen's real __init__ ever runs, so
    it never actually starts.
    """
    with conftest.expect_violation("process-guard"):
        subprocess.Popen(["echo", "a-program-outside-the-allowlist"])


def test_process_guard_allows_ps() -> None:
    """process-guard: `ps` itself is on the allowlist (used by
    _posix_descendants to find a trainer's game-window child).
    """
    assert conftest._is_allowed_process(["ps", "-A", "-o", "pid=,ppid="]) is True


def test_process_guard_allows_sys_executable_on_a_tests_file() -> None:
    """process-guard: sys.executable running a file inside tests/ - the shape
    every fake-trainer-backed test in test_central_de_treino.py relies on - is
    allowed.
    """
    assert conftest._is_allowed_process([sys.executable, str(FAKE_TRAINER)]) is True


def test_process_guard_rejects_sys_executable_on_a_non_tests_file() -> None:
    """process-guard: sys.executable running something outside tests/ (e.g.
    on_verify_env's real scripts/verify_env.py) is not on the allowlist.
    """
    outside = Path(__file__).resolve().parent.parent / "scripts" / "verify_env.py"
    assert conftest._is_allowed_process([sys.executable, str(outside)]) is False


# ----------------------------------------------------------------------------
# leftover-process-guard (teardown-only: test the checking function directly)
# ----------------------------------------------------------------------------


class _FakePopen:
    """A minimal stand-in for subprocess.Popen's poll()/pid surface."""

    def __init__(self, *, running: bool, pid: int = 4242) -> None:
        self.pid = pid
        self._running = running

    def poll(self) -> int | None:
        return None if self._running else 0


def test_leftover_process_guard_detects_running_child() -> None:
    """leftover-process-guard: a process still running (poll() is None) at
    teardown is a violation. Calls the checking function directly, per the
    brief's instruction for teardown-only guards, with a fake Popen so no real
    process is ever started to prove it.
    """
    with conftest.expect_violation("leftover-process-guard"):
        conftest._check_no_leftover_processes([_FakePopen(running=True)])


def test_leftover_process_guard_allows_a_finished_child() -> None:
    """leftover-process-guard: a process that already exited (poll() returns an
    int) is not a violation - this is the normal case for every existing test
    that reaps its fake_trainer.py child before returning.
    """
    conftest._check_no_leftover_processes([_FakePopen(running=False)])  # must not raise
    assert conftest._GUARD_VIOLATIONS == []


# ----------------------------------------------------------------------------
# clipboard-guard
# ----------------------------------------------------------------------------


def test_clipboard_guard_blocks_clipboard_clear(tk_root: tk.Tk) -> None:
    """clipboard-guard: clipboard_clear() fails before it can touch the owner's
    real system clipboard.
    """
    with conftest.expect_violation("clipboard-guard"):
        tk_root.clipboard_clear()


def test_clipboard_guard_blocks_clipboard_append(tk_root: tk.Tk) -> None:
    """clipboard-guard: clipboard_append() fails before it can touch the owner's
    real system clipboard.
    """
    with conftest.expect_violation("clipboard-guard"):
        tk_root.clipboard_append("x")
