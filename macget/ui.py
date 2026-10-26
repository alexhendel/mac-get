"""Terminal output primitives: spinner line, step lines, boxes, header/footer."""
import sys
import time

from .style import (PAD, SPINNER, accent, bold, cyan, fmt_secs, green, muted, plural, red,
                    term_width, truncate, visible_len, wrap, yellow)


class UI:
    def __init__(self, args):
        self.args = args
        self.start = time.monotonic()
        self.stage = "Preparing"
        self.stage_start = self.start
        self.frame = 0
        self.spinner_visible = False
        self.paused = False          # e.g. while sudo asks for a password
        self.total = 0               # packages we expect to finish
        self.done = 0
        self.warnings = 0
        self.errors = 0

    # low-level output -------------------------------------------------------

    def write(self, s):
        sys.stdout.write(s)
        sys.stdout.flush()

    def hide_cursor(self):
        self.write("\033[?25l")

    def show_cursor(self):
        self.write("\033[?25h")

    def clear_spinner(self):
        if self.spinner_visible:
            self.write("\r\033[2K")
            self.spinner_visible = False

    def println(self, s=""):
        self.clear_spinner()
        self.write(s + "\n")

    def draw_spinner(self):
        if self.paused:
            return
        self.frame += 1
        width = term_width()
        glyph = accent(SPINNER[self.frame % len(SPINNER)])
        elapsed = muted(fmt_secs(time.monotonic() - self.stage_start))

        bar = ""
        if self.total > 1:
            slots = 18
            filled = int(slots * min(self.done, self.total) / self.total)
            bar = (
                accent("━" * filled) + muted("─" * (slots - filled))
                + " " + muted(f"{self.done}/{self.total}") + "  "
            )

        room = width - len(PAD) - 2 - visible_len(bar) - visible_len(elapsed) - 4
        label = truncate(self.stage, max(10, room))
        gap = " " * max(2, room - len(label) + 2)
        line = f"{PAD}{glyph} {bold(label)}{gap}{bar}{elapsed}"
        if visible_len(line) >= width:  # very narrow terminal: drop extras
            line = f"{PAD}{glyph} {truncate(self.stage, width - 6)}"
        self.write("\r\033[2K" + line)
        self.spinner_visible = True

    # semantic helpers -------------------------------------------------------

    def set_stage(self, text):
        self.stage = text
        self.stage_start = time.monotonic()
        self.paused = False

    def step(self, icon, title, detail=""):
        width = term_width()
        detail = muted(detail) if detail else ""
        head = f"{PAD}{icon} {title}"
        gap = width - visible_len(head) - visible_len(detail) - 2
        if detail and gap >= 2:
            self.println(head + " " * gap + detail)
        else:
            self.println(head + (f"  {detail}" if detail else ""))

    def ok(self, title, detail=""):
        self.step(green("✓"), title, detail)

    def note(self, text):
        width = term_width() - len(PAD) - 4
        self.println(f"{PAD}  {muted(truncate(text, width))}")

    def warn(self, text):
        self.warnings += 1
        self.println(f"{PAD}{yellow('▲')} {yellow(bold('Warning'))} {text}")

    def error(self, text):
        self.errors += 1
        self.println(f"{PAD}{red('✗')} {red(bold('Error'))} {text}")

    def box(self, title, lines, color=cyan):
        while lines and not lines[-1].strip():
            lines.pop()
        while lines and not lines[0].strip():
            lines.pop(0)
        if not lines:
            return
        width = min(term_width() - len(PAD) - 2, 96)
        self.println()
        self.println(PAD + color("╭─ ") + bold(title) + " " + color("─" * max(0, width - len(title) - 4)))
        for ln in lines:
            for chunk in wrap(ln, width - 4):
                self.println(PAD + color("│ ") + " " + chunk)
        self.println(PAD + color("╰" + "─" * (width - 1)))
        self.println()

    # lifecycle --------------------------------------------------------------

    def header(self):
        cmd = " ".join(self.args) or "help"
        self.println()
        self.println(f"{PAD}{accent('◆')} {bold('mac-get')} {muted('›')} {cmd}")
        self.println()

    def footer(self, code, bits=()):
        self.clear_spinner()
        took = fmt_secs(time.monotonic() - self.start)
        bits = list(bits)
        if self.warnings:
            bits.append(yellow(f"{self.warnings} {plural(self.warnings, 'warning')}"))
        summary = muted(" · ").join(bits)
        self.println()
        if code == 0:
            self.println(f"{PAD}{green('●')} {green(bold('Done'))} {muted('in ' + took)}"
                         + (f"   {summary}" if summary else ""))
        elif code == 130:
            self.println(f"{PAD}{yellow('●')} {yellow(bold('Cancelled'))} {muted('after ' + took)}")
        else:
            self.println(f"{PAD}{red('●')} {red(bold('Failed'))} {muted(f'(exit {code}) after {took}')}"
                         + (f"   {summary}" if summary else ""))
        self.println()
