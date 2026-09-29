"""Round 2 regression tests for the Central de treino (task T6f, gate G1 findings).

Covers R1 to R8 of the T6f brief: one stop request per run (G1-P-1, G1-U-1), module
defaults that come back on a config change (G1-P-5, G1-U-3), the name-conflict dialog
(G1-U-4), no second trainer (G1-P-3, G1-U-12), the Treinar list (N2, G1-U-6), a slow stop
that points to Forçar parada (G1-P-2), the time limit field (m9) and the empty name
(G1-U-9). All were open at efe0fed: every test that fails there is a strict xfail that the
fix turns green, and the few tests that pass there guard what the fix must keep.

Every test builds the real CentralDeTreinoApp on the session's withdrawn root
(tests/conftest.py) and injects a counting stand-in process through the app's
_process_factory seam. Tk's after()/after_cancel() run on a virtual clock that the test
advances by hand, so the 100 ms poll, the 30 s force-stop timer and the watch time limit
fire in order without waiting. No process starts, no window or dialog is mapped: the
conflict dialog is created withdrawn and its buttons are invoked, and the root's destroy()
is recorded instead of performed.
"""

from __future__ import annotations

import contextlib
import shlex
import shutil
import sys
import tkinter as tk
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from tkinter import ttk

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

TESTS_DIR = Path(__file__).resolve().parent
REAL_CONFIGS_DIR = TESTS_DIR.parent / "python" / "configs"

# The configurations of Modules 1, 2 and 3, in module order, with the run name and the
# "Mostrar a janela do jogo" box that each module uses in the docs and slides.
MODULE_DEFAULTS: dict[str, tuple[str, bool]] = {
    "FlappyBird_ppo.yaml": ("ppo1", True),
    "FlappyBird_run1.yaml": ("il1", False),
    "FlappyBird_desafio.yaml": ("ppo2", False),
}
MODULE_CONFIG_DIRS = {
    "FlappyBird_ppo.yaml": "ppo",
    "FlappyBird_run1.yaml": "imitation",
    "FlappyBird_desafio.yaml": "desafio",
}
# Run names the tutorial gives to its own steps. A suggested name is never one of them.
TUTORIAL_RUN_NAMES = frozenset({"ppo1", "ppo2", "il1", "il2", "il3"})
_BEHAVIOR_CONFIG = "behaviors:\n  FlappyAgent:\n    trainer_type: ppo\n    max_steps: 50000\n"
GRACEFUL_STOP_MS = 30_000
ONE_MINUTE_MS = 60_000


# ----------------------------------------------------------------------------
# Virtual clock for Tk's after()
# ----------------------------------------------------------------------------


@dataclass
class _Job:
    due_ms: int
    seq: int
    func: Callable[..., object]
    args: tuple[object, ...]


class VirtualClock:
    """Tk's after()/after_cancel() on a clock that only moves when the test advances it.

    A callback that raises propagates to the test, which is what a real Tk loop would
    report through report_callback_exception while its poll chain dies.
    """

    def __init__(self) -> None:
        self.now_ms = 0
        self._seq = 0
        self._jobs: dict[str, _Job] = {}

    def schedule(
        self, ms: int, func: Callable[..., object] | None, args: tuple[object, ...]
    ) -> str:
        assert func is not None, "after() without a callback would block the Tk thread"
        self._seq += 1
        job_id = f"virtual-after#{self._seq}"
        self._jobs[job_id] = _Job(self.now_ms + int(ms), self._seq, func, args)
        return job_id

    def cancel(self, job_id: str) -> None:
        if not job_id:
            raise ValueError("id must be a valid identifier returned from after or after_idle")
        self._jobs.pop(job_id, None)

    def advance_to(self, target_ms: int) -> None:
        """Move the clock to target_ms, running every job that falls due, in due order."""
        while True:
            due = [(job.due_ms, job.seq, key) for key, job in self._jobs.items()]
            due = [entry for entry in due if entry[0] <= target_ms]
            if not due:
                break
            due_ms, _seq, key = min(due)
            job = self._jobs.pop(key)
            self.now_ms = max(self.now_ms, due_ms)
            job.func(*job.args)
        self.now_ms = max(self.now_ms, target_ms)

    def advance(self, ms: int) -> None:
        self.advance_to(self.now_ms + ms)

    def pending_due_after(self, ms: int) -> list[int]:
        """Due times of the pending jobs that fall due after ms."""
        return sorted(job.due_ms for job in self._jobs.values() if job.due_ms > ms)


# ----------------------------------------------------------------------------
# The process the app runs: a stand-in that counts stop requests
# ----------------------------------------------------------------------------


class CountingProcess(app.ManagedProcess):
    """The app's own process class with every OS call replaced by a scripted stand-in.

    It counts request_graceful_stop() calls and keeps running until the test ends it, so
    a second click can land while a stop is in progress. graceful_timeout_elapsed() reads
    the virtual clock the way the real one reads time.monotonic(): from the latest request.
    """

    def __init__(self, args: list[str], cwd: Path, clock: VirtualClock, repo: Path) -> None:
        super().__init__(args, cwd, python_bin=Path(sys.executable))
        self.clock = clock
        self.started = False
        self.running = False
        self.stop_requests = 0
        self._last_stop_ms: int | None = None
        self.run_id = next((a.split("=", 1)[1] for a in args if a.startswith("--run-id=")), "")
        self.initialize_from = next(
            (a.split("=", 1)[1] for a in args if a.startswith("--initialize-from=")), None
        )
        # Whether results/<run id> was there when the app launched this process.
        self.run_folder_existed = (repo / "results" / self.run_id).is_dir()

    def start(self) -> None:
        self.started = True
        self.running = True
        self.output_queue.put("[INFO] Connected to Unity environment with package version 4.1.0")
        if self.initialize_from is not None:
            self.output_queue.put(
                f"[INFO] Initializing from results/{self.initialize_from}/FlappyAgent/checkpoint.pt."
            )

    def is_running(self) -> bool:
        return self.running

    @property
    def returncode(self) -> int | None:
        return None if self.running else 0

    def request_graceful_stop(self) -> None:
        self.stop_requests += 1
        self._last_stop_ms = self.clock.now_ms

    def graceful_timeout_elapsed(self) -> bool:
        if self._last_stop_ms is None:
            return False
        return self.clock.now_ms - self._last_stop_ms >= self.graceful_timeout_s * 1000

    def force_kill(self) -> None:
        self.running = False


# ----------------------------------------------------------------------------
# Fixtures: message boxes, the conflict dialog, the app harness
# ----------------------------------------------------------------------------


@dataclass
class MessageBoxes:
    """Every messagebox call; every ask* call answers `answer` (True is Sim)."""

    answer: bool = True
    asked: list[str] = field(default_factory=list)
    shown: list[tuple[str, str]] = field(default_factory=list)


@pytest.fixture
def boxes(monkeypatch: pytest.MonkeyPatch) -> MessageBoxes:
    stub = MessageBoxes()

    def _ask(kind: str) -> Callable[..., object]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> object:
            stub.asked.append(f"{kind}: {message}")
            if kind == "askquestion":
                return "yes" if stub.answer else "no"
            return stub.answer

        return _fn

    def _show(kind: str) -> Callable[..., str]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> str:
            stub.shown.append((kind, message))
            return "ok"

        return _fn

    for kind in ("askyesno", "askokcancel", "askquestion", "askyesnocancel", "askretrycancel"):
        monkeypatch.setattr(app.messagebox, kind, _ask(kind))
    for kind in ("showerror", "showwarning", "showinfo"):
        monkeypatch.setattr(app.messagebox, kind, _show(kind))
    return stub


def _descendants(widget: tk.Misc) -> list[tk.Misc]:
    found: list[tk.Misc] = []
    for child in widget.winfo_children():
        found.append(child)
        found.extend(_descendants(child))
    return found


def _buttons_in(window: tk.Misc) -> list[tk.Misc]:
    """The buttons of a window, in creation order (the order the dialog shows them)."""
    return [w for w in _descendants(window) if isinstance(w, (ttk.Button, tk.Button))]


def _text_in(window: tk.Misc) -> str:
    """Every text a window shows outside its buttons: labels, messages, entries."""
    parts: list[str] = []
    for widget in _descendants(window):
        if isinstance(widget, (ttk.Label, tk.Label, tk.Message)):
            parts.append(str(widget.cget("text")))
        elif isinstance(widget, (ttk.Entry, tk.Entry)):
            parts.append(widget.get())
    return "\n".join(parts)


@dataclass
class SeenDialog:
    text: str
    buttons: list[str]


Responder = Callable[[tk.Toplevel, list[tk.Misc]], None]


@dataclass
class ConflictDialogs:
    """The dialogs the app opened; `respond` acts for the user (default: first button)."""

    seen: list[SeenDialog] = field(default_factory=list)
    respond: Responder | None = None


@pytest.fixture
def conflict_dialogs(monkeypatch: pytest.MonkeyPatch) -> ConflictDialogs:
    """Every Toplevel the app creates is withdrawn at birth, and wait_window() hands it to
    the test instead of blocking, so the real dialog code runs without being mapped."""
    recorder = ConflictDialogs()
    real_toplevel = tk.Toplevel

    class WithdrawnDialog(real_toplevel):  # type: ignore[misc, valid-type]
        def __init__(self, *args: object, **kwargs: object) -> None:
            super().__init__(*args, **kwargs)
            self.withdraw()

        def wait_visibility(self, window: object = None) -> None:
            return None

        def grab_set(self) -> None:
            return None

        def wait_window(self, window: object = None) -> None:
            buttons = _buttons_in(self)
            recorder.seen.append(SeenDialog(_text_in(self), [str(b.cget("text")) for b in buttons]))
            if recorder.respond is not None:
                recorder.respond(self, buttons)
            elif buttons:
                buttons[0].invoke()
            if self.winfo_exists():
                self.destroy()

    monkeypatch.setattr(tk, "Toplevel", WithdrawnDialog)
    return recorder


def _press(fragment: str) -> Responder:
    """A responder that clicks the first button whose text contains fragment."""

    def _respond(_dialog: tk.Toplevel, buttons: list[tk.Misc]) -> None:
        labels = [str(b.cget("text")) for b in buttons]
        matching = [b for b, text in zip(buttons, labels) if fragment in text.lower()]
        assert matching, f"no button with {fragment!r}: {labels}"
        matching[0].invoke()

    return _respond


@dataclass
class Harness:
    gui: app.CentralDeTreinoApp
    root: tk.Tk
    repo: Path
    clock: VirtualClock
    processes: list[CountingProcess] = field(default_factory=list)
    # One entry per root.destroy() call: the run ids still running at that moment.
    destroy_calls: list[list[str]] = field(default_factory=list)
    unexpected: list[str] = field(default_factory=list)

    @property
    def started(self) -> list[CountingProcess]:
        return [process for process in self.processes if process.started]

    def end_processes(self) -> None:
        """Every running process exits; the app notices on its next poll tick."""
        for process in self.processes:
            process.running = False
        self.clock.advance(200)


def _placeholder_python_bin(tmp_path: Path) -> Path:
    """A venv-shaped bin dir that only satisfies resolve_for_execution; nothing runs it."""
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir(exist_ok=True)
    (bin_dir / "mlagents-learn").write_text("")
    python_bin = bin_dir / "python3"
    python_bin.write_text("")
    return python_bin


_MISSING = object()


@contextlib.contextmanager
def _instance_attributes(obj: object, **values: object) -> Iterator[None]:
    """Set attributes on obj itself, then put back exactly the entries it had before.

    Not monkeypatch.setattr: on an instance, its undo leaves the old bound method behind as
    an instance attribute (tests/test_lifecycle_status.py leaves one on the shared root's
    after()), and such an entry shadows any class-level patch for the rest of the session.
    """
    saved = {name: vars(obj).get(name, _MISSING) for name in values}
    vars(obj).update(values)
    try:
        yield
    finally:
        for name, old in saved.items():
            if old is _MISSING:
                vars(obj).pop(name, None)
            else:
                vars(obj)[name] = old


@pytest.fixture
def make_app(
    tk_root: tk.Tk, boxes: MessageBoxes, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[Callable[[Path], Harness]]:
    """Build the real app on the shared root, with the virtual clock and the stand-in."""
    clock = VirtualClock()
    built: list[Harness] = []

    def _after(ms: int, func: Callable[..., object] | None = None, *args: object) -> str:
        return clock.schedule(ms, func, args)

    def _after_cancel(job_id: str) -> None:
        clock.cancel(job_id)

    def _widget_after(
        _widget: tk.Misc, ms: int, func: Callable[..., object] | None = None, *args: object
    ) -> str:
        return clock.schedule(ms, func, args)

    def _widget_after_cancel(_widget: tk.Misc, job_id: str) -> None:
        clock.cancel(job_id)

    def _record_destroy() -> None:
        harness = built[-1]
        harness.destroy_calls.append([p.run_id for p in harness.processes if p.running])

    # The root's own entries win over the class, and cover self.root.after(); the class
    # patch covers after() called on any other widget of the app.
    monkeypatch.setattr(tk.Misc, "after", _widget_after)
    monkeypatch.setattr(tk.Misc, "after_cancel", _widget_after_cancel)

    def make(repo: Path) -> Harness:
        gui = app.CentralDeTreinoApp(
            tk_root, repo_root=repo, python_bin=_placeholder_python_bin(tmp_path)
        )
        harness = Harness(gui=gui, root=tk_root, repo=repo, clock=clock)

        def factory(args: list[str], cwd: Path) -> app.ManagedProcess:
            process = CountingProcess(args, cwd, clock, repo)
            harness.processes.append(process)
            return process

        def error_dialog(*, message: str, log_path: Path) -> None:
            harness.unexpected.append(f"{message} ({log_path})")

        gui._process_factory = factory  # the app's documented test seam
        gui._show_error_dialog = error_dialog  # never a real Toplevel
        built.append(harness)
        tk_root.update()
        return harness

    # destroy() is recorded, not performed: the session root must survive this test.
    with _instance_attributes(
        tk_root, after=_after, after_cancel=_after_cancel, destroy=_record_destroy
    ):
        try:
            yield make
        finally:
            for harness in built:
                for process in harness.processes:
                    process.running = False
                with contextlib.suppress(Exception):
                    clock.advance(1_000)
                harness.gui.container.destroy()


# ----------------------------------------------------------------------------
# Repo and widget helpers
# ----------------------------------------------------------------------------


def _make_repo(tmp_path: Path, *, real_configs: bool = False) -> Path:
    """A fake repo: the three module configs (or a copy of the real python/configs/), an
    empty results/ and a macOS game build."""
    root = tmp_path / "repo"
    configs = root / "python" / "configs"
    if real_configs:
        shutil.copytree(REAL_CONFIGS_DIR, configs)
    else:
        for filename, folder in MODULE_CONFIG_DIRS.items():
            (configs / folder).mkdir(parents=True, exist_ok=True)
            (configs / folder / filename).write_text(_BEHAVIOR_CONFIG)
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    return root


def _make_trained_run(repo: Path, name: str) -> None:
    """results/<name> as a finished run leaves it: configuration, checkpoint and model."""
    run_dir = repo / "results" / name
    (run_dir / "FlappyAgent").mkdir(parents=True)
    (run_dir / "configuration.yaml").write_text(_BEHAVIOR_CONFIG)
    (run_dir / "FlappyAgent" / "checkpoint.pt").write_bytes(b"pt")
    (run_dir / "FlappyAgent.onnx").write_bytes(b"onnx")


def _make_failed_run(repo: Path, name: str) -> None:
    """results/<name> as a first try that failed at start leaves it: no model at all."""
    run_dir = repo / "results" / name
    (run_dir / "run_logs").mkdir(parents=True)
    (run_dir / "run_logs" / "timers.json").write_text("{}")
    (run_dir / "configuration.yaml").write_text(_BEHAVIOR_CONFIG)


def _widget_for_variable(
    gui: app.CentralDeTreinoApp, kind: type, option: str, variable: tk.Variable
) -> tk.Misc:
    for widget in _descendants(gui.container):
        if isinstance(widget, kind) and str(widget.cget(option)) == str(variable):
            return widget
    raise AssertionError(f"no {kind.__name__} bound to {variable}")


def _config_list(gui: app.CentralDeTreinoApp) -> ttk.Combobox:
    combo = _widget_for_variable(gui, ttk.Combobox, "textvariable", gui.config_var)
    assert isinstance(combo, ttk.Combobox)
    return combo


def _config_labels(gui: app.CentralDeTreinoApp) -> list[str]:
    values = _config_list(gui).cget("values")
    if isinstance(values, str):
        values = gui.root.tk.splitlist(values)
    return [str(value) for value in values]


def _choose_config_label(gui: app.CentralDeTreinoApp, label: str) -> None:
    """What Tk does when the user picks label in the Configuração list."""
    combo = _config_list(gui)
    combo.set(label)
    combo.event_generate("<<ComboboxSelected>>")


def _choose_config(gui: app.CentralDeTreinoApp, filename: str) -> None:
    labels = [label for label in _config_labels(gui) if filename in label]
    if not labels:  # a label without the file name: fall back to the app's own mapping
        mapping = getattr(gui, "_config_by_label", {})
        labels = [label for label, path in mapping.items() if Path(path).name == filename]
    assert labels, f"{filename} is not offered: {_config_labels(gui)}"
    _choose_config_label(gui, labels[0])


def _type_run_name(gui: app.CentralDeTreinoApp, text: str) -> None:
    """Clear the Nome do treino field and type text into it."""
    entry = _widget_for_variable(gui, ttk.Entry, "textvariable", gui.run_name_var)
    entry.delete(0, "end")
    if text:
        entry.insert(0, text)


def _set_window_box(gui: app.CentralDeTreinoApp, checked: bool) -> None:
    """Click "Mostrar a janela do jogo" if it is not already in the wanted state."""
    box = _widget_for_variable(gui, ttk.Checkbutton, "variable", gui.show_window_var)
    if bool(gui.show_window_var.get()) != checked:
        box.invoke()


def _name_and_box(gui: app.CentralDeTreinoApp) -> tuple[str, bool]:
    return gui.run_name_var.get(), bool(gui.show_window_var.get())


def _config_file_in_preview(gui: app.CentralDeTreinoApp) -> str:
    tokens = shlex.split(gui.command_var.get())
    yaml_tokens = [token for token in tokens if token.endswith(".yaml")]
    return Path(yaml_tokens[0]).name if yaml_tokens else f"<preview: {gui.command_var.get()!r}>"


def _open_watch_tab(harness: Harness) -> None:
    harness.gui.notebook.select(1)
    harness.root.update()
    harness.gui.watch_run_var.set("ppo1")


def _points_to_force_stop(status: str) -> bool:
    lowered = status.lower()
    slow = any(word in lowered for word in ("ainda", "demor", "lent", "levando"))
    return "forçar parada" in lowered and slow


def _says_no_model_saved(text: str) -> bool:
    lowered = text.lower()
    return "modelo" in lowered and any(word in lowered for word in ("não", "nenhum", "sem "))


def _says_name_missing(message: str) -> bool:
    lowered = message.lower()
    missing = ("digite", "vazio", "falta", "preencha", "escreva", "em branco", "sem nome")
    return "nome" in lowered and "inválid" not in lowered and any(w in lowered for w in missing)


# ----------------------------------------------------------------------------
# R1: one stop request per run, whatever the user clicks (G1-P-1, G1-U-1)
# ----------------------------------------------------------------------------


def test_r1_parar_twice_sends_one_stop_request(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-P-1: Parar twice during a training sends the trainer exactly one stop request."""
    harness = make_app(_make_repo(tmp_path))
    harness.gui.on_start()
    harness.clock.advance(1_000)
    harness.gui.on_stop()
    harness.clock.advance(500)
    harness.gui.on_stop()
    assert [p.stop_requests for p in harness.started] == [1]


def test_r1_closing_twice_asks_once_stops_once_and_closes_after_the_end(
    make_app: Callable[[Path], Harness], boxes: MessageBoxes, tmp_path: Path
) -> None:
    """G1-U-1: X and Sim, then X again while stopping: no second question, no second stop
    request, and the window closes once the trainer has ended."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)
    gui.on_close()
    assert len(boxes.asked) == 1, f"the first close did not ask: {boxes.asked}"
    harness.clock.advance(1_000)
    assert [p.stop_requests for p in harness.started] == [1], "Sim did not stop the trainer"

    gui.on_close()

    assert len(boxes.asked) == 1, f"the second close asked again: {boxes.asked}"
    assert [p.stop_requests for p in harness.started] == [1]
    assert harness.destroy_calls == [], "the window closed while the trainer still ran"
    harness.end_processes()
    assert harness.destroy_calls == [[]], "the window did not close once the trainer ended"


def test_r1_close_after_parar_neither_asks_nor_signals_and_closes_after_the_end(
    make_app: Callable[[Path], Harness], boxes: MessageBoxes, tmp_path: Path
) -> None:
    """G1-P-1: Parar, then X: the close does not ask and sends no stop request; the window
    closes once the trainer has ended."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)
    gui.on_stop()
    harness.clock.advance(1_000)

    gui.on_close()

    assert boxes.asked == [], f"the close asked although a stop was in progress: {boxes.asked}"
    assert [p.stop_requests for p in harness.started] == [1]
    assert harness.destroy_calls == [], "the window closed while the trainer still ran"
    harness.end_processes()
    assert harness.destroy_calls == [[]], "the window did not close once the trainer ended"


def test_r1_time_limit_during_a_stop_sends_no_second_request_nor_rearms_the_force_timer(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-P-1: in a watch, the time limit falls due while a Parar is in progress: no second
    stop request, and Forçar parada still comes 30 s after Parar, not 30 s after the limit."""
    repo = _make_repo(tmp_path)
    _make_trained_run(repo, "ppo1")
    harness = make_app(repo)
    gui = harness.gui
    _open_watch_tab(harness)
    gui.no_time_limit_var.set(False)
    gui.time_limit_var.set("1")
    gui.on_start()
    assert len(harness.started) == 1, f"the watch did not start: {harness.unexpected}"
    parar_at = 50_000
    harness.clock.advance_to(parar_at)
    gui.on_stop()

    harness.clock.advance_to(ONE_MINUTE_MS + 1)  # the time limit falls due during the stop

    assert harness.started[0].stop_requests == 1
    later = harness.clock.pending_due_after(parar_at + GRACEFUL_STOP_MS)
    assert later == [], f"a timer was armed past 30 s after Parar, due at {later} ms"
    harness.clock.advance_to(parar_at + GRACEFUL_STOP_MS)
    assert gui.force_button.instate(["!disabled"]), "Forçar parada not offered 30 s after Parar"


def test_g2a_p4_sim_after_the_run_ended_by_itself_closes_at_once_and_leaves_no_mark(
    make_app: Callable[[Path], Harness],
    boxes: MessageBoxes,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """G2a-P-4: the training ends by itself while "Parar, salvar o modelo e fechar a
    Central?" is open: Sim closes
    the window at once, sends no stop, and leaves no closing mark that would close the
    window when the next run ends."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)

    def _run_ends_while_asking(title: str = "", message: str = "", **_kwargs: object) -> bool:
        boxes.asked.append(f"askyesno: {message}")
        harness.end_processes()  # the poll sees the end while the question is open
        return True

    monkeypatch.setattr(app.messagebox, "askyesno", _run_ends_while_asking)

    gui.on_close()

    assert len(boxes.asked) == 1, boxes.asked
    assert harness.destroy_calls == [[]], "Sim did not close the window at once"
    assert [p.stop_requests for p in harness.started] == [0]
    harness.destroy_calls.clear()  # this harness records destroy() and keeps the root
    gui.on_start()
    harness.clock.advance(1_000)
    harness.end_processes()
    assert harness.destroy_calls == [], "the next run's end closed the window by itself"


def test_g2a_p4_a_stale_closing_mark_does_not_survive_into_a_new_run(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G2a-P-4: a closing mark left over from an earlier run, whatever left it, is
    cleared when a new run starts, so that run's end does not close the window."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui._closing = True

    gui.on_start()
    harness.clock.advance(1_000)
    harness.end_processes()

    assert len(harness.started) == 1
    assert harness.destroy_calls == [], "a stale closing mark closed the window"


# ----------------------------------------------------------------------------
# R2: the module defaults come back on a config change (G1-P-5, G1-U-3)
# ----------------------------------------------------------------------------


@pytest.mark.parametrize("typed", ["meu_treino", "ppo1"])
@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("FlappyBird_ppo.yaml", "FlappyBird_run1.yaml"),
        ("FlappyBird_run1.yaml", "FlappyBird_desafio.yaml"),
        ("FlappyBird_desafio.yaml", "FlappyBird_ppo.yaml"),
    ],
    ids=["to_run1", "to_desafio", "to_ppo"],
)
def test_r2_another_config_after_a_typed_name_restores_its_defaults(
    make_app: Callable[[Path], Harness], tmp_path: Path, start: str, target: str, typed: str
) -> None:
    """G1-P-5: after the user typed a name (and clicked the window box), choosing another
    configuration sets the name and "Mostrar a janela do jogo" to that module's defaults."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    _choose_config(gui, start)
    _type_run_name(gui, typed)
    _set_window_box(gui, not MODULE_DEFAULTS[target][1])

    _choose_config(gui, target)

    assert _name_and_box(gui) == MODULE_DEFAULTS[target]


def test_r2_another_config_after_usar_outro_nome_restores_its_defaults(
    make_app: Callable[[Path], Harness], conflict_dialogs: ConflictDialogs, tmp_path: Path
) -> None:
    """G1-U-3: after "Usar outro nome" in the conflict dialog and the end of that run,
    choosing the Module 2 configuration gives il1 and an unmarked window box."""
    repo = _make_repo(tmp_path)
    _make_trained_run(repo, "ppo1")
    harness = make_app(repo)
    conflict_dialogs.respond = _press("outro nome")
    harness.gui.on_start()
    assert [p.run_id != "ppo1" for p in harness.started] == [True], "precondition: renamed run"
    harness.end_processes()

    _choose_config(harness.gui, "FlappyBird_run1.yaml")

    assert _name_and_box(harness.gui) == ("il1", False)


def test_r2_a_name_typed_after_choosing_the_config_stays_until_the_config_changes(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-P-5 (guard, passes at efe0fed): a name typed after the configuration was chosen
    survives the window box, a tab switch, a whole run and its end."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    _choose_config(gui, "FlappyBird_run1.yaml")
    assert _name_and_box(gui) == ("il1", False)
    _type_run_name(gui, "meu_il")
    _set_window_box(gui, True)
    gui.notebook.select(1)
    harness.root.update()
    gui.notebook.select(0)
    harness.root.update()
    assert gui.run_name_var.get() == "meu_il"

    gui.on_start()
    assert [p.run_id for p in harness.started] == ["meu_il"]
    harness.end_processes()

    assert gui.run_name_var.get() == "meu_il"


# ----------------------------------------------------------------------------
# R3: the name conflict dialog (G1-U-4)
# ----------------------------------------------------------------------------


def test_r3_conflict_without_a_saved_model_says_so_and_restarts_first(
    make_app: Callable[[Path], Harness], conflict_dialogs: ConflictDialogs, tmp_path: Path
) -> None:
    """G1-U-4: results/ppo1 holds no .onnx and no checkpoint.pt: the dialog says no model
    was saved, does not offer to continue, and its first choice restarts ppo1."""
    repo = _make_repo(tmp_path)
    _make_failed_run(repo, "ppo1")
    harness = make_app(repo)

    harness.gui.on_start()  # first button, by default

    assert len(conflict_dialogs.seen) == 1, "no conflict dialog"
    dialog = conflict_dialogs.seen[0]
    assert _says_no_model_saved(dialog.text), f"dialog text: {dialog.text!r}"
    assert not [b for b in dialog.buttons if "continu" in b.lower()], dialog.buttons
    assert len(harness.started) == 1, "the first choice started nothing"
    launched = harness.started[0]
    assert launched.run_id == "ppo1", f"the first choice ran {launched.run_id!r}"
    assert "--resume" not in launched.args
    assert "--force" in launched.args or not launched.run_folder_existed, launched.args


@pytest.mark.parametrize(
    ("config", "existing", "expected"),
    [
        ("FlappyBird_ppo.yaml", ("ppo1",), "ppo1b"),
        ("FlappyBird_run1.yaml", ("il1",), "il1b"),
        ("FlappyBird_desafio.yaml", ("ppo2",), "ppo2b"),
        ("FlappyBird_ppo.yaml", ("ppo1", "ppo1b"), "ppo1c"),
    ],
    ids=["ppo1", "il1", "ppo2", "ppo1_with_ppo1b"],
)
def test_r3_conflict_with_a_saved_model_first_offers_the_name_plus_a_letter(
    make_app: Callable[[Path], Harness],
    conflict_dialogs: ConflictDialogs,
    tmp_path: Path,
    config: str,
    existing: tuple[str, ...],
    expected: str,
) -> None:
    """G1-U-4: re-running a module whose run holds a model: the first choice is another
    name, the module's name plus a letter, so the TensorBoard filters still match it."""
    repo = _make_repo(tmp_path)
    for name in existing:
        _make_trained_run(repo, name)
    harness = make_app(repo)
    _choose_config(harness.gui, config)
    assert harness.gui.run_name_var.get() == existing[0]

    harness.gui.on_start()  # first button, by default

    assert len(conflict_dialogs.seen) == 1, "no conflict dialog"
    dialog = conflict_dialogs.seen[0]
    assert len(harness.started) == 1, "the first choice started nothing"
    launched = harness.started[0]
    assert launched.run_id == expected, f"first choice ran {launched.run_id!r}: {dialog.buttons}"
    assert "--resume" not in launched.args and "--force" not in launched.args
    assert launched.run_id not in TUTORIAL_RUN_NAMES
    assert expected in dialog.text + "\n".join(dialog.buttons), "the new name is not shown"


# ----------------------------------------------------------------------------
# R4: no second trainer (G1-P-3, G1-U-12)
# ----------------------------------------------------------------------------


def test_r4_second_iniciar_while_the_conflict_dialog_is_open_starts_nothing(
    make_app: Callable[[Path], Harness], conflict_dialogs: ConflictDialogs, tmp_path: Path
) -> None:
    """G1-P-3: the second click of a double click lands while the conflict dialog maps: it
    starts nothing, and afterwards one trainer runs and Parar reaches it."""
    repo = _make_repo(tmp_path)
    _make_trained_run(repo, "ppo1")
    harness = make_app(repo)

    def respond(_dialog: tk.Toplevel, buttons: list[tk.Misc]) -> None:
        if len(conflict_dialogs.seen) == 1:
            harness.gui.start_button.invoke()  # G1-P's model of the queued second click
        buttons[0].invoke()

    conflict_dialogs.respond = respond
    harness.gui.on_start()

    started = [p.args for p in harness.started]
    assert len(started) == 1, f"{len(started)} trainers started: {started}"
    assert len(conflict_dialogs.seen) == 1, "the second Iniciar opened another dialog"
    harness.gui.on_stop()
    assert harness.started[0].stop_requests == 1, "Parar does not reach the running trainer"


def test_r4_a_launch_is_refused_while_a_process_is_tracked(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-P-3: Iniciar's handler, called while a trainer runs, starts no second process,
    and Parar still reaches the first one."""
    harness = make_app(_make_repo(tmp_path))
    harness.gui.on_start()
    assert len(harness.started) == 1

    harness.gui.on_start()

    started = [p.args for p in harness.started]
    assert len(started) == 1, f"{len(started)} trainers started: {started}"
    assert harness.unexpected == []
    harness.gui.on_stop()
    assert harness.started[0].stop_requests == 1, "Parar does not reach the first trainer"


# ----------------------------------------------------------------------------
# R5: the Treinar list offers the three module configurations (N2, G1-U-6)
# ----------------------------------------------------------------------------


def test_r5_treinar_list_offers_the_three_module_configs_in_module_order(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-U-6: with the real python/configs/, the list offers FlappyBird_ppo.yaml,
    FlappyBird_run1.yaml and FlappyBird_desafio.yaml, in that order, and nothing else."""
    repo = _make_repo(tmp_path, real_configs=True)
    assert len(list((repo / "python" / "configs").rglob("*.yaml"))) > 3
    harness = make_app(repo)

    offered = []
    for label in _config_labels(harness.gui):
        _choose_config_label(harness.gui, label)
        offered.append(_config_file_in_preview(harness.gui))

    assert offered == list(MODULE_DEFAULTS)


# ----------------------------------------------------------------------------
# R6: a stop that takes long says so (G1-P-2)
# ----------------------------------------------------------------------------


def test_r6_a_slow_stop_points_to_forcar_parada_when_it_becomes_available(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-P-2: 30 s after Parar, with the trainer still running, the status says the stop
    is taking long and that Forçar parada can be used."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)
    gui.on_stop()
    harness.clock.advance(GRACEFUL_STOP_MS - 100)
    assert gui.force_button.instate(["disabled"]), "precondition: not yet available"
    assert "forçar parada" not in gui.status_var.get().lower(), gui.status_var.get()

    harness.clock.advance(100)

    assert gui.force_button.instate(["!disabled"]), "precondition: available after 30 s"
    assert _points_to_force_stop(gui.status_var.get()), f"status: {gui.status_var.get()!r}"


def test_g2a_u16_a_summary_line_after_parar_does_not_replace_parando(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G2a-U-16: after Parar in a training, a summary line still in flight does not
    replace "Parando..." with "Passo N/50000 ...", as the watch path already does."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)
    gui.on_stop()
    stopping = gui.status_var.get()

    harness.started[0].output_queue.put(
        "[INFO] FlappyAgent. Step: 20000. Time Elapsed: 60.123 s. Mean Reward: -1.230. "
        "Std of Reward: 0.500. Training."
    )
    harness.clock.advance(500)

    assert gui.status_var.get() == stopping


def test_g2a_u17_forcar_parada_ends_with_a_forced_stop_status_not_an_error(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G2a-U-17: after Forçar parada in a training, the final status says the training
    was stopped by force and the model may not have been saved, not that it failed."""
    harness = make_app(_make_repo(tmp_path))
    gui = harness.gui
    gui.on_start()
    harness.clock.advance(1_000)
    gui.on_stop()
    harness.clock.advance(GRACEFUL_STOP_MS)

    gui.force_button.invoke()
    harness.clock.advance(200)

    assert gui._process is None, "precondition: the run ended"
    status = gui.status_var.get().lower()
    assert "força" in status and "salvo" in status, status
    assert "erro" not in status, status


# ----------------------------------------------------------------------------
# R7: the time limit field (m9)
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    "typed",
    [
        "inf",
        "nan",
        "1e9",
        "0",
        "-5",
        "",
    ],
    ids=["inf", "nan", "1e9", "zero", "minus5", "empty"],
)
def test_r7_time_limit_never_raises_and_stays_between_1_and_60_minutes(
    make_app: Callable[[Path], Harness], boxes: MessageBoxes, tmp_path: Path, typed: str
) -> None:
    """m9: whatever is typed in "Limite de tempo (min)", nothing raises before or after the
    watch starts, and the watch is stopped after 1 to 60 minutes."""
    repo = _make_repo(tmp_path)
    _make_trained_run(repo, "ppo1")
    harness = make_app(repo)
    gui = harness.gui
    _open_watch_tab(harness)
    gui.no_time_limit_var.set(False)
    gui.time_limit_var.set(typed)

    gui.on_start()

    assert harness.unexpected == [], harness.unexpected
    assert [kind for kind, _ in boxes.shown if kind == "showerror"] == [], boxes.shown
    assert len(harness.started) == 1, "the watch did not start"
    process = harness.started[0]
    harness.clock.advance_to(ONE_MINUTE_MS - 1)
    assert process.stop_requests == 0, "the watch was stopped before 1 minute"
    sixty_minutes = 60 * ONE_MINUTE_MS
    while process.stop_requests == 0 and harness.clock.now_ms < sixty_minutes:
        harness.clock.advance_to(min(harness.clock.now_ms + 1_000, sixty_minutes))
    assert process.stop_requests == 1, "the time limit did not stop the watch within 60 min"
    assert harness.unexpected == [], harness.unexpected


# ----------------------------------------------------------------------------
# R8: the empty name (G1-U-9)
# ----------------------------------------------------------------------------


def test_r8_an_empty_name_gives_an_empty_command_preview(
    make_app: Callable[[Path], Harness], tmp_path: Path
) -> None:
    """G1-U-9: with the Nome do treino field empty, no command is previewed."""
    harness = make_app(_make_repo(tmp_path))
    assert "--run-id=ppo1" in harness.gui.command_var.get()

    _type_run_name(harness.gui, "")

    assert harness.gui.command_var.get() == ""


@pytest.mark.parametrize("name", ["Assistir", "ASSISTIR", "Reference"])
def test_r8_reserved_names_are_refused_in_any_letter_case(
    make_app: Callable[[Path], Harness], boxes: MessageBoxes, tmp_path: Path, name: str
) -> None:
    """G1-W-5: Windows folders ignore letter case, so "Assistir" is the folder that every
    watch overwrites and "Reference" the tutorial's bundled runs: Iniciar refuses both."""
    harness = make_app(_make_repo(tmp_path))
    _type_run_name(harness.gui, name)

    harness.gui.on_start()

    assert harness.started == []
    assert len(boxes.shown) == 1, boxes.shown
    assert "reservado" in boxes.shown[0][1], boxes.shown[0][1]
    # G2-T-1: a refused start must give Iniciar back, or the student is stuck.
    assert harness.gui.start_button.instate(["!disabled"]), "Iniciar stayed disabled"


def test_r8_iniciar_with_an_empty_name_says_the_name_is_missing(
    make_app: Callable[[Path], Harness], boxes: MessageBoxes, tmp_path: Path
) -> None:
    """G1-U-9: Iniciar with an empty name starts nothing and says the name is missing,
    not that it is invalid."""
    harness = make_app(_make_repo(tmp_path))
    _type_run_name(harness.gui, "")

    harness.gui.on_start()

    assert harness.started == []
    assert len(boxes.shown) == 1, boxes.shown
    assert _says_name_missing(boxes.shown[0][1]), f"message: {boxes.shown[0][1]!r}"
    # G2-T-1: a refused start must give Iniciar back, or the student is stuck.
    assert harness.gui.start_button.instate(["!disabled"]), "Iniciar stayed disabled"
