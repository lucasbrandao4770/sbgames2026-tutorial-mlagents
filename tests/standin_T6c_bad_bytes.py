"""Stand-in trainer for m7: writes one line of bytes invalid in UTF-8 (the
effective pipe encoding when Popen gets text=True with no explicit errors=),
then keeps printing valid lines, then waits for SIGINT like the real trainer.

Used to prove (or, at RP0, disprove) that ManagedProcess's reader thread
survives an undecodable line instead of dying silently on it and leaving the
pipe undrained.
"""

from __future__ import annotations

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


def main() -> int:
    """Print a bad-bytes line, then valid lines until interrupted, then exit 0."""
    signal.signal(signal.SIGINT, _handle_sigint)
    print("[FAKE] standin T6c antes dos bytes invalidos", flush=True)
    sys.stdout.buffer.write(b"\xff\xfe linha invalida em utf-8 \xff\n")
    sys.stdout.buffer.flush()
    step = 0
    while not _stop_requested:
        step += 1
        print(f"[FAKE] linha valida depois dos bytes invalidos {step}", flush=True)
        time.sleep(0.05)
    print("[FAKE] Interrompido.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
