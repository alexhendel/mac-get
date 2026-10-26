"""Contract tests against the installed brew. Opt-in: MACGET_LIVE=1.

These check that brew still prints what mac-get's parsers expect, so a brew
update that changes its output shows up here instead of as a broken screen.
They need network access and take a few seconds.
"""
import json
import os
import re
import subprocess
import unittest
from unittest import mock

from macget import stream
from macget.brew import BREW, brew_env, capture_on_pty
from macget.commands import info, search
from macget.commands.upgrade import UPGRADE_ROW

from .helpers import QuietUI, captured

LIVE = os.environ.get("MACGET_LIVE") == "1" and os.path.exists(BREW)
ENV = dict(brew_env(), HOMEBREW_NO_AUTO_UPDATE="1")


def piped(*args):
    return subprocess.run([BREW, *args], stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          env=ENV, text=True)


def on_pty(*args):
    with mock.patch.dict(os.environ, HOMEBREW_NO_AUTO_UPDATE="1"):
        return capture_on_pty(QuietUI(), list(args), "")


@unittest.skipUnless(LIVE, "live brew contract tests: set MACGET_LIVE=1")
class BrewContract(unittest.TestCase):
    def test_version(self):
        self.assertRegex(piped("--version").stdout, r"^Homebrew \d+\.\d+")

    def test_search_columns(self):
        code, text = on_pty("search", "curl")
        self.assertEqual(code, 0)
        sections, errors = search.parse(QuietUI(), text)
        self.assertIn("Formulae", [t for t, _ in sections])
        names = [e[0] for _, entries in sections for e in entries]
        self.assertIn("curl", names)
        # Every column cell must be understood, not just most of them.
        cells = [c for ln in text.splitlines() if ln.strip() and not ln.startswith(("==>", "Error"))
                 for c in re.split(r"\s{2,}", ln.strip())]
        self.assertEqual(len(cells), len(names))

    def test_search_desc(self):
        _, text = on_pty("search", "--desc", "curl")
        sections, _ = search.parse(QuietUI(), text)
        entries = [e for _, es in sections for e in es]
        self.assertTrue(entries)
        self.assertTrue(all(e[3] is not None for e in entries), "every entry has a description")

    def test_info_formula(self):
        code, text = on_pty("info", "curl")
        pkgs, errors, _ = info.parse(text)
        self.assertEqual((code, errors), (0, []))
        self.assertEqual(len(pkgs), 1)
        name, _, _, rest = pkgs[0]["head"]
        self.assertEqual(name, "curl")
        self.assertRegex(rest, r"^stable \d")
        sections = dict(pkgs[0]["sections"])
        self.assertIn("Dependencies", sections)
        self.assertIn("Analytics", sections)
        self.assertRegex("\n".join(sections["Analytics"]), r"install: [\d,]+ \(30 days\)")
        self.assertTrue(any(re.match(r"\w[\w ]*: ", l) for l in pkgs[0]["intro"]), "key: value facts")

    def test_info_cask(self):
        _, text = on_pty("info", "--cask", "firefox")
        pkgs, _, _ = info.parse(text)
        name, _, display, _ = pkgs[0]["head"]
        self.assertEqual((name, display), ("firefox", "Mozilla Firefox"))

    def test_info_unknown_package(self):
        code, text = on_pty("info", "definitely-not-a-pkg-xyz")
        self.assertNotEqual(code, 0)
        _, errors, _ = info.parse(text)
        self.assertTrue(errors)

    def test_installed_json_schema(self):
        data = json.loads(subprocess.run([BREW, "info", "--json=v2", "--installed"],
                                         stdout=subprocess.PIPE, env=ENV, text=True).stdout)
        for f in data["formulae"][:20]:
            for key in ("name", "desc", "versions", "outdated", "pinned", "keg_only",
                        "deprecated", "disabled", "installed"):
                self.assertIn(key, f)
            self.assertIn("stable", f["versions"])
            self.assertIn("version", f["installed"][-1])
            self.assertIn("installed_on_request", f["installed"][-1])
        for c in data["casks"][:20]:
            for key in ("token", "name", "desc", "version", "installed", "outdated"):
                self.assertIn(key, c)

    def test_fetch_stream(self):
        result = piped("fetch", "--force", "figlet")
        self.assertEqual(result.returncode, 0)
        op = stream.Operation(["fetch", "figlet"])
        with captured() as out:
            for line in result.stdout.splitlines():
                op.handle(line)
        self.assertIn("✓ Downloaded figlet", out[0])
        self.assertEqual(op.errors, 0)

    def test_upgrade_dry_run_rows(self):
        lines = piped("upgrade", "--dry-run").stdout.splitlines()
        if not any(l.startswith("==> Would upgrade") for l in lines):
            self.skipTest("nothing outdated")
        start = next(i for i, l in enumerate(lines) if l.startswith("==> Would upgrade"))
        rows = [l for l in lines[start + 1:] if l.strip() and not l.startswith("==>")]
        self.assertTrue(rows)
        for row in rows:
            self.assertRegex(row.strip(), UPGRADE_ROW)


if __name__ == "__main__":
    unittest.main()
