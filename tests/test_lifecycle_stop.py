"""Regression tests for the forced stop (M4) and for closing the window (M5).

Both findings are about process lifecycles, so every test here runs real stand-in
processes (tests/standin_T6b2_*.py, started with sys.executable) and waits on them only
up to a deadline. Every process a test starts carries a tag unique to that test in its
command line; the cleanup kills whatever still carries the tag and reaps what the app
started, so a failing test never leaves a process behind. Tk windows stay withdrawn and
every messagebox is stubbed.
"""

from __future__ import annotations

import contextlib
import os
import signal
import subprocess
import sys
import time
import tkinter as tk
import uuid
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

TESTS_DIR = Path(__file__).resolve().parent
TRAINER_WITH_GAME = TESTS_DIR / "standin_T6b2_trainer_with_game.py"
SLOW_STOP_TRAINER = TESTS_DIR / "standin_T6b2_slow_stop.py"

# The slow-stop stand-in needs STOP_DELAY_S to finish its graceful stop (a real run's
# final export), so a close handler that waits for it cannot return within
# CLOSE_RETURNS_WITHIN_S.
STOP_DELAY_S = 1.5
CLOSE_RETURNS_WITHIN_S = 0.5

_PPO_CONFIG = "behaviors:\n  FlappyAgent:\n    trainer_type: ppo\n    max_steps: 50000\n"

# POSIX sessions and process groups; on Windows the app would also open a console.
pytestmark = pytest.mark.skipif(os.name == "nt", reason="POSIX process lifecycle tests")


# ----------------------------------------------------------------------------
# Process helpers
# ----------------------------------------------------------------------------


def _new_tag() -> str:
    """A token unique to one test, put in the command line of every process it starts."""
    return f"T6b2-{uuid.uuid4().hex[:12]}"


def _pids_with_tag(tag: str) -> list[int]:
    """PIDs of the live (non-zombie) processes whose command line contains tag, via ps."""
    listing = subprocess.run(
        ["ps", "-A", "-o", "pid=,stat=,command="], capture_output=True, text=True, check=False
    )
    pids: list[int] = []
    for line in listing.stdout.splitlines():
        fields = line.split(None, 2)
        if len(fields) == 3 and tag in fields[2] and not fields[1].startswith("Z"):
            pids.append(int(fields[0]))
    return pids


def _alive(pid: int, tag: str) -> bool:
    """True while pid is a live, tagged process (a zombie counts as dead)."""
    return pid in _pids_with_tag(tag)


def _kill_and_reap(tag: str, process: app.ManagedProcess | None) -> None:
    """Kill every live process carrying tag, reap the one the app started, wait for the rest.

    Grandchildren are reaped by init once their parent is gone, so for them this only
    waits (bounded) until ps no longer lists them.
    """
    for pid in _pids_with_tag(tag):
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGKILL)
    popen = None if process is None else process._proc  # cleanup only, never asserted on
    if process is not None and popen is not None:
        with contextlib.suppress(OSError):
            popen.kill()
        popen.wait(timeout=5)
        process.finish_reading(timeout=2)
    deadline = time.monotonic() + 5
    while _pids_with_tag(tag) and time.monotonic() < deadline:
        time.sleep(0.02)


# ----------------------------------------------------------------------------
# M4: the forced stop also kills the game, which leads its own session
# ----------------------------------------------------------------------------


def _start_trainer_with_game(
    tmp_path: Path, tag: str, *, game_ignores_sigterm: bool
) -> app.ManagedProcess:
    args = [sys.executable, str(TRAINER_WITH_GAME), f"--tag={tag}"]
    if game_ignores_sigterm:
        args.append("--game-ignores-sigterm")
    process = app.ManagedProcess(args, tmp_path, python_bin=Path(sys.executable))
    process.start()
    return process


def _read_reported_pids(process: app.ManagedProcess, timeout_s: float = 5.0) -> dict[str, int]:
    """Collect the TRAINER_PID=... and GAME_PID=... lines the stand-in prints."""
    reported: dict[str, int] = {}
    seen: list[str] = []
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline and len(reported) < 2:
        for line in process.poll_output():
            seen.append(line)
            key, sep, value = line.partition("=")
            if sep and key in ("TRAINER_PID", "GAME_PID"):
                reported[key] = int(value)
        time.sleep(0.02)
    assert len(reported) == 2, f"the stand-in did not report both pids in time: {seen}"
    return reported


@pytest.mark.parametrize(
    "game_ignores_sigterm", [False, True], ids=["game", "game_ignores_sigterm"]
)
def test_force_kill_also_kills_the_game_in_its_own_session(
    tmp_path: Path, game_ignores_sigterm: bool
) -> None:
    """M4: the forced stop kills the trainer AND the game it started in its own session.

    mlagents starts the player with start_new_session=True, so a kill of the trainer's
    process group never reaches it. The stand-in game does the same. In the second
    variant it also ignores SIGTERM, like a hung player, so only SIGKILL removes it.
    """
    tag = _new_tag()
    process = _start_trainer_with_game(tmp_path, tag, game_ignores_sigterm=game_ignores_sigterm)
    try:
        pids = _read_reported_pids(process)
        trainer_pid, game_pid = pids["TRAINER_PID"], pids["GAME_PID"]
        # Preconditions: the game is alive and outside the trainer's process group.
        assert _alive(game_pid, tag)
        assert os.getpgid(game_pid) != os.getpgid(trainer_pid)
        if game_ignores_sigterm:
            os.kill(game_pid, signal.SIGTERM)
            assert _alive(game_pid, tag), "the stand-in game must survive SIGTERM"

        process.force_kill()

        deadline = time.monotonic() + 3
        while time.monotonic() < deadline and (process.is_running() or _alive(game_pid, tag)):
            time.sleep(0.05)
        assert not process.is_running(), "the trainer survived the forced stop"
        assert not _alive(game_pid, tag), "the game survived the forced stop"
    finally:
        _kill_and_reap(tag, process)


# ----------------------------------------------------------------------------
# M5: closing the window while a process runs
# ----------------------------------------------------------------------------


@dataclass
class DialogStub:
    """Records every messagebox call; every ask* call answers `answer`."""

    answer: bool = True
    asked: list[str] = field(default_factory=list)
    shown: list[str] = field(default_factory=list)


@pytest.fixture
def dialogs(monkeypatch: pytest.MonkeyPatch) -> DialogStub:
    """Stub the messagebox module the app uses, so no dialog is ever shown."""
    stub = DialogStub()

    def _ask(kind: str) -> Callable[..., object]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> object:
            stub.asked.append(f"{kind}: {message}")
            if kind == "askquestion":
                return "yes" if stub.answer else "no"
            return stub.answer

        return _fn

    def _show(kind: str) -> Callable[..., str]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> str:
            stub.shown.append(f"{kind}: {message}")
            return "ok"

        return _fn

    for kind in ("askyesno", "askokcancel", "askquestion", "askyesnocancel", "askretrycancel"):
        monkeypatch.setattr(app.messagebox, kind, _ask(kind))
    for kind in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(app.messagebox, kind, _show(kind))
    return stub


@pytest.fixture(scope="module")
def tk_root() -> Iterator[tk.Tk]:
    """One withdrawn Tk root for the module, like the app's single root in main().

    A second tk.Tk() per process is fragile on macOS, and on this Tk (8.6.12, Aqua) a
    Text widget that logs inside a never-mapped withdrawn Toplevel makes update() spin
    forever, so the app is built on this root and its destroy() is recorded instead.
    """
    app.ensure_tcl_tk_discoverable()
    root = tk.Tk()
    root.withdraw()
    # Safety net: a Tcl background error goes to stderr, never to Tk's error dialog.
    root.tk.eval('proc bgerror {message} {puts stderr "bgerror: $message"}')
    yield root
    root.destroy()


@dataclass
class ClosingRoot:
    """The Tk root for one test, with destroy() recorded instead of performed.

    Each destroy() call appends the tagged processes still alive at that moment, so a
    test can tell whether the app closed its window before or after its process ended.
    """

    root: tk.Tk
    tag: str
    destroy_calls: list[list[int]] = field(default_factory=list)


@pytest.fixture
def closing_root(tk_root: tk.Tk) -> Iterator[ClosingRoot]:
    """Record the app's root.destroy() for one test, then clean the root up for the next."""
    closing = ClosingRoot(root=tk_root, tag=_new_tag())
    tk_root.destroy = lambda: closing.destroy_calls.append(_pids_with_tag(closing.tag))
    try:
        yield closing
    finally:
        del tk_root.destroy  # back to the real Tk.destroy for the module teardown
        for job in tk_root.tk.splitlist(tk_root.tk.call("after", "info")):
            tk_root.tk.call("after", "cancel", job)
        for child in list(tk_root.winfo_children()):
            child.destroy()


def _pump_until(root: tk.Tk, done: Callable[[], bool], timeout_s: float) -> bool:
    """Run the Tk event loop by hand until done() holds or the deadline passes."""
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        root.update()
        if done():
            return True
        time.sleep(0.02)
    return done()


def _build_app(root: tk.Tk, tmp_path: Path, tag: str) -> app.CentralDeTreinoApp:
    """The real app on `root`; its Iniciar runs the slow-stop stand-in, tagged with tag."""
    repo_root = tmp_path / "repo"
    (repo_root / "python" / "configs" / "ppo").mkdir(parents=True)
    (repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_PPO_CONFIG)
    (repo_root / "results").mkdir()
    (repo_root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    (bin_dir / "python3").touch()
    (bin_dir / "mlagents-learn").touch()  # resolve_for_execution only checks that it exists
    markers = tmp_path / "markers"
    markers.mkdir()
    gui = app.CentralDeTreinoApp(root, repo_root=repo_root, python_bin=bin_dir / "python3")

    def _factory(_args: list[str], cwd: Path) -> app.ManagedProcess:
        stand_in = [
            sys.executable,
            str(SLOW_STOP_TRAINER),
            f"--tag={tag}",
            f"--marker-dir={markers}",
            f"--stop-delay={STOP_DELAY_S}",
        ]
        return app.ManagedProcess(stand_in, cwd, python_bin=Path(sys.executable))

    gui._process_factory = _factory  # the app's documented test seam
    return gui


def _log_text(gui: app.CentralDeTreinoApp) -> str:
    return gui.log_text.get("1.0", "end")


def test_close_while_running_asks_then_stops_without_blocking_and_closes_after_exit(
    closing_root: ClosingRoot, dialogs: DialogStub, tmp_path: Path
) -> None:
    """M5: closing while a process runs asks first; on yes, on_close returns at once, the
    graceful stop is requested, and the finish path destroys the window after the
    process ended, leaving no process behind."""
    root, tag, markers = closing_root.root, closing_root.tag, tmp_path / "markers"
    gui = _build_app(root, tmp_path, tag)
    process: app.ManagedProcess | None = None
    try:
        gui.on_start()
        process = gui._process  # kept only to reap it in the cleanup
        started = _pump_until(root, lambda: "READY" in _log_text(gui), 5.0)
        assert started, f"the stand-in did not start: {dialogs.shown}"

        dialogs.answer = True
        began = time.monotonic()
        gui.on_close()
        elapsed = time.monotonic() - began

        assert elapsed < CLOSE_RETURNS_WITHIN_S, f"on_close blocked the Tk thread {elapsed:.2f} s"
        assert len(dialogs.asked) == 1, f"expected one question, got {dialogs.asked}"
        assert _pids_with_tag(tag), "the process had already ended when on_close returned"
        assert closing_root.destroy_calls == [], "the window closed before the process ended"

        closed = _pump_until(root, lambda: bool(closing_root.destroy_calls), STOP_DELAY_S + 4.0)
        assert closed, "the window was not destroyed after the process ended"
        assert closing_root.destroy_calls == [[]], "destroyed while a process was still alive"
        assert (markers / "sigint").exists(), "no graceful stop was requested"
        assert (markers / "stopped").exists(), "the process did not finish its graceful stop"
        assert _pids_with_tag(tag) == []
        assert dialogs.shown == []
    finally:
        _kill_and_reap(tag, process)


def test_close_while_running_answer_no_stops_nothing_and_keeps_the_window(
    closing_root: ClosingRoot, dialogs: DialogStub, tmp_path: Path
) -> None:
    """M5: answering no to the close question stops nothing and keeps the window open."""
    root, tag, markers = closing_root.root, closing_root.tag, tmp_path / "markers"
    gui = _build_app(root, tmp_path, tag)
    process: app.ManagedProcess | None = None
    try:
        gui.on_start()
        process = gui._process  # kept only to reap it in the cleanup
        started = _pump_until(root, lambda: "READY" in _log_text(gui), 5.0)
        assert started, f"the stand-in did not start: {dialogs.shown}"

        dialogs.answer = False
        gui.on_close()

        assert len(dialogs.asked) == 1, f"expected one question, got {dialogs.asked}"
        # Give a deferred stop or close the chance to show up before checking it did not.
        _pump_until(
            root, lambda: (markers / "sigint").exists() or bool(closing_root.destroy_calls), 0.3
        )
        assert closing_root.destroy_calls == [], "the window closed although the answer was no"
        assert not (markers / "sigint").exists(), "a stop was requested although the answer was no"
        assert _pids_with_tag(tag), "the process ended although the answer was no"
        assert "disabled" not in gui.stop_button.state(), "Parar is no longer available"
    finally:
        _kill_and_reap(tag, process)


def test_close_with_nothing_running_closes_without_asking(
    closing_root: ClosingRoot, dialogs: DialogStub, tmp_path: Path
) -> None:
    """M5: with nothing running, closing the window does not ask and the window closes."""
    root = closing_root.root
    _build_app(root, tmp_path, closing_root.tag).on_close()
    closed = _pump_until(root, lambda: bool(closing_root.destroy_calls), 1.0)
    assert dialogs.asked == [], f"asked although nothing was running: {dialogs.asked}"
    assert closed, "the window did not close"
