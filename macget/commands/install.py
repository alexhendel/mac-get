"""install / reinstall / fetch: downloads, pouring bottles, installed kegs."""
import os
import re
import time

from ..style import bold, fmt_secs, muted, plural

COMMANDS = {"install", "reinstall", "fetch"}


def heading(op, h):
    m = re.match(r"Fetching downloads for: (.*)", h)
    if m:
        names = split_names(m.group(1))
        op.total = max(op.total, len(names))
        op.set_stage(f"Fetching {len(names)} {plural(len(names), 'package')}")
        return True
    m = re.match(r"(?:Fetching|Installing) dependencies for (\S+): (.*)", h)
    if m:
        deps = split_names(m.group(2))
        op.total = max(op.total, len(deps) + 1)
        op.set_stage(f"{h.split()[0]} {len(deps)} dependencies for {m.group(1)}")
        return True
    m = re.match(r"Installing \S+ dependency: (\S+)", h)
    if m:
        op.set_stage(f"Installing {m.group(1)}")
        return True
    m = re.match(r"Pouring (\S+?)--([^-]+?)\.[a-z0-9_]+\.bottle", h)
    if m:
        op.set_stage(f"Pouring {m.group(1)} {m.group(2)}")
        return True
    m = re.match(r"Downloading (https?://\S+)", h)
    if m:
        op.set_stage(f"Downloading {pretty_url(m.group(1))}")
        return True
    return False


def line(op, s):
    if s.startswith(("✔︎", "✔")):
        downloaded(op, s.lstrip("✔︎ ").strip(), success=True)
    elif s.startswith(("✘", "✗", "×")):
        downloaded(op, s.lstrip("✘✗× ").strip(), success=False)
    elif s.startswith("🍺"):
        poured(op, s.lstrip("🍺").strip())
    elif s.startswith("Already downloaded:"):
        if "bottle_manifest" not in s:
            op.note("cached  " + bottle_label(s.split(":", 1)[1].strip()))
    else:
        return False
    return True


def summary(op, bits):
    if op.installed:
        bits.append(f"{len(op.installed)} installed")


def downloaded(op, text, success):
    if text.startswith("Bottle Manifest") or text.startswith("API Source"):
        return
    m = re.match(r"(?:Bottle|Cask|Formula|Resource)?\s*(\S+)\s*\(([^)]+)\)", text)
    label = f"{m.group(1)} {muted(m.group(2))}" if m else text
    if success:
        op.ok(f"Downloaded {bold(label)}")
    else:
        op.error(f"Download failed: {label}")


def poured(op, text):
    # "/opt/homebrew/Cellar/wget/1.24.5: 92 files, 4.5MB, built in 2 seconds"
    m = re.match(r"(/\S+/(?:Cellar|Caskroom)/([^/]+)/([^/:]+)):\s*(.*)", text)
    if m:
        name, ver, info = m.group(2), m.group(3), m.group(4).replace(", ", " · ")
        took = fmt_secs(time.monotonic() - op.stage_start)
        op.installed.append(name)
        op.done += 1
        op.ok(f"Installed {bold(name)} {muted(ver)}", f"{info} · {took}")
        return
    m = re.match(r"(\S+) was successfully (installed|upgraded)!", text)
    if m:
        op.installed.append(m.group(1))
        op.done += 1
        op.ok(f"Installed {bold(m.group(1))}", fmt_secs(time.monotonic() - op.stage_start))
        return
    op.ok(text)


def split_names(s):
    return [n for n in re.split(r"[,\s]+", s.strip()) if n]


def pretty_url(url):
    m = re.search(r"/v2/homebrew/[^/]+/(.+?)/(?:blobs|manifests)/", url)
    if m:
        return m.group(1).replace("/", "@")
    return url.rstrip("/").split("/")[-1].split("?")[0]


def bottle_label(path):
    # ".../<sha>--figlet--2.2.5.arm64_sequoia.bottle.tar.gz" -> "figlet 2.2.5"
    base = os.path.basename(path)
    m = (re.search(r"--([^/]+?)--([^-]+?)\.[a-z0-9_]+\.bottle", base)
         or re.search(r"--([^/]+?)-([\d][^-]*?)\.[a-z0-9_]+\.bottle", base))
    return f"{m.group(1)} {m.group(2)}" if m else base
