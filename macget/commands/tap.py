"""tap / untap: adding and removing third-party repositories."""
import re

COMMANDS = {"tap", "untap"}


def line(op, s):
    if re.match(r"(Tapped|Untapped)\b", s):
        op.ok(s.rstrip("."))
        return True
    return False
