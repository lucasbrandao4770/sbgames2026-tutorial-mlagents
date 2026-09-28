"""T9c stand-in for scripts/verify_env.py: one output line holds bytes no codec decodes."""

from __future__ import annotations

import sys

if __name__ == "__main__":
    # 0xff is invalid in UTF-8 and 0x81 is undefined in cp1252: bad on every lab locale.
    sys.stdout.buffer.write(b"[OK]    byte ruim: \xff\x81\n")
    sys.stdout.buffer.write(b"Resumo: 13 OK, 0 AVISO, 0 FALHA\n")
    sys.stdout.flush()
