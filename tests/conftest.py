"""Shared fixtures and autouse safety guards for the Central de treino test suite.

The owner rehearses a talk on this Mac while the suite runs (see
local_files/build/launcher/agent_rules.md): a test that maps a window or dialog,
opens a browser tab or a socket, starts an unlisted process, leaves a child process
behind, or writes the system clipboard disturbs him. The guards below turn each of
those into an immediate, named test failure instead of letting it happen silently.

A test that must legitimately exercise a guarded call for a real reason stubs that
specific call itself with monkeypatch (see each guard's docstring for the exact
seam); the guard then sees the stub, not the real thing, because an instance-level
or later monkeypatch shadows the class/module-level patch a guard installs here.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import socket as socket_module
import subprocess
import sys
import tempfile
import tkinter as tk
import webbrowser
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import NoReturn

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

TESTS_DIR = Path(__file__).resolve().parent

# Step 5: every test gets a BASE_PORT far from the owner's own 5004-5006, so a
# real mlagents-learn subprocess launched by a test (the fake trainer ignores it,
# see tests/fake_trainer.py's parse_known_args) never lands on one of his ports by
# default. A test whose whole point is the *unset* case (no --base-port at all)
# sets monkeypatch.setattr(app, "BASE_PORT", None) itself.
BASE_PORT_FOR_TESTS = 5605


@pytest.fixture(autouse=True)
def _default_base_port(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app, "BASE_PORT", BASE_PORT_FOR_TESTS)


# ----------------------------------------------------------------------------
# Fixtures moved from test_central_de_treino.py so every test file in this
# directory gets them, not just that one.
# ----------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """Stub every tkinter.messagebox call so no test ever shows a real window.

    Autouse: applies to every test in this directory without opting in. Returns the
    list of (kind, title, message) calls recorded so far, for a test to assert
    against; a real messagebox call anywhere is a bug, per the incident where one
    of these dialogs showed up on screen during a test run and could not be
    copied from. Custom dialogs (_ask_run_conflict, _show_error_dialog) are not
    module-level functions, so each test that would reach one overrides it
    directly on the app instance instead of going through this fixture.
    """
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
    # M5's on_close() confirms via askyesno when something is running; default to
    # "yes" (proceed) so a test exercising that path does not hang on a real
    # dialog, matching the incident this fixture exists to prevent. A test that
    # needs the "no" path overrides this on the app instance, same as
    # _ask_run_conflict/_show_error_dialog below.
    monkeypatch.setattr(app.messagebox, "askyesno", _yes)
    return calls


_PPO_CONFIG = (
    "behaviors:\n"
    "  FlappyAgent:\n"
    "    trainer_type: ppo\n"
    "    max_steps: 50000\n"
    "    hyperparameters:\n"
    "      batch_size: 256\n"
)


@pytest.fixture
def repo_root(tmp_path: Path) -> Path:
    """A minimal fake repo: python/configs/ with two configs, an empty results/."""
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "imitation").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_PPO_CONFIG)
    (root / "python" / "configs" / "imitation" / "FlappyBird_run1.yaml").write_text(_PPO_CONFIG)
    (root / "results").mkdir()
    return root


@pytest.fixture(scope="module")
def tk_root() -> Iterator[tk.Tk]:
    # One Tk() for the whole module, reused by every test below, exactly like the
    # real app: main() creates exactly one root for its whole life. Creating and
    # destroying a *second* tk.Tk() in the same process was observed to break
    # Aqua Tk's after()/event processing for it on macOS (update() blocks
    # indefinitely) - a test-harness pitfall, not a production one, since
    # production never creates a second root. Each test below builds its own
    # CentralDeTreinoApp on this shared root and destroys gui.container - not
    # the root - at the end.
    app.ensure_tcl_tk_discoverable()
    root = tk.Tk()
    root.withdraw()
    yield root
    root.destroy()


# ----------------------------------------------------------------------------
# Safety guards. Every guard records the violation before it raises, so a
# violation an `except Exception` somewhere manages to swallow still fails the
# test at teardown (see _guard_teardown below). GuardViolation subclasses
# BaseException, not Exception, precisely so scripts/central_de_treino.py's own
# broad "except Exception as exc" last-resort handlers (on_edit_config,
# on_open_results, on_tensorboard, _start_training, _start_watch, ...) cannot
# catch it either.
# ----------------------------------------------------------------------------


class GuardViolation(BaseException):
    """Raised by an autouse safety guard when a test does something disallowed."""


_GUARD_VIOLATIONS: list[str] = []
_LIVE_PROCESSES: list[subprocess.Popen] = []


def _violate(guard: str, detail: str) -> NoReturn:
    """Record a guard violation and raise it (see GuardViolation's docstring)."""
    message = f"{guard}: {detail}"
    _GUARD_VIOLATIONS.append(message)
    raise GuardViolation(message)


@contextlib.contextmanager
def expect_violation(match: str) -> Iterator[None]:
    """For tests/test_guards.py: assert a guard fires with `match` in its message.

    Also consumes the violation it just verified, so the teardown net below does
    not fail the very test that deliberately (and already) proved it.
    """
    start = len(_GUARD_VIOLATIONS)
    with pytest.raises(GuardViolation, match=match):
        yield
    del _GUARD_VIOLATIONS[start:]


def _check_no_leftover_processes(processes: list[subprocess.Popen]) -> None:
    """Teardown check: fail if any of `processes` is still running.

    A standalone function (not inlined in the fixture) so tests/test_guards.py
    can call it directly, per agent_rules.md/the brief: "for teardown guards,
    test the checking function directly."
    """
    leftover = [proc for proc in processes if proc.poll() is None]
    if leftover:
        pids = ", ".join(str(proc.pid) for proc in leftover)
        _violate("leftover-process-guard", f"still running at teardown: pid(s) {pids}")


@pytest.fixture(autouse=True)
def _guard_teardown() -> Iterator[None]:
    """Resets guard state for this test, then enforces it once the test is done.

    Runs after the test function itself (including any of its own `finally:`
    cleanup) has already executed, so a test that reaps its own process before
    returning - as every existing process-starting test does - is not flagged.
    """
    _GUARD_VIOLATIONS.clear()
    _LIVE_PROCESSES.clear()
    yield
    _check_no_leftover_processes(_LIVE_PROCESSES)
    if _GUARD_VIOLATIONS:
        pytest.fail("; ".join(_GUARD_VIOLATIONS))


# -- window/dialog guard ------------------------------------------------------


def _deny_deiconify(self: tk.Wm, *_args: object, **_kwargs: object) -> NoReturn:
    _violate("window-guard", f"{type(self).__name__}.deiconify()/wm_deiconify() called")


def _deny_wait_visibility(self: tk.Misc, *_args: object, **_kwargs: object) -> NoReturn:
    _violate("window-guard", f"{type(self).__name__}.wait_visibility() called")


def _on_toplevel_mapped(event: tk.Event) -> None:
    """Safety net for a window that becomes viewable some other way.

    A callback bound to Tcl's <Map> event does not propagate its exception back
    to the caller of update()/mainloop() (Tkinter reports it via
    report_callback_exception instead), so this only withdraws the window again
    and records the violation; _guard_teardown's post-test check is what actually
    fails the test for this path.
    """
    widget = event.widget
    with contextlib.suppress(tk.TclError):
        widget.withdraw()
    _GUARD_VIOLATIONS.append(f"window-guard: {type(widget).__name__} was mapped (became viewable)")


def _guard_new_toplevel(init: Callable[..., None]) -> Callable[..., None]:
    def _wrapped(self: tk.Wm, *args: object, **kwargs: object) -> None:
        init(self, *args, **kwargs)
        self.bind("<Map>", _on_toplevel_mapped, add="+")

    return _wrapped


@pytest.fixture(autouse=True)
def _window_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may map a window or dialog (any Tk root or Toplevel becoming viewable).

    A legitimate test that needs a dialog stubs the *app's own* method that
    creates it (e.g. gui._ask_run_conflict = lambda ...), the way every existing
    GUI test in test_central_de_treino.py already does, so this guard never sees
    a real Toplevel to begin with.
    """
    monkeypatch.setattr(tk.Wm, "deiconify", _deny_deiconify)
    monkeypatch.setattr(tk.Misc, "wait_visibility", _deny_wait_visibility)
    monkeypatch.setattr(tk.Toplevel, "__init__", _guard_new_toplevel(tk.Toplevel.__init__))
    monkeypatch.setattr(tk.Tk, "__init__", _guard_new_toplevel(tk.Tk.__init__))


# -- browser guard --------------------------------------------------------


def _deny_webbrowser_open(url: str, *args: object, **kwargs: object) -> NoReturn:
    _violate("browser-guard", f"webbrowser.open({url!r})")


@pytest.fixture(autouse=True)
def _browser_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may open a browser tab.

    A test asserting on_tensorboard's browser call stubs app.webbrowser.open
    itself with monkeypatch (a no-op or a recording stand-in); that setattr runs
    from the test body, after this fixture's, so it wins for that test.
    """
    monkeypatch.setattr(webbrowser, "open", _deny_webbrowser_open)


# -- socket guard -----------------------------------------------------------


def _deny_socket_connect(
    self: socket_module.socket, address: object, *a: object, **kw: object
) -> NoReturn:
    _violate("socket-guard", f"socket.connect({address!r})")


def _deny_socket_bind(
    self: socket_module.socket, address: object, *a: object, **kw: object
) -> NoReturn:
    _violate("socket-guard", f"socket.bind({address!r})")


def _deny_create_connection(address: object, *a: object, **kw: object) -> NoReturn:
    _violate("socket-guard", f"socket.create_connection({address!r})")


@pytest.fixture(autouse=True)
def _socket_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may open a socket (TensorBoard's is_tensorboard_up/
    _tensorboard_port_open are the app's only callers; no existing test calls
    them for real). A test that needs one stubs it directly, e.g.
    monkeypatch.setattr(app, "_tensorboard_port_open", lambda *_a, **_kw: True).
    """
    monkeypatch.setattr(socket_module.socket, "connect", _deny_socket_connect)
    monkeypatch.setattr(socket_module.socket, "bind", _deny_socket_bind)
    monkeypatch.setattr(socket_module, "create_connection", _deny_create_connection)


# -- process-start allowlist guard ------------------------------------------


def _resolves_to_sys_executable(program: str) -> bool:
    try:
        return Path(program).resolve() == Path(sys.executable).resolve()
    except OSError:
        return False


def _points_under_tests_dir(candidate: Path) -> bool:
    if not candidate.is_absolute():
        return False
    try:
        candidate.resolve().relative_to(TESTS_DIR.resolve())
    except ValueError:
        return False
    return True


def _is_allowlisted_test_shim(candidate: Path) -> bool:
    """A small text file, under pytest's own tmp dir, that itself runs a tests/
    script - covers the fake-venv "mlagents-learn" shim
    tests/test_central_de_treino.py's _fake_venv() writes fresh per test (a
    `#!{python}` one-liner that runpy.run_path()s tests/fake_trainer.py): a real
    script, not a literal tests/ path, but one this suite creates for exactly
    this purpose. Bounded to pytest's temp tree and a small text file that
    mentions tests/, so it can never quietly allow a real installed binary
    living anywhere else (e.g. the pinned .venv/bin/mlagents-learn).
    """
    if not candidate.is_absolute() or not candidate.is_file():
        return False
    try:
        if candidate.stat().st_size > 8192:
            return False
        text = candidate.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False
    tmp_root = Path(tempfile.gettempdir()).resolve()
    try:
        candidate.resolve().relative_to(tmp_root)
    except ValueError:
        return False
    return str(TESTS_DIR) in text


def _is_allowed_process(argv: list[str]) -> bool:
    """True for `ps` (any argv), or sys.executable running a file inside tests/
    (directly, or via the fake-venv shim above).
    """
    if not argv:
        return False
    if Path(argv[0]).name == "ps":
        return True
    if not _resolves_to_sys_executable(argv[0]):
        return False
    return any(
        _points_under_tests_dir(Path(arg)) or _is_allowlisted_test_shim(Path(arg))
        for arg in argv[1:]
    )


def _extract_argv(args: object) -> list[str]:
    if isinstance(args, (str, bytes, Path)):
        return [str(args)]
    try:
        return [str(item) for item in args]  # type: ignore[union-attr]
    except TypeError:
        return []


def _can_possibly_execute(program: str) -> bool:
    """True if the OS could conceivably run `program` at all.

    Lets a Popen call through to its own natural OSError, instead of the guard's,
    when the target cannot start for reasons that have nothing to do with the
    allowlist (missing, or not executable) - a real Popen call in that situation
    can never actually start a process either way, and
    test_app_start_training_with_non_executable_interpreter_shows_friendly_error
    relies on exactly this OSError to reach _launch's LauncherError conversion.

    A bare name with no path separator (e.g. "echo") is resolved via PATH, the
    same way Popen itself resolves it - checking it as a literal relative file
    (the naive Path(...).is_file()) would wrongly say "cannot execute" for any
    real program found only via PATH, letting it slip past the allowlist below
    and actually run (caught live: a plain "echo" this way was not blocked and
    printed to stdout).
    """
    has_separator = os.sep in program or (os.altsep is not None and os.altsep in program)
    if not has_separator:
        return shutil.which(program) is not None
    try:
        return Path(program).is_file() and os.access(program, os.X_OK)
    except OSError:
        return False


def _guard_popen_init(init: Callable[..., None]) -> Callable[..., None]:
    def _wrapped(self: subprocess.Popen, args: object, *a: object, **kw: object) -> None:
        argv = _extract_argv(args)
        if argv and _can_possibly_execute(argv[0]) and not _is_allowed_process(argv):
            _violate("process-guard", f"subprocess start outside the allowlist: {argv!r}")
        init(self, args, *a, **kw)
        _LIVE_PROCESSES.append(self)

    return _wrapped


@pytest.fixture(autouse=True)
def _process_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Only `ps`, or sys.executable running a file inside tests/, may start as a
    child process. subprocess.run/call/check_call/check_output all construct a
    Popen internally, so patching Popen.__init__ covers every one of them too.
    A test exercising e.g. on_verify_env or the Windows helpers for real stubs
    subprocess.run/Popen itself.
    """
    monkeypatch.setattr(subprocess.Popen, "__init__", _guard_popen_init(subprocess.Popen.__init__))


# -- clipboard guard ---------------------------------------------------------


def _deny_clipboard_write(method: str) -> Callable[..., NoReturn]:
    def _fn(self: tk.Misc, *args: object, **kwargs: object) -> NoReturn:
        _violate("clipboard-guard", f"{type(self).__name__}.{method}({args!r})")

    return _fn


@pytest.fixture(autouse=True)
def _clipboard_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """No test may write the owner's real system clipboard.

    A test that needs to verify a copy-to-clipboard action (see
    test_app_copy_command_sets_clipboard) stubs clipboard_clear/append/get on its
    own tk root *instance* instead: an instance attribute shadows the
    class-level patch below, so the guard never sees those calls.
    """
    monkeypatch.setattr(tk.Misc, "clipboard_clear", _deny_clipboard_write("clipboard_clear"))
    monkeypatch.setattr(tk.Misc, "clipboard_append", _deny_clipboard_write("clipboard_append"))
