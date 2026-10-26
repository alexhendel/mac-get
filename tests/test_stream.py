"""The live renderer: line rules, section handling and the process loop."""
import os
import unittest
from unittest import mock

from macget import stream

from .helpers import FIXTURES, SnapshotMixin, captured, fixture

FAKE_BREW = os.path.join(os.path.dirname(os.path.realpath(__file__)), "fake_brew.py")


def feed(lines, args=("install", "wget")):
    """Run lines through an Operation; return (op, rendered text)."""
    op = stream.Operation(list(args))
    with captured() as out:
        for line in lines:
            op.handle(line)
        op.footer(0)
    return op, out[0]


class Session(SnapshotMixin, unittest.TestCase):
    """A transcript covering update, install, cleanup, uninstall and tap output."""

    @classmethod
    def setUpClass(cls):
        cls.op, cls.out = feed(fixture("stream_session.txt").splitlines())

    def test_snapshot(self):
        self.assertSnapshot("stream_session", self.out)

    def test_counts(self):
        self.assertEqual(self.op.installed, ["libidn2", "wget", "example-app"])
        self.assertEqual(len(self.op.removed), 4)
        self.assertEqual(self.op.cleanup_count, 2)
        self.assertAlmostEqual(self.op.cleanup_bytes, 5.7e6)
        self.assertEqual((self.op.warnings, self.op.errors), (1, 1))
        self.assertIn("3 installed · 4 removed · 1 warning", self.out)

    def test_steps(self):
        for expected in ("✓ Updated 2 taps", "✓ Homebrew updated", "✓ Downloaded libidn2 2.3.8",
                         "✓ Installed wget 1.25.0", "✓ Installed example-app", "✓ Removed figlet 2.2.5",
                         "✓ Pruned 3 symbolic links", "✓ Tapped 1 command",
                         "✓ Cleaned up 2 old files", "5.7MB freed", "cached  figlet 2.2.5",
                         "▲ Warning Some warning from brew", "✗ Error Some error from brew",
                         "✓ Homebrew is up to date"):
            self.assertIn(expected, self.out)

    def test_caveats_boxed_with_package_name(self):
        self.assertIn("╭─ Caveats · wget", self.out)
        self.assertIn("│    indented caveat line two", self.out)

    def test_unrecognised_lines_are_kept(self):
        self.assertIn("A line mac-get has no rule for", self.out)
        self.assertIn("Adjust how often this is run", self.out)

    def test_noise_is_hidden(self):
        for noise in ("Bottle Manifest", "HOMEBREW_NO_INSTALL_CLEANUP", "HOMEBREW_NO_ENV_HINTS",
                      "bottle_manifest.json"):
            self.assertNotIn(noise, self.out)

    def test_name_lists_end_at_first_non_name_line(self):
        # Regression: autoremove's list used to swallow the "Uninstalling" lines after it.
        self.assertIn("│  libexample@3, libsample\n", self.out)
        self.assertIn("✓ Removed libsample 7.1.1", self.out)
        self.assertIn("│  foo, bar, user/tap/baz\n", self.out)


class Rules(unittest.TestCase):
    def test_cleanup_sizes_with_file_counts(self):
        # Regression: "(92 files, 4.5MB)" used to be skipped.
        op, _ = feed(["==> Running `brew cleanup`...",
                      "Removing: /a... (92 files, 4.5MB)", "Removing: /b... (1.5KB)"])
        self.assertAlmostEqual(op.cleanup_bytes, 4.5e6 + 1.5e3)

    def test_upgrade_table(self):
        _, out = feed(["==> Upgrading 2 outdated packages:",
                       "curl  8.23.0 -> 8.24.0  (5.2MB)",
                       "wget  1.24.5 -> 1.25.0",
                       "==> Upgrading curl", "  8.23.0 -> 8.24.0"], args=("upgrade",))
        self.assertIn("Upgrading 2 outdated packages\n", out)
        self.assertRegex(out, r"• curl\s+8\.23\.0 → 8\.24\.0\s+5\.2MB")
        self.assertRegex(out, r"• wget\s+1\.24\.5 → 1\.25\.0")

    def test_progress_total_from_dependencies(self):
        op, _ = feed(["==> Installing dependencies for wget: a, b, c"])
        self.assertEqual(op.total, 4)

    def test_sudo_prompt_pauses_spinner(self):
        op = stream.Operation(["install", "--cask", "x"])
        with captured():
            op.handle("==> Running installer for x with sudo; the password may be necessary.")
        self.assertTrue(op.paused)
        with captured():
            op.handle("==> Moving App 'X.app' to '/Applications/X.app'")
        self.assertFalse(op.paused)  # the next stage resumes it

    def test_failed_download(self):
        op, out = feed(["✘ Bottle wget (1.25.0)"])
        self.assertEqual(op.errors, 1)
        self.assertIn("Download failed: wget 1.25.0", out)


class ProcessLoop(unittest.TestCase):
    """stream.run against tests/fake_brew.py instead of the real brew."""

    def run_fake(self, output, exit_code=0, partial=None):
        env = {"FAKE_BREW_OUTPUT": os.path.join(FIXTURES, output),
               "FAKE_BREW_EXIT": str(exit_code)}
        if partial:
            env["FAKE_BREW_PARTIAL"] = partial
        with mock.patch.object(stream, "BREW", FAKE_BREW), mock.patch.dict(os.environ, env):
            with captured() as out:
                code = stream.run(["install", "figlet"])
        return code, out[0]

    def test_renders_and_succeeds(self):
        code, out = self.run_fake("fetch_figlet.txt")
        self.assertEqual(code, 0)
        self.assertIn("◆ mac-get › install figlet", out)
        self.assertIn("✓ Downloaded figlet", out)
        self.assertIn("● Done", out)

    def test_exit_code_is_brews(self):
        code, out = self.run_fake("fetch_figlet.txt", exit_code=3)
        self.assertEqual(code, 3)
        self.assertIn("● Failed (exit 3)", out)

    def test_partial_line_is_shown_as_prompt(self):
        code, out = self.run_fake("fetch_figlet.txt", partial="Proceed? [y/N] ")
        self.assertEqual(code, 0)
        self.assertIn("Proceed? [y/N] ", out)


if __name__ == "__main__":
    unittest.main()
