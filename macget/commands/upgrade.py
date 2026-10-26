"""upgrade: the outdated-packages table and per-package version changes."""
import re

from ..style import PAD, accent, bold, green, muted

COMMANDS = {"upgrade"}

UPGRADE_ROW = re.compile(r"^(\S+)\s+(\S+)\s+->\s+(\S+)(?:\s+\((.+)\))?$")
UPGRADE_ARROW = re.compile(r"^\S+\s+->\s+\S+$")


def heading(op, h):
    if re.match(r"(Would upgrade|Upgrading) (\d+) outdated packages?", h):
        op.open_section("upgrades", h.rstrip(".").strip().rstrip(":"), render_table)
        return True
    m = re.match(r"Upgrading (\S+)$", h)
    if m:
        op.pending_upgrade = (m.group(1), "")
        op.set_stage(f"Upgrading {m.group(1)}")
        return True
    return False


def line(op, s):
    if op.pending_upgrade and UPGRADE_ARROW.match(s):
        op.pending_upgrade = (op.pending_upgrade[0], s)
        op.set_stage(f"Upgrading {op.pending_upgrade[0]}  {s}")
        return True
    return False


def render_table(op, title, lines):
    rows = [m.groups() for m in (UPGRADE_ROW.match(ln.strip()) for ln in lines) if m]
    if not rows:
        return
    op.total = max(op.total, len(rows))
    nw = max(len(r[0]) for r in rows)
    ow = max(len(r[1]) for r in rows)
    vw = max(len(r[2]) for r in rows)
    op.println()
    op.println(f"{PAD}{bold(title)}")
    for name, old, new, size in rows:
        op.println(
            f"{PAD}  {accent('•')} {bold(name.ljust(nw))}  {muted(old.ljust(ow))} "
            f"{accent('→')} {green(new.ljust(vw))}  {muted(size or '')}"
        )
    op.println()
