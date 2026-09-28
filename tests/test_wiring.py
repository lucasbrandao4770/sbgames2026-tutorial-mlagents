"""T6g: the behaviour behind each widget, driven through the widget itself.

The review G1-T (local_files/build/launcher/gates/g1/T.md) showed that the suite calls the
app's handler methods and never its widgets, so a wrongly wired button passes every test.
Each test here presses the real widget instead: Button.invoke(), the command main()
registers for the window's close button, the real <<ComboboxSelected>> event, and the real
run-conflict dialog's buttons. Everything runs on the shared withdrawn root from
tests/conftest.py, with a stand-in process injected through gui._process_factory: nothing
is mapped, no process is started, no socket or browser is opened.
"""

from __future__ import annotations

import sys
import threading
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

_REAL_APP_CLASS = app.CentralDeTreinoApp

_CONFIG_TEXT = (
    "behaviors:\n"
    "  FlappyAgent:\n"
    "    trainer_type: ppo\n"
    "    max_steps: 50000\n"
    "    hyperparameters:\n"
    "      batch_size: 256\n"
)


# ----------------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------------


def _repo(tmp_path: Path) -> Path:
    """A fake repo with the tutorial's three documented configs and a macOS build."""
    root = tmp_path / "repo"
    for relative in (
        "ppo/FlappyBird_ppo.yaml",
        "imitation/FlappyBird_run1.yaml",
        "desafio/FlappyBird_desafio.yaml",
    ):
        path = root / "python" / "configs" / relative
        path.parent.mkdir(parents=True)
        path.write_text(_CONFIG_TEXT)
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    return root


def _python_bin(tmp_path: Path) -> Path:
    """A venv-shaped bin dir that satisfies resolve_for_execution; never executed."""
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    (bin_dir / "mlagents-learn").touch()
    python_bin = bin_dir / "python3"
    python_bin.touch()
    return python_bin


def _make_run(repo: Path, name: str) -> None:
    """A fully trained run in results/: configuration.yaml, .onnx and checkpoint."""
    run_dir = repo / "results" / name
    (run_dir / "FlappyAgent").mkdir(parents=True)
    (run_dir / "configuration.yaml").write_text(_CONFIG_TEXT)
    (run_dir / "FlappyAgent.onnx").touch()
    (run_dir / "FlappyAgent" / "checkpoint.pt").touch()


class _StandInProcess:
    """Stand-in for ManagedProcess that records what the app asks of it.

    It ignores the graceful stop, like a trainer stuck on Ctrl+C, so only force_kill() or
    the test itself ends it; after a graceful request, its timeout counts as elapsed.
    """

    def __init__(self) -> None:
        self.graceful_timeout_s = 30.0
        self.args: list[str] = []
        self.running = False
        self.graceful_requests = 0
        self.kills = 0

    def start(self) -> None:
        self.running = True

    def poll_output(self) -> list[str]:
        return []

    def is_running(self) -> bool:
        return self.running

    @property
    def returncode(self) -> int | None:
        return None if self.running else 0

    def finish_reading(self, timeout: float = 2.0) -> list[str]:
        del timeout
        return []

    def request_graceful_stop(self) -> None:
        self.graceful_requests += 1

    def graceful_timeout_elapsed(self) -> bool:
        return self.graceful_requests > 0

    def force_kill(self) -> None:
        self.kills += 1
        self.running = False


def _build(
    root: tk.Tk, repo: Path, python_bin: Path | None, process: _StandInProcess
) -> app.CentralDeTreinoApp:
    gui = _REAL_APP_CLASS(root, repo_root=repo, python_bin=python_bin)

    def _factory(args: list[str], cwd: Path) -> _StandInProcess:
        del cwd
        process.args = list(args)
        return process

    gui._process_factory = _factory
    return gui


def _poll_once(gui: app.CentralDeTreinoApp, root: tk.Tk) -> None:
    """Run one tick of the app's own poll loop now, instead of waiting 100 ms for it."""
    if gui._poll_job is not None:
        root.after_cancel(gui._poll_job)
        gui._poll_job = None
    if gui._process is not None:
        gui._poll_process()


def _end_process(gui: app.CentralDeTreinoApp, root: tk.Tk, process: _StandInProcess) -> None:
    """The stand-in ends; the app's own poll loop reaps it (and cancels its timers)."""
    process.running = False
    _poll_once(gui, root)


def _teardown(gui: app.CentralDeTreinoApp, root: tk.Tk, process: _StandInProcess) -> None:
    _end_process(gui, root, process)
    for job in (gui._poll_job, gui._force_stop_job, gui._watch_time_limit_job):
        if job is not None:
            root.after_cancel(job)
    gui.container.destroy()


def _buttons_in_order(widget: tk.Misc) -> list[ttk.Button]:
    """Every ttk.Button under widget, in creation (and on-screen) order."""
    found: list[ttk.Button] = []
    for child in widget.winfo_children():
        if isinstance(child, ttk.Button):
            found.append(child)
        found.extend(_buttons_in_order(child))
    return found


def _config_label(gui: app.CentralDeTreinoApp, filename: str) -> str:
    """The dropdown entry of a config file, read from the combobox itself."""
    values = [str(value) for value in gui._config_combo.cget("values")]
    return next(value for value in values if Path(value).name == filename)


def _choose_config(gui: app.CentralDeTreinoApp, filename: str) -> None:
    """What the attendee does: pick an entry, which makes Tk fire <<ComboboxSelected>>."""
    combo = gui._config_combo
    combo.set(_config_label(gui, filename))
    combo.event_generate("<<ComboboxSelected>>")


# ----------------------------------------------------------------------------
# G1-T-1: Iniciar, Parar, Forçar parada and the window's close button.
# ----------------------------------------------------------------------------


def test_g1t1_iniciar_button_starts_the_training(tk_root: tk.Tk, tmp_path: Path) -> None:
    """G1-T-1: pressing Iniciar on the Treinar tab launches the training of the preview."""
    repo = _repo(tmp_path)
    process = _StandInProcess()
    gui = _build(tk_root, repo, _python_bin(tmp_path), process)
    tk_root.update()
    try:
        gui.start_button.invoke()
        assert process.running, "Iniciar launched nothing"
        assert "--run-id=ppo1" in process.args
        assert any(arg.endswith("FlappyBird_ppo.yaml") for arg in process.args)
        assert gui.start_button.instate(["disabled"])
        assert not gui.stop_button.instate(["disabled"])
    finally:
        _teardown(gui, tk_root, process)


def test_g1t1_parar_button_asks_for_a_graceful_stop_and_never_kills(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """G1-T-1: Parar asks the trainer to stop gracefully (it then exports the model) and
    never kills it.
    """
    repo = _repo(tmp_path)
    process = _StandInProcess()
    gui = _build(tk_root, repo, _python_bin(tmp_path), process)
    tk_root.update()
    try:
        gui.start_button.invoke()
        assert process.running
        gui.stop_button.invoke()
        assert (process.graceful_requests, process.kills) == (1, 0)
        assert process.running, "the trainer must be left to wind down by itself"
    finally:
        _teardown(gui, tk_root, process)


def test_g1t1_forcar_parada_button_kills(tk_root: tk.Tk, tmp_path: Path) -> None:
    """G1-T-1: Forçar parada, offered once the graceful stop timed out, kills the trainer."""
    repo = _repo(tmp_path)
    process = _StandInProcess()
    gui = _build(tk_root, repo, _python_bin(tmp_path), process)
    tk_root.update()
    try:
        gui.start_button.invoke()
        gui.stop_button.invoke()  # the stand-in ignores it, like a stuck trainer
        assert gui.force_button.instate(["disabled"])
        _poll_once(gui, tk_root)  # the graceful timeout has elapsed: Forçar parada is offered
        assert not gui.force_button.instate(["disabled"])
        gui.force_button.invoke()
        assert process.kills == 1
        assert not process.running
    finally:
        _teardown(gui, tk_root, process)


def test_g1t1_window_close_button_asks_first_then_stops_gracefully_and_closes(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G1-T-1: the window's close button, as main() wires it (WM_DELETE_WINDOW), asks first
    while a training runs: "no" leaves it running; "yes" asks for a graceful stop, never a
    kill, and the window closes once the trainer has ended.
    """
    repo = _repo(tmp_path)
    python_bin = _python_bin(tmp_path)
    process = _StandInProcess()
    built: list[app.CentralDeTreinoApp] = []
    destroyed: list[bool] = []
    asked: list[str] = []
    answers = iter([False, True])

    def _build_on_shared_root(root: tk.Tk, repo_root: Path) -> app.CentralDeTreinoApp:
        gui = _build(root, repo_root, python_bin, process)
        built.append(gui)
        return gui

    def _answer(title: str = "", message: str = "", **_kwargs: object) -> bool:
        asked.append(message)
        return next(answers)

    # main() runs for real on the shared withdrawn root: its window calls and its event
    # loop are no-ops on this instance, and destroy() is recorded instead of performed.
    monkeypatch.setattr(app, "ensure_tcl_tk_discoverable", lambda: None)
    monkeypatch.setattr(app.tk, "Tk", lambda: tk_root)
    monkeypatch.setattr(app, "CentralDeTreinoApp", _build_on_shared_root)
    monkeypatch.chdir(repo)
    for name in ("title", "geometry", "minsize", "mainloop"):
        monkeypatch.setattr(tk_root, name, lambda *_a, **_k: None)
    monkeypatch.setattr(tk_root, "destroy", lambda: destroyed.append(True))
    monkeypatch.setattr(app.messagebox, "askyesno", _answer)
    tk_root.protocol("WM_DELETE_WINDOW", "")
    close_command = ""
    try:
        app.main()
        assert len(built) == 1
        gui = built[0]
        close_command = str(tk_root.protocol("WM_DELETE_WINDOW"))
        assert close_command, "main() wired nothing to the window's close button"
        gui.start_button.invoke()
        assert process.running

        tk_root.tk.call(close_command)  # the attendee clicks the close button, answers "no"
        assert (len(asked), process.graceful_requests, process.kills) == (1, 0, 0)
        assert process.running
        assert destroyed == []

        tk_root.tk.call(close_command)  # clicks it again, answers "yes"
        assert (len(asked), process.graceful_requests, process.kills) == (2, 1, 0)
        assert destroyed == [], "the window closed before the trainer ended"

        _end_process(gui, tk_root, process)  # the trainer ends after its final export
        assert destroyed == [True]
    finally:
        tk_root.protocol("WM_DELETE_WINDOW", "")
        if close_command:
            tk_root.deletecommand(close_command)
        for gui in built:
            _teardown(gui, tk_root, process)


# ----------------------------------------------------------------------------
# G1-T-2: the real run-conflict dialog, each of its buttons found by position.
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("position", "action"),
    [(0, "rename"), (1, "resume"), (2, "force"), (3, None)],
    ids=["first_renames", "second_resumes", "third_overwrites", "fourth_cancels"],
)
def test_g1t2_real_conflict_dialog_buttons_launch_the_chosen_run(
    tk_root: tk.Tk,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    position: int,
    action: str | None,
) -> None:
    """G1-T-2: Iniciar on an existing run opens the real conflict dialog; its buttons, in
    order, rename to a free name, resume, overwrite (--force) or cancel, and the app
    launches exactly that choice.
    """
    repo = _repo(tmp_path)
    _make_run(repo, "ppo1")
    process = _StandInProcess()
    gui = _build(tk_root, repo, _python_bin(tmp_path), process)
    next_free = app.next_available_run_name(repo, "ppo1")
    expected_choice = {
        "rename": ("rename", next_free),
        "resume": ("resume", "ppo1"),
        "force": ("force", "ppo1"),
        None: None,
    }[action]
    button_counts: list[int] = []
    returned: list[tuple[str, str] | None] = []
    real_ask: Callable[[str], tuple[str, str] | None] = gui._ask_run_conflict

    def _press_button(widget: tk.Misc, window: tk.Misc | None = None) -> None:
        buttons = _buttons_in_order(window if window is not None else widget)
        button_counts.append(len(buttons))
        buttons[position].invoke()

    def _ask_and_record(run_name: str) -> tuple[str, str] | None:
        choice = real_ask(run_name)
        returned.append(choice)
        return choice

    # The dialog is never mapped: it is transient to the withdrawn root and nothing pumps
    # the event loop while it exists. wait_visibility() and grab_set() are replaced on
    # Toplevel only, so the window guard still covers the root; wait_window(), on any
    # widget, presses one of the dialog's real buttons instead of waiting for the attendee.
    monkeypatch.setattr(tk.Toplevel, "wait_visibility", lambda self, window=None: None)
    monkeypatch.setattr(tk.Toplevel, "grab_set", lambda self: None)
    monkeypatch.setattr(tk.Misc, "wait_window", _press_button)
    gui._ask_run_conflict = _ask_and_record
    tk_root.update()
    try:
        gui.start_button.invoke()
        assert button_counts == [4], "the dialog must offer rename, resume, overwrite, cancel"
        assert returned == [expected_choice]
        if action is None:
            assert not process.running, "Cancelar must not launch anything"
            return
        assert process.running
        run_ids = [arg for arg in process.args if arg.startswith("--run-id=")]
        assert run_ids == [f"--run-id={next_free if action == 'rename' else 'ppo1'}"]
        assert ("--resume" in process.args) is (action == "resume")
        assert ("--force" in process.args) is (action == "force")
    finally:
        _teardown(gui, tk_root, process)


# ----------------------------------------------------------------------------
# G1-T-4: the configuration dropdown, through its real <<ComboboxSelected>> event.
# ----------------------------------------------------------------------------


def test_g1t4_config_dropdown_event_applies_each_configs_defaults(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """G1-T-4: choosing a config in the real dropdown applies that config's own run name
    and game-window default, and the command preview follows.
    """
    process = _StandInProcess()
    gui = _build(tk_root, _repo(tmp_path), None, process)
    tk_root.update()
    try:
        assert (gui.run_name_var.get(), gui.show_window_var.get()) == ("ppo1", True)
        cases = [
            ("FlappyBird_run1.yaml", "il1", False),
            ("FlappyBird_desafio.yaml", "ppo2", False),
            ("FlappyBird_ppo.yaml", "ppo1", True),
        ]
        for filename, run_name, show_window in cases:
            _choose_config(gui, filename)
            assert (gui.run_name_var.get(), gui.show_window_var.get()) == (run_name, show_window)
            assert f"--run-id={run_name}" in gui.command_var.get()
    finally:
        _teardown(gui, tk_root, process)


# ----------------------------------------------------------------------------
# G1-T-3: the run just trained is preselected in Assistir, over an older choice.
# ----------------------------------------------------------------------------


def test_g1t3_new_run_is_preselected_over_the_previous_choice(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """G1-T-3: after Module 2's il1 ends, Assistir preselects il1, not Module 1's ppo1 that
    was selected before. With a single run, as in test_flow's B1 test, the fallback to the
    first run hides a missing preselection.
    """
    repo = _repo(tmp_path)
    _make_run(repo, "ppo1")
    process = _StandInProcess()
    gui = _build(tk_root, repo, _python_bin(tmp_path), process)
    tk_root.update()
    try:
        assert gui.watch_run_var.get() == "ppo1"  # Module 1's run, selected
        _choose_config(gui, "FlappyBird_run1.yaml")  # Module 2
        assert gui.run_name_var.get() == "il1"
        gui.start_button.invoke()
        assert "--run-id=il1" in process.args
        _make_run(repo, "il1")  # what the trainer writes
        _end_process(gui, tk_root, process)
        assert set(gui._run_combo.cget("values")) == {"il1", "ppo1"}
        assert gui.watch_run_var.get() == "il1"
    finally:
        _teardown(gui, tk_root, process)


# ----------------------------------------------------------------------------
# G1-T-7: TensorBoard becomes ready and the browser opens.
# ----------------------------------------------------------------------------


class _InlineThread:
    """Runs its target at start(), in the calling (Tk) thread: no thread ever exists."""

    def __init__(self, target: Callable[[], None], daemon: bool | None = None) -> None:
        del daemon
        self._target = target

    def start(self) -> None:
        self._target()


class _RunningTensorBoard:
    """Stand-in for the TensorBoard Popen: still starting, never exits by itself."""

    def poll(self) -> int | None:
        return None


def test_g1t7_tensorboard_button_opens_the_browser_once_ready(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """G1-T-7: the TensorBoard button starts TensorBoard, the readiness probe finds it up,
    and the browser opens once on its address. The probe runs inline, so no thread is left.
    """
    repo = _repo(tmp_path)
    started: list[Path] = []
    opened: list[str] = []

    def _start(python_bin: Path, repo_root: Path) -> _RunningTensorBoard:
        del python_bin
        started.append(repo_root)
        return _RunningTensorBoard()

    monkeypatch.setattr(app, "start_tensorboard", _start)
    # The port answers only once TensorBoard was started: the app asks the port first,
    # and a port that always answers would mean "already running, just open the page".
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_k: bool(started))
    monkeypatch.setattr(app.webbrowser, "open", lambda url, *_a, **_k: opened.append(url))
    monkeypatch.setattr(app, "threading", SimpleNamespace(Thread=_InlineThread))
    process = _StandInProcess()
    gui = _build(tk_root, repo, None, process)
    threads_before = set(threading.enumerate())
    tk_root.update()
    try:
        buttons = [
            button
            for button in _buttons_in_order(gui.container)
            if "tensorboard" in str(button.cget("text")).lower()
        ]
        assert len(buttons) == 1
        buttons[0].invoke()
        tk_root.update()  # runs the probe's after(0, ...) hand-back on the Tk thread
        assert started == [repo]
        assert opened == [app.TENSORBOARD_URL]
        assert not set(threading.enumerate()) - threads_before
    finally:
        gui._tensorboard_proc = None
        _teardown(gui, tk_root, process)
