#!/usr/bin/env python3
"""Run a command on a pseudo-terminal and print what the user would end up seeing.

    python3 dev/capture.py ./mac-get info jq

Spinner frames are collapsed so the output stays readable. Useful for testing
mac-get without an interactive terminal (e.g. from an agent or CI).
"""
import os
import pty
import re
import subprocess
import sys

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def capture(cmd):
    master, slave = pty.openpty()
    proc = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=slave, stderr=slave)
    os.close(slave)
    raw = b""
    while True:
        try:
            chunk = os.read(master, 65536)
        except OSError:  # EIO: child closed the pty
            break
        if not chunk:
            break
        raw += chunk
    os.close(master)
    return proc.wait(), raw.decode("utf-8", "replace")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    code, text = capture(sys.argv[1:])
    for line in text.split("\n"):
        # Keep only the last redraw of a \r-overwritten line.
        line = ANSI_RE.sub("", line.rstrip("\r").split("\r")[-1])
        if line.strip()[:1] in SPINNER and line.strip():
            continue
        print(line)
    print(f"[exit {code}]")


if __name__ == "__main__":
    main()
