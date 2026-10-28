"""search: results grouped by type, in columns, with installed and status marks."""
import re

from ..brew import PASSTHROUGH_FLAGS, capture_on_pty
from ..style import (PAD, accent, bold, columns, green, muted, plural, red, term_width, truncate,
                     yellow)
from ..ui import UI

ENTRY = re.compile(r"^(\S+)\s*(✔︎?)?\s*(?:\((\w+)\))?\s*(?::\s*(.*))?$")
NOT_FOUND = ("No formulae or casks found", "No formulae found", "No casks found")


def handles(args):
    return (args[:1] == ["search"] and any(not a.startswith("-") for a in args[1:])
            and not set(args) & PASSTHROUGH_FLAGS)


def run(args):
    ui = UI(args)
    terms = [a for a in args[1:] if not a.startswith("-")]
    code, text = capture_on_pty(ui, args, f"Searching for {' '.join(terms)}")
    if code is None:
        ui.footer(130)
        return 130

    plain = [t.lower() for t in terms if not (t.startswith("/") and t.endswith("/"))]

    def highlight(text):
        low = text.lower()
        for t in plain:
            i = low.find(t)
            if i >= 0:
                return text[:i] + accent(bold(text[i:i + len(t)])) + text[i + len(t):]
        return text

    sections, errors = parse(ui, text)

    width = term_width()
    total = 0
    for title, entries in sections:
        if not entries:
            continue
        total += len(entries)
        ui.println(f"{PAD}{bold(title)} {muted(str(len(entries)))}")

        if any(desc is not None for *_, desc in entries):  # --desc: one per line
            nw = min(max(len(e[0]) + tag(e[2])[0] for e in entries), 40)
            for name, mark, status, desc in entries:
                tlen, tstr = tag(status)
                room = width - len(PAD) - nw - 8
                desc = truncate(desc or "", room) if room > 10 else ""
                pad = " " * max(0, nw - len(name) - tlen)
                ui.println(f"{PAD}{green('✓') if mark else ' '} {highlight(name)}{tstr}{pad}"
                           f"  {muted(desc)}")
        else:
            cells = []
            for name, mark, status, _ in entries:
                tlen, tstr = tag(status)
                lead = green("✓ ") if mark else "  "
                cells.append((2 + len(name) + tlen, lead + highlight(name) + tstr))
            for row in columns(cells, width):
                ui.println(row)
        ui.println()

    for e in errors:
        if not any(n in e for n in NOT_FOUND):
            ui.error(e)
    if total:
        ui.println(f"{PAD}{green('●')} {bold(str(total))} {plural(total, 'result')}"
                   + muted(f"   {green('✓')} installed   ·   mac-get info <name> for details"))
    elif not ui.errors:
        ui.println(f"{PAD}{yellow('●')} No formulae or casks found for {bold(' '.join(terms))}")
    ui.println()
    return code


def parse(ui, text):
    """Return ([(section title, [(name, mark, status, desc)])], errors)."""
    sections, current, errors = [], None, []
    for ln in text.splitlines():
        ln = ln.strip()
        if ln.startswith("==> "):
            current = (ln[4:].strip(), [])
            sections.append(current)
        elif ln.startswith("Error:"):
            errors.append(ln[6:].strip())
        elif ln.startswith("Warning:"):
            ui.warn(ln[8:].strip())
        elif ln:
            if current is None:  # e.g. --formula without a header
                current = ("Results", [])
                sections.append(current)
            parts = [ln] if ": " in ln else re.split(r"\s{2,}", ln)
            for part in parts:
                m = ENTRY.match(part.strip())
                if m:
                    current[1].append(m.groups())
    return sections, errors


def tag(status):
    """(plain length, styled) for a deprecated/disabled tag."""
    if not status:
        return 0, ""
    color = red if status == "disabled" else yellow
    return len(status) + 1, " " + color(status)
