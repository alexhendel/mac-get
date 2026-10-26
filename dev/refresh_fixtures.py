#!/usr/bin/env python3
"""Re-capture tests/fixtures from the installed brew.

    python3 dev/refresh_fixtures.py

Run this after a brew update, then `git diff tests/fixtures` shows what changed
in brew's output, and `python3 -m unittest` shows whether mac-get still copes.
Snapshots that change for good reasons are re-recorded with UPDATE_SNAPSHOTS=1.

Needs network access (brew fetches its API data). Install marks (✔) in the
fixtures reflect what is installed on this machine.
"""
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.realpath(__file__)))
sys.path.insert(0, ROOT)

from macget.brew import BREW, brew_env, capture_on_pty  # noqa: E402

FIXTURES = os.path.join(ROOT, "tests", "fixtures")

# fixture name -> brew arguments, captured on a pty like mac-get's views do
PTY = {
    "search_curl.txt": ["search", "curl"],
    "search_desc_curl.txt": ["search", "--desc", "curl"],
    "info_curl.txt": ["info", "curl"],
    "info_cask_firefox.txt": ["info", "--cask", "firefox"],
    "info_jq_missing.txt": ["info", "jq", "definitely-not-a-pkg-xyz"],
}
# fixture name -> brew arguments, captured on a pipe like the live renderer does
PIPED = {
    "fetch_figlet.txt": ["fetch", "--force", "figlet"],
}


class QuietUI:
    """Stands in for macget.ui.UI: capture_on_pty only needs these."""

    def __getattr__(self, name):
        return lambda *a, **k: None


def main():
    os.makedirs(FIXTURES, exist_ok=True)
    env = dict(brew_env(), HOMEBREW_NO_AUTO_UPDATE="1")
    os.environ.update(HOMEBREW_NO_AUTO_UPDATE="1")
    for name, args in PTY.items():
        _, text = capture_on_pty(QuietUI(), args, "")
        write(name, text)
    for name, args in PIPED.items():
        out = subprocess.run([BREW, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                             env=env, text=True).stdout
        write(name, out)


def write(name, text):
    with open(os.path.join(FIXTURES, name), "w") as f:
        f.write(text)
    print(f"wrote tests/fixtures/{name} ({len(text.splitlines())} lines)")


if __name__ == "__main__":
    main()
