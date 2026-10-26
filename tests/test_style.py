import unittest

from macget.commands.install import bottle_label, pretty_url, split_names
from macget.stream import NAMES_LINE
from macget.style import (columns, flow, fmt_secs, human_bytes, to_bytes, truncate,
                          visible_len, wrap, green)


class TextHelpers(unittest.TestCase):
    def test_truncate(self):
        self.assertEqual(truncate("short", 10), "short")
        self.assertEqual(truncate("abcdefghij", 5), "abcd…")

    def test_visible_len_ignores_colors(self):
        self.assertEqual(visible_len(green("abc")), 3)

    def test_fmt_secs(self):
        self.assertEqual(fmt_secs(1.25), "1.2s")
        self.assertEqual(fmt_secs(125), "2m 05s")

    def test_bytes(self):
        self.assertEqual(to_bytes("4.5", "MB"), 4.5e6)
        self.assertEqual(human_bytes(5.7e6), "5.7MB")
        self.assertEqual(human_bytes(512), "512B")

    def test_wrap_keeps_indent(self):
        lines = wrap("  one two three four five", 12)
        self.assertTrue(all(len(l) <= 12 for l in lines))
        self.assertTrue(all(l.startswith("  ") for l in lines))

    def test_columns_fill_down_then_across(self):
        cells = [(1, c) for c in "abcde"]
        rows = columns(cells, 20)  # cell width 4 → 4 per row → 2 rows
        self.assertEqual([r.split() for r in rows], [["a", "c", "e"], ["b", "d"]])

    def test_flow_wraps_with_indent(self):
        tokens = [(3, "aaa"), (3, "bbb"), (3, "ccc")]
        self.assertEqual(flow(tokens, 9, ">"), ["aaa  bbb", ">ccc"])


class BrewOutputHelpers(unittest.TestCase):
    def test_pretty_url_ghcr(self):
        self.assertEqual(pretty_url("https://ghcr.io/v2/homebrew/core/wget/manifests/1.25.0"), "wget")
        self.assertEqual(pretty_url("https://ghcr.io/v2/homebrew/core/python/3.13/blobs/sha256:ab"),
                         "python@3.13")

    def test_pretty_url_plain(self):
        self.assertEqual(pretty_url("https://example.com/dl/app-1.0.dmg?x=1"), "app-1.0.dmg")

    def test_bottle_label_both_cache_formats(self):
        self.assertEqual(bottle_label("/c/4239--figlet--2.2.5.arm64_tahoe.bottle.tar.gz"), "figlet 2.2.5")
        self.assertEqual(bottle_label("/c/4239--figlet-2.2.5.arm64_tahoe.bottle.tar.gz"), "figlet 2.2.5")

    def test_split_names(self):
        self.assertEqual(split_names("wget, libidn2 gettext"), ["wget", "libidn2", "gettext"])

    def test_names_line(self):
        for ok in ("wget", "python@3.13", "foo  bar", "user/tap/baz", "c++-lib"):
            self.assertTrue(NAMES_LINE.match(ok), ok)
        for not_names in ("Uninstalling /opt/homebrew/Cellar/x/1.0... (1 files, 1MB)",
                          "Updated Homebrew from 7.0.10 to 7.0.11.", "Warning: x"):
            self.assertFalse(NAMES_LINE.match(not_names), not_names)


if __name__ == "__main__":
    unittest.main()
