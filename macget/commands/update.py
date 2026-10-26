"""update (and auto-update before other commands): Homebrew and tap updates."""
import re

from ..style import plural

COMMANDS = {"update"}


def heading(op, h):
    if re.match(r"(New|Outdated|Deleted|Renamed) (Formulae|Casks)", h):
        op.open_list(h.rstrip(".").strip())
        return True
    if re.match(r"(Auto-)?[Uu]pdating Homebrew", h):
        op.set_stage("Updating Homebrew")
        return True
    m = re.match(r"Updated (\d+) taps? \((.*)\)", h)
    if m:
        n = int(m.group(1))
        op.ok(f"Updated {n} {plural(n, 'tap')}", m.group(2))
        return True
    return False


def line(op, s):
    if s.startswith("Updated Homebrew from"):
        op.ok("Homebrew updated", s.replace("Updated Homebrew from", "").strip(" ."))
    elif s == "Already up-to-date.":
        op.ok("Homebrew is up to date")
    else:
        return False
    return True
