"""Routing: which arguments get restyled and which go straight to brew."""
import io
import os
import unittest
from unittest import mock

from macget import cli, stream
from macget.commands import info, search, version
from macget.commands import list as list_view


class FakeStdout(io.StringIO):
    def __init__(self, tty):
        super().__init__()
        self.tty = tty

    def isatty(self):
        return self.tty


def route(args, tty=True, env=None):
    """Return which handler main() picks for args: a module name or 'brew'."""
    targets = {"version": version, "list": list_view, "search": search, "info": info,
               "stream": stream}
    patches = [mock.patch.object(mod, "run", return_value=0) for mod in targets.values()]
    with mock.patch("sys.argv", ["mac-get", *args]), \
            mock.patch("sys.stdout", FakeStdout(tty)), \
            mock.patch.dict(os.environ, env or {}), \
            mock.patch.object(cli, "exec_brew") as exec_brew:
        os.environ.pop("MAC_GET_PLAIN", None) if not env else None
        mocks = [p.start() for p in patches]
        try:
            try:
                cli.main()
            except SystemExit:
                pass
        finally:
            for p in patches:
                p.stop()
    called = [name for name, m in zip(targets, mocks) if m.called]
    if exec_brew.called:
        called.append("brew")
    assert len(called) == 1, f"{args}: expected one route, got {called}"
    return called[0]


class Routing(unittest.TestCase):
    def test_restyled_commands(self):
        cases = {
            ("install", "wget"): "stream",
            ("upgrade",): "stream",
            ("rm", "wget"): "stream",
            ("update",): "stream",
            ("cleanup",): "stream",
            ("tap", "user/repo"): "stream",
            ("search", "curl"): "search",
            ("search", "--desc", "curl"): "search",
            ("info", "jq"): "info",
            ("info", "--cask", "firefox"): "info",
            ("list",): "list",
            ("ls", "--cask"): "list",
            ("--version",): "version",
            ("-v",): "version",
        }
        for args, expected in cases.items():
            with self.subTest(args=args):
                self.assertEqual(route(list(args)), expected)

    def test_passed_through(self):
        cases = [
            [], ["doctor"], ["outdated"], ["deps", "wget"],
            ["install", "--help"], ["info", "--json=v2", "jq"], ["info"],
            ["info", "--analytics", "jq"], ["search"], ["search", "--help"],
            ["list", "wget"], ["list", "--versions"], ["list", "-1"],
            ["info", "-v", "jq"], ["--version", "extra"],
        ]
        for args in cases:
            with self.subTest(args=args):
                self.assertEqual(route(args), "brew")

    def test_not_a_tty_always_passes_through(self):
        for args in (["install", "wget"], ["search", "curl"], ["list"], ["--version"]):
            with self.subTest(args=args):
                self.assertEqual(route(args, tty=False), "brew")

    def test_mac_get_plain_passes_through(self):
        self.assertEqual(route(["install", "wget"], env={"MAC_GET_PLAIN": "1"}), "brew")


if __name__ == "__main__":
    unittest.main()
