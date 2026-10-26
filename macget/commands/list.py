"""list / ls: installed packages from brew's JSON, with versions and outdated marks."""
import json

from ..brew import capture_output
from ..style import (PAD, bold, columns, cyan, green, muted, plural, red, term_width, truncate,
                     visible_len, yellow)
from ..ui import UI

FLAGS = {"--formula": "formulae", "--formulae": "formulae", "--cask": "casks", "--casks": "casks"}


def handles(args):
    return args[:1] in (["list"], ["ls"]) and all(a in FLAGS for a in args[1:])


def run(args):
    ui = UI(args)
    kinds = {FLAGS[a] for a in args[1:]} or {"formulae", "casks"}
    code, out, err = capture_output(ui, ["info", "--json=v2", "--installed"],
                                    "Reading installed packages")
    if code is None:
        ui.footer(130)
        return 130
    if code != 0:
        for ln in err.splitlines():
            ui.error(ln.replace("Error:", "").strip())
        ui.println()
        return code
    data = json.loads(out)

    total = outdated = 0
    if "formulae" in kinds and data.get("formulae"):
        n, o = render_formulae(ui, data["formulae"])
        total, outdated = total + n, outdated + o
    if "casks" in kinds and data.get("casks"):
        n, o = render_casks(ui, data["casks"])
        total, outdated = total + n, outdated + o

    if not total:
        ui.println(f"{PAD}{yellow('●')} Nothing installed")
    else:
        hint = (f"   {yellow(f'↑ {outdated} outdated')} {muted('· mac-get upgrade')}"
                if outdated else f"   {muted('everything up to date')}")
        ui.println(f"{PAD}{green('●')} {bold(str(total))} {plural(total, 'package')}{hint}")
    ui.println()
    return 0


def render_formulae(ui, formulae):
    formulae = sorted(formulae, key=lambda f: f["name"])
    requested = [f for f in formulae if any(i.get("installed_on_request") for i in f["installed"])]
    deps = [f for f in formulae if f not in requested]
    outdated = sum(bool(f["outdated"]) for f in formulae)

    ui.println(f"{PAD}{bold('Formulae')} {muted(str(len(formulae)))}   "
               + muted(f"{len(requested)} installed by you · {len(deps)} dependencies"))
    ui.println()
    rows = []
    for f in requested:
        inst = f["installed"][-1]["version"]
        v, vlen = version_cell(inst, f["versions"].get("stable"), f["outdated"])
        rows.append((mark(f["outdated"]), f["name"], v, vlen, f.get("desc"), tags(f)))
    if rows:
        table(ui, rows)
    if deps:
        ui.println()
        ui.println(f"{PAD}  {muted('Dependencies')}")
        cells = []
        for f in deps:
            inst = f["installed"][-1]["version"]
            lead = yellow("↑ ") if f["outdated"] else muted("· ")
            cells.append((len(f["name"]) + len(inst) + 3, lead + f["name"] + " " + muted(inst)))
        for row in columns(cells, term_width()):
            ui.println(row)
    ui.println()
    return len(formulae), outdated


def render_casks(ui, casks):
    casks = sorted(casks, key=lambda c: c["token"])
    outdated = sum(bool(c.get("outdated")) for c in casks)

    ui.println(f"{PAD}{bold('Casks')} {muted(str(len(casks)))}")
    ui.println()
    rows = []
    for c in casks:
        inst = c.get("installed") or "?"
        v, vlen = version_cell(inst, c.get("version"), c.get("outdated"))
        display = (c.get("name") or [""])[0]
        if display.lower() == c["token"].lower():
            display = ""
        desc = " · ".join(x for x in (display, c.get("desc")) if x)
        rows.append((mark(c.get("outdated")), c["token"], v, vlen, desc,
                     tags(c, (("auto_updates", muted),))))
    table(ui, rows)
    ui.println()
    return len(casks), outdated


def table(ui, rows):
    """rows: (mark, name, styled version, version length, desc, tag list)"""
    width = term_width()
    nw = min(max(len(r[1]) for r in rows), 28)
    vw = min(max(r[3] for r in rows), 30)
    for mk, name, version, vlen, desc, tag_list in rows:
        tag_str = "  " + " ".join(tag_list) if tag_list else ""
        room = width - len(PAD) - nw - vw - visible_len(tag_str) - 10
        d = muted(truncate(desc or "", room)) if room > 12 else ""
        ui.println(f"{PAD}  {mk} {bold(truncate(name, nw).ljust(nw))}  "
                   f"{version}{' ' * max(0, vw - vlen)}  {d}{tag_str}")


def mark(outdated):
    return yellow("↑") if outdated else green("✓")


def version_cell(installed, latest, outdated):
    """(styled, plain length): `installed → latest` when outdated."""
    if outdated and latest and latest != installed:
        return f"{yellow(installed)} {muted('→')} {green(latest)}", len(installed) + len(latest) + 3
    return green(installed), len(installed)


def tags(pkg, extra=()):
    out = []
    for flag, color in (("pinned", cyan), ("keg_only", muted), ("deprecated", yellow),
                        ("disabled", red), *extra):
        if pkg.get(flag):
            out.append(color(flag.replace("_", "-")))
    return out
