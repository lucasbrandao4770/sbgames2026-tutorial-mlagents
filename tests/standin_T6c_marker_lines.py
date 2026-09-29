"""Stand-in trainer for M7: prints a controlled subset of the two "game
connected" marker lines, so a test can prove the app's watch status depends on
the main-process line ("Initializing from") and not on the environment-worker
lines ("Connected to Unity environment" / "Connected new brain"), which on
Windows most likely never reach the app's pipe (see
scripts/central_de_treino.py's _GAME_CONNECTED_MARKER and CPython's
multiprocessing/popen_spawn_win32.py, which spawns that worker with no handle
inheritance there).

Which lines it prints is controlled by a CLI flag the test's venv shim
appends, not by anything central_de_treino.py itself passes: the app always
builds the same watch argv, so the shim is the only place this can be varied.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from types import FrameType

_stop_requested = False


def _handle_sigint(signum: int, frame: FrameType | None) -> None:
    """Mark the loop for a clean exit, mirroring the real trainer's Ctrl+C handling."""
    del signum, frame
    global _stop_requested
    _stop_requested = True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Accept (and ignore) the flags central_de_treino.py's watch command passes."""
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--run-id", default="fake")
    parser.add_argument("--initialize-from", default=None)
    parser.add_argument("--inference", action="store_true")
    parser.add_argument("--time-scale", default=None)
    parser.add_argument("--capture-frame-rate", default=None)
    parser.add_argument(
        "--emit-main-line",
        action="store_true",
        help="Print the main-process 'Initializing from' line (M7's fixed marker).",
    )
    parser.add_argument(
        "--emit-worker-lines",
        action="store_true",
        help=(
            "Print the env-worker-only 'Connected to Unity environment' / "
            "'Connected new brain' lines (M7's old, unreliable marker)."
        ),
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    """Print the requested marker lines, then wait for SIGINT like the real trainer."""
    args = parse_args(argv)
    signal.signal(signal.SIGINT, _handle_sigint)
    print(f"[FAKE] standin T6c de mentira, run-id={args.run_id}", flush=True)
    if args.emit_main_line:
        print(
            f"[INFO] Initializing from results/{args.initialize_from}/FlappyAgent/checkpoint.pt.",
            flush=True,
        )
    if args.emit_worker_lines:
        print("[INFO] Connected to Unity environment with package version 4.1.0", flush=True)
        print("[INFO] Connected new brain FlappyAgent?team=0 to mlagents.", flush=True)
    while not _stop_requested:
        time.sleep(0.02)
    print("[FAKE] Interrompido.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
