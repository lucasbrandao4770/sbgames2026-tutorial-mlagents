"""Stand-in for mlagents-learn used by tests/test_lifecycle_status.py (task T6b1).

Prints the lines it is given, optionally keeps printing summary lines until SIGINT
(or forever, with --ignore-sigint, like a hung trainer), optionally lingers after
SIGINT the way the real trainer takes a moment to shut down, optionally writes a
model file, and exits with the requested code. Never touches Unity or mlagents.
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from types import FrameType

_stop_requested = False


def _handle_sigint(signum: int, frame: FrameType | None) -> None:
    """Mark the loop for a clean exit, mirroring the real trainer's Ctrl+C handling."""
    del signum, frame
    global _stop_requested
    _stop_requested = True


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the scenario flags; the app's own mlagents flags never reach this script."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--print", dest="lines", action="append", default=[])
    parser.add_argument("--until-sigint", action="store_true")
    parser.add_argument("--ignore-sigint", action="store_true")
    parser.add_argument("--linger", type=float, default=0.0)
    parser.add_argument("--write-model", type=Path, default=None)
    parser.add_argument("--exit-code", type=int, default=0)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Play the scenario described by the flags and return its exit code."""
    args = parse_args(argv)
    signal.signal(signal.SIGINT, signal.SIG_IGN if args.ignore_sigint else _handle_sigint)
    for line in args.lines:
        print(line, flush=True)
    step = 0
    while args.until_sigint and not _stop_requested:
        step += 1000
        print(
            f"FlappyAgent. Step: {step}. Time Elapsed: 1.000 s. Mean Reward: 1.000. "
            "Std of Reward: 0.500. Training.",
            flush=True,
        )
        time.sleep(0.02)
    if _stop_requested:
        print("[STANDIN] Ctrl+C recebido, encerrando.", flush=True)
        time.sleep(args.linger)
    if args.write_model is not None:
        args.write_model.parent.mkdir(parents=True, exist_ok=True)
        args.write_model.write_bytes(b"onnx")
    return args.exit_code


if __name__ == "__main__":
    sys.exit(main())
