"""Regression tests for review_launcher.md's Windows-hardening batch: H1-H7.

All seven findings are OPEN in this working copy (RP0): every test here is
expected to fail today and is marked xfail(strict=True) with the file:line
evidence in its reason. Windows is simulated by monkeypatching subprocess.run
and the ManagedProcess `system=` seam the app already uses for this; nothing
here starts TensorBoard, opens a socket or a browser, or maps a window.

Self-contained: does not import tests/test_central_de_treino.py or edit
tests/fake_trainer.py. Uses the shared, module-scoped `tk_root` fixture from
tests/conftest.py instead of creating its own Tk root (a second root in the
same process hangs Aqua Tk - see conftest.py's own tk_root docstring).
"""

from __future__ import annotations

import subprocess
import sys
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

_PPO_CONFIG = "behaviors:\n  FlappyAgent:\n    trainer_type: ppo\n    max_steps: 50000\n"


def _minimal_repo(tmp_path: Path) -> Path:
    """A minimal fake repo: one trainer config, empty results/, no trained runs."""
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_PPO_CONFIG)
    (root / "results").mkdir()
    return root


def _repo_with_trained_run(tmp_path: Path, name: str = "ppo1") -> Path:
    """A repo like _minimal_repo, plus one trained run ready for the Assistir tab."""
    root = _minimal_repo(tmp_path)
    behavior_dir = root / "results" / name / "FlappyAgent"
    behavior_dir.mkdir(parents=True)
    (root / "results" / name / "configuration.yaml").write_text(_PPO_CONFIG)
    (behavior_dir / "checkpoint.pt").write_bytes(b"pt")
    return root


def _log_text(gui: app.CentralDeTreinoApp) -> str:
    return gui.log_text.get("1.0", "end")


def _mute_error_dialog(gui: app.CentralDeTreinoApp) -> None:
    """Stub the app's own Toplevel error dialog so an unrelated except-clause
    firing for real never maps a window (its real body is a tk.Toplevel)."""
    gui._show_error_dialog = lambda **_kw: None


class _StubProc:
    """Minimal stand-in for a subprocess.Popen handle: only .poll() is used."""

    def __init__(self, returncode: int | None) -> None:
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode


class _FinishedStub:
    """Minimal stand-in for a ManagedProcess that has already ended cleanly."""

    def __init__(self) -> None:
        self.returncode = 0

    def finish_reading(self) -> list[str]:
        return []


def _windows_process_with_fake_pid(repo: Path, pid: int = 4321) -> app.ManagedProcess:
    """A real ManagedProcess on the Windows path, with a fake already-started
    handle (never actually spawned), for exercising request_graceful_stop()/
    force_kill() without a real child process."""
    process = app.ManagedProcess(
        [sys.executable], repo, python_bin=Path(sys.executable), system="Windows"
    )
    process._proc = SimpleNamespace(pid=pid)  # type: ignore[assignment]
    return process


# ----------------------------------------------------------------------------
# H2 (priority 2): a file error while refreshing the Assistir list must not
# swallow a pending close.
# ----------------------------------------------------------------------------


def test_h2_pending_close_survives_watch_config_write_failure(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H2: an OSError/PermissionError while writing a run's watch config (an
    antivirus lock, a read-only results/ folder) must not escape the finish
    path; the refresh must survive it, the log area must say what failed, and
    a pending close (the user already asked to close while this run was
    ending) must still happen."""
    repo = _repo_with_trained_run(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    try:
        monkeypatch.setattr(
            app,
            "generate_watch_config",
            lambda *_a, **_k: (_ for _ in ()).throw(PermissionError("simulated antivirus lock")),
        )
        closed: list[bool] = []
        gui._close_now = lambda: closed.append(True)
        gui._process = _FinishedStub()  # type: ignore[assignment]
        gui._closing = True
        gui._finish_process()
        assert closed == [True], "a pending close did not happen after the refresh failed"
        assert "erro" in _log_text(gui).lower(), _log_text(gui)
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H3 (priority 3): a stop that fails on Windows must say why.
# ----------------------------------------------------------------------------


def test_h3_stop_logs_windows_helper_result(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H3: after Parar on the Windows path, the ctrl+c helper's return code,
    and its stderr when not empty, must reach the log area."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    gui._process = _windows_process_with_fake_pid(repo)  # type: ignore[assignment]

    def _fake_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        return subprocess.CompletedProcess(args, returncode=53, stderr="access is denied")

    monkeypatch.setattr(app.subprocess, "run", _fake_run)
    try:
        tk_root.update()
        gui.on_stop()
        log_text = _log_text(gui)
        assert "53" in log_text, log_text
        assert "access is denied" in log_text, log_text
    finally:
        if gui._force_stop_job is not None:
            tk_root.after_cancel(gui._force_stop_job)
        gui.container.destroy()


def test_h3_stop_survives_helper_timeout(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H3: a subprocess.TimeoutExpired from the ctrl+c helper must not escape
    on_stop(); it must be logged and the app must stay usable instead of the
    click raising all the way out of the Tk callback."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    gui._process = _windows_process_with_fake_pid(repo)  # type: ignore[assignment]

    def _fake_run(args: list[str], **_kwargs: object) -> subprocess.CompletedProcess:
        raise subprocess.TimeoutExpired(cmd=args, timeout=10)

    monkeypatch.setattr(app.subprocess, "run", _fake_run)
    try:
        tk_root.update()
        gui.on_stop()  # must not raise
        assert "tempo" in _log_text(gui).lower(), _log_text(gui)
    finally:
        if gui._force_stop_job is not None:
            tk_root.after_cancel(gui._force_stop_job)
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H4 (priority 4): taskkill needs CREATE_NO_WINDOW and its result must be
# visible.
# ----------------------------------------------------------------------------


def test_h4_force_stop_uses_create_no_window_and_logs_taskkill_result(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H4: the forced stop on Windows must call taskkill with CREATE_NO_WINDOW,
    and its return code must reach the log area."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    gui._process = _windows_process_with_fake_pid(repo)  # type: ignore[assignment]
    monkeypatch.setattr(app.subprocess, "CREATE_NO_WINDOW", 0x08000000, raising=False)
    run_calls: list[tuple[list[str], dict[str, object]]] = []

    def _fake_run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess:
        run_calls.append((list(args), kwargs))
        return subprocess.CompletedProcess(args, returncode=25)

    monkeypatch.setattr(app.subprocess, "run", _fake_run)
    try:
        tk_root.update()
        gui.on_force_stop()
        assert run_calls, "taskkill was never invoked"
        _args, kwargs = run_calls[-1]
        assert kwargs.get("creationflags") == 0x08000000, kwargs
        assert "25" in _log_text(gui), _log_text(gui)
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H5 (priority 5): the first TensorBoard check must not use urlopen.
# ----------------------------------------------------------------------------


def test_h5_first_click_uses_raw_probe_not_urlopen(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H5: the first TensorBoard click must probe readiness with the same raw
    127.0.0.1 TCP connect the later checks use, and must never call urlopen -
    which can freeze the Tk thread for about 2 s on Windows when a proxy
    answers for the port."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    monkeypatch.setattr(
        app.CentralDeTreinoApp, "_poll_tensorboard_ready", lambda self, deadline: None
    )
    urlopen_calls: list[str] = []

    class _FakeHTTPResponse:
        def __enter__(self) -> _FakeHTTPResponse:  # noqa: PYI034 - typing.Self needs 3.11+
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    def _fake_urlopen(url: str, timeout: float = 0) -> _FakeHTTPResponse:
        urlopen_calls.append(url)
        return _FakeHTTPResponse()

    probe_calls: list[tuple[str, int]] = []

    def _fake_probe(*_a: object, **_k: object) -> bool:
        probe_calls.append(("127.0.0.1", 6006))
        return True  # something already answers: an existing TensorBoard, or a proxy

    browser_calls: list[str] = []
    monkeypatch.setattr(app.urllib.request, "urlopen", _fake_urlopen)
    monkeypatch.setattr(app, "_tensorboard_port_open", _fake_probe)
    monkeypatch.setattr(app.webbrowser, "open", lambda url, *_a, **_k: browser_calls.append(url))

    def _must_not_start(*_a: object, **_k: object) -> _StubProc:
        raise AssertionError("must not start a new TensorBoard when one already answers")

    monkeypatch.setattr(app, "start_tensorboard", _must_not_start)
    try:
        tk_root.update()
        gui.on_tensorboard()
        assert urlopen_calls == [], f"urlopen was called: {urlopen_calls}"
        assert probe_calls, "the raw TCP probe (_tensorboard_port_open) was never used"
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H6 (priority 6): a second click while TensorBoard is already running.
# ----------------------------------------------------------------------------


def test_h6_second_click_reopens_page_when_already_running(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H6: a click while TensorBoard is already running (the child is alive
    and the port answers) must reopen the page instead of silently doing
    nothing."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    monkeypatch.setattr(
        app.CentralDeTreinoApp, "_poll_tensorboard_ready", lambda self, deadline: None
    )
    browser_calls: list[str] = []
    monkeypatch.setattr(app.webbrowser, "open", lambda url, *_a, **_k: browser_calls.append(url))
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: True)

    def _must_not_urlopen(*_a: object, **_k: object) -> None:
        raise AssertionError("must not use urlopen for a running TensorBoard")

    def _must_not_start(*_a: object, **_k: object) -> _StubProc:
        raise AssertionError("must not start a second TensorBoard process")

    monkeypatch.setattr(app.urllib.request, "urlopen", _must_not_urlopen)
    monkeypatch.setattr(app, "start_tensorboard", _must_not_start)
    gui._tensorboard_proc = _StubProc(returncode=None)  # type: ignore[assignment]
    try:
        tk_root.update()
        gui.on_tensorboard()
        assert browser_calls, "the second click did not reopen the TensorBoard page"
    finally:
        gui._tensorboard_proc = None
        gui.container.destroy()


class _InlineThread:
    """Stands in for threading.Thread inside the app: runs its target at once, on
    the calling (Tk) thread, so the probe's root.after() hand-back works in a test
    that drives Tk with update() instead of mainloop()."""

    def __init__(self, target: Callable[[], None], daemon: bool = False) -> None:
        self._target = target

    def start(self) -> None:
        self._target()


def _pump(tk_root: tk.Tk, seconds: float, until: Callable[[], bool] = lambda: False) -> None:
    """Process Tk events for up to `seconds`, stopping early once until() is true."""
    deadline = time.monotonic() + seconds
    while not until() and time.monotonic() < deadline:
        tk_root.update()
        time.sleep(0.02)


def test_h6_click_while_still_starting_opens_page_once_when_ready(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H6: a click while TensorBoard is still starting, here after its 30 s wait
    already ran out, must not start a second process and must say in the log area
    that it is still starting; the page must then open, once, when the probe
    succeeds."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    port = {"open": False}
    starts: list[_StubProc] = []
    browser_calls: list[str] = []

    def _start(*_a: object, **_k: object) -> _StubProc:
        starts.append(_StubProc(returncode=None))  # alive, not answering yet
        return starts[-1]

    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=_InlineThread))
    monkeypatch.setattr(app, "is_tensorboard_up", lambda *_a, **_k: False)
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: port["open"])
    monkeypatch.setattr(app, "start_tensorboard", _start)
    monkeypatch.setattr(app.webbrowser, "open", lambda url, *_a, **_k: browser_calls.append(url))
    monkeypatch.setattr(app, "TENSORBOARD_READY_TIMEOUT_S", 0.0)  # the wait runs out at once
    pending_before = set(tk_root.tk.splitlist(tk_root.tk.call("after", "info")))
    try:
        tk_root.update()
        gui.on_tensorboard()
        assert len(starts) == 1
        _pump(tk_root, 0.2)
        gui.on_tensorboard()
        assert len(starts) == 1, "a click while TensorBoard was starting started another one"
        assert "ainda está iniciando" in _log_text(gui), _log_text(gui)
        assert browser_calls == []
        port["open"] = True
        _pump(tk_root, 3.0, until=lambda: bool(browser_calls))
        _pump(tk_root, 0.6)  # a second, duplicate wait would open the page again here
        assert browser_calls == [app.TENSORBOARD_URL], browser_calls
    finally:
        pending = set(tk_root.tk.splitlist(tk_root.tk.call("after", "info")))
        for job in pending - pending_before:
            tk_root.after_cancel(job)
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H7 (priority 7): visible feedback in the LOG AREA for every click.
# ----------------------------------------------------------------------------


def test_h7_start_feedback_reaches_log_area_when_idle(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H7: the moment TensorBoard starts, a line naming it must land in the
    LOG AREA at once - not only the status bar, which a student watching the
    log (where all the trainer output goes) can easily miss."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    monkeypatch.setattr(
        app.CentralDeTreinoApp, "_poll_tensorboard_ready", lambda self, deadline: None
    )
    monkeypatch.setattr(app, "is_tensorboard_up", lambda *_a, **_k: False)
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: False)
    monkeypatch.setattr(app, "start_tensorboard", lambda *_a, **_k: _StubProc(None))
    try:
        tk_root.update()
        assert gui._process is None  # idle: the scenario the finding names
        gui.on_tensorboard()
        log_lower = _log_text(gui).lower()
        assert "tensorboard" in log_lower and "inici" in log_lower, _log_text(gui)
    finally:
        gui.container.destroy()


def test_h7_already_running_feedback_reaches_log_area(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H7: opening an already-running TensorBoard, while a training is running
    too, must also leave a line in the log area."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    monkeypatch.setattr(
        app.CentralDeTreinoApp, "_poll_tensorboard_ready", lambda self, deadline: None
    )
    monkeypatch.setattr(app, "is_tensorboard_up", lambda *_a, **_k: True)
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: True)
    monkeypatch.setattr(app.webbrowser, "open", lambda *_a, **_k: None)
    gui._process = object()  # type: ignore[assignment]  # something else is running
    try:
        tk_root.update()
        gui.on_tensorboard()
        log_lower = _log_text(gui).lower()
        assert "tensorboard" in log_lower, _log_text(gui)
    finally:
        gui._process = None
        gui.container.destroy()


def test_h7_start_failure_feedback_says_what_to_do(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H7: when starting TensorBoard fails, the log line must say what to do
    about it (e.g. try the button again) - not just that an error happened."""
    repo = _minimal_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo, python_bin=Path(sys.executable))
    _mute_error_dialog(gui)
    monkeypatch.setattr(
        app.CentralDeTreinoApp, "_poll_tensorboard_ready", lambda self, deadline: None
    )
    monkeypatch.setattr(app, "is_tensorboard_up", lambda *_a, **_k: False)
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: False)

    def _fail_to_start(*_a: object, **_k: object) -> None:
        raise OSError("no such file or directory: tensorboard")

    monkeypatch.setattr(app, "start_tensorboard", _fail_to_start)
    try:
        tk_root.update()
        gui.on_tensorboard()
        log_lower = _log_text(gui).lower()
        assert "tensorboard" in log_lower and "tente" in log_lower, _log_text(gui)
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# H1 (priority 1): invisible errors under pythonw. Run last: this is the only
# test that drives main() itself, so it touches the shared tk_root's
# report_callback_exception/protocol - both are reset in `finally` before any
# later test could see them.
# ----------------------------------------------------------------------------


def test_h1_callback_exception_reaches_unexpected_error_path(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """H1: an exception raised inside a Tk callback must reach the app's own
    unexpected-error path (the dialog function and the error log) through
    root.report_callback_exception, wired the way main() builds it - instead
    of vanishing, as it does under pythonw where stderr is None."""
    repo = _minimal_repo(tmp_path)
    monkeypatch.chdir(repo)
    monkeypatch.setattr(app.tk, "Tk", lambda: tk_root)
    monkeypatch.setattr(tk_root, "mainloop", lambda: None)

    built: list[app.CentralDeTreinoApp] = []
    real_init = app.CentralDeTreinoApp.__init__

    def _capturing_init(self: app.CentralDeTreinoApp, *a: object, **kw: object) -> None:
        real_init(self, *a, **kw)
        built.append(self)

    monkeypatch.setattr(app.CentralDeTreinoApp, "__init__", _capturing_init)
    try:
        app.main()
        assert "report_callback_exception" in vars(tk_root), (
            "main() never wired root.report_callback_exception to the app's handler"
        )
        assert built, "main() never built a CentralDeTreinoApp"
        gui = built[0]
        dialog_calls: list[tuple[str, Path]] = []
        gui._show_error_dialog = lambda *, message, log_path: dialog_calls.append(
            (message, log_path)
        )

        def _boom() -> None:
            raise RuntimeError("h1-callback-boom")

        tk_root.after(0, _boom)
        deadline = time.monotonic() + 2
        while not dialog_calls and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert dialog_calls, "the callback exception never reached _show_error_dialog"
        _message, log_path = dialog_calls[0]
        assert Path(log_path).is_file(), "no error log file was written for the exception"
    finally:
        if "report_callback_exception" in vars(tk_root):
            del tk_root.__dict__["report_callback_exception"]
        tk_root.protocol("WM_DELETE_WINDOW", lambda: None)
        for gui in built:
            gui.container.destroy()
