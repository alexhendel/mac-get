"""Running brew: pass-through exec, pty capture and JSON capture (with spinner)."""
import os
import shutil
import subprocess
import threading

from .style import ANSI_RE

BREW = shutil.which("brew") or "/opt/homebrew/bin/brew"

# Flags that mean the output is for machines or for reading help, or that brew
# will hand the terminal to the user (a build shell, debug prompts): never restyle.
PASSTHROUGH_FLAGS = {"-h", "--help", "--json", "-n", "--dry-run-json",
                     "-i", "--interactive", "-d", "--debug"}


def brew_env(color=False):
    env = dict(os.environ, HOMEBREW_NO_ENV_HINTS="1")
    if not color:
        env["HOMEBREW_NO_COLOR"] = "1"
    return env


def exec_brew(args):
    os.execv(BREW, [BREW, *args])


def capture_on_pty(ui, args, stage):
    """Run brew on a pty with a spinner; return (exit code, ANSI-stripped output).

    On a pty brew emits section headers, ✔ installed marks and status tags it
    leaves out when piped. The pty is very wide so nothing gets truncated.
    Returns code None if the user cancelled.
    """
    import fcntl, pty, struct, termios

    master, slave = pty.openpty()
    fcntl.ioctl(slave, termios.TIOCSWINSZ, struct.pack("HHHH", 50, 1000, 0, 0))
    proc = subprocess.Popen([BREW, *args], stdin=subprocess.DEVNULL, stdout=slave,
                            stderr=slave, env=brew_env(color=True))
    os.close(slave)

    def read():
        raw = b""
        while True:
            try:
                chunk = os.read(master, 65536)
            except OSError:  # EIO: brew closed the pty
                return raw
            if not chunk:
                return raw
            raw += chunk

    try:
        raw = spin(ui, stage, proc, read)
    finally:
        os.close(master)
    if raw is None:
        return None, ""
    return proc.wait(), ANSI_RE.sub("", raw.decode("utf-8", "replace")).replace("\r", "")


def capture_output(ui, args, stage):
    """Run brew on pipes with a spinner; return (exit code, stdout, stderr).

    Code is None if cancelled.
    """
    proc = subprocess.Popen([BREW, *args], stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env=brew_env(), text=True)
    io = spin(ui, stage, proc, proc.communicate)
    if io is None:
        return None, "", ""
    return (proc.returncode, *io)


def spin(ui, stage, proc, read):
    """Show the spinner while read() collects brew's output; return its result.

    read() runs on a thread because output may exceed a pipe buffer, and polling
    alone would deadlock. Returns None if the user cancelled (brew is killed).
    """
    result = []
    reader = threading.Thread(target=lambda: result.append(read()), daemon=True)
    reader.start()
    ui.header()
    ui.set_stage(stage)
    ui.hide_cursor()
    try:
        while reader.is_alive():
            ui.draw_spinner()
            reader.join(0.08)
    except KeyboardInterrupt:
        proc.kill()
        return None
    finally:
        ui.show_cursor()
    ui.clear_spinner()
    return result[0]
