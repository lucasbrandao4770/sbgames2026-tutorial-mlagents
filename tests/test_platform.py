"""Regression tests for review_launcher.md batch W ("Windows and startup"):
M7, M6, M8, m7, m19, m8.

Windows code paths are exercised on this Mac by monkeypatching sys.platform,
os.name, subprocess.Popen, subprocess.run, os.startfile (raising=False, it
does not exist here) and the socket/urllib calls the TensorBoard probe uses.
No test opens a real socket, starts a real TensorBoard, or maps a window.

Self-contained: does not import tests/test_central_de_treino.py or edit
tests/fake_trainer.py. Two stand-in trainers live alongside this file:
standin_T6c_marker_lines.py (M7) and standin_T6c_bad_bytes.py (m7).
"""

from __future__ import annotations

import http.client
import io
import sys
import threading
import time
import tkinter as tk
from pathlib import Path
from types import SimpleNamespace

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

STANDIN_MARKER_LINES = Path(__file__).resolve().parent / "standin_T6c_marker_lines.py"
STANDIN_BAD_BYTES = Path(__file__).resolve().parent / "standin_T6c_bad_bytes.py"


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub every tkinter.messagebox call so no test can ever show a real dialog."""

    def _noop(*_args: object, **_kwargs: object) -> None:
        return None

    def _yes(*_args: object, **_kwargs: object) -> bool:
        return True

    monkeypatch.setattr(app.messagebox, "showerror", _noop)
    monkeypatch.setattr(app.messagebox, "showwarning", _noop)
    monkeypatch.setattr(app.messagebox, "showinfo", _noop)
    monkeypatch.setattr(app.messagebox, "askyesno", _yes)


@pytest.fixture(autouse=True)
def no_real_browser(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blanket safety net: nothing in this file may open a real browser tab,
    even through a reverted mutant that falls through to the unstubbed code
    path. Tests that specifically check the webbrowser.open call override this
    again with their own recorder.
    """
    monkeypatch.setattr(app.webbrowser, "open", lambda *a, **k: None)


# tk_root comes from tests/conftest.py: one withdrawn Tk root for the whole session.


def _stop_and_destroy(gui: app.CentralDeTreinoApp, tk_root: tk.Tk) -> None:
    """Reap any live child and cancel any pending after() job, then drop the widgets."""
    if gui._process is not None:
        gui._process.force_kill()
    if gui._poll_job is not None:
        tk_root.after_cancel(gui._poll_job)
        gui._poll_job = None
    if gui._watch_time_limit_job is not None:
        tk_root.after_cancel(gui._watch_time_limit_job)
        gui._watch_time_limit_job = None
    gui.container.destroy()


def _watch_ready_repo(tmp_path: Path) -> Path:
    """A repo with one trained run (checkpoint present) and a fake macOS build,
    ready for the Assistir tab.
    """
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(
        "behaviors:\n"
        "  FlappyAgent:\n"
        "    trainer_type: ppo\n"
        "    max_steps: 50000\n"
        "    hyperparameters:\n"
        "      batch_size: 256\n"
    )
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    run_dir = root / "results" / "ppo1"
    behavior_dir = run_dir / "FlappyAgent"
    behavior_dir.mkdir(parents=True)
    (run_dir / "configuration.yaml").write_text(
        "behaviors:\n"
        "  FlappyAgent:\n"
        "    trainer_type: ppo\n"
        "    max_steps: 50000\n"
        "env_settings:\n"
        "  base_port: 5005\n"
        "engine_settings:\n"
        "  no_graphics: true\n"
        "  width: 84\n"
    )
    (run_dir / "FlappyAgent.onnx").touch()
    (behavior_dir / "checkpoint.pt").touch()
    return root


def _venv_with_standin(tmp_path: Path, standin: Path, extra_flag: str) -> Path:
    """A venv-shaped bin dir whose mlagents-learn runs `standin` with extra_flag
    appended, the same shape as the existing suite's fake-trainer shim, pointed
    at one of this file's own stand-ins instead.
    """
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.symlink_to(sys.executable)
    shim = bin_dir / "mlagents-learn"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import runpy, sys\n"
        f"sys.argv = [sys.argv[0], *sys.argv[1:], {extra_flag!r}]\n"
        f"runpy.run_path({str(standin)!r}, run_name='__main__')\n"
    )
    shim.chmod(0o755)
    return python_bin


# ----------------------------------------------------------------------------
# M7 (priority 1): the watch status must gate on the trainer's MAIN-process
# line ("Initializing from"), not on the environment-worker's lines
# ("Connected to Unity environment" / "Connected new brain"). fake_trainer.py
# prints both together (main line first), which would hide a regression to
# the old marker; these stand-ins decouple the two so each direction is
# checked on its own.
# ----------------------------------------------------------------------------


def test_m7_watch_status_ignores_worker_only_lines(tk_root: tk.Tk, tmp_path: Path) -> None:
    """M7: env-worker-only lines ("Connected to Unity environment"/"Connected
    new brain") must not move the watch status off "Iniciando..." by
    themselves - the review says those most likely never reach this app's
    pipe on Windows, so the status must not depend on them.
    """
    repo_root = _watch_ready_repo(tmp_path)
    python_bin = _venv_with_standin(tmp_path, STANDIN_MARKER_LINES, "--emit-worker-lines")
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=python_bin)
    gui.no_time_limit_var.set(True)
    try:
        tk_root.update()
        gui.notebook.select(1)
        tk_root.update()
        assert gui._selected_run() is not None, "fixture did not produce a watchable run"
        gui.on_start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not any(
            "Connected to Unity environment" in line for line in gui._output_history
        ):
            tk_root.update()
            time.sleep(0.02)
        assert any("Connected to Unity environment" in line for line in gui._output_history), (
            "the stand-in never printed the worker-only lines"
        )
        settle_deadline = time.monotonic() + 0.5
        while time.monotonic() < settle_deadline:
            tk_root.update()
            time.sleep(0.02)
        assert gui.status_var.get() == "Iniciando..."
        assert gui._watch_connected is False
    finally:
        _stop_and_destroy(gui, tk_root)


def test_m7_watch_status_leaves_iniciando_on_main_process_line(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """M7: the watch status must leave "Iniciando..." once the trainer's MAIN
    process prints "Initializing from", even when the env-worker's lines never
    arrive at all - the scenario the review expects on Windows.
    """
    repo_root = _watch_ready_repo(tmp_path)
    python_bin = _venv_with_standin(tmp_path, STANDIN_MARKER_LINES, "--emit-main-line")
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=python_bin)
    gui.no_time_limit_var.set(True)
    try:
        tk_root.update()
        gui.notebook.select(1)
        tk_root.update()
        assert gui._selected_run() is not None, "fixture did not produce a watchable run"
        gui.on_start()
        deadline = time.monotonic() + 5
        while gui.status_var.get() == "Iniciando..." and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert gui.status_var.get() != "Iniciando..."
        assert gui._watch_connected is True
        assert not any("Connected to Unity environment" in line for line in gui._output_history)
        assert not any("Connected new brain" in line for line in gui._output_history)
    finally:
        _stop_and_destroy(gui, tk_root)


# ----------------------------------------------------------------------------
# M6 (priority 2): "Editar arquivo" must fall back to a text editor instead of
# raising / silently doing nothing when nothing is associated with .yaml.
# open_in_default_editor is the pure function on_edit_config calls.
# ----------------------------------------------------------------------------


def test_m6_windows_startfile_success_does_not_fall_back_to_notepad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M6: when os.startfile succeeds on Windows, notepad.exe must not also launch."""
    config = tmp_path / "FlappyBird_desafio.yaml"
    config.write_text("behaviors: {}\n")
    startfile_calls: list[str] = []
    monkeypatch.setattr(
        app.os, "startfile", lambda path: startfile_calls.append(path), raising=False
    )
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(app.subprocess, "Popen", lambda args, **_k: popen_calls.append(args))
    app.open_in_default_editor(config, system="Windows")
    assert startfile_calls == [str(config)]
    assert popen_calls == []


def test_m6_windows_startfile_oserror_falls_back_to_notepad(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M6: a clean lab PC with no .yaml association raises OSError from
    os.startfile; the user must land in Notepad, not the unexpected-error dialog.
    """
    config = tmp_path / "FlappyBird_desafio.yaml"
    config.write_text("behaviors: {}\n")

    def _raise(_path: str) -> None:
        raise OSError("no application is associated with this file")

    monkeypatch.setattr(app.os, "startfile", _raise, raising=False)
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(app.subprocess, "Popen", lambda args, **_k: popen_calls.append(args))
    app.open_in_default_editor(config, system="Windows")
    assert popen_calls == [["notepad.exe", str(config)]]


def test_m6_macos_opens_default_text_editor_not_plain_open(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """M6: on macOS, a plain `open` on a .yaml with nothing associated exits 1
    and does nothing; `open -t` always opens the default *text* editor instead.
    """
    config = tmp_path / "FlappyBird_desafio.yaml"
    config.write_text("behaviors: {}\n")
    popen_calls: list[list[str]] = []
    monkeypatch.setattr(app.subprocess, "Popen", lambda args, **_k: popen_calls.append(args))
    app.open_in_default_editor(config, system="Darwin")
    assert popen_calls == [["open", "-t", str(config)]]


# ----------------------------------------------------------------------------
# M8 (priority 3): the TensorBoard readiness probe must never block the Tk
# thread, must target 127.0.0.1 (not localhost), and must stop early with a
# PT-BR message when the TensorBoard process already died.
# ----------------------------------------------------------------------------


class _StubProc:
    """Minimal stand-in for a subprocess.Popen handle: only .poll() is used
    by the TensorBoard lifecycle code exercised here.
    """

    def __init__(self, returncode: int | None) -> None:
        self._returncode = returncode

    def poll(self) -> int | None:
        return self._returncode


def test_m8_tensorboard_probe_runs_off_the_tk_thread(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M8: the readiness probe must run off the Tk thread, so a slow probe
    cannot freeze the window while TensorBoard is starting.

    Only the non-blocking return and the probe's thread identity are checked
    here, not the after(0, ...) hand-back into _on_tensorboard_probe_result:
    Tcl only allows a background thread to call root.after() while the main
    thread is inside a real mainloop(), which this headless test (like the
    rest of the suite) drives with update() instead, so that hand-back is
    exercised by test_m8_tensorboard_probe_stops_early_when_process_already_died
    and the m7/M7 tests' _poll_process loop instead.
    """
    repo_root = _watch_ready_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=Path(sys.executable))
    probe_threads: list[threading.Thread] = []
    probe_done = threading.Event()

    def _slow_probe(*_a: object, **_k: object) -> bool:
        probe_threads.append(threading.current_thread())
        time.sleep(0.15)
        probe_done.set()
        return False  # avoid a real Tcl after() call from this background thread (see above)

    monkeypatch.setattr(app, "_tensorboard_port_open", _slow_probe)
    try:
        tk_root.update()
        started = time.monotonic()
        gui._poll_tensorboard_ready(time.monotonic() + 30.0)
        elapsed = time.monotonic() - started
        assert elapsed < 0.08, f"_poll_tensorboard_ready blocked the caller for {elapsed:.3f}s"
        deadline = time.monotonic() + 5
        while not probe_done.is_set() and time.monotonic() < deadline:
            time.sleep(0.02)
        assert probe_done.is_set()
        assert probe_threads and probe_threads[0] is not threading.main_thread()
    finally:
        gui.container.destroy()


def test_m8_tensorboard_probe_stops_early_when_process_already_died(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """M8: if the TensorBoard process already died, stop waiting immediately
    with a PT-BR message instead of probing until the 30 s timeout.
    """
    repo_root = _watch_ready_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=Path(sys.executable))
    probed: list[bool] = []
    monkeypatch.setattr(
        app, "_tensorboard_port_open", lambda *a, **k: (probed.append(True), False)[1]
    )
    try:
        tk_root.update()
        gui._tensorboard_proc = _StubProc(returncode=1)
        gui._poll_tensorboard_ready(time.monotonic() + 30.0)
        assert gui._tensorboard_proc is None
        assert "fechou sozinho" in gui.status_var.get()
        assert probed == []
    finally:
        gui.container.destroy()


def test_m8_probe_targets_127_0_0_1_not_localhost(monkeypatch: pytest.MonkeyPatch) -> None:
    """M8: the probe must connect to 127.0.0.1 directly. On Windows,
    "localhost" resolves to ::1 first, and a refused IPv6 connect there costs
    about a second per probe (TensorBoard/werkzeug binds IPv4 only).
    """
    calls: list[tuple[str, int]] = []

    class _Ctx:
        def __enter__(self) -> _Ctx:  # noqa: PYI034 - typing.Self needs 3.11+, pinned to 3.10
            return self

        def __exit__(self, *_exc: object) -> bool:
            return False

    def _fake_create_connection(address: tuple[str, int], timeout: float) -> _Ctx:
        del timeout
        calls.append(address)
        return _Ctx()

    monkeypatch.setattr(app.socket, "create_connection", _fake_create_connection)
    assert app._tensorboard_port_open() is True
    assert calls == [("127.0.0.1", 6006)]


# ----------------------------------------------------------------------------
# m7 (priority 4, OPEN): output decoding has no error handling.
# ----------------------------------------------------------------------------


@pytest.mark.xfail(
    strict=True,
    reason=(
        "m7: _posix_popen (scripts/central_de_treino.py:640-648) uses text=True "
        "with no errors=, so decoding defaults to strict; readline() raises "
        "UnicodeDecodeError on the bad line inside _read_output's for loop "
        "(central_de_treino.py:828), which has no try/except, so the reader "
        "thread dies right there and every later line is lost."
    ),
)
def test_m7_reader_thread_survives_undecodable_bytes(tmp_path: Path) -> None:
    """m7: a line invalid in the pipe's encoding must not kill the reader
    thread; later, valid lines must still arrive and the process end must
    still be detected via finish_reading()/returncode.
    """
    args = [sys.executable, str(STANDIN_BAD_BYTES)]
    process = app.ManagedProcess(args, tmp_path, python_bin=Path(sys.executable))
    process.start()
    try:
        deadline = time.monotonic() + 5
        lines: list[str] = []
        while time.monotonic() < deadline and not any(
            "linha valida depois" in line for line in lines
        ):
            lines.extend(process.poll_output())
            time.sleep(0.05)
        assert any("linha valida depois" in line for line in lines), (
            f"no valid line arrived after the bad one; collected so far: {lines!r}"
        )
        process.request_graceful_stop()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and process.is_running():
            time.sleep(0.05)
        assert process.is_running() is False
        lines.extend(process.finish_reading())
        assert process.returncode == 0
    finally:
        process.force_kill()


class _StubPopenHandle:
    """Minimal stand-in for what ManagedProcess.start() touches on a
    subprocess.Popen return value: an already-at-EOF stdout and wait()/poll().
    """

    def __init__(self) -> None:
        self.stdout = io.StringIO("")
        self.pid = 12345

    def wait(self) -> int:
        return 0

    def poll(self) -> int | None:
        return 0


@pytest.mark.xfail(
    strict=True,
    reason=(
        "m7: neither _posix_popen (central_de_treino.py:640-648) nor "
        "_windows_popen (:731-740) passes errors= to subprocess.Popen; "
        "captured kwargs['errors'] is None, not 'replace', on both paths."
    ),
)
def test_m7_launch_passes_errors_replace(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """m7: text=True with no errors= defaults to "strict"; both the POSIX and
    the Windows launch call must pass errors="replace" so an undecodable byte
    in the child's output cannot kill the reader thread (see the sibling test,
    which reproduces the crash against a real process at RP0).
    """
    captured: list[dict[str, object]] = []

    def _fake_popen(_args: list[str], **kwargs: object) -> _StubPopenHandle:
        captured.append(kwargs)
        return _StubPopenHandle()

    monkeypatch.setattr(app.subprocess, "Popen", _fake_popen)

    posix_process = app.ManagedProcess(
        ["mlagents-learn"], tmp_path, python_bin=Path(sys.executable), system="Darwin"
    )
    posix_process.start()
    assert captured, "subprocess.Popen was never called (POSIX)"
    assert captured[-1].get("errors") == "replace"

    # subprocess.STARTUPINFO and friends are Windows-only; stub them the same
    # way os.startfile is stubbed for M6, so _windows_popen's setup can run here.
    monkeypatch.setattr(
        app.subprocess,
        "STARTUPINFO",
        type("_FakeStartupInfo", (), {"__init__": lambda self: setattr(self, "dwFlags", 0)}),
        raising=False,
    )
    monkeypatch.setattr(app.subprocess, "STARTF_USESHOWWINDOW", 1, raising=False)
    monkeypatch.setattr(app.subprocess, "CREATE_NEW_CONSOLE", 0x10, raising=False)
    captured.clear()
    windows_process = app.ManagedProcess(
        ["mlagents-learn"], tmp_path, python_bin=Path(sys.executable), system="Windows"
    )
    windows_process.start()
    assert captured, "subprocess.Popen was never called (Windows)"
    assert captured[-1].get("errors") == "replace"


# ----------------------------------------------------------------------------
# m19 (priority 5, OPEN): the initial window size must fit a small screen.
# ----------------------------------------------------------------------------


class _FakeMainRoot:
    """Stands in for tk.Tk() in the m19 seam test (main()), so the literal
    window geometry can be exercised without ever creating a real Tk window.
    """

    def __init__(self, screen_size: tuple[int, int]) -> None:
        self._screen_size = screen_size
        self.geometry_calls: list[str] = []

    def title(self, _text: str) -> None:
        pass

    def geometry(self, spec: str) -> None:
        self.geometry_calls.append(spec)

    def minsize(self, _width: int, _height: int) -> None:
        pass

    def winfo_screenwidth(self) -> int:
        return self._screen_size[0]

    def winfo_screenheight(self) -> int:
        return self._screen_size[1]

    def protocol(self, _name: str, _handler: object) -> None:
        pass

    def mainloop(self) -> None:
        pass


@pytest.mark.xfail(
    strict=True,
    reason=(
        'm19: root.geometry("900x680") in main() (scripts/central_de_treino.py:2030) is a '
        "hardcoded literal - it never calls winfo_screenwidth()/winfo_screenheight(), so "
        "height=680 exceeds a 1366x768@125% screen's ~614 Tk-unit work area."
    ),
)
def test_m19_window_geometry_fits_small_screen_and_keeps_default_on_large(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """m19: the initial window must fit a 1366x768 screen at 125% scaling
    (about 1093x614 in Tk's DPI-unaware units) and keep 900x680 on a screen
    large enough for it. geometry("900x680") is a literal inside main() with
    no smaller function seam, so this drives main() itself, with tk.Tk() and
    CentralDeTreinoApp replaced by recording stand-ins so no real window is mapped.
    """
    monkeypatch.setattr(app, "ensure_tcl_tk_discoverable", lambda: None)
    monkeypatch.setattr(
        app,
        "CentralDeTreinoApp",
        lambda root, repo_root: SimpleNamespace(on_close=lambda: None),
    )

    small = _FakeMainRoot((1093, 614))
    monkeypatch.setattr(app.tk, "Tk", lambda: small)
    app.main()
    assert small.geometry_calls, "main() never called root.geometry(...)"
    width, height = (int(part) for part in small.geometry_calls[-1].split("x"))
    assert width <= 1093
    assert height <= 614

    large = _FakeMainRoot((1920, 1080))
    monkeypatch.setattr(app.tk, "Tk", lambda: large)
    app.main()
    width, height = (int(part) for part in large.geometry_calls[-1].split("x"))
    assert (width, height) == (900, 680)


# ----------------------------------------------------------------------------
# m8 (priority 6): TensorBoard lifecycle - no duplicate process, no raise on
# a non-HTTP listener.
# ----------------------------------------------------------------------------


def test_m8_is_tensorboard_up_does_not_raise_on_non_http_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """m8: a non-HTTP listener on the TensorBoard port raises
    http.client.HTTPException from urlopen, not OSError; is_tensorboard_up
    must catch it and report "not up" instead of propagating.
    """

    def _boom(*_args: object, **_kwargs: object) -> None:
        raise http.client.HTTPException("non-HTTP answer on the port")

    monkeypatch.setattr(app.urllib.request, "urlopen", _boom)
    assert app.is_tensorboard_up() is False


def test_m8_second_tensorboard_click_does_not_start_second_process(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """m8: a second click on TensorBoard while it is already starting (or
    running) must not launch a second TensorBoard process.
    """
    repo_root = _watch_ready_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=Path(sys.executable))
    starts: list[object] = []
    monkeypatch.setattr(
        app, "start_tensorboard", lambda *a, **k: (starts.append(1), _StubProc(None))[1]
    )
    monkeypatch.setattr(app, "is_tensorboard_up", lambda *a, **k: False)
    # Defensive: on a mutant that drops the early-return guard, on_tensorboard()
    # would fall through into _poll_tensorboard_ready()'s real socket probe;
    # stub it so that can never reach 127.0.0.1:6006 for real either way.
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *a, **k: False)
    try:
        tk_root.update()
        gui._tensorboard_proc = _StubProc(returncode=None)  # already starting/running
        gui.on_tensorboard()
        assert starts == []
    finally:
        gui.container.destroy()
