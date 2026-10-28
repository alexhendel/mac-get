# mac-get

A Homebrew wrapper: same arguments as `brew`, restyled TUI output. See README.md
for user-facing behaviour.

## Layout

```
mac-get                    entry script (on PATH via symlink); adds this dir to sys.path
macget/
  cli.py                   dispatch: views → live renderer → exec brew
  brew.py                  BREW path, env, exec, capture_on_pty, capture_output
  style.py                 colors, PAD, width/wrap/columns/flow helpers
  ui.py                    UI: spinner line, ok/note/warn/error, box, header/footer
  stream.py                live renderer engine for commands that change the system
  commands/                one module per brew command
    search.py info.py list.py version.py                views
    install.py upgrade.py uninstall.py update.py        rule modules for stream.py
    cleanup.py tap.py
dev/capture.py             run a command on a pty and print the final screen
dev/refresh_fixtures.py    re-capture tests/fixtures from the installed brew
tests/
  test_style.py            text helpers, URL/bottle/name-line parsing
  test_cli.py              routing: restyled vs passed through
  test_stream.py           rule modules, sections, process loop (fake_brew.py)
  test_views.py            search/info/list parsing + snapshots
  test_brew_contract.py    live checks against the real brew (MACGET_LIVE=1)
  fixtures/  snapshots/
```

`~/.local/bin/mac-get` is a symlink to `mac-get`, so edits here are live.

## Constraints

- **Standard library only, Python 3.9 compatible** (macOS system python): no
  `match`, no `X | Y` type unions, no third-party packages.
- **Never change brew's behaviour.** Arguments go through unchanged and the exit
  code is always brew's. If output can't be restyled confidently, pass through
  (`exec_brew`) rather than guess.
- **Pass through when stdout is not a TTY** or `MAC_GET_PLAIN` is set, so
  scripts and pipes get brew's exact output.
- Lines the parser doesn't recognise must still be shown (dimmed via
  `UI.note`), never silently dropped. Only known noise goes in `stream.NOISE`.

## Architecture

`cli.main()` tries each view's `handles(args)` (version, list, search, info),
then `stream.handles(args)`, and otherwise `exec`s brew.

The version lives in `macget/__init__.py` (`__version__`); bump it there.
`commands/version.py` prints it, then `exec`s `brew --version` so brew's line
and exit code are unchanged.

**Views** (`commands/search.py`, `info.py`, `list.py`) collect brew's output
behind a spinner, then parse and render it in one go. Each exposes
`handles(args)` and `run(args) -> exit code`. Ways to get the data, in order of
preference:

- **JSON** via `brew.capture_output` (e.g. `list` uses
  `brew info --json=v2 --installed`). Prefer it wherever brew offers JSON.
- **pty** via `brew.capture_on_pty`: on a TTY brew adds section headers,
  ✔ installed marks and `(deprecated)`/`(disabled)` tags it omits when piped.

**Live renderer** (`stream.py`) for install, upgrade, uninstall, update,
cleanup, tap and friends: brew runs on a pipe and each line goes through
`Operation.handle` / `handle_heading`. Generic cases (warnings, errors, caveats,
sudo prompts, fallback notes) are handled there; everything else is delegated
to the **rule modules** in `stream.RULES`. A rule module may define
`COMMANDS`, `heading(op, h)`, `line(op, s)` (return True when consumed) and
`summary(op, bits)`. All rules are active for every streamed command, because
one `install` also prints update, cleanup and caveat output.

Sections: `op.open_section(kind, title, render)` buffers lines until the next
heading and then calls `render(op, title, lines)`; `op.open_list(title)` is a
name list in a box that also ends at the first line that isn't package names.
A partial line with no newline for 0.4s is treated as an interactive prompt.

Adding a command: new module in `commands/`. A view gets `handles`/`run` and an
entry in `cli.VIEWS`; a streamed command gets rules and an entry in
`stream.RULES`.

## Testing

Run `python3 -m unittest` after every change (offline, ~1s). Run
`MACGET_LIVE=1 python3 -m unittest` when touching a parser or after a brew
update: the contract tests check brew's real output still matches what the
parsers expect.

- Snapshot diffs are behaviour changes. Only re-record (`UPDATE_SNAPSHOTS=1`)
  when the change is intended, and say so; never to make a failure go away.
- A new parsing rule needs a test: add the brew lines to a fixture
  (`tests/fixtures/stream_session.txt` for the live renderer) and assert on
  the result. Bugs get a regression test first.
- `dev/refresh_fixtures.py` re-captures fixtures; review `git diff tests/fixtures`.

Also check by eye against real brew output:

```sh
python3 dev/capture.py ./mac-get search curl
python3 dev/capture.py ./mac-get info --cask firefox
HOMEBREW_NO_AUTO_UPDATE=1 python3 dev/capture.py ./mac-get fetch --force figlet
./mac-get info jq | head          # piped → must be identical to brew
```

To see the raw text brew emits for a new case: `brew <cmd> 2>&1 | cat -v`
(piped) or `python3 dev/capture.py brew <cmd>` (TTY).

Gotchas:

- `uninstall` triggers brew's autoremove, which can remove other orphaned
  packages. Prefer `fetch --force` or `upgrade --dry-run` to exercise the
  install path, and tell the user about any uninstall side effects.
- Terminals inside harnesses may report 0 columns; `term_width()` falls back to 100.
- `pty.spawn` with stdin at EOF hangs on Python 3.9; use the `openpty` +
  `Popen` pattern from `dev/capture.py` instead.
- Polling a process whose output exceeds the pipe buffer deadlocks; read it on
  a thread (see `brew.spin`, shared by both capture functions).
