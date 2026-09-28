"""Stand-in for mlagents-learn that starts a game in its own session (M4).

Mirrors mlagents_envs/env_utils.py: the game is started with start_new_session=True
and its output goes to DEVNULL, so it leads its own session and process group, and a
killpg on the trainer's group never reaches it. Once the game is ready, prints
"TRAINER_PID=<pid>" and "GAME_PID=<pid>", then idles until killed (default SIGTERM
disposition). It exits by itself after 60 s, a last resort should a test fail.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

GAME = Path(__file__).resolve().parent / "standin_T6b2_game.py"


def main() -> int:
    """Start the game, wait until it is ready, report both pids, then idle."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--game-ignores-sigterm", action="store_true")
    parser.add_argument("--tag", default="", help="Marks both processes for the test's cleanup.")
    args = parser.parse_args()
    read_fd, write_fd = os.pipe()
    game_args = [sys.executable, str(GAME), str(write_fd), f"--tag={args.tag}"]
    if args.game_ignores_sigterm:
        game_args.append("--ignore-sigterm")
    game = subprocess.Popen(
        game_args,
        pass_fds=(write_fd,),
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    os.close(write_fd)
    with os.fdopen(read_fd) as ready:
        line = ready.readline()  # returns at "ready" or at EOF if the game died first
    if line.strip() != "ready":
        print("GAME_FAILED", flush=True)
        game.kill()
        game.wait()
        return 1
    print(f"TRAINER_PID={os.getpid()}", flush=True)
    print(f"GAME_PID={game.pid}", flush=True)
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
