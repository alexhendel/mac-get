"""The live renderer: line rules, section handling and the process loop."""
import os
import signal
import subprocess
import sys
import tempfile
import time
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

    def test_long_unrecognised_lines_wrap(self):
        # Regression (#3): long notes were truncated, losing their end.
        long = ("Logs: /Users/x/Library/Logs/Homebrew/example-formula/01.configure "
                "/Users/x/Library/Logs/Homebrew/example-formula/02.make (see the end)")
        _, out = feed([long])
        self.assertNotIn("…", out)
        self.assertEqual(" ".join(out.split()).count(long), 1)
        self.assertTrue(all(len(l) <= 100 for l in out.splitlines()))

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

    def test_cleanup_command(self):
        # Regression (#2): `brew cleanup` prints no heading before its Removing lines.
        op, out = feed(["Removing: /c/Homebrew/gettext--0.26... (10.2MB)",
                        "Removing: /opt/homebrew/Cellar/x/1.0... (1,707 files, 34.6MB)",
                        "==> This operation has freed approximately 44.8MB of disk space."],
                       args=("cleanup",))
        self.assertEqual(op.cleanup_count, 2)
        self.assertIn("✓ Cleaned up 2 old files", out)
        self.assertIn("44.8MB freed", out)
        self.assertNotIn("Removing:", out)

    def test_cleanup_dry_run(self):
        op, out = feed(["Would remove: /c/Homebrew/lpeg--1.1.0_2 (96.2KB)",
                        "Would remove: /c/Homebrew/usage--7.1.1 (4.4MB)",
                        "==> This operation would free approximately 4.5MB of disk space."],
                       args=("cleanup", "--dry-run"))
        self.assertEqual(op.cleanup_count, 2)
        self.assertIn("✓ Would clean up 2 old files", out)
        self.assertIn("4.5MB would be freed", out)
        self.assertNotIn("Would remove:", out)

    def test_caveats_summary_one_box_per_package(self):
        # Regression (#13): with 2+ packages brew repeats all caveats at the end,
        # one `==> <name>` heading each, after a bare `==> Caveats`.
        _, out = feed(["==> Caveats",
                       "==> curl",
                       "curl is keg-only, which means it was not symlinked into /opt/homebrew,",
                       "==> postgresql@17",
                       "To start postgresql@17 now and restart at login:",
                       "  brew services start postgresql@17"], args=("upgrade",))
        self.assertIn("╭─ Caveats · curl", out)
        self.assertIn("│  curl is keg-only", out)
        self.assertIn("╭─ Caveats · postgresql@17", out)
        self.assertIn("│    brew services start postgresql@17", out)

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

    def ctrl_c(self, presses, exit_code=130):
        """Run mac-get in its own session against fake brew and press Ctrl-C.

        Returns (mac-get's exit code, its stdout, its stderr, SIGINTs brew saw)."""
        with tempfile.TemporaryDirectory() as tmp:
            siglog = os.path.join(tmp, "sigint.log")
            env = dict(os.environ, FAKE_BREW_OUTPUT=os.path.join(FIXTURES, "fetch_figlet.txt"),
                       FAKE_BREW_SIGLOG=siglog, FAKE_BREW_EXIT=str(exit_code))
            code = ("import sys; from macget import stream; stream.BREW = sys.argv[1]; "
                    "sys.exit(stream.run(['install', 'figlet']))")
            proc = subprocess.Popen([sys.executable, "-c", code, FAKE_BREW], env=env,
                                    cwd=os.path.dirname(os.path.dirname(FAKE_BREW)),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                    text=True, start_new_session=True)
            deadline = time.monotonic() + 10
            while not os.path.exists(siglog + ".ready") and time.monotonic() < deadline:
                time.sleep(0.02)
            for _ in range(presses):
                os.killpg(proc.pid, signal.SIGINT)  # what the terminal does on Ctrl-C
                time.sleep(0.1)
            out, err = proc.communicate(timeout=10)
            with open(siglog) as f:
                return proc.returncode, out, err, f.read().count("SIGINT")

    def test_ctrl_c_reaches_brew_once(self):
        # Regression (#1): brew shares our process group, so the terminal already
        # interrupts it; a second SIGINT from us could abort brew's own cleanup.
        code, _, _, sigints = self.ctrl_c(1)
        self.assertEqual((code, sigints), (130, 1))

    def test_ctrl_c_keeps_brews_exit_code_and_output(self):
        # Regression (#12): the exit code was always 130 and brew's last lines were lost.
        code, out, _, _ = self.ctrl_c(1, exit_code=1)
        self.assertEqual(code, 1)
        self.assertIn("Cleaned up after interrupt", out)

    def test_repeated_ctrl_c_does_not_crash(self):
        # Regression (#12): a second Ctrl-C raised out of proc.wait() with a traceback.
        code, out, err, sigints = self.ctrl_c(2)
        self.assertEqual((code, sigints), (130, 2))
        self.assertNotIn("Traceback", err)
        self.assertIn("Cancelled", out)


if __name__ == "__main__":
    unittest.main()
