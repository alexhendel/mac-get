"""cleanup (and the automatic cleanup after installs): removed files and space freed."""
import re

from ..style import human_bytes, plural, to_bytes

COMMANDS = {"cleanup"}

SIZE = r"([\d.]+)\s*([KMGT]?B)"


def heading(op, h):
    if re.match(r"Running `brew cleanup", h) or h.startswith("Cleaning"):
        op.open_section("cleanup")
        op.set_stage("Cleaning up")
        return True
    # "This operation has freed approximately 10.3MB of disk space." (or "would free")
    m = re.match(r"This operation (?:has freed|would free) approximately " + SIZE, h)
    if m:
        op.cleanup_bytes = to_bytes(m.group(1), m.group(2))  # brew's total is authoritative
        return True
    return False


def line(op, s):
    removing = s.startswith("Removing:")
    if (removing or s.startswith("Would remove:")) and (
            op.section == "cleanup" or op.args[:1] == ["cleanup"]):
        op.cleanup_count += 1
        op.cleanup_dry = not removing
        # "Removing: /path... (1.2MB)" or "Would remove: /path (1,707 files, 34.6MB)"
        m = re.search(SIZE + r"\)$", s)
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
        files = f"{op.cleanup_count} old {plural(op.cleanup_count, 'file')}"
        size = human_bytes(op.cleanup_bytes) if op.cleanup_bytes else ""
        if op.cleanup_dry:
            op.ok(f"Would clean up {files}", size and size + " would be freed")
        else:
            op.ok(f"Cleaned up {files}", size and size + " freed")
