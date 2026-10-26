"""Shared test helpers: fixtures, captured rendering and snapshots."""
import contextlib
import io
import os
import re

from macget.style import ANSI_RE

HERE = os.path.dirname(os.path.realpath(__file__))
FIXTURES = os.path.join(HERE, "fixtures")
SNAPSHOTS = os.path.join(HERE, "snapshots")


def fixture(name):
    with open(os.path.join(FIXTURES, name)) as f:
        return f.read()


def plain(text):
    """Strip colors and make timings stable."""
    return re.sub(r"\b\d+\.\ds\b", "X.Xs", ANSI_RE.sub("", text))


@contextlib.contextmanager
def captured():
    """Collect everything written to stdout; yields a list holding the text."""
    buf, result = io.StringIO(), []
    with contextlib.redirect_stdout(buf):
        yield result
    result.append(plain(buf.getvalue()))


class QuietUI:
    """Stands in for macget.ui.UI where only output side effects are called."""

    def __getattr__(self, name):
        return lambda *a, **k: None


class SnapshotMixin:
    """assertSnapshot compares rendered output to tests/snapshots/<name>.txt.

    Missing snapshots are recorded. To accept intentional changes, run the
    tests with UPDATE_SNAPSHOTS=1 and review the diff.
    """

    def assertSnapshot(self, name, text):
        path = os.path.join(SNAPSHOTS, name + ".txt")
        if os.environ.get("UPDATE_SNAPSHOTS") or not os.path.exists(path):
            os.makedirs(SNAPSHOTS, exist_ok=True)
            with open(path, "w") as f:
                f.write(text)
            return
        with open(path) as f:
            expected = f.read()
        self.maxDiff = None
        self.assertEqual(expected, text, f"snapshot {name} changed "
                         "(UPDATE_SNAPSHOTS=1 to accept)")
