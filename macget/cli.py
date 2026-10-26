"""Entry point: decide whether to restyle a brew command or pass it through."""
import os
import sys

from . import stream
from .brew import exec_brew
from .commands import info, search, version
from .commands import list as list_view

VIEWS = (version, list_view, search, info)


def main():
    args = sys.argv[1:]
    if sys.stdout.isatty() and not os.environ.get("MAC_GET_PLAIN"):
        for view in VIEWS:
            if view.handles(args):
                sys.exit(view.run(args))
        if stream.handles(args):
            sys.exit(stream.run(args))
    exec_brew(args)
