"""Stand-in for the game player that mlagents starts in its own session (M4).

Started by tests/standin_T6b2_trainer_with_game.py. Writes "ready" to the file
descriptor given as its first argument once its signal handling is in place, then
idles until killed. With --ignore-sigterm it survives SIGTERM, like a hung player.
It exits by itself after 60 s, a last resort should a test fail to kill it.
"""

from __future__ import annotations

import argparse
import os
import signal
import time


def main() -> int:
    """Signal readiness through the inherited pipe, then idle."""
    parser = argparse.ArgumentParser()
    parser.add_argument("ready_fd", type=int)
    parser.add_argument("--ignore-sigterm", action="store_true")
    parser.add_argument("--tag", default="", help="Marks the process for the test's cleanup.")
    args = parser.parse_args()
    if args.ignore_sigterm:
        signal.signal(signal.SIGTERM, signal.SIG_IGN)
    os.write(args.ready_fd, b"ready\n")
    os.close(args.ready_fd)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
