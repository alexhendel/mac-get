"""search, info and list: parsing brew's output and rendering it."""
import os
import tempfile
import threading
import unittest
from unittest import mock

from macget import brew
from macget.commands import info, search
from macget.commands import list as list_view

from .helpers import FAKE_BREW, QuietUI, SnapshotMixin, captured, fixture


def render_view(view, args, text, patch="capture_on_pty", code=0):
    """Run a view with brew's output replaced by fixture text."""
    result = (code, text) if patch == "capture_on_pty" else (code, text, "")
    with mock.patch.object(view, patch, return_value=result):
        with captured() as out:
            rc = view.run(args)
    return rc, out[0]


class Search(SnapshotMixin, unittest.TestCase):
    def test_parse_sections_marks_and_tags(self):
        sections, errors = search.parse(QuietUI(), fixture("search_curl.txt"))
        titles = [t for t, _ in sections]
        self.assertEqual(titles[0], "Formulae")
        entries = {e[0]: e for e in sections[0][1]}
        self.assertEqual(len(entries), 9)
        self.assertTrue(entries["curl"][1], "curl should carry the installed mark")
        self.assertEqual(entries["curlftpfs"][2], "deprecated")
        self.assertEqual(errors, [])

    def test_parse_desc(self):
        sections, _ = search.parse(QuietUI(), fixture("search_desc_curl.txt"))
        entries = {e[0]: e for e in sections[0][1]}
        self.assertEqual(entries["curlie"][3], "Power of curl, ease of use of httpie")
        self.assertEqual(entries["curlftpfs"][2], "deprecated")

    def test_render(self):
        rc, out = render_view(search, ["search", "curl"], fixture("search_curl.txt"))
        self.assertEqual(rc, 0)
        self.assertSnapshot("search_curl", out)

    def test_render_desc(self):
        _, out = render_view(search, ["search", "--desc", "curl"], fixture("search_desc_curl.txt"))
        self.assertSnapshot("search_desc_curl", out)

    def test_no_results(self):
        rc, out = render_view(search, ["search", "zzz"],
                              'Error: No formulae or casks found for "zzz".\n', code=1)
        self.assertEqual(rc, 1)
        self.assertIn("● No formulae or casks found for zzz", out)
        self.assertNotIn("✗ Error", out)


class Info(SnapshotMixin, unittest.TestCase):
    def test_parse_formula(self):
        pkgs, errors, _ = info.parse(fixture("info_curl.txt"))
        self.assertEqual(len(pkgs), 1)
        name, mark, display, rest = pkgs[0]["head"]
        self.assertEqual(name, "curl")
        self.assertTrue(rest.startswith("stable "))
        sections = [t for t, _ in pkgs[0]["sections"]]
        for expected in ("Dependencies", "Options", "Caveats", "Analytics"):
            self.assertIn(expected, sections)
        self.assertEqual(errors, [])

    def test_parse_cask(self):
        pkgs, _, _ = info.parse(fixture("info_cask_firefox.txt"))
        name, _, display, _ = pkgs[0]["head"]
        self.assertEqual((name, display), ("firefox", "Mozilla Firefox"))

    def test_parse_missing_package(self):
        pkgs, errors, _ = info.parse(fixture("info_jq_missing.txt"))
        self.assertEqual([p["head"][0] for p in pkgs], ["jq"])
        self.assertEqual(len(errors), 1)

    def test_render_formula(self):
        rc, out = render_view(info, ["info", "curl"], fixture("info_curl.txt"))
        self.assertEqual(rc, 0)
        self.assertSnapshot("info_curl", out)

    def test_render_cask(self):
        _, out = render_view(info, ["info", "--cask", "firefox"], fixture("info_cask_firefox.txt"))
        self.assertSnapshot("info_cask_firefox", out)

    def test_render_missing_package(self):
        rc, out = render_view(info, ["info", "jq", "nope"], fixture("info_jq_missing.txt"), code=1)
        self.assertEqual(rc, 1)
        self.assertIn("✗ Error", out)
        # Installed Size is a fact, not the install status (former bug).
        self.assertRegex(out, r"Installed Size\s+\S")
        self.assertEqual(out.count("Status"), 1)


class List(SnapshotMixin, unittest.TestCase):
    def render(self, args):
        return render_view(list_view, args, fixture("list_installed.json"), patch="capture_output")

    def test_render(self):
        rc, out = self.render(["list"])
        self.assertEqual(rc, 0)
        self.assertSnapshot("list", out)

    def test_requested_vs_dependencies(self):
        _, out = self.render(["list"])
        self.assertIn("2 installed by you · 2 dependencies", out)
        self.assertRegex(out, r"Dependencies\n.*libexample 2\.3\.8")

    def test_outdated(self):
        _, out = self.render(["list"])
        self.assertRegex(out, r"↑ curl\s+8\.23\.0 → 8\.24\.0")
        self.assertRegex(out, r"↑ example-app\s+150\.0 → 158\.0\.1")
        self.assertIn("↑ libsample@3 3.5.9", out)
        self.assertIn("6 packages   ↑ 3 outdated", out)

    def test_tags_and_cask_names(self):
        _, out = self.render(["list"])
        self.assertRegex(out, r"wget .*pinned")
        self.assertRegex(out, r"curl .*keg-only")
        self.assertIn("Example App · Made-up outdated cask", out)
        self.assertNotIn("example-tool · Made-up", out)  # display name equal to token is not repeated

    def test_capture_output_drains_large_output(self):
        # brew's JSON for `list` is often bigger than a pipe buffer (~64KB); reading
        # it any way but concurrently deadlocks (#15).
        with tempfile.TemporaryDirectory() as tmp:
            big = os.path.join(tmp, "big.txt")
            with open(big, "w") as f:
                f.write(("x" * 99 + "\n") * 10000)  # 1MB
            result = []
            with mock.patch.object(brew, "BREW", FAKE_BREW), \
                    mock.patch.dict(os.environ, FAKE_BREW_OUTPUT=big):
                t = threading.Thread(target=lambda: result.append(
                    brew.capture_output(QuietUI(), [], "")), daemon=True)
                t.start()
                t.join(15)
        self.assertFalse(t.is_alive(), "capture_output hung on a full pipe")
        code, out, _ = result[0]
        self.assertEqual((code, len(out)), (0, 1000000))

    def test_filter(self):
        _, out = self.render(["list", "--cask"])
        self.assertNotIn("Formulae", out)
        self.assertIn("Casks 2", out)


if __name__ == "__main__":
    unittest.main()
