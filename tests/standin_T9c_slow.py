"""T9c stand-in for scripts/verify_env.py: never answers within the (shortened) limit.

It sleeps a bounded time, so it ends by itself even if a test fails to stop it.
"""

from __future__ import annotations

import time

if __name__ == "__main__":
    time.sleep(20)
    print("Resumo: 13 OK, 0 AVISO, 0 FALHA")
