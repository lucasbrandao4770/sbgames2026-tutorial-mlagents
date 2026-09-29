"""Tests for messages and dialogs in scripts/central_de_treino.py (batch M).

Covers findings m1, M9, m22, m13 and m5 (name check only) from
local_files/build/launcher/review_launcher.md. Dialogs are never mapped: either
the real Toplevel is built on a withdrawn root and inspected (with grab_set
stubbed, since m17's grab-before-visible issue is out of scope here), or the
dialog function itself is stubbed and its arguments inspected. Self-contained:
does not import tests/test_central_de_treino.py, tests/fake_trainer.py or
tests/test_run_name_suggestion.py.
"""

from __future__ import annotations

import ast
import gc
import re
import sys
import time
import tkinter as tk
from collections.abc import Callable
from pathlib import Path
from tkinter import ttk

import pytest

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

_SCRIPT_PATH = SCRIPTS_DIR / "central_de_treino.py"
_REAL_DESAFIO_CONFIG = (
    Path(__file__).resolve().parent.parent
    / "python"
    / "configs"
    / "desafio"
    / "FlappyBird_desafio.yaml"
)


@pytest.fixture(autouse=True)
def stub_messagebox(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """Stub every tkinter.messagebox call so no test ever shows a real dialog.

    Per agent_rules.md: Tk roots stay withdrawn and dialogs are stubbed, never
    shown. The custom Toplevel built by _show_error_dialog is exercised directly
    in some tests below and is kept off-screen by withdrawing it right after
    creation instead, never by this fixture.
    """
    calls: list[tuple[str, str, str]] = []

    def _record(kind: str) -> Callable[..., object]:
        def _fn(title: str = "", message: str = "", **_kwargs: object) -> bool:
            calls.append((kind, title, message))
            return True

        return _fn

    monkeypatch.setattr(app.messagebox, "showerror", _record("showerror"))
    monkeypatch.setattr(app.messagebox, "showwarning", _record("showwarning"))
    monkeypatch.setattr(app.messagebox, "showinfo", _record("showinfo"))
    monkeypatch.setattr(app.messagebox, "askyesno", _record("askyesno"))
    return calls


# tk_root comes from tests/conftest.py: one withdrawn Tk root for the whole session,
# matching main()'s own lifetime (one root, ever). Each test builds its own
# CentralDeTreinoApp on that shared root and destroys gui.container (not the root).


_MINIMAL_CONFIG = (
    "behaviors:\n"
    "  FlappyAgent:\n"
    "    trainer_type: ppo\n"
    "    max_steps: 50000\n"
    "    hyperparameters:\n"
    "      batch_size: 256\n"
)


def _repo_root(tmp_path: Path) -> Path:
    """A minimal fake repo: one config and an empty results/, enough for __init__."""
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_MINIMAL_CONFIG)
    (root / "results").mkdir()
    return root


class _StubProcess:
    """Minimal stand-in for ManagedProcess: only what _finish_process reads."""

    def __init__(self, returncode: int) -> None:
        self.returncode = returncode

    def finish_reading(self) -> list[str]:
        return []


def _malformed_desafio_yaml() -> str:
    """A copy of the real desafio config with docs/03's exact known mistake:
    deleting only the "#" of a commented line, leaving an extra leading space."""
    lines = _REAL_DESAFIO_CONFIG.read_text(encoding="utf-8").splitlines(keepends=True)
    target = next(i for i, line in enumerate(lines) if line.strip() == "# curiosity:")
    lines[target] = lines[target].replace("# curiosity:", " curiosity:", 1)
    return "".join(lines)


# ----------------------------------------------------------------------------
# m1: the error dialog's read-only Entry must show the real log path
# ----------------------------------------------------------------------------


def test_m1_error_dialog_entry_shows_log_path(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """m1: the error dialog's read-only field shows the log file path, not ''."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    # m17 (grab-before-visible) is out of scope for m1; neutralize grab_set so the
    # unrelated platform-specific TclError it can raise never masks this test.
    monkeypatch.setattr(tk.Toplevel, "grab_set", lambda self: None)
    dialog: tk.Toplevel | None = None
    try:
        log_path = tmp_path / "central_de_treino_erro_teste.log"
        log_path.write_text("erro de teste", encoding="utf-8")
        before = set(gui.root.winfo_children())
        gui._show_error_dialog(message="Mensagem de teste.", log_path=log_path)
        created = [w for w in gui.root.winfo_children() if w not in before]
        toplevels = [w for w in created if isinstance(w, tk.Toplevel)]
        assert len(toplevels) == 1, "expected exactly one new dialog"
        dialog = toplevels[0]
        dialog.withdraw()  # never mapped on screen
        entries = [w for w in dialog.winfo_children() if isinstance(w, ttk.Entry)]
        assert len(entries) == 1, "expected exactly one Entry in the dialog"
        gc.collect()
        expected = app._display_path(repo_root, log_path)
        assert entries[0].get() == expected
    finally:
        if dialog is not None:
            dialog.destroy()
        gui.container.destroy()


# ----------------------------------------------------------------------------
# M9: malformed YAML -> PT-BR message with line number + instruction, detail logged
# ----------------------------------------------------------------------------


def test_M9_yaml_error_message_has_line_number_and_instruction(tmp_path: Path) -> None:
    """M9: a malformed YAML gets a PT-BR message with the line number and what to do."""
    bad_path = tmp_path / "FlappyBird_desafio.yaml"
    bad_path.write_text(_malformed_desafio_yaml(), encoding="utf-8")
    with pytest.raises(app.LauncherError) as excinfo:
        app.load_yaml(bad_path)
    message = excinfo.value.message
    assert "linha 52" in message, message
    assert any(kw in message.lower() for kw in ("editar arquivo", "espaços")), message
    assert excinfo.value.detail is not None
    assert "block mapping" in excinfo.value.detail.lower(), excinfo.value.detail


def test_M9_yaml_error_detail_reaches_log_area(tk_root: tk.Tk, tmp_path: Path) -> None:
    """M9: the technical detail (raw YAML error) reaches the log area."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    try:
        bad_path = tmp_path / "FlappyBird_desafio.yaml"
        bad_path.write_text(_malformed_desafio_yaml(), encoding="utf-8")
        with pytest.raises(app.LauncherError) as excinfo:
            app.load_yaml(bad_path)
        gui._show_launcher_error(excinfo.value)
        log_text = gui.log_text.get("1.0", "end")
        assert "block mapping" in log_text.lower(), log_text
    finally:
        gui.container.destroy()


# ----------------------------------------------------------------------------
# m22: dialog title, final period, unexpected-error instruction, no new dashes
# ----------------------------------------------------------------------------


def test_m22_error_dialog_title_has_no_spaced_hyphen(
    tk_root: tk.Tk, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """m22: the error dialog's title is "Erro na Central de treino"."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    monkeypatch.setattr(tk.Toplevel, "grab_set", lambda self: None)  # m17 out of scope
    dialog: tk.Toplevel | None = None
    try:
        before = set(gui.root.winfo_children())
        gui._show_error_dialog(message="Mensagem de teste.", log_path=tmp_path / "x.log")
        created = [w for w in gui.root.winfo_children() if w not in before]
        toplevels = [w for w in created if isinstance(w, tk.Toplevel)]
        assert len(toplevels) == 1
        dialog = toplevels[0]
        dialog.withdraw()
        assert dialog.title() == "Erro na Central de treino"
    finally:
        if dialog is not None:
            dialog.destroy()
        gui.container.destroy()


def test_m22_model_saved_status_ends_with_period(tk_root: tk.Tk, tmp_path: Path) -> None:
    """m22: the "model saved" status line ends with a period."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    try:
        run_dir = repo_root / "results" / "ppo1"
        run_dir.mkdir(parents=True)
        launched_at = time.time()
        time.sleep(0.05)
        (run_dir / "FlappyAgent.onnx").touch()
        gui._process = _StubProcess(returncode=0)
        gui._mode = "treinar"
        gui._run_name = "ppo1"
        gui._current_behaviors = ("FlappyAgent",)
        gui._launched_at = launched_at
        gui._output_history = []
        gui._finish_process()
        status = gui.status_var.get()
        assert "Modelo salvo em" in status, status
        assert status.endswith("."), status
    finally:
        gui.container.destroy()


def test_m22_unexpected_error_tells_user_what_to_do(tk_root: tk.Tk, tmp_path: Path) -> None:
    """m22: the unexpected-error text tells the user what to do with the path."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    recorded: list[dict[str, object]] = []
    gui._show_error_dialog = lambda **kwargs: recorded.append(kwargs)  # avoid a real Toplevel
    try:
        gui._show_unexpected_error("um teste", ValueError("algo deu errado"))
        assert len(recorded) == 1
        message = str(recorded[0]["message"])
        assert "mostre o caminho" in message.lower(), message
    finally:
        gui.container.destroy()


# m22: legitimate hyphen uses a naive scan would flag - command-line flags and
# paths never use a *spaced* hyphen, so this starts empty; add an exact string
# here only for a genuine future exception, never to silence a real dash.
_DASH_ALLOWLIST: frozenset[str] = frozenset()
_SPACED_HYPHEN_RE = re.compile(r"(?<=\s)-(?=\s)")


def _docstring_constant_ids(tree: ast.AST) -> set[int]:
    """id() of every ast.Constant that is a module/class/function docstring.

    Docstrings are developer-facing English text (project rule), not the PT-BR
    text a user reads, so the dash rule (which targets user-facing text) does
    not apply to them.
    """
    ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                ids.add(id(body[0].value))
    return ids


def _dash_offenders() -> list[tuple[int, str]]:
    """Every non-docstring string literal in the script with U+2013, U+2014 or a
    hyphen used as a spaced dash, minus the explicit allowlist."""
    source = _SCRIPT_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(_SCRIPT_PATH))
    doc_ids = _docstring_constant_ids(tree)
    offenders: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Constant) and isinstance(node.value, str)):
            continue
        if id(node) in doc_ids or node.value in _DASH_ALLOWLIST:
            continue
        text = node.value
        if "–" in text or "—" in text or _SPACED_HYPHEN_RE.search(text):
            offenders.append((node.lineno, text))
    return offenders


def test_m22_no_dash_characters_in_user_facing_strings() -> None:
    """m22: no U+2013, U+2014 or spaced hyphen used as a dash in a user-facing string."""
    offenders = _dash_offenders()
    assert offenders == [], offenders


# ----------------------------------------------------------------------------
# m13: a PT-BR hint for every listed trainer failure, and no phantom checkbox
# ----------------------------------------------------------------------------


def test_m13_hint_for_unity_timeout() -> None:
    """m13: a Unity connection timeout gets a PT-BR hint, keyed on its meaning."""
    line = (
        "mlagents_envs.exception.UnityTimeOutException: The Unity environment took too "
        "long to respond. Make sure that:"
    )
    output = [line]
    hint = app.diagnose_failure(output, returncode=1)
    assert hint is not None, "no hint returned"
    lowered = hint.lower()
    assert any(kw in lowered for kw in ("tempo", "demorou", "timeout", "--timeout-wait")), hint


def test_m13_hint_for_trainer_config_error() -> None:
    """m13: an invalid YAML option gets a PT-BR hint, keyed on its meaning."""
    line = (
        "mlagents.trainers.exception.TrainerConfigError: The option 'nromalize' was "
        "specified in your YAML file, but is invalid."
    )
    output = [line]
    hint = app.diagnose_failure(output, returncode=1)
    assert hint is not None, "no hint returned"
    lowered = hint.lower()
    assert any(kw in lowered for kw in ("config", "yaml", "opç", "parâmetro", "arquivo")), hint


def test_m13_hint_for_missing_checkpoint_after_continue() -> None:
    """m13: FileNotFoundError on checkpoint.pt after Continuar gets a PT-BR hint."""
    line = (
        "FileNotFoundError: [Errno 2] No such file or directory: "
        "'results/ppo1/FlappyAgent/checkpoint.pt'"
    )
    output = [line]
    hint = app.diagnose_failure(output, returncode=1)
    assert hint is not None, "no hint returned"
    lowered = hint.lower()
    assert any(kw in lowered for kw in ("checkpoint", "continuar", "recomeç", "anterior")), hint


def test_m13_resume_hint_does_not_mention_nonexistent_checkbox() -> None:
    """m13: the resume-not-found hint never tells the user to uncheck "continuar"."""
    output = ["Previous data from this run ID was not found."]
    hint = app.diagnose_failure(output, returncode=1)
    assert hint is not None
    assert "desmarque" not in hint.lower(), hint


def test_m13_hint_for_charmap_decode_error() -> None:
    """m13: on Windows mlagents reads the YAML as cp1252; a character it cannot decode
    there gets a PT-BR hint to remove the accents from the config file's comments.

    The output is the one mlagents 1.1.0 prints (cli_utils.load_config turns the
    UnicodeDecodeError into a TrainerConfigError), so the generic TrainerConfigError
    hint must not win over this one.
    """
    output = [
        (
            "UnicodeDecodeError: 'charmap' codec can't decode byte 0x8d in position 1210: "
            "character maps to <undefined>"
        ),
        "During handling of the above exception, another exception occurred:",
        (
            "mlagents.trainers.exception.TrainerConfigError: There was an error decoding "
            "Config file from python/configs/desafio/FlappyBird_desafio.yaml. Make sure your "
            "file is save using UTF-8"
        ),
    ]
    hint = app.diagnose_failure(output, returncode=1)
    assert hint is not None, "no hint returned"
    lowered = hint.lower()
    assert "acent" in lowered, hint
    assert "coment" in lowered, hint


# ----------------------------------------------------------------------------
# m5: reserved training names (name check only)
# ----------------------------------------------------------------------------


def test_m5_reserved_run_names_rejected_before_launch(
    tk_root: tk.Tk, tmp_path: Path, stub_messagebox: list[tuple[str, str, str]]
) -> None:
    """m5: "assistir" and "reference" are rejected as training names, before any
    process starts, with a PT-BR message."""
    repo_root = _repo_root(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root)
    try:
        for reserved in ("assistir", "reference"):
            gui.run_name_var.set(reserved)
            tk_root.update()
            gui._start_training()
            assert gui._process is None, f"{reserved} must not start a process"
        assert len(stub_messagebox) == 2
        for kind, _title, message in stub_messagebox:
            assert kind == "showerror"
            assert "reservad" in message.lower(), message
    finally:
        gui.container.destroy()
