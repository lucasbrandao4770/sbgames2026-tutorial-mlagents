"""Stand-in for a trainer whose graceful stop takes a while (M5).

Prints "READY" once its SIGINT handler is in place. On SIGINT it writes the marker
file "sigint" into --marker-dir, waits --stop-delay seconds (a real run's final model
export), writes the marker "stopped" and exits 0. It exits by itself after 60 s
without a SIGINT, a last resort should a test fail to stop it.
"""

from __future__ import annotations

import argparse
import signal
import time
from pathlib import Path
from types import FrameType

_stop_requested = False


def _on_sigint(signum: int, frame: FrameType | None) -> None:
    """Mark the loop for a graceful stop, like the real trainer's Ctrl+C handling."""
    del signum, frame
    global _stop_requested
    _stop_requested = True


def main() -> int:
    """Idle until SIGINT, then stop slowly and leave markers for the test."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--marker-dir", type=Path, required=True)
    parser.add_argument("--stop-delay", type=float, default=1.5)
    parser.add_argument("--tag", default="", help="Marks the process for the test's cleanup.")
    args = parser.parse_args()
    signal.signal(signal.SIGINT, _on_sigint)
    print("READY", flush=True)
    deadline = time.monotonic() + 60
    while not _stop_requested:
        if time.monotonic() > deadline:
            return 2
        time.sleep(0.02)
    (args.marker_dir / "sigint").write_text("")
    print("STOPPING", flush=True)
    time.sleep(args.stop_delay)
    (args.marker_dir / "stopped").write_text("")
    print("STOPPED", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
