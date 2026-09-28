"""What the Central de treino says and allows when a process ends (task T6b1).

Covers review findings M1 (end-of-run status: exit-code race, stale .onnx, status
order), M2 (stale force-stop timer) and m2 (watch status overwriting the stop
messages) from local_files/build/launcher/review_launcher.md. Every test builds the
real CentralDeTreinoApp on one withdrawn Tk root, swaps its process factory for a
real ManagedProcess running tests/standin_T6b1_trainer.py, calls the button handlers
and pumps the Tk loop with update(). No window is mapped, no socket is opened.
"""

from __future__ import annotations

import contextlib
import os
import subprocess
import sys
import threading
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import TextIO

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

STANDIN = Path(__file__).resolve().parent / "standin_T6b1_trainer.py"
MODEL_NAME = "FlappyAgent.onnx"
PORT_NEEDLE = "UnityWorkerInUseException"
PORT_HINT = dict(app._KNOWN_FAILURES)[PORT_NEEDLE]
PORT_LINE = (
    f"mlagents_envs.exception.{PORT_NEEDLE}: Couldn't start socket communication because "
    "worker number 0 is still in use."
)
LAST_LINE = "[STANDIN] ultima linha antes de sair"
CONNECTED_LINE = f"[INFO] {app._GAME_CONNECTED_MARKER} results/ppo1/FlappyAgent/checkpoint.pt."
GAME_CLOSED_LINE = f"[ERROR] Worker 0 {app._GAME_CLOSED_MARKER} for this environment."
_PPO_CONFIG = "behaviors:\n  FlappyAgent:\n    trainer_type: ppo\n    max_steps: 50000\n"
_HINTS = tuple(hint for _needle, hint in app._KNOWN_FAILURES)
_END_WORDS = ("encerrad", "terminou", "finalizad", "concluíd", "acabou")


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str]]:
    """Stub every messagebox call and webbrowser.open; returns the (kind, message) calls."""
    calls: list[tuple[str, str]] = []

    def _record(kind: str) -> Callable[..., None]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> None:
            calls.append((kind, message))

        return _fn

    def _yes(title: str = "", message: str = "", **_kwargs: object) -> bool:
        calls.append(("askyesno", message))
        return True

    for kind in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(app.messagebox, kind, _record(kind))
    monkeypatch.setattr(app.messagebox, "askyesno", _yes)
    monkeypatch.setattr(app.webbrowser, "open", lambda *_args, **_kwargs: False)
    return calls


# tk_root comes from tests/conftest.py: one withdrawn Tk root for the whole session.


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _make_repo(tmp_path: Path) -> Path:
    """A fake repo: one training config, an empty results/ and a macOS game build."""
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_PPO_CONFIG)
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    return root


def _make_trained_run(repo: Path, name: str = "ppo1") -> None:
    """A results/<name> run with a checkpoint, so the Assistir tab lists it."""
    behavior_dir = repo / "results" / name / "FlappyAgent"
    behavior_dir.mkdir(parents=True)
    (repo / "results" / name / "configuration.yaml").write_text(_PPO_CONFIG)
    (behavior_dir / "checkpoint.pt").write_bytes(b"pt")


def _make_stale_model(repo: Path, age_s: float, name: str = "ppo1") -> Path:
    """An .onnx left by an earlier session: its mtime lies age_s seconds in the past."""
    model = repo / "results" / name / MODEL_NAME
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"old onnx")
    past = time.time() - age_s
    os.utime(model, (past, past))
    return model


def _placeholder_python_bin(tmp_path: Path) -> Path:
    """A venv-shaped bin dir that only satisfies resolve_for_execution's file check.

    Nothing in it ever runs: every test swaps the app's process factory for a
    ManagedProcess that runs sys.executable on the stand-in script.
    """
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    (bin_dir / "mlagents-learn").write_text("")
    python_bin = bin_dir / "python3"
    python_bin.write_text("")
    return python_bin


def _pending_after_jobs(root: tk.Tk) -> set[str]:
    """Ids of every after() job Tcl still has pending; fired or cancelled jobs are gone."""
    return set(root.tk.splitlist(root.tk.call("after", "info")))


def _pump_until(root: tk.Tk, condition: Callable[[], bool], timeout: float = 5.0) -> bool:
    """Run the Tk loop until condition() holds; False if timeout seconds pass first."""
    deadline = time.monotonic() + timeout
    while True:
        root.update()
        if condition():
            return True
        if time.monotonic() >= deadline:
            return False
        time.sleep(0.01)


def _finished(gui: app.CentralDeTreinoApp) -> bool:
    """True once the app treats the run as over: Iniciar is enabled again."""
    return bool(gui.start_button.instate(["!disabled"]))


def _log(gui: app.CentralDeTreinoApp) -> str:
    """The text of the app's log area."""
    return gui.log_text.get("1.0", "end")


def _status_meaning(status: str) -> str:
    """Name the case a final status reports, by meaning rather than exact wording.

    Checked in the review's priority order, so a status is named after the first
    case it expresses. Hints come from the app's own table, so rewording a hint
    does not break this.
    """
    lowered = status.lower()
    if "jogo" in lowered and "fech" in lowered:
        return "game_closed"
    if "salv" in lowered and (".onnx" in lowered or "results/" in lowered):
        return "saved"
    if any(hint in status for hint in _HINTS):
        return "hint"
    if "erro" in lowered:
        return "error"
    if any(word in lowered for word in _END_WORDS):
        return "normal"
    return f"unrecognised: {status}"


@contextlib.contextmanager
def _gui_session(
    tk_root: tk.Tk,
    repo: Path,
    tmp_path: Path,
    specs: list[list[str]],
    *,
    graceful_timeout_s: float = app.GRACEFUL_STOP_TIMEOUT_S,
    conflict_choice: str = "resume",
) -> Iterator[tuple[app.CentralDeTreinoApp, list[app.ManagedProcess]]]:
    """Build the app with the stand-in behind its process factory, and always clean up.

    The n-th launch runs the stand-in with specs[n] (the last spec repeats). The
    "run already exists" dialog answers conflict_choice. At exit every process is
    killed and reaped, the app ends it through its own poll loop, and every after()
    job scheduled during the session is cancelled.
    """
    jobs_before = _pending_after_jobs(tk_root)
    launched: list[app.ManagedProcess] = []
    unexpected: list[str] = []
    gui = app.CentralDeTreinoApp(
        tk_root, repo_root=repo, python_bin=_placeholder_python_bin(tmp_path)
    )

    def factory(_real_args: list[str], cwd: Path) -> app.ManagedProcess:
        spec = specs[min(len(launched), len(specs) - 1)]
        process = app.ManagedProcess(
            [sys.executable, str(STANDIN), *spec],
            cwd,
            python_bin=Path(sys.executable),
            graceful_timeout_s=graceful_timeout_s,
        )
        launched.append(process)
        return process

    def ask_conflict(run_name: str) -> tuple[str, str]:
        return conflict_choice, run_name

    def error_dialog(*, message: str, log_path: Path) -> None:
        unexpected.append(f"{message} ({log_path})")

    gui._process_factory = factory
    gui._ask_run_conflict = ask_conflict
    gui._show_error_dialog = error_dialog
    tk_root.update()
    try:
        yield gui, launched
        assert not unexpected, f"unexpected error dialog: {unexpected}"
    finally:
        for process in launched:
            if process.is_running():
                process.force_kill()
        _pump_until(tk_root, lambda: gui._process is None, timeout=5.0)
        for job in _pending_after_jobs(tk_root) - jobs_before:
            tk_root.after_cancel(job)
        gui.container.destroy()


def _start_watch(tk_root: tk.Tk, gui: app.CentralDeTreinoApp, *, time_limit: bool) -> None:
    """Select the Assistir tab and the ppo1 run, set the time limit box, press Iniciar."""
    gui.notebook.select(1)
    gui.watch_run_var.set("ppo1")
    gui.no_time_limit_var.set(not time_limit)
    tk_root.update()
    gui.on_start()


# ----------------------------------------------------------------------------
# M1, part 1: the exit code and the last lines, when the reader lags behind poll()
# ----------------------------------------------------------------------------


class _HeldStdout:
    """A child's stdout as the reader thread sees it, with one line held back.

    readline() returns what the real pipe returns, but the first line for which
    hold(line) is true is handed over only once the gate opens. This builds the
    losing order of the race on purpose: the process has ended (poll() answers)
    while the reader thread has not delivered the last lines, or seen EOF, yet.
    """

    def __init__(self, real: TextIO, hold: Callable[[str], bool]) -> None:
        self.real = real
        self.hold = hold
        self.gate = threading.Event()
        self.holding = threading.Event()

    def readline(self) -> str:
        line = self.real.readline()
        if not self.gate.is_set() and self.hold(line):
            self.holding.set()
            self.gate.wait(timeout=10)
        return line

    def __iter__(self) -> Iterator[str]:
        """Iterating the stream holds the same line as readline() does."""
        return iter(self.readline, "")


@pytest.mark.parametrize("held", ["last_lines", "eof"])
def test_m1a_hint_and_last_lines_survive_a_reader_behind_the_exit(
    held: str, tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M1: the process has exited but its reader has not delivered the last lines
    (last_lines) or reached EOF (eof) when the app sees the end; the final status still
    carries the port-in-use hint and the last lines still reach the log."""
    streams: list[_HeldStdout] = []
    real_posix_popen = app._posix_popen

    def is_held(line: str) -> bool:
        return PORT_NEEDLE in line if held == "last_lines" else line == ""

    def held_posix_popen(args: list[str], cwd: Path, python_bin: Path) -> subprocess.Popen:
        proc = real_posix_popen(args, cwd, python_bin)
        stream = _HeldStdout(proc.stdout, is_held)
        proc.stdout = stream
        streams.append(stream)
        return proc

    monkeypatch.setattr(app, "_posix_popen", held_posix_popen)
    repo = _make_repo(tmp_path)
    spec = ["--print", "[STANDIN] conectando ao jogo", "--print", PORT_LINE]
    spec += ["--print", LAST_LINE, "--exit-code", "1"]
    release: threading.Timer | None = None
    with _gui_session(tk_root, repo, tmp_path, [spec]) as (gui, launched):
        try:
            gui.on_start()
            # on_start() ends by scheduling the app's next poll tick 100 ms ahead.
            tick_due_at = time.monotonic() + 0.1
            assert len(launched) == 1 and len(streams) == 1
            # Without running the Tk loop, wait until the process has ended while the
            # reader holds the tail, and until the app's next poll tick is due.
            deadline = tick_due_at + 5
            while time.monotonic() < deadline and not (
                streams[0].holding.is_set() and not launched[0].is_running()
            ):
                time.sleep(0.01)
            assert streams[0].holding.is_set() and not launched[0].is_running()
            while time.monotonic() < tick_due_at + 0.02:
                time.sleep(0.01)
            # The reader goes on 0.15 s after the tick that sees the end starts, so
            # the tail reaches the app only if the app waits for its reader.
            release = threading.Timer(0.15, streams[0].gate.set)
            release.start()
            assert _pump_until(tk_root, lambda: _finished(gui))
            status = gui.status_var.get()
            assert PORT_HINT in status, status
            assert PORT_LINE in _log(gui)
            assert LAST_LINE in _log(gui)
        finally:
            if release is not None:
                release.cancel()
            for stream in streams:
                stream.gate.set()


# ----------------------------------------------------------------------------
# M1, part 2: an .onnx from before this session is not "saved" by this session
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("choice", ["resume", "force"])
def test_m1b_stale_model_not_reported_saved_when_session_fails(
    choice: str, tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M1: after Continuar (resume) or Recomeçar (force) on a run whose .onnx predates
    this session, a session that exits nonzero without a known hint reads as an error,
    not as "Modelo salvo"."""
    repo = _make_repo(tmp_path)
    _make_stale_model(repo, age_s=2.0)
    spec = ["--print", "[STANDIN] Traceback: algo deu errado", "--exit-code", "1"]
    with _gui_session(tk_root, repo, tmp_path, [spec], conflict_choice=choice) as (
        gui,
        launched,
    ):
        gui.on_start()
        assert len(launched) == 1
        assert _pump_until(tk_root, lambda: _finished(gui))
        status = gui.status_var.get()
        assert _status_meaning(status) == "error", status


def test_m1b_stale_model_not_reported_saved_after_force_stop(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M1: a Continuar run stopped with Parar and then Forçar parada, while an .onnx
    from an earlier session sits in its folder, is not reported as saved and does not
    read as a normal end. The stand-in ignores SIGINT, so only the kill can end it."""
    repo = _make_repo(tmp_path)
    _make_stale_model(repo, age_s=2.0)
    spec = ["--until-sigint", "--ignore-sigint"]
    with _gui_session(tk_root, repo, tmp_path, [spec], graceful_timeout_s=0.2) as (
        gui,
        launched,
    ):
        gui.on_start()
        assert len(launched) == 1
        assert _pump_until(tk_root, lambda: bool(_log(gui).strip()))
        gui.on_stop()
        assert _pump_until(tk_root, lambda: bool(gui.force_button.instate(["!disabled"])), 3)
        gui.force_button.invoke()
        assert _pump_until(tk_root, lambda: _finished(gui))
        status = gui.status_var.get()
        assert _status_meaning(status) == "error", status


# ----------------------------------------------------------------------------
# M1, part 3: the status order the review asks for
# ----------------------------------------------------------------------------

# (id, mode, model, printed lines, exit code, expected meaning). model: "none", "new"
# (written by this session), "stale" (left by an earlier one) or "stale+new".
_ORDER_MATRIX: list[tuple[str, str, str, list[str], int, str]] = [
    ("train_saved", "treinar", "new", [], 0, "saved"),
    ("train_saved_over_stale", "treinar", "stale+new", [], 0, "saved"),
    ("train_saved_beats_hint", "treinar", "new", [PORT_LINE], 1, "saved"),
    ("train_stale_then_hint", "treinar", "stale", [PORT_LINE], 1, "hint"),
    ("train_stale_then_nonzero", "treinar", "stale", [], 1, "error"),
    ("train_stale_then_clean_exit", "treinar", "stale", [], 0, "normal"),
    ("train_hint", "treinar", "none", [PORT_LINE], 1, "hint"),
    ("train_nonzero", "treinar", "none", [], 1, "error"),
    ("train_clean_exit", "treinar", "none", [], 0, "normal"),
    ("watch_closed_nonzero", "assistir", "none", [GAME_CLOSED_LINE], 1, "game_closed"),
    ("watch_closed_clean_exit", "assistir", "none", [GAME_CLOSED_LINE], 0, "game_closed"),
    (
        "watch_closed_beats_hint",
        "assistir",
        "none",
        [PORT_LINE, GAME_CLOSED_LINE],
        1,
        "game_closed",
    ),
    ("watch_hint", "assistir", "none", [PORT_LINE], 1, "hint"),
    ("watch_nonzero", "assistir", "none", [], 1, "error"),
    ("watch_clean_exit", "assistir", "none", [], 0, "normal"),
]


@pytest.mark.parametrize(
    ("mode", "model", "lines", "exit_code", "expected"),
    [row[1:] for row in _ORDER_MATRIX],
    ids=[row[0] for row in _ORDER_MATRIX],
)
def test_m1c_final_status_follows_the_review_order(
    mode: str,
    model: str,
    lines: list[str],
    exit_code: int,
    expected: str,
    tk_root: tk.Tk,
    tmp_path: Path,
) -> None:
    """M1: the final status names the first case that holds, in the review's order:
    game closed (watch only), model saved this session, known hint, nonzero exit,
    normal end."""
    repo = _make_repo(tmp_path)
    spec = ["--print", "[STANDIN] inicio"]
    if mode == "assistir":
        _make_trained_run(repo)
        spec += ["--print", CONNECTED_LINE]
    if "stale" in model:
        _make_stale_model(repo, age_s=3600.0)
    for line in lines:
        spec += ["--print", line]
    if "new" in model:
        spec += ["--write-model", str(repo / "results" / "ppo1" / MODEL_NAME)]
    spec += ["--exit-code", str(exit_code)]
    with _gui_session(tk_root, repo, tmp_path, [spec]) as (gui, launched):
        if mode == "assistir":
            _start_watch(tk_root, gui, time_limit=False)
        else:
            gui.on_start()
        assert len(launched) == 1
        assert _pump_until(tk_root, lambda: _finished(gui))
        status = gui.status_var.get()
        assert _status_meaning(status) == expected, status


# ----------------------------------------------------------------------------
# M2: the force-stop timer of one run never reaches the next run
# ----------------------------------------------------------------------------


def test_m2_stale_force_stop_timer_does_not_enable_force_stop_on_next_run(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M2: stop run A, start run B inside A's graceful window and never press Parar on
    B; when A's force-stop timer would have fired, Forçar parada stays disabled for B.
    B's own Parar still offers it after B's own window."""
    window_s = 0.6
    repo = _make_repo(tmp_path)
    run_a = ["--until-sigint"]
    run_b = ["--until-sigint", "--ignore-sigint"]
    with _gui_session(tk_root, repo, tmp_path, [run_a, run_b], graceful_timeout_s=window_s) as (
        gui,
        launched,
    ):
        gui.on_start()
        assert _pump_until(tk_root, lambda: bool(_log(gui).strip()))
        a_stopped_at = time.monotonic()
        gui.on_stop()
        assert _pump_until(tk_root, lambda: _finished(gui))
        gui.on_start()
        assert len(launched) == 2
        assert time.monotonic() - a_stopped_at < window_s, "B did not start in A's window"
        while time.monotonic() < a_stopped_at + window_s + 0.3:
            tk_root.update()
            assert gui.force_button.instate(["disabled"]), "Forçar parada enabled for B"
            time.sleep(0.01)
        assert launched[1].is_running()
        gui.on_stop()
        assert _pump_until(
            tk_root, lambda: bool(gui.force_button.instate(["!disabled"])), window_s + 1
        )
        gui.force_button.invoke()
        assert _pump_until(tk_root, lambda: _finished(gui))


def test_m2_force_stop_timer_cancelled_when_run_ends_and_next_launches(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M2: the force-stop timer armed by Parar (30 s) is no longer pending once that
    run has ended, nor after the next run has launched, nor after that run ends."""
    repo = _make_repo(tmp_path)
    with _gui_session(tk_root, repo, tmp_path, [["--until-sigint"]]) as (gui, launched):
        gui.on_start()
        assert _pump_until(tk_root, lambda: bool(_log(gui).strip()))
        before = _pending_after_jobs(tk_root)
        gui.on_stop()
        armed_a = _pending_after_jobs(tk_root) - before
        assert _pump_until(tk_root, lambda: _finished(gui))
        assert not armed_a & _pending_after_jobs(tk_root), "A's timer pending after A ended"
        log_size = len(_log(gui))
        gui.on_start()
        assert len(launched) == 2
        assert not armed_a & _pending_after_jobs(tk_root), "A's timer pending after B launched"
        assert _pump_until(tk_root, lambda: len(_log(gui)) > log_size)
        before = _pending_after_jobs(tk_root)
        gui.on_stop()
        armed_b = _pending_after_jobs(tk_root) - before
        assert _pump_until(tk_root, lambda: _finished(gui))
        assert not armed_b & _pending_after_jobs(tk_root), "B's timer pending after B ended"


# ----------------------------------------------------------------------------
# m2: after Parar or the time limit, the watch status does not come back
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "ending",
    [
        "parar_without_time_limit",
        pytest.param(
            "parar_with_time_limit",
            marks=pytest.mark.xfail(
                strict=True,
                reason=(
                    "m2: Parar in a watch that has a time limit ends with the time-limit "
                    "status (time_limit_stopped ignores who stopped it)"
                ),
            ),
        ),
        "time_limit",
    ],
)
def test_m2_watch_status_not_restored_after_stop(
    ending: str, tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """m2: after Parar or the time limit in watch mode, no status tick restores "O modelo
    está jogando"; the final status says the time limit ended the session only when it
    did."""
    if ending == "time_limit":
        real_after = tk_root.after

        def quick_after(ms: int, func: Callable[..., object] | None = None, *args: object) -> str:
            # The time limit is the only after() of a minute or more (the UI's floor);
            # fire it 0.6 s from now instead of minutes from now.
            return real_after(600 if int(ms) >= 60_000 else ms, func, *args)

        monkeypatch.setattr(tk_root, "after", quick_after)
    repo = _make_repo(tmp_path)
    _make_trained_run(repo)
    spec = ["--print", CONNECTED_LINE, "--until-sigint", "--linger", "0.3"]
    with _gui_session(tk_root, repo, tmp_path, [spec]) as (gui, launched):
        writes: list[tuple[str, bool]] = []

        def record_write(*_args: object) -> None:
            writes.append((gui.status_var.get(), bool(gui.stop_button.instate(["disabled"]))))

        trace_id = gui.status_var.trace_add("write", record_write)
        try:
            _start_watch(tk_root, gui, time_limit=ending != "parar_without_time_limit")
            assert len(launched) == 1
            assert _pump_until(tk_root, lambda: "jogando" in gui.status_var.get().lower())
            if ending == "time_limit":
                # The limit presses Parar by itself, which disables the Parar button.
                assert _pump_until(tk_root, lambda: bool(gui.stop_button.instate(["disabled"])))
            else:
                gui.on_stop()
            assert _pump_until(tk_root, lambda: _finished(gui))
        finally:
            gui.status_var.trace_remove("write", trace_id)
        after_stop = [text for text, stop_disabled in writes if stop_disabled]
        restored = [text for text in after_stop if "jogando" in text.lower()]
        assert not restored, after_stop
        final = gui.status_var.get()
        if ending == "time_limit":
            assert "limite" in final.lower(), final
        else:
            assert "limite" not in final.lower(), final
            assert _status_meaning(final) == "normal", final
