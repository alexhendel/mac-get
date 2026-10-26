"""info: a card per package, then status, dependencies, options, caveats, analytics."""
import re

from ..brew import capture_on_pty
from ..style import (PAD, accent, bold, cyan, flow, green, italic, muted, term_width, wrap,
                     yellow)
from ..ui import UI

HEAD = re.compile(r"^(\S+?)(\s*✔︎?)?(?:\s+\(([^)]*)\))?:\s*(.*)$")
FLAGS = {"--formula", "--formulae", "--cask", "--casks"}
LABEL_W = 16


def handles(args):
    return (args[:1] in (["info"], ["abv"])
            and any(not a.startswith("-") for a in args[1:])
            and all(a in FLAGS for a in args[1:] if a.startswith("-")))


def run(args):
    ui = UI(args)
    names = [a for a in args[1:] if not a.startswith("-")]
    code, text = capture_on_pty(ui, args, f"Looking up {' '.join(names)}")
    if code is None:
        ui.footer(130)
        return 130
    pkgs, errors, warnings = parse(text)
    for w in warnings:
        ui.warn(w)
    for pkg in pkgs:
        render(ui, pkg)
    for e in errors:
        ui.error(e)
    if errors:
        ui.println()
    return code


def parse(text):
    """Split `brew info` output into packages: {head, intro, sections}."""
    pkgs, errors, warnings = [], [], []
    pkg, section = None, None
    for ln in text.splitlines():
        s = ln.strip()
        if s.startswith("Error:"):
            errors.append(s[6:].strip())
        elif s.startswith("Warning:"):
            warnings.append(s[8:].strip())
        elif s.startswith("==> "):
            h = s[4:].strip()
            m = HEAD.match(h)
            if h.startswith("Downloading "):
                section = None
            elif m and not h.startswith(("Caveats", "Analytics")):
                pkg = {"head": m.groups(), "intro": [], "sections": []}
                pkgs.append(pkg)
                section = None
            elif pkg:
                section = (h, [])
                pkg["sections"].append(section)
        elif pkg is not None:
            if section:
                section[1].append(ln.rstrip())
            elif s:
                pkg["intro"].append(s)
    return pkgs, errors, warnings


def render(ui, pkg):
    width = min(term_width(), 110)

    def row(label, value, w=LABEL_W):
        ui.println(f"{PAD}  {muted(label.ljust(max(w, len(label) + 2)))}{value}")

    def heading(title):
        ui.println()
        ui.println(f"{PAD}  {accent('▍')}{bold(title)}")

    intro = pkg["intro"]
    desc = intro[0] if intro and not re.match(r"(https?://|Installed|Not installed|\w[\w ]*: )", intro[0]) else ""
    url = next((l for l in intro if l.startswith(("http://", "https://"))), "")
    render_card(ui, pkg["head"], desc, url, width)
    render_facts(intro, desc, url, row)

    for title, lines in pkg["sections"]:
        body = [l for l in lines if l.strip()]
        if title == "Caveats":
            ui.box("Caveats", list(lines), yellow)
            continue
        if not body:
            continue
        heading(title)
        renderer = SECTIONS.get(title, render_bullets)
        renderer(ui, body, row, width)
    ui.println()


def render_card(ui, head, desc, url, width):
    name, mark, display, rest = head
    m = re.match(r"(?:stable\s+)?(\S+?),?(?:\s+(.*))?$", rest)
    version, tags = (m.group(1), re.findall(r"[\w.-]+", m.group(2) or "")) if m else (rest, [])

    inner = width - len(PAD) - 4
    title = (bold(name) + (" " + green("✓") if mark else "") + "  " + green(version)
             + (muted("  " + " · ".join(tags)) if tags else ""))
    bar = accent("─" * inner)
    ui.println(f"{PAD}{accent('╭')}{bar}")
    ui.println(f"{PAD}{accent('│')}  {title}" + (f"  {muted(italic(display))}" if display else ""))
    for extra in (desc, url):
        if extra:
            for chunk in wrap(extra, inner - 2):
                styled = cyan(chunk) if extra is url else chunk
                ui.println(f"{PAD}{accent('│')}  {styled}")
    ui.println(f"{PAD}{accent('╰')}{bar}")
    ui.println()


def render_facts(intro, desc, url, row):
    for l in intro:
        if re.match(r"Installed( \(|$)", l):
            row("Status", green("✓ " + l))
        elif l.startswith("Not installed"):
            row("Status", muted("○ ") + l)
    paths = []
    for l in intro:
        if l in (desc, url) or re.match(r"(Installed( \(|$)|Not installed)", l):
            continue
        if l.startswith("/"):
            paths.append(l)
        elif re.match(r"[\w][\w ]*: ", l):
            k, v = l.split(": ", 1)
            v = cyan(v) if v.startswith("http") else v
            row("Source" if k == "From" else k, v)
        else:
            row("", yellow(l))
    for p in paths:
        row("Location", muted(p))


def render_versions(ui, body, row, width):
    for l in body:
        m = re.match(r"(\S+)\s*(✔︎?)?\s*(\S+)\s*(?:\((.*)\))?", l.strip())
        if m:
            row(m.group(3), green("✓ ") + muted((m.group(4) or "").replace(", ", " · ")))
        else:
            row("", l.strip())


def render_dependencies(ui, body, row, width):
    dep_w = max([LABEL_W] + [len(l.strip().partition(": ")[0]) + 2 for l in body])
    indent = PAD + "  " + " " * dep_w
    for l in body:
        k, _, items = l.strip().partition(": ")
        tokens = []
        for item in items.split(", "):
            ok = "✔" in item
            item = item.replace("✔︎", "").replace("✔", "").strip()
            tokens.append((len(item) + 2, (green("✓ ") + item) if ok else (muted("○ ") + muted(item))))
        lines_out = flow(tokens, width - len(indent), indent)
        row(k, lines_out[0], dep_w)
        for extra in lines_out[1:]:
            ui.println(extra)


def render_options(ui, body, row, width):
    opt = None
    for l in body:
        if l.startswith(("\t", " ")):
            row(opt or "", muted(l.strip()))
            opt = None
        else:
            if opt:
                row(opt, "")
            opt = l.strip()
    if opt:
        row(opt, "")


def render_analytics(ui, body, row, width):
    parsed = []
    for l in body:
        k, _, v = l.strip().partition(": ")
        counts = dict((d, n) for n, d in re.findall(r"([\d,]+) \((\d+) days\)", v))
        parsed.append((k, counts))
    periods = [d for d in ("30", "90", "365") if any(d in c for _, c in parsed)]
    label_w = max(LABEL_W, max(len(k) for k, _ in parsed) + 2)
    ui.println(f"{PAD}  {' ' * label_w}" + "".join(muted(f"{d + 'd':>12}") for d in periods))
    for k, counts in parsed:
        ui.println(f"{PAD}  {muted(k.ljust(label_w))}"
                   + "".join(f"{counts.get(d, '–'):>12}" for d in periods))


def render_languages(ui, body, row, width):
    tokens = [(len(x), muted(x)) for x in " ".join(body).split(", ")]
    for l in flow(tokens, width - len(PAD) - 4, PAD + "  "):
        ui.println(l if l.startswith(PAD) else PAD + "  " + l)


def render_bullets(ui, body, row, width):
    for l in body:
        ui.println(f"{PAD}  {accent('•')} {l.strip()}")


SECTIONS = {
    "Installed Versions": render_versions,
    "Dependencies": render_dependencies,
    "Requirements": render_dependencies,
    "Options": render_options,
    "Analytics": render_analytics,
    "Languages": render_languages,
}
