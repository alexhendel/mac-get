# mac-get

A friendlier face for [Homebrew](https://brew.sh). `mac-get` takes exactly the
same arguments as `brew` and passes them straight through, but renders the
output as a modern terminal UI: consistent spacing, colors, a live spinner with
per-step timing, and a progress bar while installing.

```
  ◆ mac-get › install wget

  ✓ Updated 2 taps                                    homebrew/core, homebrew/cask
  ✓ Downloaded libidn2 2.3.8
  ✓ Downloaded wget 1.25.0
  ✓ Installed libidn2 2.3.8                          281 files · 1.6MB · 0.4s
  ⠼ Pouring wget 1.25.0            ━━━━━━━━━─────────  1/2   0.3s

  ● Done in 6.1s   2 installed
```

## Install

Requires macOS, Homebrew and `python3` (the system Python 3.9 is enough; no
third-party packages).

From the project directory:

```sh
ln -s "$PWD/mac-get" ~/.local/bin/mac-get   # any directory on your PATH works
ln -s "$PWD/mac-get" ~/.local/bin/mget      # optional short alias
```

(`mg` would be shorter, but macOS already ships `/usr/bin/mg`, a text editor.)

Symlink rather than copy: the `mac-get` script loads the `macget/` package that
sits next to it, and the symlink also means changes to the project are live
immediately.

## Usage

Use it anywhere you would use `brew`:

```sh
mac-get install wget
mac-get upgrade
mac-get search fig
mac-get info --cask firefox
mac-get list
mac-get uninstall wget
```

### What gets restyled

| Commands | Output |
| --- | --- |
| `install`, `reinstall`, `upgrade`, `uninstall`/`remove`/`rm`, `update`, `cleanup`, `autoremove`, `tap`, `untap`, `fetch` | Live spinner showing the current step, ✓ line per download/install/removal with size and timing, a package progress bar, upgrade tables (`name  old → new  size`), caveats in a box, highlighted warnings/errors and a final summary |
| `search` | Results grouped into Formulae and Casks, laid out in columns, query highlighted, installed packages marked ✓, deprecated/disabled tags colored; `--desc` gives aligned descriptions |
| `info` | A card per package with version, tags, description and homepage, followed by status, dependencies (✓ installed / ○ missing), options, caveats and an analytics table |
| `list` / `ls` (optionally `--formula` or `--cask`) | A table of what you installed (version, description, pinned/keg-only/deprecated tags), dependencies in compact columns, casks, and outdated packages marked ↑ with `installed → latest` |

### Version

`mac-get --version` (or `-v`) shows mac-get's version above brew's:

```
mac-get 0.1.0
Homebrew 7.0.11
```

When piped, only brew's line is printed, so scripts that parse
`brew --version` keep working.

### What is passed through untouched

Everything else runs `brew` directly via `exec`, so behaviour, output and exit
codes are identical. That includes:

- every other command (`outdated`, `deps`, `doctor`, `services`, …)
- `--help`, `--json` and other machine-readable flags
- `--interactive`/`-i` and `--debug`/`-d`, where brew hands you a shell or asks questions
- `search` without a search term
- `info` without package names, or with flags other than `--formula`/`--cask`
- `list` with package names (lists their files) or any other flag (`-1`, `--versions`, `--pinned`, …)
- any run where stdout is not a terminal (pipes, redirects, scripts)

Set `MAC_GET_PLAIN=1` to always bypass the TUI, and `NO_COLOR=1` to disable colors.

## Notes

- Exit codes are always brew's. Ctrl-C cancels cleanly and restores the cursor.
- Interactive prompts (sudo passwords for cask installers, `[y/N]` questions)
  pause the spinner so you can answer them.
- The progress bar counts packages, not bytes: brew does not report download
  progress when its output is captured.
- Styling works by recognising brew's text output. Lines it does not recognise
  are still shown (dimmed), so a future brew change can make things look
  plainer but never hides information.

## Project structure

```
mac-get                    entry script (the file you symlink onto PATH)
macget/
  cli.py                   decides: restyled view, live renderer, or plain brew
  brew.py                  running brew: pass-through, captured, JSON
  style.py                 colors and text/column helpers
  ui.py                    spinner, step lines, boxes, header and footer
  stream.py                live renderer for commands that change the system
  commands/                one module per restyled command
    search.py info.py list.py version.py           read-only views
    install.py upgrade.py uninstall.py update.py   output rules for the live renderer
    cleanup.py tap.py
dev/capture.py             run a command on a pseudo-terminal, print the result
dev/refresh_fixtures.py    re-capture test fixtures from the installed brew
tests/                     unit tests, brew contract tests, fixtures, snapshots
```

`search`, `info` and `list` collect brew's output and render it in one go.
The commands that change the system share one live renderer, and each command
module contributes the rules for recognising its own output. All rules stay
active for every run, because a single `install` also prints update, cleanup
and caveat output.

## Development

Plain Python 3.9 standard library, no dependencies and no build step.

### Tests

```sh
python3 -m unittest                                # offline, ~1s
MACGET_LIVE=1 python3 -m unittest                  # + contract tests against your brew
UPDATE_SNAPSHOTS=1 python3 -m unittest             # accept intended output changes
```

- **Offline tests** feed saved brew output (`tests/fixtures/`) through the
  parsers and renderers and compare the result with recorded snapshots
  (`tests/snapshots/`). They also cover which arguments are restyled or passed
  through, and run the live renderer against a fake brew (`tests/fake_brew.py`).
- **Contract tests** (`MACGET_LIVE=1`) run the installed brew and check that
  its output still has the shape mac-get's parsers expect. They need network
  access.

**After a brew update:**

1. `MACGET_LIVE=1 python3 -m unittest`. A failing contract test means brew
   changed a format mac-get depends on.
2. `python3 dev/refresh_fixtures.py` re-captures the fixtures from the new
   brew; `git diff tests/fixtures` shows exactly what changed.
3. `python3 -m unittest` shows how the rendering is affected. Fix the parser,
   or accept intended differences with `UPDATE_SNAPSHOTS=1` and review the
   snapshot diff.

Fixtures captured by the script show install marks (✔) for this machine; the
stream session and `list` JSON fixtures are written by hand.

### Checking by eye

```sh
python3 dev/capture.py ./mac-get search curl
python3 dev/capture.py ./mac-get info --cask firefox
HOMEBREW_NO_AUTO_UPDATE=1 python3 dev/capture.py ./mac-get fetch --force figlet
./mac-get list | head        # piped output must be identical to brew's
```

Prefer `fetch --force` or `upgrade --dry-run` for testing installs:
`uninstall` runs brew's autoremove, which can also remove other packages that
nothing depends on any more. [CLAUDE.md](CLAUDE.md) has the architecture
details and the conventions for adding a command.

## License

[MIT](LICENSE.md)
