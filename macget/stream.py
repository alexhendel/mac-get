"""Live renderer for commands that change the system (install, upgrade, ...).

brew runs on a pipe and every line it prints is routed through the rule
modules in RULES. Each module recognises the output of its own command, but
all of them are active for every run: an `install` also prints auto-update,
cleanup and caveat output, for example.

A rule module may define:
  COMMANDS             brew commands it adds to the restyled set
  heading(op, h)       handle a `==> ...` line; return True if consumed
  line(op, s)          handle any other line; return True if consumed
  summary(op, bits)    contribute to the final summary (append to bits)
"""
import os
import re
import select
import subprocess
import time

from .brew import BREW, PASSTHROUGH_FLAGS, brew_env
from .commands import cleanup, install, tap, uninstall, update, upgrade
from .style import ANSI_RE, PAD, cyan, yellow
from .ui import UI

RULES = (update, upgrade, install, uninstall, cleanup, tap)
COMMANDS = set().union(*(getattr(r, "COMMANDS", ()) for r in RULES))

NOISE = (
    "Disable this behaviour by setting",
    "Hide these hints",
    "You have ",
    "Bottle Manifest",
    "==> Downloading bottle manifests",
)
# A line of package names, e.g. "wget" or "foo  bar  user/tap/baz" (names are lowercase).
NAMES_LINE = re.compile(r"^[a-z0-9][\w@+.-]*(?:/[\w@+.-]+)*(?:\s+[a-z0-9][\w@+.-]*(?:/[\w@+.-]+)*)*$")


def handles(args):
    return bool(args) and args[0] in COMMANDS and not any(a in PASSTHROUGH_FLAGS for a in args)


class Operation(UI):
    """UI plus the parsing state the rule modules share."""

    def __init__(self, args):
        super().__init__(args)
        self.section = None          # current section kind, e.g. "caveats", "cleanup"
        self.section_title = ""
        self.section_render = None   # set for sections whose lines are buffered
        self.buffer = []
        self.installed, self.removed = [], []
        self.cleanup_count = 0
        self.cleanup_bytes = 0.0
        self.cleanup_dry = False     # "Would remove:" lines from cleanup --dry-run
        self.pending_upgrade = None

    # sections ---------------------------------------------------------------

    def open_section(self, kind, title="", render=None):
        """Start a section. With render, its lines are buffered and passed to
        render(op, title, lines) when the section ends."""
        self.close_section()
        self.section, self.section_title, self.section_render = kind, title, render
        self.buffer = []

    def open_list(self, title):
        """A section that is a plain list of names, shown in a box."""
        self.open_section("list", title, lambda op, t, lines: lines and op.box(
            t, [", ".join(" ".join(lines).split())], cyan))

    def close_section(self):
        render, title, lines = self.section_render, self.section_title, self.buffer
        self.section, self.section_render, self.buffer = None, None, []
        if render:
            render(self, title, lines)

    def stage_pkg(self):
        parts = self.stage.split()
        return parts[1] if len(parts) > 1 else ""

    def prompt(self, text):
        """brew is about to ask for input (e.g. a sudo password): stop the spinner."""
        self.println(f"{PAD}{yellow('🔑')} {text}")
        self.paused = True

    # line dispatch ----------------------------------------------------------

    def handle(self, raw):
        line = ANSI_RE.sub("", raw).rstrip()
        s = line.strip()
        if not s:
            if self.section_render:
                self.buffer.append("")
            return
        if s.startswith("==> "):
            self.handle_heading(s[4:].strip())
            return
        if any(s.startswith(p) for p in NOISE):
            return
        if self.section == "list" and not NAMES_LINE.match(s):
            # brew doesn't always end a name list with a heading
            # (e.g. autoremove goes straight on to "Uninstalling ...").
            self.close_section()
        if self.section_render:
            self.buffer.append(line)
            return

        if s.startswith("Warning:"):
            self.warn(s[8:].strip())
        elif s.startswith("Error:"):
            self.error(s[6:].strip())
        elif "the password may be necessary" in s or s.lower().startswith("password"):
            self.prompt(s)
        elif not any(hasattr(r, "line") and r.line(self, s) for r in RULES):
            self.note(s)

    def handle_heading(self, h):
        if h.startswith("Caveats"):
            title = self.stage_pkg()
            self.open_section("caveats", title, lambda op, t, lines: op.box(
                f"Caveats · {t}" if t else "Caveats", lines, yellow))
            return
        if h.startswith(("Summary", "Downloading bottle manifests")):
            self.close_section()
            if h.startswith("Downloading"):
                self.set_stage("Resolving packages")
            return

        self.close_section()
        if any(hasattr(r, "heading") and r.heading(self, h) for r in RULES):
            return
        if h.startswith("Running installer for") or "sudo" in h:
            self.prompt(h)
            return
        self.set_stage(h.rstrip(".").strip())

    # lifecycle --------------------------------------------------------------

    def footer(self, code, bits=()):
        self.close_section()
        bits = list(bits)
        for r in RULES:
            if hasattr(r, "summary"):
                r.summary(self, bits)
        super().footer(code, bits)


def run(args):
    op = Operation(args)
    proc = subprocess.Popen(
        [BREW, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=brew_env(),
    )
    fd = proc.stdout.fileno()
    op.header()
    op.hide_cursor()
    buf = b""
    last_data = time.monotonic()
    try:
        while True:
            ready, _, _ = select.select([fd], [], [], 0.08)
            if ready:
                chunk = os.read(fd, 65536)
                if not chunk:
                    break
                last_data = time.monotonic()
                buf += chunk
                *lines, buf = re.split(rb"\r\n|\n|\r", buf)
                for ln in lines:
                    op.handle(ln.decode("utf-8", "replace"))
            elif buf and time.monotonic() - last_data > 0.4:
                # A partial line with no newline is usually an interactive prompt.
                op.clear_spinner()
                op.show_cursor()
                op.write(PAD + ANSI_RE.sub("", buf.decode("utf-8", "replace")))
                buf = b""
                op.paused = True
                continue
            op.draw_spinner()
        if buf:
            op.handle(buf.decode("utf-8", "replace"))
        code = proc.wait()
    except KeyboardInterrupt:
        # brew is in our process group, so the terminal already sent it SIGINT;
        # sending another could abort its cleanup. Just give it time to finish.
        try:
            proc.wait(timeout=5)
        except Exception:
            proc.kill()
        code = 130
    finally:
        proc.stdout.close()
        op.show_cursor()
    op.footer(code)
    return code
