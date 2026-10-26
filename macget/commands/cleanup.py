"""cleanup (and the automatic cleanup after installs): removed files and space freed."""
import re

from ..style import human_bytes, plural, to_bytes

COMMANDS = {"cleanup"}


def heading(op, h):
    if re.match(r"Running `brew cleanup", h) or h.startswith("Cleaning"):
        op.open_section("cleanup")
        op.set_stage("Cleaning up")
        return True
    return False


def line(op, s):
    if s.startswith("Removing:") and op.section == "cleanup":
        op.cleanup_count += 1
        # "Removing: /path... (1.2MB)" or "Removing: /path... (92 files, 4.5MB)"
        m = re.search(r"([\d.]+)\s*([KMGT]?B)\)$", s)
        if m:
            op.cleanup_bytes += to_bytes(m.group(1), m.group(2))
        return True
    if re.match(r"(Pruned|Removed)\b", s):
        op.ok(s.rstrip("."))
        return True
    return False


def summary(op, bits):
    # Printed as a step line rather than a summary bit: it's the cleanup's result.
    if op.cleanup_count:
        op.ok(f"Cleaned up {op.cleanup_count} old {plural(op.cleanup_count, 'file')}",
              human_bytes(op.cleanup_bytes) + " freed" if op.cleanup_bytes else "")
