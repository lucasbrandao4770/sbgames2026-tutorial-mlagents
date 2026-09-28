"""Central de treino: janela Tkinter para o tutorial de Unity ML-Agents.

Roda os mesmos comandos de terminal que o tutorial ensina (treinar, assistir a um modelo
treinado, abrir o TensorBoard) a partir de uma janela simples, sempre mostrando o comando
exato que está prestes a rodar. Toda a lógica que não depende de janela (montagem de
comandos, validação de nomes, busca de configs/builds/runs, leitura do YAML, parsing da
saída do treinador e o gerenciador de processos) vive em funções e classes puras, sem
nenhum objeto Tk: a janela só é criada dentro de main().
"""

from __future__ import annotations

import dataclasses
import http.client
import os
import platform
import queue
import re
import shlex
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
import traceback
import urllib.error
import urllib.request
import webbrowser
from collections.abc import Callable, Iterable
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

import yaml

# ----------------------------------------------------------------------------
# Constantes
# ----------------------------------------------------------------------------

CONFIGS_GLOB = "python/configs/**/*.yaml"
# m14: an Editor-only config (behavior "Basic"); the Treinar tab would run it against
# the FlappyBird build, where mlagents trains FlappyAgent with default settings.
EXCLUDED_CONFIG_NAMES: frozenset[str] = frozenset({"Basic_ppo.yaml"})
DEFAULT_CONFIG_RELATIVE = Path("python/configs/ppo/FlappyBird_ppo.yaml")
DEFAULT_RUN_NAME = "ppo1"
RUN_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")

# B2: the tutorial's docs use one specific run name (and show/hide the game
# window) per config, keyed by filename since that is stable regardless of
# which subfolder under python/configs/ a config lives in.
DOC_DEFAULT_RUN_SETTINGS: dict[str, tuple[str, bool]] = {
    "FlappyBird_ppo.yaml": ("ppo1", True),
    "FlappyBird_run1.yaml": ("il1", False),
    "FlappyBird_desafio.yaml": ("ppo2", False),
}
# Run names the tutorial's docs and slides use for steps that have no default above
# (the second and third imitation runs). Never suggested as an alternative name.
RESERVED_RUN_NAMES: frozenset[str] = frozenset({"il2", "il3"})

WATCH_RUN_ID = "assistir"
# Fica sob results/ (já ignorado pelo git, exceto results/reference/), nunca dentro do
# próprio run treinado: assim o YAML gerado não conflita com o run original. Um
# arquivo por run (M3), não um único arquivo compartilhado: veja _watch_config_path.
WATCH_CONFIG_DIR = Path("results") / ".central_de_treino"
WATCH_DEFAULT_TIME_LIMIT_MIN = 3

TENSORBOARD_URL = "http://localhost:6006"
TENSORBOARD_READY_TIMEOUT_S = 30.0
GRACEFUL_STOP_TIMEOUT_S = 30.0

BASE_PORT_ENV_VAR = "CENTRAL_DE_TREINO_BASE_PORT"


def _read_base_port() -> int | None:
    """Read BASE_PORT_ENV_VAR once; None means "use the trainer's own default"."""
    raw = os.environ.get(BASE_PORT_ENV_VAR)
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


# Read once at import time, not per command: with the variable unset, nothing
# changes (--base-port is simply never added). Set it to steer every trainer this
# app launches to a non-default port, e.g. to avoid a port someone else is using.
BASE_PORT: int | None = _read_base_port()


# ----------------------------------------------------------------------------
# Descoberta de Tcl/Tk: alguns interpretadores Python (por exemplo, um build
# portátil gerenciado pelo uv) reorganizam os arquivos do Tcl/Tk para fora dos
# caminhos que o _tkinter procura sozinho, e tk.Tk() falha com "Can't find a
# usable init.tcl". Deve rodar antes de qualquer objeto Tk ser criado.
# ----------------------------------------------------------------------------


def _find_tcl_tk_library(base_prefix: Path, name: str) -> Path | None:
    """Find the newest lib/<name>8.* folder under base_prefix that really has its
    main script file (init.tcl for Tcl, tk.tcl for Tk), without hardcoding a
    version. Returns None if nothing usable is found.
    """
    marker = "init.tcl" if name == "tcl" else "tk.tcl"
    candidates = sorted((base_prefix / "lib").glob(f"{name}8.*"), reverse=True)
    for candidate in candidates:
        if (candidate / marker).is_file():
            return candidate
    return None


def ensure_tcl_tk_discoverable() -> None:
    """Set TCL_LIBRARY/TK_LIBRARY when this interpreter cannot find them by itself.

    Only a fallback: does nothing when the two variables are already set (never
    overrides a value the user set), and looks under sys.base_prefix (the real
    interpreter behind any venv), not sys.prefix, since a venv does not carry its
    own copy of Tcl/Tk. Safe to call even when nothing needs fixing. Must run
    before any Tk object is created, and before anything else that needs Tcl.
    """
    base_prefix = Path(sys.base_prefix)
    if "TCL_LIBRARY" not in os.environ:
        tcl_dir = _find_tcl_tk_library(base_prefix, "tcl")
        if tcl_dir is not None:
            os.environ["TCL_LIBRARY"] = str(tcl_dir)
    if "TK_LIBRARY" not in os.environ:
        tk_dir = _find_tcl_tk_library(base_prefix, "tk")
        if tk_dir is not None:
            os.environ["TK_LIBRARY"] = str(tk_dir)


SUMMARY_LINE_RE = re.compile(
    r"(?P<behavior>[\w.-]+)\.\s+Step:\s+(?P<step>\d+)\.\s+"
    r"Time Elapsed:\s+(?P<elapsed>[\d.]+)\s*s\.\s+"
    r"Mean Reward:\s+(?P<reward>N/A|-?[\d.]+)\.\s+Std of Reward:\s+(?P<std>N/A|-?[\d.]+)\.\s+"
    r"(?P<state>Not Training|Training)\."
)

# Trechos conhecidos da saída do mlagents-learn (ver report.md de inference_test) mapeados
# para uma dica curta em português. returncode != 0 é exigido pelo chamador antes de olhar
# para o texto.
_KNOWN_FAILURES: tuple[tuple[str, str], ...] = (
    (
        "Previous data from this run ID was not found",
        (
            "Não há dados salvos desse treino para continuar. "
            "Clique em Iniciar de novo para começar do zero."
        ),
    ),
    (
        "Previous data from this run ID was found",
        "Já existe um treino salvo com esse nome. Escolha continuar, recomeçar ou outro nome.",
    ),
    (
        "UnityWorkerInUseException",
        (
            "A porta de comunicação com o jogo ainda está em uso. Espere alguns segundos "
            "e tente de novo."
        ),
    ),
    (
        "Couldn't launch",
        "Não consegui abrir o jogo. Confira o caminho do build.",
    ),
    # m13: on Windows mlagents reads the YAML with the locale encoding (cp1252), and
    # turns this error into a TrainerConfigError, so this entry must come before that one.
    (
        "'charmap' codec can't decode",
        (
            "O treinador não conseguiu ler um caractere do arquivo de configuração. "
            "Tire os acentos dos comentários desse arquivo e clique em Iniciar de novo."
        ),
    ),
    (
        "TrainerConfigError",
        (
            "O arquivo de configuração tem uma opção ou um valor inválido. "
            "Veja o erro no registro abaixo e corrija o arquivo."
        ),
    ),
    (
        "UnityTimeOutException",
        "O jogo demorou demais para responder. Clique em Iniciar de novo.",
    ),
    # The end of the FileNotFoundError that torch.load raises when "Continuar" runs on
    # a training that never saved a checkpoint.
    (
        "checkpoint.pt'",
        (
            "Esse treino não tem um modelo salvo para continuar. "
            "Clique em Iniciar de novo e escolha Recomeçar ou Usar outro nome."
        ),
    ),
)


class LauncherError(Exception):
    """Erro com uma mensagem curta em português, pronta para mostrar ao usuário."""

    def __init__(self, message: str, detail: str | None = None) -> None:
        """Store the short user-facing message plus an optional technical detail."""
        super().__init__(message)
        self.message = message
        self.detail = detail


@dataclasses.dataclass(frozen=True)
class TrainedRun:
    """A results/ folder ready to be watched with --initialize-from."""

    relative_id: str  # valor passado para --initialize-from
    path: Path
    behaviors: tuple[str, ...]


@dataclasses.dataclass(frozen=True)
class TrainerSummary:
    """One parsed "Step: N. Mean Reward: X" summary line from the trainer."""

    behavior: str
    step: int
    mean_reward: float | None
    is_training: bool


# ----------------------------------------------------------------------------
# Descoberta e validação
# ----------------------------------------------------------------------------


def find_configs(repo_root: Path) -> list[Path]:
    """Return every tutorial trainer config, sorted for a stable dropdown order."""
    configs = repo_root.glob(CONFIGS_GLOB)
    return sorted(path for path in configs if path.name not in EXCLUDED_CONFIG_NAMES)


def default_config(repo_root: Path) -> Path | None:
    """Return the tutorial's default config, or the first one found, or None."""
    preferred = repo_root / DEFAULT_CONFIG_RELATIVE
    if preferred.is_file():
        return preferred
    configs = find_configs(repo_root)
    return configs[0] if configs else None


def is_valid_run_name(name: str) -> bool:
    """A run name must be non-empty and use only letters, digits, _ and -."""
    return bool(RUN_NAME_RE.match(name))


def run_exists(repo_root: Path, run_name: str) -> bool:
    """True when results/<run_name> already exists (mlagents-learn would refuse it)."""
    return (repo_root / "results" / run_name).is_dir()


def default_run_settings_for_config(config_path: Path) -> tuple[str, bool]:
    """Return the (run_name, show_window) the docs use for a given trainer config.

    B2: previously the run name field always defaulted to "ppo1" no matter which
    config was selected, so switching to the imitation or desafio module kept
    "ppo1" - and, worse, a name conflict against an unrelated ppo1 run offered to
    resume or overwrite it. Falls back to the config file's stem, lowercased, for
    any config the docs don't name explicitly (e.g. one an attendee added), and to
    showing the game window, matching the original default.
    """
    settings = DOC_DEFAULT_RUN_SETTINGS.get(config_path.name)
    if settings is not None:
        return settings
    return config_path.stem.lower(), True


def next_available_run_name(repo_root: Path, run_name: str) -> str:
    """Return the first "<base><N>" (N starting at 2) that is free and not reserved.

    Used to suggest a safe alternative in the run-name conflict dialog, so
    accepting it can never collide with (and therefore never risks damaging) an
    existing run. Names the tutorial gives to its own steps are skipped too:
    ppo1 -> ppo3, never ppo2, which is the name of the Module 3 run.
    """
    reserved = {name for name, _show_window in DOC_DEFAULT_RUN_SETTINGS.values()}
    reserved.update(RESERVED_RUN_NAMES)
    base = re.sub(r"\d+$", "", run_name) or run_name
    n = 2
    candidate = f"{base}{n}"
    while run_exists(repo_root, candidate) or candidate in reserved:
        n += 1
        candidate = f"{base}{n}"
    return candidate


def find_build(repo_root: Path, *, system: str | None = None) -> Path | None:
    """Auto-detect the FlappyBird build under builds/ for the given OS.

    system is injectable so every branch can be unit tested from one machine; it
    defaults to platform.system() for real use.
    """
    system = system or platform.system()
    builds_dir = repo_root / "builds"
    if not builds_dir.is_dir():
        return None
    if system == "Darwin":
        candidates = sorted(builds_dir.glob("*.app"))
        return candidates[0] if candidates else None
    if system == "Windows":
        candidates = sorted(
            path for path in builds_dir.glob("**/*.exe") if "crashhandler" not in path.name.lower()
        )
        return candidates[0] if candidates else None
    # Linux: nenhum build existe neste repositório ainda, então esta busca não foi
    # verificada contra um build real. Procura um arquivo executável sem extensão.
    candidates = sorted(
        path
        for path in builds_dir.glob("**/*")
        if path.is_file() and not path.suffix and os.access(path, os.X_OK)
    )
    return candidates[0] if candidates else None


def _run_behaviors_with_checkpoint(run_dir: Path) -> tuple[str, ...]:
    """List the behavior subfolders of run_dir that have an exported checkpoint.pt."""
    if not run_dir.is_dir():
        return ()
    behaviors = [
        child.name
        for child in sorted(run_dir.iterdir())
        if child.is_dir() and (child / "checkpoint.pt").is_file()
    ]
    return tuple(behaviors)


def find_trained_runs(repo_root: Path) -> list[TrainedRun]:
    """List results/ (and results/reference/) folders ready for --initialize-from.

    A run only qualifies once mlagents-learn has written a <Behavior>/checkpoint.pt.
    The bundled results/reference/ runs ship only the final .onnx to keep the
    repository small (see results/reference/README.md), so as shipped none of them
    currently qualify; this is expected, not a bug (see docs/05).
    """
    results_dir = repo_root / "results"
    if not results_dir.is_dir():
        return []
    runs: list[TrainedRun] = []
    for entry in sorted(results_dir.iterdir()):
        if not entry.is_dir() or entry.name in ("reference", ".central_de_treino"):
            continue
        behaviors = _run_behaviors_with_checkpoint(entry)
        if behaviors:
            runs.append(TrainedRun(entry.name, entry, behaviors))
    reference_dir = results_dir / "reference"
    if reference_dir.is_dir():
        for entry in sorted(reference_dir.iterdir()):
            if not entry.is_dir():
                continue
            behaviors = _run_behaviors_with_checkpoint(entry)
            if behaviors:
                runs.append(TrainedRun(f"reference/{entry.name}", entry, behaviors))
    return runs


# ----------------------------------------------------------------------------
# YAML: leitura de configs e geração do YAML reduzido para "Assistir"
# ----------------------------------------------------------------------------


def load_yaml(path: Path) -> dict:
    """Load a YAML file as a dict, raising LauncherError with a short PT-BR message."""
    try:
        with path.open("r", encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
    except OSError as exc:
        raise LauncherError(f"Não consegui abrir {path.name}.", detail=str(exc)) from exc
    except yaml.YAMLError as exc:
        # M9: docs/03 warns that deleting only the "#" (and not the following
        # space) leaves the YAML broken; without a line number, the attendee has
        # no way to find that extra space themselves.
        mark = getattr(exc, "problem_mark", None)
        where = f" perto da linha {mark.line + 1}" if mark is not None else ""
        raise LauncherError(
            f"O arquivo {path.name} tem um erro de formatação{where}. "
            'Abra com "Editar arquivo" e confira os espaços no começo da linha.',
            detail=str(exc),
        ) from exc
    if not isinstance(data, dict):
        raise LauncherError(f"O arquivo {path.name} está vazio ou não é uma configuração válida.")
    return data


def read_behaviors(config_path: Path) -> dict:
    """Return the behaviors mapping of a trainer config, or raise LauncherError."""
    data = load_yaml(config_path)
    behaviors = data.get("behaviors")
    if not isinstance(behaviors, dict) or not behaviors:
        raise LauncherError(f'{config_path.name} não tem uma seção "behaviors".')
    return behaviors


def read_max_steps(config_path: Path) -> int | None:
    """Return max_steps of the first behavior in the config, or None if absent.

    The tutorial's own configs always define exactly one behavior (FlappyAgent or
    Basic), so "the first one" is unambiguous in practice.
    """
    for settings in read_behaviors(config_path).values():
        if isinstance(settings, dict) and isinstance(settings.get("max_steps"), int):
            return settings["max_steps"]
    return None


def generate_watch_config(trained_run_config: Path, dest: Path) -> None:
    """Write a minimal YAML with only the behaviors section of a trained run.

    Keeping only behaviors guarantees the saved network architecture matches the
    checkpoint while dropping every engine/env setting recorded at training time
    (e.g. no_graphics: true), so watching always opens a window regardless of how
    the run was originally trained. See docs/05-central-de-treino.md.
    """
    behaviors = read_behaviors(trained_run_config)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("w", encoding="utf-8") as handle:
        yaml.safe_dump({"behaviors": behaviors}, handle, sort_keys=False, allow_unicode=True)


# ----------------------------------------------------------------------------
# Saída do treinador: parsing e diagnóstico
# ----------------------------------------------------------------------------


def parse_summary_line(line: str) -> TrainerSummary | None:
    """Parse a "Step: N. Time Elapsed: .. Mean Reward: .." line, or return None."""
    match = SUMMARY_LINE_RE.search(line)
    if match is None:
        return None
    reward_text = match.group("reward")
    mean_reward = None if reward_text == "N/A" else float(reward_text)
    return TrainerSummary(
        behavior=match.group("behavior"),
        step=int(match.group("step")),
        mean_reward=mean_reward,
        is_training=match.group("state") == "Training",
    )


def diagnose_failure(output_lines: Iterable[str], returncode: int) -> str | None:
    """Match a known mlagents-learn failure in the captured output to a PT-BR hint."""
    if returncode == 0:
        return None
    text = "\n".join(output_lines)
    for needle, hint in _KNOWN_FAILURES:
        if needle in text:
            return hint
    return None


# With --max-lifetime-restarts=0, both a graceful quit and a hard kill of the game
# print this line before the trainer exits on its own (see inference_test/report.md,
# Round 4); a hard kill additionally raises UnityEnvironmentException with a
# nonzero exit code, which is still a normal end here, not a real failure.
_GAME_CLOSED_MARKER = "exceeded the allowed number of restarts"


def watch_ended_by_closing_game(output_lines: Iterable[str]) -> bool:
    """True when a watch session ended because the attendee closed the game window."""
    return any(_GAME_CLOSED_MARKER in line for line in output_lines)


# The game window is open and the model is playing once this line appears. At
# --time-scale=1 (real time), the first "Step: N ... Mean Reward: ..." summary
# line only arrives after summary_freq decisions - about 4 minutes for this
# tutorial's configs - so the status line cannot wait for one of those instead.
# M7: not "Connected to Unity environment" - that line is logged inside
# UnityEnvironment, which CPython 3.10 on Windows spawns via
# _winapi.CreateProcess with no handle inheritance (multiprocessing's
# popen_spawn_win32.py), so it most likely never reaches this app's pipe there.
# "Initializing from" is logged by torch_model_saver.py in the main process
# instead (every --initialize-from run), which this app's pipe always sees, and
# it doubles as proof that the right checkpoint loaded.
_GAME_CONNECTED_MARKER = "Initializing from"


def model_output_paths(repo_root: Path, run_name: str, behaviors: Iterable[str]) -> list[Path]:
    """Return the expected results/<run>/<Behavior>.onnx path for each behavior."""
    return [repo_root / "results" / run_name / f"{behavior}.onnx" for behavior in behaviors]


def existing_model_paths(
    repo_root: Path, run_name: str, behaviors: Iterable[str], *, saved_since: float | None = None
) -> list[Path]:
    """Filter model_output_paths to the ones that actually exist on disk.

    Checking the filesystem, instead of trusting an "Exported ..." log line, is the
    only way to honestly report where the model was saved. saved_since (an
    st_mtime, typically the moment this session's process was launched) excludes a
    stale .onnx left over from an earlier session on the same run name - without
    it, a failed or force-stopped "Continuar"/"Recomeçar" would read as a normal
    save because the *old* file is still sitting there.
    """
    return [
        path
        for path in model_output_paths(repo_root, run_name, behaviors)
        if path.is_file() and (saved_since is None or path.stat().st_mtime >= saved_since)
    ]


# ----------------------------------------------------------------------------
# Construção de comandos (forma exibível, igual ao que os docs ensinam)
# ----------------------------------------------------------------------------


def _display_path(repo_root: Path, path: Path) -> str:
    """Render a path the way the tutorial docs do: relative, with forward slashes."""
    try:
        return path.resolve().relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return str(path)


def build_train_command(
    *,
    repo_root: Path,
    config: Path,
    run_name: str,
    build: Path,
    show_window: bool,
    resume: bool = False,
    force: bool = False,
) -> list[str]:
    """Build the doc-style mlagents-learn command for the "Treinar" tab.

    resume and force are mutually exclusive; the "run already exists" dialog is
    responsible for only ever setting one of them.
    """
    if resume and force:
        raise LauncherError("Não é possível continuar e recomeçar ao mesmo tempo.")
    if not is_valid_run_name(run_name):
        raise LauncherError("Nome do treino inválido: use só letras, números, _ e -, sem espaços.")
    args = [
        "mlagents-learn",
        _display_path(repo_root, config),
        f"--env={_display_path(repo_root, build)}",
        f"--run-id={run_name}",
    ]
    if BASE_PORT is not None:
        args.append(f"--base-port={BASE_PORT}")
    if resume:
        args.append("--resume")
    if force:
        args.append("--force")
    if not show_window:
        args.append("--no-graphics")
    return args


def build_watch_command(
    *,
    repo_root: Path,
    watch_config: Path,
    build: Path,
    trained_run_id: str,
) -> list[str]:
    """Build the doc-style watch command (see inference_test/report.md, Round 4).

    Uses --initialize-from with a fixed, reused --run-id and --force, which never
    touches the trained run's own folder no matter how many times it is used
    (verified against a real run, see docs/05-central-de-treino.md).
    --max-lifetime-restarts=0 makes closing the game end the session by itself
    instead of ml-agents silently relaunching it as a crashed worker; it must stay
    off the training command, where the default restart behavior is wanted.
    """
    args = [
        "mlagents-learn",
        _display_path(repo_root, watch_config),
        f"--env={_display_path(repo_root, build)}",
        f"--run-id={WATCH_RUN_ID}",
    ]
    if BASE_PORT is not None:
        args.append(f"--base-port={BASE_PORT}")
    args.extend(
        [
            f"--initialize-from={trained_run_id}",
            "--inference",
            "--force",
            "--time-scale=1",
            "--capture-frame-rate=0",
            "--max-lifetime-restarts=0",
        ]
    )
    return args


def build_tensorboard_command() -> list[str]:
    """Build the doc-style TensorBoard command (matches README/docs exactly)."""
    return ["tensorboard", "--logdir", "results"]


def build_verify_env_command() -> list[str]:
    """Build the doc-style command to run the environment checker."""
    return ["python", "scripts/verify_env.py"]


def format_command_for_display(args: list[str], *, system: str | None = None) -> str:
    """Render argv the way a person would type it at a terminal on this OS."""
    system = system or platform.system()
    if system == "Windows":
        return subprocess.list2cmdline(args)
    return shlex.join(args)


def resolve_for_execution(display_args: list[str], python_bin: Path) -> list[str]:
    """Turn a doc-style display command into a real, absolute argv for Popen.

    Every argument stays identical except argv[0]: the bare command name shown in
    the UI ("mlagents-learn", "tensorboard", "python") is replaced by the actual
    binary next to the active interpreter, so the app never depends on the venv
    being activated on PATH. This keeps "the exact command it runs" honest: the
    displayed string is exactly what you would type with the environment active.
    """
    if not display_args:
        raise LauncherError("Comando vazio.")
    program = display_args[0]
    bin_dir = python_bin.parent
    if program == "python":
        resolved = python_bin
    else:
        exe_name = program + (".exe" if os.name == "nt" else "")
        resolved = bin_dir / exe_name
    if not resolved.is_file():
        raise LauncherError(
            f'"{program}" não foi encontrado no ambiente virtual ({bin_dir}). '
            "Confira a instalação em docs/00-instalacao.md."
        )
    return [str(resolved), *display_args[1:]]


# ----------------------------------------------------------------------------
# Gerenciador de processos (treinador e assistir)
# ----------------------------------------------------------------------------

# A process started in the background of a non-interactive shell (a trailing &)
# inherits SIGINT set to ignore (POSIX: "the INT and QUIT signals for an
# asynchronous list shall be set to ignore"). Python then never raises
# KeyboardInterrupt on it, and mlagents-learn's own stop path relies on exactly
# that exception (trainer_controller.py catches KeyboardInterrupt around its main
# loop), so an inherited SIG_IGN would make graceful stop silently do nothing.
# preexec_fn could reset it but is documented as unsafe in a program with
# threads (this app has a reader thread per process), so instead the child's
# first exec is this tiny wrapper, which resets SIGINT to the OS default and
# then os.execv's the real command - a plain exec, not preexec_fn, so it runs
# after the fork/exec machinery has already replaced the process image.
_POSIX_RESET_SIGINT_AND_EXEC = (
    "import os, signal, sys\n"
    "signal.signal(signal.SIGINT, signal.SIG_DFL)\n"
    "os.execv(sys.argv[1], sys.argv[1:])\n"
)


def _posix_wrap_for_sigint_reset(real_args: list[str], python_bin: Path) -> list[str]:
    """Prefix a resolved argv with the SIGINT-reset wrapper, for POSIX Popen calls."""
    return [str(python_bin), "-c", _POSIX_RESET_SIGINT_AND_EXEC, *real_args]


def _posix_popen(args: list[str], cwd: Path, python_bin: Path) -> subprocess.Popen:
    """Start a subprocess in its own session so SIGINT can target the whole group.

    A lone SIGINT to the trainer's PID does not stop it (confirmed against a real
    run, see inference_test/report.md); it has to reach the process group that
    start_new_session=True creates. args is wrapped with _posix_wrap_for_sigint_reset
    first, so the child always starts with SIGINT at its OS default regardless of
    what this process itself inherited.
    """
    wrapped = _posix_wrap_for_sigint_reset(args, python_bin)
    return subprocess.Popen(
        wrapped,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        start_new_session=True,
    )


def _posix_graceful_stop(proc: subprocess.Popen) -> None:
    """Send SIGINT to the whole process group, mirroring a terminal Ctrl+C."""
    try:
        pgid = os.getpgid(proc.pid)
        os.killpg(pgid, signal.SIGINT)
    except ProcessLookupError:
        pass


def _posix_descendants(root_pid: int) -> list[int]:
    """List every descendant PID of root_pid right now, via ps (stdlib-only).

    mlagents launches the game with its own start_new_session=True
    (mlagents_envs/env_utils.py), so it leads a *different* session/group than
    the trainer: os.killpg on the trainer's group never reaches it (M4). Must be
    called while root_pid is still alive - once it exits, its children are
    reparented (PPID becomes 1 or a subreaper) and this lineage walk finds
    nothing, so the caller captures this before killing anything.
    """
    ps = subprocess.run(
        ["ps", "-A", "-o", "pid=,ppid="], capture_output=True, text=True, check=False
    )
    children: dict[int, list[int]] = {}
    for line in ps.stdout.splitlines():
        fields = line.split()
        if len(fields) != 2:
            continue
        pid, ppid = (int(field) for field in fields)
        children.setdefault(ppid, []).append(pid)
    found: list[int] = []
    stack = [root_pid]
    while stack:
        for child in children.get(stack.pop(), []):
            found.append(child)
            stack.append(child)
    return found


def _posix_force_kill(proc: subprocess.Popen) -> None:
    """Escalate to SIGTERM then SIGKILL against the whole process group, then
    SIGKILL any descendant that is still alive afterward (M4: the game, started
    in its own session, survives a killpg on the trainer's group; a responsive
    game usually already quit once the trainer's gRPC link dropped, so this
    sweep is normally a no-op).
    """
    descendants = _posix_descendants(proc.pid)  # capture before anything dies
    try:
        pgid = os.getpgid(proc.pid)
    except ProcessLookupError:
        pgid = None
    if pgid is not None:
        for sig in (signal.SIGTERM, signal.SIGKILL):
            try:
                os.killpg(pgid, sig)
            except ProcessLookupError:
                break
            try:
                proc.wait(timeout=3)
                break
            except subprocess.TimeoutExpired:
                continue
    for pid in descendants:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass


def _windows_popen(args: list[str], cwd: Path) -> subprocess.Popen:
    """Start the trainer with its own hidden console, WITHOUT a new process group.

    A dedicated console lets the short helper process in _windows_send_ctrl_c
    attach to it later and deliver Ctrl+C. CREATE_NEW_PROCESS_GROUP is
    deliberately not used here: per the brief, testing on this project showed the
    trainer does not react to it. Untested in this sandbox (no Windows available);
    see windows_checklist.md.
    """
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = 0  # SW_HIDE
    return subprocess.Popen(
        args,
        cwd=cwd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
        creationflags=subprocess.CREATE_NEW_CONSOLE,
        startupinfo=startupinfo,
    )


# Helper de linha única para enviar Ctrl+C a um console alheio. Roda como processo
# próprio (nunca dentro do processo da GUI) porque um processo só consegue ficar
# preso a um console por vez, e este aqui não pode se desligar do seu próprio.
_WINDOWS_CTRL_C_HELPER_SRC = """
import ctypes
import sys

pid = int(sys.argv[1])
kernel32 = ctypes.windll.kernel32
kernel32.FreeConsole()
if not kernel32.AttachConsole(pid):
    sys.exit(1)
kernel32.SetConsoleCtrlHandler(None, True)
kernel32.GenerateConsoleCtrlEvent(0, 0)
"""


def _windows_send_ctrl_c(pid: int) -> None:
    """Deliver Ctrl+C to a trainer running in its own hidden console.

    Sequence: FreeConsole, AttachConsole(pid), SetConsoleCtrlHandler(None, True) so
    the helper ignores the event it is about to raise, then
    GenerateConsoleCtrlEvent(CTRL_C_EVENT, 0). Untested in this sandbox; see
    windows_checklist.md.
    """
    subprocess.run(
        [sys.executable, "-c", _WINDOWS_CTRL_C_HELPER_SRC, str(pid)],
        capture_output=True,
        timeout=10,
        check=False,
    )


def _windows_force_kill(pid: int) -> None:
    """Kill the trainer's entire process tree via taskkill. Untested in this sandbox."""
    subprocess.run(["taskkill", "/F", "/T", "/PID", str(pid)], capture_output=True, check=False)


class ManagedProcess:
    """Owns one child process (trainer or watch session) across its whole life.

    Output is handed off through a thread-safe queue: a background thread reads
    stdout line by line and the caller (the Tk event loop, via after()) drains it
    with poll_output(). Nothing here ever touches Tk directly, so it can be driven
    from plain tests with the fake trainer.
    """

    def __init__(
        self,
        args: list[str],
        cwd: Path,
        *,
        python_bin: Path,
        graceful_timeout_s: float = GRACEFUL_STOP_TIMEOUT_S,
        system: str | None = None,
    ) -> None:
        """Store launch parameters; start() actually spawns the child.

        python_bin is only used on POSIX, to run the SIGINT-reset wrapper ahead of
        args (see _posix_wrap_for_sigint_reset); Windows's Ctrl+C delivery does not
        need it.
        """
        self.args = args
        self.cwd = cwd
        self.python_bin = python_bin
        self.graceful_timeout_s = graceful_timeout_s
        self.system = system or platform.system()
        self.output_queue: queue.Queue[str] = queue.Queue()
        self.exit_code: int | None = None
        self._proc: subprocess.Popen | None = None
        self._reader_thread: threading.Thread | None = None
        self._graceful_stop_requested_at: float | None = None

    def start(self) -> None:
        """Spawn the child process and start reading its output in the background."""
        if self.system == "Windows":
            self._proc = _windows_popen(self.args, self.cwd)
        else:
            self._proc = _posix_popen(self.args, self.cwd, self.python_bin)
        self._reader_thread = threading.Thread(target=self._read_output, daemon=True)
        self._reader_thread.start()

    def _read_output(self) -> None:
        """Background-thread body: stream stdout lines, then capture the exit code."""
        assert self._proc is not None and self._proc.stdout is not None
        for line in iter(self._proc.stdout.readline, ""):
            self.output_queue.put(line.rstrip("\n"))
        self.exit_code = self._proc.wait()

    def poll_output(self) -> list[str]:
        """Drain every output line queued since the last call, without blocking."""
        lines: list[str] = []
        while True:
            try:
                lines.append(self.output_queue.get_nowait())
            except queue.Empty:
                break
        return lines

    def is_running(self) -> bool:
        """True while the child process is still alive."""
        return self._proc is not None and self._proc.poll() is None

    @property
    def returncode(self) -> int | None:
        """The child's exit code, or None if it has not exited yet.

        Prefer this over exit_code right after is_running() turns False: exit_code
        is only set by the reader thread after it observes EOF and calls wait(),
        which can lag is_running() becoming False by a beat (seen ~7% of the time
        against a stand-in reader/worker pair). poll() reflects the OS state
        directly and needs no such race.
        """
        return None if self._proc is None else self._proc.poll()

    def finish_reading(self, timeout: float = 2.0) -> list[str]:
        """Join the reader thread (bounded) and drain whatever it queued.

        Call this before reading returncode/output at the end of a run, so the
        last lines the process printed (often the ones with the actual hint) are
        not lost to a poll() that raced ahead of the reader thread.
        """
        if self._reader_thread is not None:
            self._reader_thread.join(timeout)
        return self.poll_output()

    def request_graceful_stop(self) -> None:
        """Ask the child to stop the way a terminal Ctrl+C would."""
        if self._proc is None:
            return
        self._graceful_stop_requested_at = time.monotonic()
        if self.system == "Windows":
            _windows_send_ctrl_c(self._proc.pid)
        else:
            _posix_graceful_stop(self._proc)

    def graceful_timeout_elapsed(self) -> bool:
        """True once graceful_timeout_s has passed since request_graceful_stop()."""
        if self._graceful_stop_requested_at is None:
            return False
        return (time.monotonic() - self._graceful_stop_requested_at) >= self.graceful_timeout_s

    def force_kill(self) -> None:
        """Kill the whole process tree. The final model of this run may be lost."""
        if self._proc is None:
            return
        if self.system == "Windows":
            _windows_force_kill(self._proc.pid)
        else:
            _posix_force_kill(self._proc)


def start_tensorboard(
    python_bin: Path, repo_root: Path, *, system: str | None = None
) -> subprocess.Popen:
    """Start `tensorboard --logdir results` as a child with no visible console."""
    system = system or platform.system()
    args = resolve_for_execution(build_tensorboard_command(), python_bin)
    kwargs: dict = {"cwd": repo_root, "stdout": subprocess.DEVNULL, "stderr": subprocess.DEVNULL}
    if system == "Windows":
        kwargs["creationflags"] = subprocess.CREATE_NO_WINDOW
    else:
        args = _posix_wrap_for_sigint_reset(args, python_bin)
    return subprocess.Popen(args, **kwargs)


def stop_tensorboard(proc: subprocess.Popen) -> None:
    """Terminate the TensorBoard child, escalating to kill if it will not quit."""
    if proc.poll() is not None:
        return
    proc.terminate()
    try:
        proc.wait(timeout=5)
    except subprocess.TimeoutExpired:
        proc.kill()


def is_tensorboard_up(url: str = TENSORBOARD_URL, timeout: float = 1.0) -> bool:
    """True when something already answers at url (ours or someone else's).

    A one-off check (the initial click of the TensorBoard button), so a real
    HTTP GET is fine here; m8: also catch http.client.HTTPException, which a
    non-HTTP listener on the port can raise and which is not an OSError.
    """
    try:
        with urllib.request.urlopen(url, timeout=timeout):
            return True
    except (urllib.error.URLError, OSError, http.client.HTTPException):
        return False


def _tensorboard_port_open(
    host: str = "127.0.0.1", port: int = 6006, timeout: float = 0.25
) -> bool:
    """True if something accepts a TCP connection on host:port right now.

    Used for the *repeated* readiness probe instead of an HTTP GET (M8): on
    Windows, "localhost" resolves to ::1 first, and TensorBoard/werkzeug binds
    IPv4 only, so a refused IPv6 connect there can cost about a second per
    probe. Probing 127.0.0.1 directly by raw TCP connect skips both the DNS
    step and the HTTP round trip.
    """
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


# ----------------------------------------------------------------------------
# Erros e abrir arquivos/pastas no sistema
# ----------------------------------------------------------------------------


def write_error_log(repo_root: Path, context: str, exc: BaseException) -> Path:
    """Write a full traceback to disk and return its path.

    Prefers results/ (already gitignored tutorial output); falls back to the
    system temp folder if results/ cannot be created or written to.
    """
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    log_name = f"central_de_treino_erro_{timestamp}.log"
    content = f"Contexto: {context}\n\n" + "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    try:
        target_dir = repo_root / "results"
        target_dir.mkdir(parents=True, exist_ok=True)
        log_path = target_dir / log_name
        log_path.write_text(content, encoding="utf-8")
        return log_path
    except OSError:
        log_path = Path(tempfile.gettempdir()) / log_name
        log_path.write_text(content, encoding="utf-8")
        return log_path


def _file_manager_command(system: str, path: Path) -> list[str]:
    """Argv to reveal path in the OS file manager. Pure so every branch is testable."""
    if system == "Darwin":
        return ["open", str(path)]
    if system == "Windows":
        return ["explorer", str(path)]
    return ["xdg-open", str(path)]


def open_results_folder(repo_root: Path, *, system: str | None = None) -> None:
    """Create results/ if needed and open it in the OS file manager."""
    system = system or platform.system()
    results_dir = repo_root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(_file_manager_command(system, results_dir))


def _default_app_command(system: str, path: Path) -> list[str] | None:
    """Argv to open path in a text editor, or None to signal os.startfile.

    -t makes macOS's `open` use the default *text* editor (per `man open`)
    instead of whatever, if anything, claims the .yaml extension: a clean lab
    Mac is unlikely to have any app associated with .yaml at all (M6).
    """
    if system == "Darwin":
        return ["open", "-t", str(path)]
    if system == "Windows":
        return None
    return ["xdg-open", str(path)]


def open_in_default_editor(path: Path, *, system: str | None = None) -> None:
    """Open path with whatever app the OS associates with its file type.

    M6: a clean lab PC likely has nothing associated with .yaml, which raises
    on Windows (os.startfile) and silently does nothing on macOS (a plain
    `open`, no -t, exits 1); fall back to a text editor that is always present.
    """
    system = system or platform.system()
    if system == "Windows":
        try:
            os.startfile(str(path))  # type: ignore[attr-defined]  # Windows-only stdlib call
        except OSError:
            subprocess.Popen(["notepad.exe", str(path)])
        return
    command = _default_app_command(system, path)
    assert command is not None
    subprocess.Popen(command)


# ----------------------------------------------------------------------------
# Janela (Tkinter). A classe abaixo só cria widgets dentro de __init__: nada
# neste módulo cria um objeto Tk antes que alguém instancie CentralDeTreinoApp
# (normalmente só main(), ou um teste que construiu a raiz Tk de propósito).
# ----------------------------------------------------------------------------


class CentralDeTreinoApp:
    """The whole window: two config tabs plus a shared start/stop/log area."""

    def __init__(self, root: tk.Tk, repo_root: Path, python_bin: Path | None = None) -> None:
        """Build every widget and prime the dropdowns from repo_root's contents."""
        self.root = root
        self.repo_root = repo_root
        self.python_bin = python_bin or Path(sys.executable)

        # Seam for tests: swap in a ManagedProcess built against the fake trainer.
        self._process_factory: Callable[[list[str], Path], ManagedProcess] = lambda args, cwd: (
            ManagedProcess(args, cwd, python_bin=self.python_bin)
        )

        self._process: ManagedProcess | None = None
        self._mode: str | None = None
        self._run_name: str = ""
        self._current_behaviors: tuple[str, ...] = ()
        self._max_steps: int | None = None
        self._output_history: list[str] = []
        self._watch_ending: bool = False
        self._watch_connected: bool = False
        self._watch_deadline: float | None = None
        self._stop_requested: bool = False
        self._stopped_by_time_limit: bool = False
        self._launched_at: float = 0.0
        self._closing: bool = False
        self._run_name_is_custom: bool = False
        self._setting_run_name_programmatically: bool = False
        self._build_path: Path | None = None
        self._tensorboard_proc: subprocess.Popen | None = None
        self._poll_job: str | None = None
        self._force_stop_job: str | None = None
        self._watch_time_limit_job: str | None = None
        self._config_widgets: list[tk.Widget] = []
        self._config_by_label: dict[str, Path] = {}
        self._runs_by_label: dict[str, TrainedRun] = {}

        self.config_var = tk.StringVar()
        self.run_name_var = tk.StringVar(value=DEFAULT_RUN_NAME)
        self.build_var = tk.StringVar()
        self.show_window_var = tk.BooleanVar(value=True)
        self.watch_run_var = tk.StringVar()
        self.time_limit_var = tk.StringVar(value=str(WATCH_DEFAULT_TIME_LIMIT_MIN))
        self.no_time_limit_var = tk.BooleanVar(value=False)
        self.command_var = tk.StringVar()
        self.status_var = tk.StringVar(value="Pronto.")
        self.progress_var = tk.DoubleVar(value=0.0)

        self._build_widgets()
        self._refresh_config_choices()
        self._refresh_build_choice()
        self._refresh_trained_runs()
        self._update_command_preview()

    # -- construção da janela -------------------------------------------------

    def _build_widgets(self) -> None:
        # Everything lives under one container frame, instead of directly under
        # root, so a test can destroy just this app's widgets (gui.container.destroy())
        # and reuse the same Tk root for the next one. Creating and destroying more
        # than one tk.Tk() per process is fragile on macOS's Aqua Tk (after() timers
        # can stop firing for the second interpreter); production only ever builds
        # one root, in main(), so this only matters for the test suite.
        self.container = ttk.Frame(self.root)
        self.container.pack(fill="both", expand=True)

        self.notebook = ttk.Notebook(self.container)
        self.notebook.pack(fill="both", expand=True, padx=8, pady=8)

        treinar_tab = ttk.Frame(self.notebook, padding=8)
        assistir_tab = ttk.Frame(self.notebook, padding=8)
        self.notebook.add(treinar_tab, text="Treinar")
        self.notebook.add(assistir_tab, text="Assistir")
        self.notebook.bind("<<NotebookTabChanged>>", self._update_command_preview)

        self._build_treinar_tab(treinar_tab)
        self._build_assistir_tab(assistir_tab)
        self._build_controls(self.container)

    def _build_treinar_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Configuração:").grid(row=0, column=0, sticky="w", pady=4)
        config_combo = ttk.Combobox(parent, textvariable=self.config_var, state="readonly")
        config_combo.grid(row=0, column=1, sticky="ew", padx=4)
        config_combo.bind("<<ComboboxSelected>>", self._on_config_selected)
        self._config_combo = config_combo
        edit_button = ttk.Button(parent, text="Editar arquivo", command=self.on_edit_config)
        edit_button.grid(row=0, column=2, padx=4)

        ttk.Label(parent, text="Nome do treino:").grid(row=1, column=0, sticky="w", pady=4)
        vcmd = (self.root.register(self._validate_run_name_input), "%P")
        run_name_entry = ttk.Entry(
            parent, textvariable=self.run_name_var, validate="key", validatecommand=vcmd
        )
        run_name_entry.grid(row=1, column=1, sticky="ew", padx=4)
        self.run_name_var.trace_add("write", self._on_run_name_written)

        ttk.Label(parent, text="Build do jogo:").grid(row=2, column=0, sticky="w", pady=4)
        build_entry = ttk.Entry(parent, textvariable=self.build_var, state="readonly")
        build_entry.grid(row=2, column=1, sticky="ew", padx=4)
        browse_button = ttk.Button(parent, text="Procurar...", command=self.on_browse_build)
        browse_button.grid(row=2, column=2, padx=4)

        show_window_check = ttk.Checkbutton(
            parent,
            text="Mostrar a janela do jogo",
            variable=self.show_window_var,
            command=self._update_command_preview,
        )
        show_window_check.grid(row=3, column=0, columnspan=2, sticky="w", pady=4)

        self._config_widgets.extend(
            [
                config_combo,
                edit_button,
                run_name_entry,
                build_entry,
                browse_button,
                show_window_check,
            ]
        )

    def _build_assistir_tab(self, parent: ttk.Frame) -> None:
        parent.columnconfigure(1, weight=1)

        ttk.Label(parent, text="Treino salvo:").grid(row=0, column=0, sticky="w", pady=4)
        run_combo = ttk.Combobox(parent, textvariable=self.watch_run_var, state="readonly")
        run_combo.grid(row=0, column=1, sticky="ew", padx=4)
        run_combo.bind("<<ComboboxSelected>>", self._on_watch_run_selected)
        self._run_combo = run_combo

        ttk.Label(parent, text="Limite de tempo (min):").grid(row=1, column=0, sticky="w", pady=4)
        time_limit_spin = ttk.Spinbox(
            parent, from_=1, to=60, textvariable=self.time_limit_var, width=6
        )
        time_limit_spin.grid(row=1, column=1, sticky="w", padx=4)
        self.time_limit_var.trace_add("write", self._update_command_preview)

        def _toggle_time_limit() -> None:
            time_limit_spin.state(["disabled"] if self.no_time_limit_var.get() else ["!disabled"])
            self._update_command_preview()

        no_limit_check = ttk.Checkbutton(
            parent,
            text="Sem limite de tempo",
            variable=self.no_time_limit_var,
            command=_toggle_time_limit,
        )
        no_limit_check.grid(row=2, column=0, columnspan=2, sticky="w", pady=4)

        ttk.Label(parent, text="Velocidade: normal (tempo real)").grid(
            row=3, column=0, columnspan=2, sticky="w", pady=4
        )

        self._config_widgets.extend([run_combo, time_limit_spin, no_limit_check])

    def _build_controls(self, parent: tk.Widget) -> None:
        frame = ttk.Frame(parent, padding=8)
        frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        frame.columnconfigure(0, weight=1)

        ttk.Label(frame, text="Comando:").grid(row=0, column=0, sticky="w")
        command_entry = ttk.Entry(frame, textvariable=self.command_var, state="readonly")
        command_entry.grid(row=1, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(frame, text="Copiar comando", command=self.on_copy_command).grid(row=1, column=1)

        button_row = ttk.Frame(frame)
        button_row.grid(row=2, column=0, columnspan=2, sticky="w", pady=6)
        self.start_button = ttk.Button(button_row, text="Iniciar", command=self.on_start)
        self.start_button.pack(side="left", padx=(0, 4))
        self.stop_button = ttk.Button(button_row, text="Parar", command=self.on_stop)
        self.stop_button.pack(side="left", padx=4)
        self.stop_button.state(["disabled"])
        self.force_button = ttk.Button(button_row, text="Forçar parada", command=self.on_force_stop)
        self.force_button.pack(side="left", padx=4)
        self.force_button.state(["disabled"])

        utility_row = ttk.Frame(frame)
        utility_row.grid(row=3, column=0, columnspan=2, sticky="w")
        ttk.Button(utility_row, text="Verificar instalação", command=self.on_verify_env).pack(
            side="left", padx=(0, 4)
        )
        ttk.Button(
            utility_row, text="Abrir pasta de resultados", command=self.on_open_results
        ).pack(side="left", padx=4)
        ttk.Button(utility_row, text="TensorBoard", command=self.on_tensorboard).pack(
            side="left", padx=4
        )

        ttk.Label(frame, textvariable=self.status_var).grid(
            row=4, column=0, columnspan=2, sticky="w", pady=(6, 0)
        )
        self.progress = ttk.Progressbar(frame, variable=self.progress_var, mode="determinate")
        self.progress.grid(row=5, column=0, columnspan=2, sticky="ew", pady=4)

        log_frame = ttk.Frame(frame)
        log_frame.grid(row=6, column=0, columnspan=2, sticky="nsew")
        frame.rowconfigure(6, weight=1)
        self.log_text = tk.Text(log_frame, height=12, state="disabled", wrap="word")
        scrollbar = ttk.Scrollbar(log_frame, orient="vertical", command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)
        self.log_text.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")

    # -- estado auxiliar --------------------------------------------------

    def _validate_run_name_input(self, proposed: str) -> bool:
        return proposed == "" or bool(RUN_NAME_RE.match(proposed))

    def _current_tab(self) -> str:
        return "treinar" if self.notebook.index(self.notebook.select()) == 0 else "assistir"

    def _refresh_config_choices(self) -> None:
        configs = find_configs(self.repo_root)
        self._config_by_label = {_display_path(self.repo_root, path): path for path in configs}
        self._config_combo["values"] = list(self._config_by_label.keys())
        default = default_config(self.repo_root)
        if default is not None:
            self.config_var.set(_display_path(self.repo_root, default))
            self._on_config_selected()

    def _on_config_selected(self, *_args: object) -> None:
        """Apply the newly selected config's doc default run name/window (B2).

        Never overwrites a name the attendee already typed by hand (tracked via
        _run_name_is_custom): switching configs to look something up should not
        silently discard a name someone is in the middle of choosing.
        """
        config = self._selected_config()
        if config is not None and not self._run_name_is_custom:
            run_name, show_window = default_run_settings_for_config(config)
            self._setting_run_name_programmatically = True
            try:
                self.run_name_var.set(run_name)
            finally:
                self._setting_run_name_programmatically = False
            self.show_window_var.set(show_window)
        self._update_command_preview()

    def _on_run_name_written(self, *_args: object) -> None:
        """Track attendee edits to the run name field, to gate B2's auto-fill."""
        if not self._setting_run_name_programmatically:
            self._run_name_is_custom = True
        self._update_command_preview()

    def _refresh_build_choice(self) -> None:
        build = find_build(self.repo_root)
        if build is not None:
            self._set_build(build)

    def _refresh_trained_runs(self, prefer: str | None = None) -> None:
        """Reload results/ into the Assistir dropdown, keeping or preselecting a run.

        Called at startup, after every process ends, and whenever the Assistir tab
        is shown - never just once at startup, or "train, then watch" would still
        show the pre-training (empty) list until the app was restarted.
        """
        current = prefer or self.watch_run_var.get()
        runs = find_trained_runs(self.repo_root)
        self._runs_by_label = {run.relative_id: run for run in runs}
        self._run_combo["values"] = list(self._runs_by_label.keys())
        for run in runs:
            # M3: refresh every listed run's own watch config, not only the one
            # selected, so the command shown for any run in the dropdown is
            # already pasteable before Iniciar is ever pressed. A run with a
            # broken configuration.yaml just will not preview/paste cleanly;
            # that is reported when the attendee actually selects or starts it.
            try:
                self._ensure_watch_config(run)
            except LauncherError:
                pass
        if current in self._runs_by_label:
            self.watch_run_var.set(current)
        else:
            self.watch_run_var.set(runs[0].relative_id if runs else "")

    def _on_watch_run_selected(self, *_args: object) -> None:
        """Refresh the selected run's own watch config, then the command preview."""
        run = self._selected_run()
        if run is not None:
            try:
                self._ensure_watch_config(run)
            except LauncherError as exc:
                self._show_launcher_error(exc)
        self._update_command_preview()

    def _watch_config_path(self, run: TrainedRun) -> Path:
        """Return this run's own generated watch config path.

        M3: one file per run, instead of a single shared
        results/.central_de_treino/assistir_config.yaml overwritten by whichever
        run was watched last - which meant the displayed command broke if it was
        copied and pasted into a terminal before Iniciar was pressed for that
        specific run, or if a different run was selected afterwards.
        """
        safe_id = run.relative_id.replace("/", "_")
        return WATCH_CONFIG_DIR / f"assistir_{safe_id}.yaml"

    def _ensure_watch_config(self, run: TrainedRun) -> Path:
        """Write (or refresh) run's generated watch config, and return its path."""
        dest = self.repo_root / self._watch_config_path(run)
        generate_watch_config(run.path / "configuration.yaml", dest)
        return dest

    def _set_build(self, path: Path) -> None:
        self._build_path = path
        self.build_var.set(_display_path(self.repo_root, path))
        self._update_command_preview()

    def _selected_config(self) -> Path | None:
        return self._config_by_label.get(self.config_var.get())

    def _selected_run(self) -> TrainedRun | None:
        return self._runs_by_label.get(self.watch_run_var.get())

    def _time_limit_minutes(self) -> float:
        try:
            return max(1.0, float(self.time_limit_var.get()))
        except ValueError:
            return float(WATCH_DEFAULT_TIME_LIMIT_MIN)

    def _append_log(self, text: str) -> None:
        if not text:
            return
        self.log_text.configure(state="normal")
        self.log_text.insert("end", text + "\n")
        self.log_text.see("end")
        self.log_text.configure(state="disabled")

    def _set_running_state(self, running: bool) -> None:
        state = ["disabled"] if running else ["!disabled"]
        for widget in self._config_widgets:
            widget.state(state)
        self.start_button.state(state)
        self.stop_button.state(["!disabled"] if running else ["disabled"])
        self.force_button.state(["disabled"])
        other_tab = 1 if self._current_tab() == "treinar" else 0
        self.notebook.tab(other_tab, state="disabled" if running else "normal")

    # -- pré-visualização do comando ---------------------------------------

    def _update_command_preview(self, *_args: object) -> None:
        try:
            if self._current_tab() == "treinar":
                args = self._build_preview_train_command()
            else:
                if self._process is None:
                    # B1: also refresh on switching to Assistir (not only after a
                    # process ends), so a run trained in an earlier app launch, or
                    # dropped into results/ by hand, shows up without restarting.
                    self._refresh_trained_runs()
                args = self._build_preview_watch_command()
        except LauncherError:
            self.command_var.set("")
            return
        if args is None:
            self.command_var.set("")
            return
        self.command_var.set(format_command_for_display(args))

    def _build_preview_train_command(self) -> list[str] | None:
        config = self._selected_config()
        build = self._build_path
        if config is None or build is None:
            return None
        run_name = self.run_name_var.get().strip() or DEFAULT_RUN_NAME
        return build_train_command(
            repo_root=self.repo_root,
            config=config,
            run_name=run_name,
            build=build,
            show_window=self.show_window_var.get(),
        )

    def _build_preview_watch_command(self) -> list[str] | None:
        run = self._selected_run()
        build = self._build_path
        if run is None or build is None:
            return None
        watch_config = self.repo_root / self._watch_config_path(run)
        return build_watch_command(
            repo_root=self.repo_root,
            watch_config=watch_config,
            build=build,
            trained_run_id=run.relative_id,
        )

    # -- ações: iniciar / parar -------------------------------------------

    def on_start(self) -> None:
        """Dispatch Start to the training or watch flow, per the active tab."""
        if self._current_tab() == "treinar":
            self._start_training()
        else:
            self._start_watch()

    def _start_training(self) -> None:
        try:
            config = self._selected_config()
            if config is None:
                raise LauncherError("Nenhuma configuração encontrada em python/configs/.")
            run_name = self.run_name_var.get().strip()
            if not is_valid_run_name(run_name):
                raise LauncherError(
                    "Nome do treino inválido: use só letras, números, _ e -, sem espaços."
                )
            if run_name in (WATCH_RUN_ID, "reference"):
                # m5: both are reserved by this app (assistir_*.yaml configs live
                # under results/.central_de_treino/, and results/reference/ ships
                # the tutorial's bundled runs) - training into either would collide.
                raise LauncherError(
                    f'"{run_name}" é reservado pelo Central de treino; escolha outro nome.'
                )
            build = self._build_path
            if build is None:
                raise LauncherError(
                    "Nenhum build do jogo encontrado em builds/. Use o botão Procurar."
                )
            resume = False
            force = False
            if run_exists(self.repo_root, run_name):
                choice = self._ask_run_conflict(run_name)
                if choice is None:
                    return
                action, run_name = choice
                resume = action == "resume"
                force = action == "force"
                if action == "rename":
                    # Reflect the chosen name back into the field, so the attendee
                    # sees what is about to run and it survives switching configs.
                    self._setting_run_name_programmatically = True
                    try:
                        self.run_name_var.set(run_name)
                    finally:
                        self._setting_run_name_programmatically = False
                    self._run_name_is_custom = True
            display_args = build_train_command(
                repo_root=self.repo_root,
                config=config,
                run_name=run_name,
                build=build,
                show_window=self.show_window_var.get(),
                resume=resume,
                force=force,
            )
            self._current_behaviors = tuple(read_behaviors(config).keys())
            self._max_steps = read_max_steps(config)
            self._launch(display_args, mode="treinar", run_name=run_name)
        except LauncherError as exc:
            self._show_launcher_error(exc)
        except Exception as exc:  # noqa: BLE001 - último recurso, vira log + aviso curto
            self._show_unexpected_error("iniciar o treino", exc)

    def _start_watch(self) -> None:
        try:
            run = self._selected_run()
            if run is None:
                raise LauncherError("Nenhum treino salvo encontrado. Treine um agente primeiro.")
            build = self._build_path
            if build is None:
                raise LauncherError(
                    "Nenhum build do jogo encontrado em builds/. Use o botão Procurar."
                )
            watch_config = self._ensure_watch_config(run)
            self._current_behaviors = run.behaviors
            self._max_steps = None
            display_args = build_watch_command(
                repo_root=self.repo_root,
                watch_config=watch_config,
                build=build,
                trained_run_id=run.relative_id,
            )
            self._launch(display_args, mode="assistir", run_name=WATCH_RUN_ID)
            if not self.no_time_limit_var.get():
                minutes = self._time_limit_minutes()
                self._watch_deadline = time.monotonic() + minutes * 60
                self._watch_time_limit_job = self.root.after(
                    int(minutes * 60_000), self._on_watch_time_limit
                )
        except LauncherError as exc:
            self._show_launcher_error(exc)
        except Exception as exc:  # noqa: BLE001
            self._show_unexpected_error("assistir ao treino", exc)

    def _ask_run_conflict(self, run_name: str) -> tuple[str, str] | None:
        """Ask what to do about an existing results/<run_name>.

        B2: the safe choice - a different, never-used name - is offered first,
        instead of only resume/overwrite. Before this fix the run name defaulted
        to "ppo1" for every config, so this dialog could easily be about a run
        from a completely different module than the one currently selected.
        Returns (action, run_name) with action one of "rename"/"resume"/"force",
        or None if cancelled.
        """
        next_free = next_available_run_name(self.repo_root, run_name)
        dialog = tk.Toplevel(self.root)
        dialog.title("Treino já existe")
        dialog.transient(self.root)
        dialog.resizable(False, False)
        message = f'Já existe um treino salvo com o nome "{run_name}".\nO que você quer fazer?'
        ttk.Label(dialog, text=message, justify="left", padding=12).pack()

        result: dict[str, tuple[str, str] | None] = {"choice": None}

        def choose(value: tuple[str, str] | None) -> None:
            result["choice"] = value
            dialog.destroy()

        button_frame = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        button_frame.pack(fill="x")
        ttk.Button(
            button_frame,
            text=f"Usar outro nome ({next_free})",
            command=lambda: choose(("rename", next_free)),
        ).pack(fill="x", pady=2)
        ttk.Button(
            button_frame,
            text=f'Continuar o treino "{run_name}" com esta configuração',
            command=lambda: choose(("resume", run_name)),
        ).pack(fill="x", pady=2)
        ttk.Button(
            button_frame,
            text="Recomeçar (apaga o anterior)",
            command=lambda: choose(("force", run_name)),
        ).pack(fill="x", pady=2)
        ttk.Button(button_frame, text="Cancelar", command=lambda: choose(None)).pack(
            fill="x", pady=2
        )
        dialog.protocol("WM_DELETE_WINDOW", lambda: choose(None))
        # m17: grab_set() before the dialog is actually mapped can raise on some
        # X11/Linux window managers; wait_visibility() first avoids that.
        dialog.wait_visibility()
        dialog.grab_set()
        dialog.wait_window()
        return result["choice"]

    def _launch(self, display_args: list[str], *, mode: str, run_name: str) -> None:
        real_args = resolve_for_execution(display_args, self.python_bin)
        process = self._process_factory(real_args, self.repo_root)
        try:
            process.start()
        except OSError as exc:
            # resolve_for_execution already confirmed the file exists; getting here
            # means it exists but could not actually be run (e.g. not executable,
            # or the venv's own interpreter is corrupted) - a short, specific
            # message beats the generic unexpected-error path for this one.
            raise LauncherError(
                "Não consegui iniciar o treinador. O ambiente virtual pode estar "
                "corrompido. Reinstale seguindo docs/00-instalacao.md.",
                detail=str(exc),
            ) from exc
        self._process = process
        self._mode = mode
        self._run_name = run_name
        self._output_history = []
        self._watch_ending = False
        self._watch_connected = False
        self._watch_deadline = None
        self._stop_requested = False
        self._stopped_by_time_limit = False
        self._launched_at = time.time()
        if self._force_stop_job is not None:
            # M2: a timer left over from a *previous* run (nobody clicked Forçar
            # parada before this one started) must not fire mid-way through this
            # one and silently enable Forçar parada on a training that is fine.
            self.root.after_cancel(self._force_stop_job)
            self._force_stop_job = None
        self._set_running_state(True)
        self.status_var.set("Iniciando...")
        self.progress_var.set(0.0)
        self.command_var.set(format_command_for_display(display_args))
        self._poll_process()

    def _poll_process(self) -> None:
        process = self._process
        if process is None:
            return
        for line in process.poll_output():
            self._append_log(line)
            self._output_history.append(line)
            if (
                self._mode == "assistir"
                and not self._watch_connected
                and _GAME_CONNECTED_MARKER in line
            ):
                self._watch_connected = True
            if self._mode == "assistir" and not self._watch_ending and _GAME_CLOSED_MARKER in line:
                # The game was closed; --max-lifetime-restarts=0 means the trainer
                # is now winding down by itself, not hung and not user-stopped, so
                # Forçar parada must not appear (graceful_timeout_elapsed() is only
                # true after request_graceful_stop(), which this path never calls).
                self._watch_ending = True
                self.status_var.set("O jogo foi fechado. Encerrando...")
            summary = parse_summary_line(line)
            if summary is not None and self._mode != "assistir" and not self._watch_ending:
                self._update_status_from_summary(summary)
        if (
            self._mode == "assistir"
            and self._watch_connected
            and not self._watch_ending
            and not self._stop_requested
        ):
            # Do not wait for a parsed summary line: at --time-scale=1 the first
            # one only arrives after ~4 minutes (summary_freq decisions at real
            # time), so the status is derived from connection + elapsed time instead.
            # Skipped once a stop was requested (m2), so this does not overwrite
            # "Parando..." or "Tempo limite atingido..." on the next 100 ms tick.
            self.status_var.set(self._watch_status_text())
        if process.is_running():
            if process.graceful_timeout_elapsed():
                self.force_button.state(["!disabled"])
            self._poll_job = self.root.after(100, self._poll_process)
            return
        self._poll_job = None
        self._finish_process()

    def _watch_status_text(self) -> str:
        """Status shown while a watch session plays, independent of summary lines."""
        text = "O modelo está jogando, ou clique em Parar."
        if self._watch_deadline is not None:
            remaining = max(0, int(self._watch_deadline - time.monotonic()))
            minutes, seconds = divmod(remaining, 60)
            text += f" Tempo restante: {minutes}m{seconds:02d}s."
        return text

    def _update_status_from_summary(self, summary: TrainerSummary) -> None:
        state = "treinando" if summary.is_training else "sem treinar (inferência)"
        reward = "N/A" if summary.mean_reward is None else f"{summary.mean_reward:.2f}"
        if self._max_steps:
            self.progress.configure(mode="determinate", maximum=self._max_steps)
            self.progress_var.set(min(summary.step, self._max_steps))
            self.status_var.set(
                f"Passo {summary.step}/{self._max_steps}, recompensa média {reward} ({state})"
            )
        else:
            self.status_var.set(f"Passo {summary.step}, recompensa média {reward} ({state})")

    def _finish_process(self) -> None:
        process = self._process
        assert process is not None
        # M1: join the reader thread (bounded) before trusting either the output
        # or the exit code - poll() can already report "not running" a beat
        # before the reader thread has drained the last lines and called wait().
        for line in process.finish_reading():
            self._append_log(line)
            self._output_history.append(line)
        returncode = process.returncode
        if returncode is None:
            returncode = 0
        mode = self._mode
        run_name = self._run_name
        # m2: only the time limit itself counts, not a Parar pressed by the user in a
        # watch that merely had a time limit set.
        time_limit_stopped = self._stopped_by_time_limit
        self._process = None
        self._mode = None
        self._set_running_state(False)
        hint = diagnose_failure(self._output_history, returncode)
        if mode == "treinar":
            # Only a model saved *by this session* counts (M1): a stale .onnx
            # from an earlier "Continuar"/"Recomeçar" on the same name must not
            # read as "saved" for a run that just failed or was force-stopped.
            saved = existing_model_paths(
                self.repo_root, run_name, self._current_behaviors, saved_since=self._launched_at
            )
            if saved:
                joined = ", ".join(_display_path(self.repo_root, path) for path in saved)
                self.status_var.set(f"Treino encerrado. Modelo salvo em {joined}.")
            elif hint:
                self.status_var.set(f"Treino terminou com erro. {hint}")
            elif returncode != 0:
                self.status_var.set(
                    "O treino parou com erro. Veja as últimas linhas do registro abaixo."
                )
            else:
                self.status_var.set("Treino encerrado.")
        elif watch_ended_by_closing_game(self._output_history):
            # Normal end, even with a nonzero exit code (a hard-killed game raises
            # UnityEnvironmentException instead of exiting 0 - see report.md Round 4
            # Q5); either way this is not a real failure and must not read as one.
            self.status_var.set("O jogo foi fechado. A exibição terminou.")
        elif time_limit_stopped:
            self.status_var.set("Tempo limite atingido. A exibição terminou.")
        elif hint:
            self.status_var.set(f"Sessão encerrada. {hint}")
        elif returncode != 0:
            self.status_var.set(
                "A exibição parou com erro. Veja as últimas linhas do registro abaixo."
            )
        else:
            self.status_var.set("Sessão de observação encerrada.")
        if self._watch_time_limit_job is not None:
            self.root.after_cancel(self._watch_time_limit_job)
            self._watch_time_limit_job = None
        if self._force_stop_job is not None:
            self.root.after_cancel(self._force_stop_job)
            self._force_stop_job = None
        # B1: a run that just finished training, or one that just stopped watching,
        # must show up (or drop out) of the Assistir list right away - otherwise
        # "train, then watch" only works after restarting the app.
        self._refresh_trained_runs(prefer=run_name if mode == "treinar" else None)
        if self._closing:
            self._close_now()

    def _on_watch_time_limit(self) -> None:
        self._watch_time_limit_job = None
        if self._process is not None and self._mode == "assistir":
            self._stop_requested = True
            self._stopped_by_time_limit = True
            self.status_var.set("Tempo limite atingido, parando...")
            self.on_stop()

    def on_stop(self) -> None:
        """Ask the running process to stop gracefully and arm the force-stop timer."""
        if self._process is None:
            return
        self._stop_requested = True
        self.status_var.set("Parando...")
        self._process.request_graceful_stop()
        self.stop_button.state(["disabled"])
        if self._force_stop_job is not None:
            self.root.after_cancel(self._force_stop_job)
        self._force_stop_job = self.root.after(
            int(self._process.graceful_timeout_s * 1000), self._offer_force_stop
        )

    def _offer_force_stop(self) -> None:
        self._force_stop_job = None
        # M2: also require graceful_timeout_elapsed(), not just "still running" -
        # without it, a timer left over from a *different, already-stopped* run
        # could enable Forçar parada on whatever is running now, seconds after it
        # started, well before its own 30 s are up.
        if (
            self._process is not None
            and self._process.is_running()
            and self._process.graceful_timeout_elapsed()
        ):
            self.force_button.state(["!disabled"])

    def on_force_stop(self) -> None:
        """Kill the process tree immediately; the final model may not be saved."""
        if self._process is None:
            return
        self._process.force_kill()
        self.force_button.state(["disabled"])
        messagebox.showwarning(
            "Central de treino",
            "Parada forçada. O último modelo deste treino pode não ter sido salvo.",
        )

    # -- outras ações ------------------------------------------------------

    def on_copy_command(self) -> None:
        """Copy the currently displayed command to the clipboard."""
        self.root.clipboard_clear()
        self.root.clipboard_append(self.command_var.get())

    def on_browse_build(self) -> None:
        """Let the user pick the game build by hand when auto-detection misses it."""
        system = platform.system()
        filetypes = (
            [("Executável", "*.exe")] if system == "Windows" else [("Todos os arquivos", "*")]
        )
        initial = self.repo_root / "builds"
        chosen = filedialog.askopenfilename(
            title="Escolha o executável do jogo",
            initialdir=str(initial if initial.is_dir() else self.repo_root),
            filetypes=filetypes,
        )
        if chosen:
            self._set_build(Path(chosen))

    def on_edit_config(self) -> None:
        """Open the selected config file in the system's default editor."""
        config = self._selected_config()
        if config is None:
            return
        try:
            open_in_default_editor(config)
        except Exception as exc:  # noqa: BLE001
            self._show_unexpected_error("abrir o arquivo de configuração", exc)

    def on_verify_env(self) -> None:
        """Run scripts/verify_env.py in the background and log its output."""
        display_args = build_verify_env_command()
        self._append_log("$ " + format_command_for_display(display_args))
        try:
            real_args = resolve_for_execution(display_args, self.python_bin)
        except LauncherError as exc:
            self._append_log(exc.message)
            if exc.detail:
                self._append_log(exc.detail)
            return

        def run() -> None:
            try:
                result = subprocess.run(
                    real_args,
                    cwd=self.repo_root,
                    capture_output=True,
                    text=True,
                    timeout=60,
                    check=False,
                )
                output = result.stdout + result.stderr
            except Exception as exc:  # noqa: BLE001
                output = f"Falha ao rodar verify_env.py: {exc}"
            self.root.after(0, lambda: self._append_log(output))

        threading.Thread(target=run, daemon=True).start()

    def on_open_results(self) -> None:
        """Open results/ in the OS file manager."""
        try:
            open_results_folder(self.repo_root)
        except Exception as exc:  # noqa: BLE001
            self._show_unexpected_error("abrir a pasta de resultados", exc)

    def on_tensorboard(self) -> None:
        """Open TensorBoard in the browser, starting it first if needed."""
        if self._tensorboard_proc is not None and self._tensorboard_proc.poll() is None:
            # m8: already starting or already running; a second click must not
            # launch a second TensorBoard and drop the handle to the first one.
            return
        if is_tensorboard_up():
            webbrowser.open(TENSORBOARD_URL)
            return
        try:
            self._tensorboard_proc = start_tensorboard(self.python_bin, self.repo_root)
        except Exception as exc:  # noqa: BLE001
            self._show_unexpected_error("abrir o TensorBoard", exc)
            return
        self._tensorboard_status("Iniciando o TensorBoard...")
        self._poll_tensorboard_ready(time.monotonic() + TENSORBOARD_READY_TIMEOUT_S)

    def _tensorboard_status(self, text: str) -> None:
        """Show a TensorBoard progress message, without stepping on an active
        train/watch status (m8: seen replacing a live watch status in evidence).
        """
        if self._process is None:
            self.status_var.set(text)
        else:
            self._append_log(text)

    def _poll_tensorboard_ready(self, deadline: float) -> None:
        if self._tensorboard_proc is not None and self._tensorboard_proc.poll() is not None:
            # m8: died on its own (e.g. the port was already taken by something
            # non-HTTP) - do not wait out the rest of the 30 s to notice.
            self._tensorboard_proc = None
            self._tensorboard_status(
                "O TensorBoard fechou sozinho ao iniciar. Confira se a porta 6006 já está em uso."
            )
            return
        if time.monotonic() >= deadline:
            self._tensorboard_status("O TensorBoard não respondeu a tempo.")
            if self._process is None:
                messagebox.showerror(
                    "Central de treino",
                    "O TensorBoard demorou demais para responder. Tente o botão de novo.",
                )
            return

        def _probe() -> None:
            # M8: the socket probe runs off the Tk thread; only the (cheap)
            # continuation is handed back via after(), so this never blocks the
            # window even when a probe takes its full timeout to refuse.
            up = _tensorboard_port_open()
            self.root.after(0, lambda: self._on_tensorboard_probe_result(up, deadline))

        threading.Thread(target=_probe, daemon=True).start()

    def _on_tensorboard_probe_result(self, up: bool, deadline: float) -> None:
        if up:
            self._tensorboard_status("TensorBoard pronto.")
            webbrowser.open(TENSORBOARD_URL)
            return
        self.root.after(450, lambda: self._poll_tensorboard_ready(deadline))

    def _show_launcher_error(self, exc: LauncherError) -> None:
        """Show a LauncherError's short message, and log its technical detail.

        M9: exc.detail (e.g. the exact PyYAML error text) used to be attached to
        every LauncherError but never actually shown anywhere; this is the one
        place all of them go through now.
        """
        messagebox.showerror("Central de treino", exc.message)
        if exc.detail:
            self._append_log(exc.detail)

    def _show_unexpected_error(self, context: str, exc: Exception) -> None:
        log_path = write_error_log(self.repo_root, context, exc)
        # Written to the log area too, so the path survives after the dialog closes.
        self._append_log(
            f"Erro inesperado ao {context}. Log: {_display_path(self.repo_root, log_path)}"
        )
        self._show_error_dialog(
            message=(
                f"Ocorreu um erro inesperado ao {context}. "
                "Mostre o caminho abaixo a quem estiver ajudando."
            ),
            log_path=log_path,
        )

    def _show_error_dialog(self, *, message: str, log_path: Path) -> None:
        """A small, copyable error window: message, a selectable log path, and
        buttons to open the log or copy its path.

        A plain messagebox has no selectable text on some platforms, so a
        beginner asked to "send the log path" cannot copy it out; this dialog
        exists specifically so they can.
        """
        dialog = tk.Toplevel(self.root)
        dialog.title("Erro na Central de treino")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        ttk.Label(
            dialog, text=message, justify="left", wraplength=360, padding=(12, 12, 12, 4)
        ).pack(fill="x")
        path_text = _display_path(self.repo_root, log_path)
        # m1: the text lives in the Entry itself, not in a throwaway StringVar that
        # the garbage collector frees, which left the field empty.
        path_entry = ttk.Entry(dialog)
        path_entry.insert(0, path_text)
        path_entry.state(["readonly"])
        path_entry.pack(fill="x", padx=12, pady=(0, 8))

        def _open_log() -> None:
            # Best effort: the path is already shown and copyable either way, so a
            # failure to launch an editor here is not worth its own error dialog.
            try:
                open_in_default_editor(log_path)
            except Exception:  # noqa: BLE001, S110
                pass

        def _copy_path() -> None:
            self.root.clipboard_clear()
            self.root.clipboard_append(path_text)

        button_row = ttk.Frame(dialog, padding=(12, 0, 12, 12))
        button_row.pack(fill="x")
        ttk.Button(button_row, text="Abrir o log", command=_open_log).pack(side="left", padx=(0, 4))
        ttk.Button(button_row, text="Copiar caminho", command=_copy_path).pack(side="left", padx=4)
        ttk.Button(button_row, text="Fechar", command=dialog.destroy).pack(side="left", padx=4)
        dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)

    def on_close(self) -> None:
        """Ask before closing if something is running, then stop it and close.

        M5: the old version blocked the Tk thread in a time.sleep loop for up to
        10 s and then force-killed without asking, freezing the window ("Não
        respondendo" on Windows) and risking the final export. This version asks
        first, then reuses the normal Parar path (graceful stop, the usual 30 s
        Forçar parada offer) and lets the ordinary poll loop finish the job;
        _finish_process() closes the window once the process actually stops.
        """
        if self._process is not None and self._process.is_running():
            if not messagebox.askyesno(
                "Central de treino", "Um treino está rodando. Parar e fechar?"
            ):
                return
            self._closing = True
            self.on_stop()
            return
        self._close_now()

    def _close_now(self) -> None:
        """Stop TensorBoard if running, cancel pending timers, and destroy the root."""
        if self._tensorboard_proc is not None:
            stop_tensorboard(self._tensorboard_proc)
        # Cancel any pending after() timers explicitly instead of relying on
        # destroy() to discard them: a scheduled _poll_process tick that still
        # fires mid-teardown would touch widgets that no longer exist.
        for job in (self._poll_job, self._force_stop_job, self._watch_time_limit_job):
            if job is not None:
                self.root.after_cancel(job)
        self.root.destroy()


def tcl_tk_failure_message(exc: BaseException) -> str:
    """Short PT-BR explanation for when tk.Tk() still fails after auto-discovery."""
    return (
        "Não consegui abrir a janela porque este Python não encontrou o Tcl/Tk.\n"
        "Provavelmente o ambiente virtual está com um problema de instalação.\n"
        "Rode scripts/verify_env.py para checar o ambiente, ou reinstale seguindo "
        "docs/00-instalacao.md.\n"
        f"Detalhe técnico: {exc}"
    )


def main() -> None:
    """Entry point: build the real Tk window and run the event loop."""
    ensure_tcl_tk_discoverable()
    repo_root = Path.cwd()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        # No window exists yet to show this in, so print it: the starter scripts
        # (central_de_treino.command / .cmd) keep the terminal open on a nonzero
        # exit specifically so this stays on screen and can be copied.
        print(tcl_tk_failure_message(exc), file=sys.stderr)
        sys.exit(1)
    root.title("Central de treino")
    root.geometry("900x680")
    root.minsize(760, 560)
    app = CentralDeTreinoApp(root, repo_root=repo_root)
    root.protocol("WM_DELETE_WINDOW", app.on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
