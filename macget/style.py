"""Colors, layout constants and text helpers shared by every view."""
import os
import re
import shutil

USE_COLOR = "NO_COLOR" not in os.environ


def sgr(code):
    return (lambda s: f"\033[{code}m{s}\033[0m") if USE_COLOR else (lambda s: s)


bold, italic = sgr("1"), sgr("3")
red, green, yellow, cyan = (sgr(f"9{i}") for i in (1, 2, 3, 6))
accent = sgr("38;5;141")  # soft violet
muted = sgr("38;5;244")

ANSI_RE = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]|\x1b\][^\x07]*\x07")
SPINNER = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"
PAD = "  "


def visible_len(s):
    return len(ANSI_RE.sub("", s))


def term_width():
    return shutil.get_terminal_size((100, 24)).columns or 100


def fmt_secs(s):
    if s < 60:
        return f"{s:.1f}s"
    m, s = divmod(int(s), 60)
    return f"{m}m {s:02d}s"


def truncate(text, width):
    """Truncate a plain string to width, with an ellipsis."""
    return text if len(text) <= width else text[: max(0, width - 1)] + "…"


def plural(n, word, suffix="s"):
    return f"{word}{suffix if n != 1 else ''}"


def to_bytes(num, unit):
    mult = {"B": 1, "KB": 1e3, "MB": 1e6, "GB": 1e9, "TB": 1e12}
    return float(num) * mult.get(unit, 1)


def human_bytes(n):
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1000:
            return f"{n:.1f}{unit}" if unit != "B" else f"{int(n)}B"
        n /= 1000
    return f"{n:.1f}TB"


def wrap(text, width):
    text = text.rstrip()
    if len(text) <= width:
        return [text]
    indent = re.match(r"\s*", text).group(0)
    out, cur = [], indent
    for word in text.split():
        if cur.strip() and len(cur) + 1 + len(word) > width:
            out.append(cur)
            cur = indent + word
        else:
            cur = f"{cur} {word}" if cur.strip() else cur + word
    if cur:
        out.append(cur)
    return out


def columns(cells, width):
    """Lay out (plain_len, styled) cells in newspaper-style columns."""
    cell = max(n for n, _ in cells) + 3
    per_row = max(1, (width - len(PAD) - 2) // cell)
    rows = (len(cells) + per_row - 1) // per_row
    out = []
    for r in range(rows):
        row = [cells[c * rows + r] for c in range(per_row) if c * rows + r < len(cells)]
        out.append(PAD + "  " + "".join(s + " " * (cell - n) for n, s in row).rstrip())
    return out


def flow(tokens, width, indent):
    """Wrap (plain_len, styled) tokens onto lines no wider than width."""
    lines, cur, cur_len = [], [], 0
    for n, s in tokens:
        if cur and cur_len + 2 + n > width:
            lines.append("  ".join(cur))
            cur, cur_len = [], 0
        cur.append(s)
        cur_len += n + (2 if cur_len else 0)
    if cur:
        lines.append("  ".join(cur))
    return [l if i == 0 else indent + l for i, l in enumerate(lines)]
