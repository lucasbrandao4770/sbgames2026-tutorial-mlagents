"""Tests for scripts/central_de_treino.py.

Covers the pure logic (discovery, validation, command building, parsing) with plain
unit tests, the process manager against tests/fake_trainer.py as a real subprocess,
and a headless drive of the Tk window: build the app, set options, call the button
handlers, pump the loop with update(). No OS-level GUI automation is used.
"""

from __future__ import annotations

import os
import signal
import sys
import time
import tkinter as tk
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parent.parent / "scripts"
sys.path.insert(0, str(SCRIPTS_DIR))

import central_de_treino as app

FAKE_TRAINER = Path(__file__).resolve().parent / "fake_trainer.py"


@pytest.fixture(autouse=True)
def no_real_dialogs(monkeypatch: pytest.MonkeyPatch) -> list[tuple[str, str, str]]:
    """Stub every tkinter.messagebox call so no test ever shows a real window.

    Autouse: applies to every test in this file without opting in. Returns the
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


# ----------------------------------------------------------------------------
# Fixtures e helpers de repositório falso
# ----------------------------------------------------------------------------

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


def _make_run(
    base: Path, name: str, *, behavior: str = "FlappyAgent", checkpoint: bool = True
) -> Path:
    """Create a results-shaped run folder, with or without a checkpoint.pt."""
    run_dir = base / name
    behavior_dir = run_dir / behavior
    behavior_dir.mkdir(parents=True)
    (run_dir / "configuration.yaml").write_text(
        "behaviors:\n"
        f"  {behavior}:\n"
        "    trainer_type: ppo\n"
        "    max_steps: 50000\n"
        "env_settings:\n"
        "  base_port: 5005\n"
        "engine_settings:\n"
        "  no_graphics: true\n"
        "  width: 84\n"
    )
    (run_dir / f"{behavior}.onnx").touch()
    if checkpoint:
        (behavior_dir / "checkpoint.pt").touch()
    return run_dir


# ----------------------------------------------------------------------------
# Validação e descoberta
# ----------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("ppo1", True),
        ("meu_treino-2", True),
        ("A", True),
        ("", False),
        ("tem espaco", False),
        ("acentuação", False),
        ("../etc", False),
        ("a/b", False),
    ],
)
def test_is_valid_run_name(name: str, valid: bool) -> None:
    assert app.is_valid_run_name(name) is valid


def test_find_configs_and_default(repo_root: Path) -> None:
    configs = app.find_configs(repo_root)
    assert len(configs) == 2
    default = app.default_config(repo_root)
    assert default is not None
    assert default.name == "FlappyBird_ppo.yaml"


def test_default_config_falls_back_when_default_missing(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    (root / "python" / "configs" / "imitation").mkdir(parents=True)
    only_config = root / "python" / "configs" / "imitation" / "FlappyBird_run1.yaml"
    only_config.write_text(_PPO_CONFIG)
    assert app.default_config(root) == only_config


def test_run_exists(repo_root: Path) -> None:
    assert app.run_exists(repo_root, "ppo1") is False
    (repo_root / "results" / "ppo1").mkdir()
    assert app.run_exists(repo_root, "ppo1") is True


def test_find_build_macos(repo_root: Path) -> None:
    (repo_root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    found = app.find_build(repo_root, system="Darwin")
    assert found == repo_root / "builds" / "FlappyBird.app"


def test_find_build_windows_skips_crash_handler(repo_root: Path) -> None:
    win_dir = repo_root / "builds" / "FlappyBird-Windows-x64"
    win_dir.mkdir(parents=True)
    (win_dir / "UnityCrashHandler64.exe").touch()
    (win_dir / "FlappyBird.exe").touch()
    found = app.find_build(repo_root, system="Windows")
    assert found == win_dir / "FlappyBird.exe"


def test_find_build_linux_needs_executable_bit(repo_root: Path) -> None:
    linux_dir = repo_root / "builds" / "FlappyBird-Linux"
    linux_dir.mkdir(parents=True)
    binary = linux_dir / "FlappyBird"
    binary.touch()
    assert app.find_build(repo_root, system="Linux") is None
    binary.chmod(0o755)
    assert app.find_build(repo_root, system="Linux") == binary


def test_find_build_none_when_builds_dir_missing(repo_root: Path) -> None:
    assert app.find_build(repo_root, system="Darwin") is None


def test_find_trained_runs_requires_checkpoint(repo_root: Path) -> None:
    _make_run(repo_root / "results", "ppo1", checkpoint=True)
    _make_run(repo_root / "results", "ppo_sem_checkpoint", checkpoint=False)
    runs = app.find_trained_runs(repo_root)
    ids = [run.relative_id for run in runs]
    assert ids == ["ppo1"]


def test_find_trained_runs_includes_reference_subfolders(repo_root: Path) -> None:
    reference_dir = repo_root / "results" / "reference"
    _make_run(reference_dir, "FlappyBird_ppo_500k", checkpoint=True)
    _make_run(reference_dir, "FlappyBird_ppo_sem_pt", checkpoint=False)
    runs = app.find_trained_runs(repo_root)
    ids = [run.relative_id for run in runs]
    assert ids == ["reference/FlappyBird_ppo_500k"]


def test_find_trained_runs_empty_when_no_results_dir(tmp_path: Path) -> None:
    assert app.find_trained_runs(tmp_path / "repo") == []


# ----------------------------------------------------------------------------
# YAML: behaviors, max_steps, geração do config de "Assistir"
# ----------------------------------------------------------------------------


def test_read_behaviors_and_max_steps(repo_root: Path) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    behaviors = app.read_behaviors(config)
    assert set(behaviors) == {"FlappyAgent"}
    assert app.read_max_steps(config) == 50000


def test_read_behaviors_missing_section_raises(tmp_path: Path) -> None:
    config = tmp_path / "sem_behaviors.yaml"
    config.write_text("default_settings: null\n")
    with pytest.raises(app.LauncherError):
        app.read_behaviors(config)


def test_load_yaml_invalid_syntax_raises(tmp_path: Path) -> None:
    config = tmp_path / "quebrado.yaml"
    config.write_text("behaviors: [este: não, fecha")
    with pytest.raises(app.LauncherError):
        app.load_yaml(config)


def test_generate_watch_config_strips_engine_settings(repo_root: Path) -> None:
    run_dir = _make_run(repo_root / "results", "ppo1")
    dest = repo_root / "results" / ".central_de_treino" / "assistir_config.yaml"
    app.generate_watch_config(run_dir / "configuration.yaml", dest)
    data = yaml.safe_load(dest.read_text())
    assert list(data.keys()) == ["behaviors"]
    assert "engine_settings" not in data
    assert data["behaviors"]["FlappyAgent"]["max_steps"] == 50000


# ----------------------------------------------------------------------------
# Parsing da saída do treinador
# ----------------------------------------------------------------------------


def test_parse_summary_line_training() -> None:
    line = (
        "FlappyAgent. Step: 2000. Time Elapsed: 5.234 s. "
        "Mean Reward: -1.234. Std of Reward: 0.567. Training."
    )
    summary = app.parse_summary_line(line)
    assert summary == app.TrainerSummary("FlappyAgent", 2000, -1.234, True)


def test_parse_summary_line_not_training_with_info_prefix() -> None:
    line = (
        "[INFO] FlappyAgent. Step: 44000. Time Elapsed: 3.489 s. "
        "Mean Reward: 1.750. Std of Reward: 0.829. Not Training."
    )
    summary = app.parse_summary_line(line)
    assert summary is not None
    assert summary.step == 44000
    assert summary.mean_reward == 1.750
    assert summary.is_training is False


def test_parse_summary_line_reward_na() -> None:
    line = (
        "FlappyAgent. Step: 2000. Time Elapsed: 1.0 s. "
        "Mean Reward: N/A. Std of Reward: N/A. Training."
    )
    summary = app.parse_summary_line(line)
    assert summary is not None
    assert summary.mean_reward is None


def test_parse_summary_line_no_match() -> None:
    assert app.parse_summary_line("qualquer outra linha de log") is None


def test_diagnose_failure_known_and_unknown() -> None:
    hint = app.diagnose_failure(["algo", "UnityWorkerInUseException: worker 0"], 1)
    assert hint is not None and "porta" in hint
    assert app.diagnose_failure(["tudo bem"], 0) is None
    assert app.diagnose_failure(["erro nunca visto antes"], 1) is None


def test_watch_ended_by_closing_game_normal_quit() -> None:
    # Exact lines from inference_test/report.md, Round 4 Q1 (exit code 0).
    lines = [
        "[INFO] Initializing from results/teste_painel/FlappyAgent/checkpoint.pt.",
        "[INFO] Starting training from step 0 and saving to results/assistir/FlappyAgent.",
        "[ERROR] Worker 0 exceeded the allowed number of restarts.",
        "[INFO] Learning was interrupted. Please wait while the graph is generated.",
        "[ERROR] SubprocessEnvManager had workers that didn't signal shutdown",
    ]
    assert app.watch_ended_by_closing_game(lines) is True


def test_watch_ended_by_closing_game_hard_kill_with_traceback() -> None:
    # Round 4 Q2 (exit code 1, ends in a UnityEnvironmentException traceback).
    lines = [
        "[ERROR] Worker 0 exceeded the allowed number of restarts.",
        "[INFO] Learning was interrupted. Please wait while the graph is generated.",
        "Traceback (most recent call last):",
        (
            "mlagents_envs.exception.UnityEnvironmentException: Environment shut down "
            "with return code -15 (SIGTERM)."
        ),
    ]
    assert app.watch_ended_by_closing_game(lines) is True


def test_watch_ended_by_closing_game_false_for_ordinary_stop() -> None:
    lines = ["FlappyAgent. Step: 2000. ...", "[INFO] Learning was interrupted."]
    assert app.watch_ended_by_closing_game(lines) is False


def test_model_output_paths_and_existing(repo_root: Path) -> None:
    expected = repo_root / "results" / "ppo1" / "FlappyAgent.onnx"
    assert app.model_output_paths(repo_root, "ppo1", ["FlappyAgent"]) == [expected]
    assert app.existing_model_paths(repo_root, "ppo1", ["FlappyAgent"]) == []
    expected.parent.mkdir(parents=True)
    expected.touch()
    assert app.existing_model_paths(repo_root, "ppo1", ["FlappyAgent"]) == [expected]


# ----------------------------------------------------------------------------
# Construção e exibição de comandos
# ----------------------------------------------------------------------------


def test_build_train_command_base(repo_root: Path) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    args = app.build_train_command(
        repo_root=repo_root, config=config, run_name="ppo1", build=build, show_window=True
    )
    assert args == [
        "mlagents-learn",
        "python/configs/ppo/FlappyBird_ppo.yaml",
        "--env=builds/FlappyBird.app",
        "--run-id=ppo1",
    ]


def test_build_train_command_no_window_adds_flag(repo_root: Path) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    args = app.build_train_command(
        repo_root=repo_root, config=config, run_name="ppo1", build=build, show_window=False
    )
    assert args[-1] == "--no-graphics"


@pytest.mark.parametrize(("flag", "expected"), [("resume", "--resume"), ("force", "--force")])
def test_build_train_command_resume_or_force(repo_root: Path, flag: str, expected: str) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    args = app.build_train_command(
        repo_root=repo_root,
        config=config,
        run_name="ppo1",
        build=build,
        show_window=True,
        **{flag: True},
    )
    assert expected in args


def test_build_train_command_resume_and_force_raises(repo_root: Path) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    with pytest.raises(app.LauncherError):
        app.build_train_command(
            repo_root=repo_root,
            config=config,
            run_name="ppo1",
            build=build,
            show_window=True,
            resume=True,
            force=True,
        )


def test_build_train_command_invalid_name_raises(repo_root: Path) -> None:
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    with pytest.raises(app.LauncherError):
        app.build_train_command(
            repo_root=repo_root,
            config=config,
            run_name="tem espaco",
            build=build,
            show_window=True,
        )


def test_build_watch_command(repo_root: Path) -> None:
    watch_config = repo_root / "results" / ".central_de_treino" / "assistir_config.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    args = app.build_watch_command(
        repo_root=repo_root,
        watch_config=watch_config,
        build=build,
        trained_run_id="reference/FlappyBird_ppo",
    )
    assert args == [
        "mlagents-learn",
        "results/.central_de_treino/assistir_config.yaml",
        "--env=builds/FlappyBird.app",
        "--run-id=assistir",
        "--initialize-from=reference/FlappyBird_ppo",
        "--inference",
        "--force",
        "--time-scale=1",
        "--capture-frame-rate=0",
        "--max-lifetime-restarts=0",
    ]


def test_build_commands_omit_base_port_by_default(repo_root: Path) -> None:
    assert app.BASE_PORT is None  # CENTRAL_DE_TREINO_BASE_PORT is not set in this test env
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    train_args = app.build_train_command(
        repo_root=repo_root, config=config, run_name="ppo1", build=build, show_window=True
    )
    assert not any(a.startswith("--base-port") for a in train_args)


def test_build_commands_add_base_port_when_set(
    repo_root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(app, "BASE_PORT", 5605)
    config = repo_root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml"
    build = repo_root / "builds" / "FlappyBird.app"
    train_args = app.build_train_command(
        repo_root=repo_root, config=config, run_name="ppo1", build=build, show_window=True
    )
    assert "--base-port=5605" in train_args

    watch_config = repo_root / "results" / ".central_de_treino" / "assistir_config.yaml"
    watch_args = app.build_watch_command(
        repo_root=repo_root, watch_config=watch_config, build=build, trained_run_id="ppo1"
    )
    assert "--base-port=5605" in watch_args


@pytest.mark.parametrize(("raw", "expected"), [("5605", 5605), ("", None), ("not-a-number", None)])
def test_read_base_port(raw: str, expected: int | None, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(app.BASE_PORT_ENV_VAR, raw)
    assert app._read_base_port() == expected


def test_read_base_port_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv(app.BASE_PORT_ENV_VAR, raising=False)
    assert app._read_base_port() is None


def test_build_tensorboard_and_verify_env_commands() -> None:
    assert app.build_tensorboard_command() == ["tensorboard", "--logdir", "results"]
    assert app.build_verify_env_command() == ["python", "scripts/verify_env.py"]


def test_format_command_for_display_posix() -> None:
    text = app.format_command_for_display(
        ["mlagents-learn", "a b/c.yaml", "--run-id=x"], system="Darwin"
    )
    assert text == "mlagents-learn 'a b/c.yaml' --run-id=x"


def test_format_command_for_display_windows() -> None:
    text = app.format_command_for_display(
        ["mlagents-learn", "a b/c.yaml", "--run-id=x"], system="Windows"
    )
    assert text == 'mlagents-learn "a b/c.yaml" --run-id=x'


def test_resolve_for_execution_found(tmp_path: Path) -> None:
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.touch()
    (bin_dir / "mlagents-learn").touch()
    resolved = app.resolve_for_execution(["mlagents-learn", "--run-id=x"], python_bin)
    assert resolved == [str(bin_dir / "mlagents-learn"), "--run-id=x"]


def test_resolve_for_execution_python_uses_interpreter(tmp_path: Path) -> None:
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.touch()
    resolved = app.resolve_for_execution(["python", "scripts/verify_env.py"], python_bin)
    assert resolved == [str(python_bin), "scripts/verify_env.py"]


def test_resolve_for_execution_missing_raises(tmp_path: Path) -> None:
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.touch()
    with pytest.raises(app.LauncherError):
        app.resolve_for_execution(["tensorboard", "--logdir", "results"], python_bin)


# ----------------------------------------------------------------------------
# Erros e helpers de plataforma
# ----------------------------------------------------------------------------


def test_write_error_log_writes_traceback(repo_root: Path) -> None:
    try:
        raise ValueError("algo deu errado")
    except ValueError as exc:
        log_path = app.write_error_log(repo_root, "teste", exc)
    assert log_path.is_file()
    content = log_path.read_text(encoding="utf-8")
    assert "teste" in content
    assert "ValueError" in content
    assert "algo deu errado" in content


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        ("Darwin", ["open", "/x"]),
        ("Windows", ["explorer", "/x"]),
        ("Linux", ["xdg-open", "/x"]),
    ],
)
def test_file_manager_command(system: str, expected: list[str]) -> None:
    assert app._file_manager_command(system, Path("/x")) == expected


@pytest.mark.parametrize(
    ("system", "expected"),
    [
        # M6: -t forces macOS's `open` to use the default *text* editor, since a
        # clean lab Mac is unlikely to have anything associated with .yaml.
        ("Darwin", ["open", "-t", "/x"]),
        ("Windows", None),
        ("Linux", ["xdg-open", "/x"]),
    ],
)
def test_default_app_command(system: str, expected: list[str] | None) -> None:
    assert app._default_app_command(system, Path("/x")) == expected


# ----------------------------------------------------------------------------
# Descoberta de Tcl/Tk
# ----------------------------------------------------------------------------


def _make_fake_tcl_tk_tree(
    base: Path, *, tcl_version: str = "8.6", tk_version: str = "8.6"
) -> None:
    tcl_dir = base / "lib" / f"tcl{tcl_version}"
    tk_dir = base / "lib" / f"tk{tk_version}"
    tcl_dir.mkdir(parents=True)
    tk_dir.mkdir(parents=True)
    (tcl_dir / "init.tcl").write_text("# fake init.tcl")
    (tk_dir / "tk.tcl").write_text("# fake tk.tcl")


def test_find_tcl_tk_library_found(tmp_path: Path) -> None:
    _make_fake_tcl_tk_tree(tmp_path, tcl_version="8.7")
    found = app._find_tcl_tk_library(tmp_path, "tcl")
    assert found == tmp_path / "lib" / "tcl8.7"


def test_find_tcl_tk_library_ignores_folder_without_marker_file(tmp_path: Path) -> None:
    # A same-named folder that does not actually have init.tcl must not count.
    (tmp_path / "lib" / "tcl8.6").mkdir(parents=True)
    assert app._find_tcl_tk_library(tmp_path, "tcl") is None


def test_find_tcl_tk_library_missing(tmp_path: Path) -> None:
    assert app._find_tcl_tk_library(tmp_path, "tcl") is None
    assert app._find_tcl_tk_library(tmp_path, "tk") is None


def test_ensure_tcl_tk_discoverable_sets_both_when_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_fake_tcl_tk_tree(tmp_path)
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path))
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    try:
        app.ensure_tcl_tk_discoverable()
        assert os.environ["TCL_LIBRARY"] == str(tmp_path / "lib" / "tcl8.6")
        assert os.environ["TK_LIBRARY"] == str(tmp_path / "lib" / "tk8.6")
    finally:
        # ensure_tcl_tk_discoverable() writes os.environ directly, not through
        # monkeypatch: since the keys were absent (not merely different) before
        # delenv() ran, monkeypatch registers no teardown for them, so a fake,
        # non-functional path set here would otherwise leak into every later
        # test in this module, including the shared tk_root fixture's real
        # tk.Tk() - this was caught by exactly that failure once, live.
        os.environ.pop("TCL_LIBRARY", None)
        os.environ.pop("TK_LIBRARY", None)


def test_ensure_tcl_tk_discoverable_never_overrides_user_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _make_fake_tcl_tk_tree(tmp_path)
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path))
    monkeypatch.setenv("TCL_LIBRARY", "/set/by/the/user")
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    try:
        app.ensure_tcl_tk_discoverable()
        assert os.environ["TCL_LIBRARY"] == "/set/by/the/user"
        assert os.environ["TK_LIBRARY"] == str(tmp_path / "lib" / "tk8.6")
    finally:
        # TCL_LIBRARY was set through monkeypatch.setenv, so monkeypatch reverts
        # it; TK_LIBRARY was written directly by the function under test and
        # needs the same explicit cleanup as above.
        os.environ.pop("TK_LIBRARY", None)


def test_ensure_tcl_tk_discoverable_leaves_env_alone_when_nothing_found(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "base_prefix", str(tmp_path))
    monkeypatch.delenv("TCL_LIBRARY", raising=False)
    monkeypatch.delenv("TK_LIBRARY", raising=False)
    app.ensure_tcl_tk_discoverable()  # must not raise
    assert "TCL_LIBRARY" not in os.environ
    assert "TK_LIBRARY" not in os.environ


def test_tcl_tk_failure_message_is_short_and_actionable() -> None:
    message = app.tcl_tk_failure_message(RuntimeError("boom"))
    assert "Tcl/Tk" in message
    assert "docs/00-instalacao.md" in message
    assert "boom" in message


# ----------------------------------------------------------------------------
# Gerenciador de processos, contra o treinador de mentira (real subprocess)
# ----------------------------------------------------------------------------


def test_posix_wrap_for_sigint_reset_prefixes_without_changing_real_args() -> None:
    python_bin = Path("/opt/venv/bin/python3")
    real_args = ["/opt/venv/bin/mlagents-learn", "config.yaml", "--run-id=x"]
    wrapped = app._posix_wrap_for_sigint_reset(real_args, python_bin)
    assert wrapped[0] == str(python_bin)
    assert wrapped[1] == "-c"
    assert "SIG_DFL" in wrapped[2]
    assert "os.execv" in wrapped[2]
    assert wrapped[3:] == real_args


def _fake_trainer_process(
    tmp_path: Path,
    *,
    extra_args: list[str] | None = None,
    graceful_timeout_s: float = app.GRACEFUL_STOP_TIMEOUT_S,
) -> app.ManagedProcess:
    args = [sys.executable, str(FAKE_TRAINER), "--interval=0.02", *(extra_args or [])]
    return app.ManagedProcess(
        args, tmp_path, python_bin=Path(sys.executable), graceful_timeout_s=graceful_timeout_s
    )


def test_managed_process_streams_output(tmp_path: Path) -> None:
    process = _fake_trainer_process(tmp_path)
    process.start()
    try:
        deadline = time.monotonic() + 5
        collected: list[str] = []
        while time.monotonic() < deadline and len(collected) < 3:
            collected.extend(process.poll_output())
            time.sleep(0.02)
        assert any(app.parse_summary_line(line) is not None for line in collected)
        assert process.is_running() is True
    finally:
        process.force_kill()


def test_managed_process_graceful_stop_exits_cleanly(tmp_path: Path) -> None:
    process = _fake_trainer_process(tmp_path, graceful_timeout_s=5.0)
    process.start()
    try:
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not process.poll_output():
            time.sleep(0.02)
        process.request_graceful_stop()
        deadline = time.monotonic() + 5
        lines: list[str] = []
        while time.monotonic() < deadline and process.is_running():
            lines.extend(process.poll_output())
            time.sleep(0.02)
        assert process.is_running() is False
        assert process.exit_code == 0
        lines.extend(process.poll_output())
        assert any("Interrompido" in line for line in lines)
    finally:
        process.force_kill()


def test_managed_process_graceful_stop_survives_parent_sigint_ignored(tmp_path: Path) -> None:
    """A child must not inherit a SIG_IGN SIGINT disposition from its parent.

    A process started in the background of a non-interactive shell (a trailing &)
    inherits SIGINT set to ignore (reproduced directly: `bash -c "<python> -c
    '...' & wait"` prints Handlers.SIG_IGN, vs. the default handler without the
    &). Simulate that here by setting this test process's own SIGINT to SIG_IGN
    before starting the fake trainer through the real process manager; the
    SIGINT-reset wrapper in _posix_popen must still let it be stopped gracefully.
    """
    original_handler = signal.getsignal(signal.SIGINT)
    signal.signal(signal.SIGINT, signal.SIG_IGN)
    process = _fake_trainer_process(tmp_path, graceful_timeout_s=5.0)
    try:
        process.start()
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not process.poll_output():
            time.sleep(0.02)
        process.request_graceful_stop()
        deadline = time.monotonic() + 5
        lines: list[str] = []
        while time.monotonic() < deadline and process.is_running():
            lines.extend(process.poll_output())
            time.sleep(0.02)
        assert process.is_running() is False
        assert process.exit_code == 0
        lines.extend(process.poll_output())
        assert any("Interrompido" in line for line in lines)
    finally:
        signal.signal(signal.SIGINT, original_handler)
        process.force_kill()


def test_managed_process_graceful_timeout_elapsed(tmp_path: Path) -> None:
    process = _fake_trainer_process(
        tmp_path, extra_args=["--ignore-sigint"], graceful_timeout_s=0.2
    )
    process.start()
    try:
        # Wait for the first line so --ignore-sigint has already installed SIG_IGN;
        # otherwise SIGINT can race the child's own startup and hit the default
        # handler instead, which raises KeyboardInterrupt and kills it for real.
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline and not process.poll_output():
            time.sleep(0.02)
        assert process.graceful_timeout_elapsed() is False
        process.request_graceful_stop()
        assert process.graceful_timeout_elapsed() is False
        time.sleep(0.35)
        assert process.graceful_timeout_elapsed() is True
        # A hung trainer keeps running: this is exactly when the UI offers "Forçar parada".
        assert process.is_running() is True
    finally:
        process.force_kill()


def test_managed_process_force_kill_stops_hung_process(tmp_path: Path) -> None:
    process = _fake_trainer_process(tmp_path, extra_args=["--ignore-sigint"])
    process.start()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and not process.poll_output():
        time.sleep(0.02)
    process.request_graceful_stop()
    time.sleep(0.3)
    assert process.is_running() is True  # SIGINT is ignored on purpose
    process.force_kill()
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline and process.is_running():
        time.sleep(0.05)
    assert process.is_running() is False


# ----------------------------------------------------------------------------
# Janela headless: cria o app de verdade, mexe nas opções, chama os handlers,
# bombeia o loop com update(). Sem automação de GUI no nível do SO.
# ----------------------------------------------------------------------------


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


def _fake_venv(tmp_path: Path) -> Path:
    """Build a venv-shaped bin dir whose mlagents-learn actually runs fake_trainer.py.

    python_bin is a real, working interpreter (symlinked to sys.executable), not just
    a placeholder: _posix_wrap_for_sigint_reset execs it directly for every launch.
    """
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.symlink_to(sys.executable)
    shim = bin_dir / "mlagents-learn"
    shim.write_text(
        f"#!{sys.executable}\n"
        "import runpy, sys\n"
        "sys.argv = [sys.argv[0], *sys.argv[1:], '--interval=0.01']\n"
        f"runpy.run_path({str(FAKE_TRAINER)!r}, run_name='__main__')\n"
    )
    shim.chmod(0o755)
    return python_bin


def _full_repo(tmp_path: Path) -> Path:
    root = tmp_path / "repo"
    (root / "python" / "configs" / "ppo").mkdir(parents=True)
    (root / "python" / "configs" / "ppo" / "FlappyBird_ppo.yaml").write_text(_PPO_CONFIG)
    (root / "results").mkdir()
    (root / "builds" / "FlappyBird.app" / "Contents").mkdir(parents=True)
    return root


def test_app_builds_and_previews_train_command(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        tk_root.update()
        assert "mlagents-learn" in gui.command_var.get()
        assert "FlappyBird_ppo.yaml" in gui.command_var.get()
        assert "--run-id=ppo1" in gui.command_var.get()
    finally:
        gui.container.destroy()


def test_app_previews_watch_command_on_tab_switch(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    _make_run(repo_root / "results", "ppo1")
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        tk_root.update()
        gui.notebook.select(1)
        tk_root.update()
        command = gui.command_var.get()
        assert "--initialize-from=ppo1" in command
        assert "--inference" in command
    finally:
        gui.container.destroy()


def test_app_run_name_validator_blocks_invalid_characters(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        assert gui._validate_run_name_input("ppo_2") is True
        assert gui._validate_run_name_input("tem espaco") is False
        assert gui._validate_run_name_input("") is True  # allow clearing while typing
    finally:
        gui.container.destroy()


def test_app_copy_command_sets_clipboard(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        tk_root.update()
        gui.on_copy_command()
        tk_root.update()
        assert tk_root.clipboard_get() == gui.command_var.get()
    finally:
        gui.container.destroy()


def test_app_start_conflict_dialog_dispatches_force(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    (repo_root / "results" / "ppo1").mkdir()
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    # avoid a real modal dialog in tests
    gui._ask_run_conflict = lambda run_name: ("force", run_name)
    gui.run_name_var.set("ppo1")
    tk_root.update()
    try:
        gui.on_start()
        deadline = time.monotonic() + 5
        while gui._process is None and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert gui._process is not None
        assert "--force" in gui.command_var.get()
        # Let a couple of real poll ticks run so the process is properly reaped
        # through the normal _finish_process path, instead of tearing down the
        # container with a live process and a still-scheduled poll job.
        deadline = time.monotonic() + 5
        while gui._process is not None and time.monotonic() < deadline:
            gui._process.force_kill()
            tk_root.update()
            time.sleep(0.02)
    finally:
        if gui._process is not None:
            gui._process.force_kill()
        if gui._poll_job is not None:
            tk_root.after_cancel(gui._poll_job)
            gui._poll_job = None
        gui.container.destroy()


def test_app_start_stop_end_to_end_with_fake_trainer(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    gui.run_name_var.set("ppo1")
    gui.show_window_var.set(False)
    tk_root.update()
    try:
        assert "disabled" not in gui.start_button.state()

        gui.on_start()
        deadline = time.monotonic() + 5
        while "Passo" not in gui.status_var.get() and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert "Passo" in gui.status_var.get()
        assert "disabled" in gui.start_button.state()
        assert "disabled" not in gui.stop_button.state()

        gui.on_stop()
        deadline = time.monotonic() + 5
        while gui._process is not None and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert gui._process is None
        assert "disabled" not in gui.start_button.state()
        assert "encerrado" in gui.status_var.get().lower()
    finally:
        if gui._process is not None:
            gui._process.force_kill()
        gui.container.destroy()


def test_app_start_training_with_non_executable_interpreter_shows_friendly_error(
    tk_root: tk.Tk, tmp_path: Path, no_real_dialogs: list[tuple[str, str, str]]
) -> None:
    """The real incident this reproduces: python_bin exists but is not executable.

    Must take the short LauncherError path (a plain, specific PT-BR message via
    the stubbed messagebox.showerror), not _show_unexpected_error's generic
    unexpected-error-plus-log-file path.
    """
    repo_root = _full_repo(tmp_path)
    bin_dir = tmp_path / "venv_bin"
    bin_dir.mkdir()
    python_bin = bin_dir / "python3"
    python_bin.write_bytes(b"")  # exists, but no chmod +x: not executable
    (bin_dir / "mlagents-learn").write_bytes(b"")  # only needs to exist for resolve
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=python_bin)
    gui.run_name_var.set("ppo1")
    tk_root.update()
    try:
        gui.on_start()
        assert gui._process is None
        assert len(no_real_dialogs) == 1
        kind, _title, message = no_real_dialogs[0]
        assert kind == "showerror"
        assert "ambiente virtual" in message.lower()
        assert "erro inesperado" not in message.lower()
    finally:
        gui.container.destroy()


def test_show_unexpected_error_uses_rich_dialog_not_plain_messagebox(
    tk_root: tk.Tk, tmp_path: Path, no_real_dialogs: list[tuple[str, str, str]]
) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    recorded: list[dict[str, object]] = []
    gui._show_error_dialog = lambda **kwargs: recorded.append(kwargs)  # avoid a real Toplevel
    try:
        gui._show_unexpected_error("um teste", ValueError("algo deu errado"))
        assert not no_real_dialogs  # the plain messagebox path was not used
        assert len(recorded) == 1
        assert "um teste" in str(recorded[0]["message"])
        log_path = recorded[0]["log_path"]
        assert isinstance(log_path, Path)
        assert log_path.is_file()
        # the path also survives in the log area, not just the (closeable) dialog
        assert log_path.name in gui.log_text.get("1.0", "end")
    finally:
        gui.container.destroy()


def test_watch_status_text_without_time_limit(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        gui._watch_deadline = None
        text = gui._watch_status_text()
        assert "jogando" in text
        assert "Parar" in text
        assert "Tempo restante" not in text
    finally:
        gui.container.destroy()


def test_watch_status_text_with_time_limit_counts_down(tk_root: tk.Tk, tmp_path: Path) -> None:
    repo_root = _full_repo(tmp_path)
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    try:
        gui._watch_deadline = time.monotonic() + 90  # 1 minute 30 seconds left
        text = gui._watch_status_text()
        assert "Tempo restante: 1m" in text
        gui._watch_deadline = time.monotonic() - 5  # already past: never show negative time
        text = gui._watch_status_text()
        assert "Tempo restante: 0m00s" in text
    finally:
        gui.container.destroy()


def test_app_watch_status_does_not_wait_for_first_summary_line(
    tk_root: tk.Tk, tmp_path: Path
) -> None:
    """The real gap this closes: at --time-scale=1 the first summary line only
    arrives after summary_freq decisions (~4 minutes for this tutorial's configs),
    so the status must switch to "playing" on the connection line instead.
    """
    repo_root = _full_repo(tmp_path)
    _make_run(repo_root / "results", "ppo1")
    gui = app.CentralDeTreinoApp(tk_root, repo_root=repo_root, python_bin=_fake_venv(tmp_path))
    gui.notebook.select(1)
    gui.watch_run_var.set("ppo1")
    gui.no_time_limit_var.set(True)
    tk_root.update()
    try:
        gui.on_start()
        deadline = time.monotonic() + 5
        while "jogando" not in gui.status_var.get() and time.monotonic() < deadline:
            tk_root.update()
            time.sleep(0.02)
        assert "jogando" in gui.status_var.get()
        assert "Passo" not in gui.status_var.get()
        assert gui._watch_connected is True
    finally:
        if gui._process is not None:
            gui._process.force_kill()
        gui.container.destroy()
