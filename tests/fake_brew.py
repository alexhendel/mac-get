#!/usr/bin/env python3
"""A stand-in for brew used by the stream tests.

Prints $FAKE_BREW_OUTPUT (a fixture path) line by line, optionally ends with
$FAKE_BREW_PARTIAL (text without a newline, like an interactive prompt) and
exits with $FAKE_BREW_EXIT.

With $FAKE_BREW_SIGLOG set it instead touches $FAKE_BREW_SIGLOG.ready, waits
to be interrupted, appends one line to that file per SIGINT received, prints
a cleanup message and exits with $FAKE_BREW_EXIT (default 130), like brew on Ctrl-C.
"""
import os
import signal
import sys
import time

siglog = os.environ.get("FAKE_BREW_SIGLOG")
if siglog:
    def interrupted(*_):
        with open(siglog, "a") as f:
            f.write("SIGINT\n")
    signal.signal(signal.SIGINT, interrupted)

with open(os.environ["FAKE_BREW_OUTPUT"]) as f:
    for line in f:
        sys.stdout.write(line)
sys.stdout.flush()

if siglog:
    open(siglog + ".ready", "w").close()
    deadline = time.monotonic() + 5
    while not os.path.exists(siglog) and time.monotonic() < deadline:
        time.sleep(0.02)
    time.sleep(0.5)  # brew's cleanup: a second Ctrl-C would land here
    print("Cleaned up after interrupt", flush=True)
    sys.exit(int(os.environ.get("FAKE_BREW_EXIT", "130")))

partial = os.environ.get("FAKE_BREW_PARTIAL")
if partial:
    sys.stdout.write(partial)
    sys.stdout.flush()
    time.sleep(0.8)  # long enough for mac-get to treat it as a prompt
    sys.stdout.write("\n")

sys.exit(int(os.environ.get("FAKE_BREW_EXIT", "0")))
