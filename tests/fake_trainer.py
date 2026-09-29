"""Stand-in for mlagents-learn, used by the process-manager and headless GUI tests.

Prints summary lines shaped like the real trainer's ("Step: N. ... Mean Reward: ...")
at a fast, configurable interval, and on SIGINT prints a line and exits 0 - fast enough
for the test suite, without ever touching Unity, PyTorch or mlagents.
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
    """Accept (and ignore) the same flags central_de_treino.py might pass."""
    parser = argparse.ArgumentParser()
    parser.add_argument("config", nargs="?", default=None)
    parser.add_argument("--env", default=None)
    parser.add_argument("--run-id", default="fake")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--no-graphics", action="store_true")
    parser.add_argument("--initialize-from", default=None)
    parser.add_argument("--inference", action="store_true")
    parser.add_argument("--time-scale", default=None)
    parser.add_argument("--capture-frame-rate", default=None)
    parser.add_argument(
        "--interval",
        type=float,
        default=0.05,
        help="Seconds between fake summary lines (fast by default, for tests).",
    )
    parser.add_argument(
        "--ignore-sigint",
        action="store_true",
        help="Simulate a hung trainer, to exercise the force-kill path in tests.",
    )
    args, _unknown = parser.parse_known_args(argv)
    return args


def main(argv: list[str] | None = None) -> int:
    """Print fake summary lines until interrupted, then exit like the real trainer."""
    args = parse_args(argv)
    behavior = "FlappyAgent"
    if args.ignore_sigint:
        signal.signal(signal.SIGINT, signal.SIG_IGN)
    else:
        signal.signal(signal.SIGINT, _handle_sigint)
    step = 0
    print(f"[FAKE] mlagents-learn de mentira, run-id={args.run_id}", flush=True)
    # Mirrors the real trainer's main-process lines (see central_de_treino.py's
    # _GAME_CONNECTED_MARKER), which the app uses to detect the game window
    # opening without waiting for the first (much later, at real time) summary.
    if args.initialize_from:
        print(
            f"[INFO] Initializing from results/{args.initialize_from}/FlappyAgent/checkpoint.pt.",
            flush=True,
        )
    print("[INFO] Connected to Unity environment with package version 4.1.0", flush=True)
    while not _stop_requested:
        step += 2000
        reward = 1.5 + (step % 5000) / 1000.0
        state = "Not Training" if args.inference else "Training"
        print(
            f"{behavior}. Step: {step}. Time Elapsed: {step / 1000:.3f} s. "
            f"Mean Reward: {reward:.3f}. Std of Reward: 0.500. {state}.",
            flush=True,
        )
        time.sleep(args.interval)
    print("[FAKE] Interrompido, salvando modelo...", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
