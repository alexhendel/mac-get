#!/usr/bin/env python3
"""A stand-in for brew used by the stream tests.

Prints $FAKE_BREW_OUTPUT (a fixture path) line by line, optionally ends with
$FAKE_BREW_PARTIAL (text without a newline, like an interactive prompt) and
exits with $FAKE_BREW_EXIT.
"""
import os
import sys
import time

with open(os.environ["FAKE_BREW_OUTPUT"]) as f:
    for line in f:
        sys.stdout.write(line)
sys.stdout.flush()

partial = os.environ.get("FAKE_BREW_PARTIAL")
if partial:
    sys.stdout.write(partial)
    sys.stdout.flush()
    time.sleep(0.8)  # long enough for mac-get to treat it as a prompt
    sys.stdout.write("\n")

sys.exit(int(os.environ.get("FAKE_BREW_EXIT", "0")))
