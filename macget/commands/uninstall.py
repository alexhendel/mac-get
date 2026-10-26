"""uninstall / remove / rm / autoremove: removed kegs and casks."""
import os
import re

from ..style import bold, muted

COMMANDS = {"uninstall", "remove", "rm", "autoremove"}


def heading(op, h):
    if re.match(r"(Autoremoving|Would autoremove) \d+ unneeded", h):
        op.open_list(h.rstrip(".:").strip())
        return True
    return False


def line(op, s):
    if s.startswith("Uninstalling "):
        m = re.match(r"Uninstalling (\S+?)\.\.\. \((.+)\)", s)
        if m:
            path = m.group(1).rstrip("/")
            name = f"{os.path.basename(os.path.dirname(path))} {muted(os.path.basename(path))}"
            removed(op, name, m.group(2).replace(", ", " · "))
        else:
            op.set_stage(s.rstrip("."))
        return True
    if s.endswith("was successfully uninstalled!"):
        removed(op, s.split()[0])
        return True
    return False


def summary(op, bits):
    if op.removed:
        bits.append(f"{len(op.removed)} removed")


def removed(op, name, detail=""):
    op.removed.append(name)
    op.done += 1
    op.ok(f"Removed {bold(name)}", detail)
