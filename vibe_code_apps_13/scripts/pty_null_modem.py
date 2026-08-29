#!/usr/bin/env python3
"""Link two PTYs as a soft null-modem for serial-wire-test (no USB / dialout needed).

Prints two slave paths on stdout (one per line), then bridges until killed.
"""
from __future__ import annotations

import os
import pty
import select
import sys


def main() -> int:
    m1, s1 = pty.openpty()
    m2, s2 = pty.openpty()
    print(os.ttyname(s1), flush=True)
    print(os.ttyname(s2), flush=True)
    # Hold slave fds open so the PTY pair stays valid while the test runs.
    try:
        while True:
            ready, _, _ = select.select([m1, m2], [], [])
            for src, dst in ((m1, m2), (m2, m1)):
                if src not in ready:
                    continue
                try:
                    data = os.read(src, 4096)
                except OSError:
                    return 0
                if not data:
                    return 0
                os.write(dst, data)
    except KeyboardInterrupt:
        return 0
    finally:
        for fd in (m1, m2, s1, s2):
            try:
                os.close(fd)
            except OSError:
                pass


if __name__ == "__main__":
    raise SystemExit(main())
