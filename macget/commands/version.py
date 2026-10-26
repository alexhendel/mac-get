"""--version / -v: mac-get's version above brew's own version output."""
import sys

from .. import __version__
from ..brew import exec_brew
from ..style import bold


def handles(args):
    return args in (["--version"], ["-v"])


def run(args):
    sys.stdout.write(f"{bold('mac-get')} {__version__}\n")
    sys.stdout.flush()  # exec replaces the process; unflushed output would be lost
    exec_brew(args)
