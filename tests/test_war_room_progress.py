"""The war-room says what the round in flight is doing, or says why it cannot.

`RUN IN FLIGHT: dispatcher pid=... since ...` tells the operator the door is
shut and nothing else; the round's log is empty until the round ends, so a
glance at the pulse page during a four-hour Dispatcher round shows no pulse
(issue #366). The engine writes its transcript live, so the progress is
derivable with no new machinery -- and the whole risk of deriving it is that
the banner then reads as authoritative. A derived line that goes blank, or
that shows the operator's own interactive session, is worse than the silence
it replaced: it is a silent wrong answer wearing a confident banner.

So the derivation is total over its own failure modes. Every way it can fail
to name the round's work names itself instead -- `progress: not derivable
(reason)` -- and the reason vocabulary is a closed set this module pins
against the script, not a list either side maintains by hand.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      `war-room.sh --derive` is the same code path the page builds
              from -- both call `progress_line` / `log_last_line` and escape
              through `html_escape`, so a cell asserts what the banner shows.
Establishes:  the in-flight banner carries exactly one progress line; it is
              either `currently: <work> (step N, HH:MMZ)` or `progress: not
              derivable (<reason>)` drawn from the pinned vocabulary; a run
              log's last line is never silently cut.
Now illegal:  an empty progress line; a reason string with no cell; a
              transcript older than the lock rendering as this round's work;
              a truncated log line indistinguishable from a complete one.

Completeness ledger
--------------------
property:   the in-flight banner never renders an empty or unattributed
            progress line: every input state reaches either a named
            `currently:` line or a named `not derivable` reason.
domain:     the derivation's inputs, crossed -- the lock holder
            {absent, no `since` stamp, well-formed} x the transcript root
            {missing, empty, populated} x the newest session's freshness
            {predates the lock, follows it} x its parse state {clean,
            truncated tail, garbage} x its content {no assistant event,
            assistant without tool call, tool call} x which field names the
            work {`description`, `command`, `file_path`, the tool's `name`}.
            The later axes are unreachable when an earlier one refuses, so
            the grid is the reachable enumeration: each axis member appears
            in at least one cell, and every cell that reaches the naming
            axis crosses all four of its members. The field axis is DERIVED
            from the on-disk schema, not guessed: over the 360 tool calls of
            the round of 2026-08-17, 137 carry one of the three input fields,
            215 carry two, and 8 carry none -- `Skill`, `TaskStop`,
            `ToolSearch` -- which is why `name` is the fourth rung and not a
            flourish.
registry:   `_reasons_the_script_can_emit()` scrapes the reason vocabulary
            from `war-room.sh` itself; `test_every_reason_the_script_can_emit_has_a_cell`
            fails by name when a reason is added without a cell, and when a
            cell names a reason the script cannot emit. The grid is the
            crossing; neither list is maintained by hand.
covered:    `test_the_progress_line_is_what_the_round_is_doing` -- 19 cells,
            each a real `war-room.sh --derive` run against a synthetic lock
            and transcript root. `test_a_run_log_line_is_never_silently_cut`
            -- 6 cells over the Runs table's last-line rendering. The two
            misuse probes (`test_an_unknown_derivation_is_refused`,
            `test_a_derivation_missing_its_arguments_is_refused`) prove the
            seam's own refusals. `test_the_page_still_inserts_what_it_derives`
            pins the two call sites, because a derivation the page stopped
            inserting would leave every cell above green and the banner
            silent; that pin was born green, so
            `test_the_insertion_pin_reddens_when_the_call_is_dropped` runs
            its reddening mutation rather than asserting it. Every cell was
            authored red and run red before the implementation existed.
sampled:    none. Every cell listed is an executed row.
residual:   THREE, each with its guard or its owner:
            (1) the selection heuristic is "newest session under the fleet
            clone's transcript root, if it postdates the lock". An operator
            running `claude` interactively in the fleet clone DURING a round
            writes to the same root and would be shown as the round's work.
            The freshness check bounds it to the round's own window and no
            further; closing it needs the wrapper to record the engine's
            session id, which is a change to `run-role.sh`, not to the page.
            R4 -- it takes the operator working in the clone while a
            scheduled round holds the lock. This ledger owns the record.
            (2) sidechain (subagent) tool calls are counted and shown like
            the main thread's, because they are equally "what the round is
            doing". A round whose subagent is mid-search reports the
            subagent's call. Deliberate, not a gap; this ledger owns it.
            (3) the whole module skips off Darwin: `war-room.sh` is BSD-only
            by charter (`stat -f`, `date -j`, `date -r`) and runs on the
            operator's Mac under launchd. The merge gate is the self-hosted
            macOS pool and executes every cell; the weekly Linux canary
            skips them, visibly, with the reason below. R4 -- reaching it
            means running the fleet's generator on Linux, which nothing does.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
from typing import NamedTuple

import pytest

_REPO = pathlib.Path(__file__).resolve().parent.parent
_SCRIPT = _REPO / "tools" / "fleet" / "war-room.sh"

pytestmark = pytest.mark.skipif(
    sys.platform != "darwin",
    reason=(
        "war-room.sh is BSD/macOS-only by charter (stat -f, date -j, date -r); "
        "the merge gate runs on the self-hosted macOS pool and executes these cells"
    ),
)

# The lock holder's own format, as run-role.sh writes it.
_SINCE = dt.datetime(2026, 8, 17, 1, 18, 19, tzinfo=dt.timezone.utc)
_HOLDER = "dispatcher pid=4805 since 2026-08-17T01:18:19Z"

# The Runs table's last-line budget, and the marker a cut line must carry.
_LOG_LIMIT = 400


class _Run(NamedTuple):
    returncode: int
    out: str
    err: str


def _derive(*args: str) -> _Run:
    """Run the generator's derivation seam -- the page's own code path."""
    proc = subprocess.run(
        [str(_SCRIPT), "--derive", *args],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO),
    )
    return _Run(proc.returncode, proc.stdout.rstrip("\n"), proc.stderr)


# ------------------------------------------------------------ the reason registry

# A CALL to `not_derivable` with a literal first argument: not a comment
# mentioning one, and not some other helper whose name merely ends the same
# way. A scrape wider than the class it names is this repo's own recurring
# defect, so the precision below is an executed claim, not an assumption.
_REASON_CALL = re.compile(r'(?m)^(?!\s*#).*(?<![\w-])not_derivable "([^"$]+)"')


def _reasons_in(text: str) -> frozenset[str]:
    return frozenset(_REASON_CALL.findall(text))


def _reasons_the_script_can_emit() -> frozenset[str]:
    """The reason vocabulary, read off the script rather than restated here."""
    return _reasons_in(_SCRIPT.read_text())


# ------------------------------------------------------------- transcript records


def _assistant(*blocks: dict[str, object]) -> str:
    return json.dumps({"type": "assistant", "message": {"content": list(blocks)}})


def _tool_use(name: str, **fields: str) -> dict[str, object]:
    return {"type": "tool_use", "name": name, "input": dict(fields)}


def _text(body: str) -> dict[str, object]:
    return {"type": "text", "text": body}


def _body(*records: str) -> str:
    return "".join(record + "\n" for record in records)


_TOOL_CALL = _assistant(_tool_use("Bash", command="pytest -q", description="Full suite evidence run"))


class _Cell(NamedTuple):
    cell: str
    holder: str | None
    root: str  # "missing" | "empty" | "populated"
    sessions: tuple[tuple[int, str], ...]  # (mtime offset from `since`, file body)
    kind: str  # "reason" | "currently"
    expect: str  # the reason literal, or the rendered work text
    steps: int  # asserted only for "currently"
    offset: int  # the newest session's offset, for the rendered clock


def _currently(
    cell: str, records: str, expect: str, *, steps: int = 1, offset: int = 60
) -> _Cell:
    return _Cell(cell, _HOLDER, "populated", ((offset, records),), "currently", expect, steps, offset)


def _refuses(
    cell: str,
    reason: str,
    *,
    holder: str | None = _HOLDER,
    root: str = "populated",
    sessions: tuple[tuple[int, str], ...] = ((60, _body(_TOOL_CALL)),),
) -> _Cell:
    return _Cell(cell, holder, root, sessions, "reason", reason, 0, 60)


_LONG = "x" * 300
_GRID: tuple[_Cell, ...] = (
    # --- the lock holder axis
    _refuses("holder-absent", "lock holder unreadable", holder=None),
    _refuses("holder-without-since", "lock holder carries no start time", holder="dispatcher pid=4805"),
    # --- the transcript root axis
    _refuses("root-missing", "no transcript directory", root="missing"),
    _refuses("root-without-sessions", "no transcript files", root="empty"),
    # --- the freshness axis: the operator's own session must not read as the round
    _refuses(
        "session-predates-the-lock",
        "newest transcript predates the lock",
        sessions=((-60, _body(_TOOL_CALL)),),
    ),
    # --- the parse axis
    _refuses("session-is-garbage", "transcript unparsable", sessions=((60, "not json at all\n"),)),
    # --- the content axis
    _refuses(
        "no-assistant-event",
        "no assistant step yet",
        sessions=((60, _body(json.dumps({"type": "user"}))),),
    ),
    _refuses(
        "assistant-without-tool-call",
        "no tool call yet",
        sessions=((60, _body(_assistant(_text("thinking")))),),
    ),
    # --- the naming axis: all four rungs of the fallback
    _currently(
        "description-names-the-work",
        _body(_assistant(_tool_use("Bash", command="pytest -q", description="Full suite evidence run"))),
        "Full suite evidence run",
    ),
    _currently(
        "command-when-there-is-no-description",
        _body(_assistant(_tool_use("Bash", command="pytest -q -n 8"))),
        "pytest -q -n 8",
    ),
    _currently(
        "file-path-when-there-is-neither",
        _body(_assistant(_tool_use("Read", file_path="cardlang/parse.py"))),
        "cardlang/parse.py",
    ),
    _currently(
        "tool-name-when-the-input-names-nothing",
        _body(_assistant(_tool_use("Skill", skill="role-warden", args="run"))),
        "Skill",
    ),
    _currently(
        "a-tool-call-naming-nothing-at-all-still-renders",
        _body(_assistant(_tool_use(""))),
        "(unnamed tool call)",
    ),
    # --- the step count, and which call is "most recent"
    _currently(
        "step-count-is-assistant-events",
        _body(
            _assistant(_tool_use("Bash", description="first")),
            _assistant(_text("thinking")),
            _assistant(_tool_use("Bash", description="third")),
        ),
        "third",
        steps=3,
    ),
    # --- a live transcript is appended to while it is read
    _Cell(
        "truncated-tail-uses-what-parsed",
        _HOLDER,
        "populated",
        ((60, _body(_TOOL_CALL) + '{"type":"assistant","message":{"cont'),),
        "currently",
        "Full suite evidence run",
        1,
        60,
    ),
    # --- the newest session wins
    _Cell(
        "newest-session-wins",
        _HOLDER,
        "populated",
        (
            (30, _body(_assistant(_tool_use("Bash", description="the older session")))),
            (90, _body(_assistant(_tool_use("Bash", description="the newer session")))),
        ),
        "currently",
        "the newer session",
        1,
        90,
    ),
    # --- rendering: one line, escaped, bounded
    _currently(
        "whitespace-is-collapsed-to-one-line",
        _body(_assistant(_tool_use("Bash", command="pytest -q \\\n  -n 8"))),
        "pytest -q \\ -n 8",
    ),
    _currently(
        "markup-is-escaped",
        _body(_assistant(_tool_use("Bash", description='<b>&"x"'))),
        "&lt;b&gt;&amp;&quot;x&quot;",
    ),
    _currently(
        "long-work-text-is-marked-truncated",
        _body(_assistant(_tool_use("Bash", description=_LONG))),
        "x" * 200 + " ...",
    ),
)


def _build(tmp: pathlib.Path, cell: _Cell) -> tuple[str, str]:
    """Materialize one cell's lock holder and transcript root; return their paths."""
    holder = tmp / "holder"
    if cell.holder is not None:
        holder.write_text(cell.holder + "\n")
    root = tmp / "transcripts"
    if cell.root != "missing":
        root.mkdir()
    if cell.root == "populated":
        for index, (offset, body) in enumerate(cell.sessions):
            session = root / f"session-{index}.jsonl"
            session.write_text(body)
            when = _SINCE.timestamp() + offset
            os.utime(session, (when, when))
    return str(holder), str(root)


@pytest.mark.parametrize("cell", _GRID, ids=[c.cell for c in _GRID])
def test_the_progress_line_is_what_the_round_is_doing(cell: _Cell) -> None:
    """Every input state reaches a named line -- never a blank, never a guess."""
    with tempfile.TemporaryDirectory() as tmp:
        holder, root = _build(pathlib.Path(tmp), cell)
        run = _derive("progress-line", holder, root)
    assert run.returncode == 0, f"the derivation must never fail the build: {run.err}"
    assert run.out, "an empty progress line is the defect this module exists for"
    if cell.kind == "reason":
        head = f"progress: not derivable ({cell.expect}"
        assert run.out.startswith(head), f"expected {head!r}..., got {run.out!r}"
        assert run.out.endswith(")")
    else:
        clock = dt.datetime.fromtimestamp(
            _SINCE.timestamp() + cell.offset, dt.timezone.utc
        ).strftime("%H:%MZ")
        assert run.out == f"currently: {cell.expect} (step {cell.steps}, {clock})"


def test_every_reason_the_script_can_emit_has_a_cell() -> None:
    """The reason vocabulary is closed: the script's list and the grid's agree.

    Reddens both ways -- a reason added to the script with no cell, and a cell
    naming a reason the script cannot emit."""
    in_script = _reasons_the_script_can_emit()
    assert in_script, "no reasons scraped from war-room.sh -- the scrape went blind"
    in_grid = frozenset(c.expect for c in _GRID if c.kind == "reason")
    assert in_grid == in_script


def test_the_reason_scrape_sees_calls_and_only_calls() -> None:
    """It must find a real call in every shape the script writes one, and must
    not find a mention. A vocabulary pin reading its own comments would agree
    with itself forever."""
    assert _reasons_in(
        '  not_derivable "at the start of a line"\n'
        '  [ -r "$x" ] || { not_derivable "after a brace" "$x"; return 0; }\n'
        '# not_derivable "a comment, not a call"\n'
        '  x_not_derivable "another helper entirely"\n'
    ) == frozenset({"at the start of a line", "after a brace"})


# ------------------------------------------------ the Runs table's last-line render

_LOG_GRID: tuple[tuple[str, str, str], ...] = (
    ("short-line-is-whole", "the round began\n", "the round began"),
    ("blank-tail-is-skipped", "the round began\n\n\n", "the round began"),
    ("at-the-limit-is-unmarked", "y" * _LOG_LIMIT + "\n", "y" * _LOG_LIMIT),
    ("over-the-limit-is-marked", "y" * (_LOG_LIMIT + 100) + "\n", "y" * _LOG_LIMIT + " ..."),
    ("markup-is-escaped", '<b>&"x"\n', "&lt;b&gt;&amp;&quot;x&quot;"),
    ("missing-file-says-so", "", "(unreadable)"),
)


@pytest.mark.parametrize(
    ("cell", "body", "expected"), _LOG_GRID, ids=[c for c, _, _ in _LOG_GRID]
)
def test_a_run_log_line_is_never_silently_cut(cell: str, body: str, expected: str) -> None:
    """A cut line carries its marker, so a fragment never reads as the whole.

    The witness: a benign startup warning cut at 160 characters read as a
    denial (issue #366)."""
    with tempfile.TemporaryDirectory() as tmp:
        log = pathlib.Path(tmp) / "dispatcher-20260817-011819.log"
        if cell != "missing-file-says-so":
            log.write_text(body)
        run = _derive("last-log-line", str(log))
    assert run.returncode == 0, f"the derivation must never fail the build: {run.err}"
    assert run.out == expected


# ------------------------------------------------- the page's insertion points
#
# The grid proves the derivations; it says nothing about whether the page
# still inserts them. Deleting either emit line would leave every cell above
# green and the banner silent again -- the vacuously-green class -- so the two
# call sites are pinned here, and the pin is proven to redden.

_INSERTIONS: tuple[tuple[str, str, str], ...] = (
    ("in-flight banner", 'if [ -e "$LOCK_HOLDER" ]; then', "progress_line_html"),
    ("runs table row", "while IFS='|' read -r r_mtime r_size r_path; do", "log_last_line_html"),
)


def _block(text: str, opener: str) -> str:
    """The shell block introduced by `opener`, to its matching un-indented close."""
    lines = text.splitlines()
    start = next(i for i, line in enumerate(lines) if line.strip() == opener)
    indent = len(lines[start]) - len(lines[start].lstrip())
    for end in range(start + 1, len(lines)):
        stripped = lines[end].strip()
        closes = stripped in ("fi", "done")
        if closes and len(lines[end]) - len(lines[end].lstrip()) == indent:
            return "\n".join(lines[start : end + 1])
    raise AssertionError(f"unterminated block for {opener!r}")


@pytest.mark.parametrize(
    ("site", "opener", "helper"), _INSERTIONS, ids=[s for s, _, _ in _INSERTIONS]
)
def test_the_page_still_inserts_what_it_derives(site: str, opener: str, helper: str) -> None:
    assert helper in _block(_SCRIPT.read_text(), opener), f"{site} no longer calls {helper}"


def test_the_insertion_pin_reddens_when_the_call_is_dropped() -> None:
    """Run the plant, do not merely state it: drop each call, watch the pin fail.

    The absence must be an absence the pin could have seen -- so the mutated
    block is asserted to still BE the block, or a scrape that silently found
    nothing would read as a passing reddening proof."""
    text = _SCRIPT.read_text()
    for site, opener, helper in _INSERTIONS:
        mutated = "\n".join(line for line in text.splitlines() if helper not in line)
        block = _block(mutated, opener)
        assert opener in block, f"the {site} mutation lost the block itself"
        assert len(block.splitlines()) > 1, f"the {site} block collapsed to its opener"
        assert helper not in block, f"the {site} pin cannot see its own loss"


# ------------------------------------------------------------------ misuse probes


def test_an_unknown_derivation_is_refused() -> None:
    """A typo in the seam is loud, not a silently empty line."""
    run = _derive("progres-line", "/nonexistent/holder", "/nonexistent/root")
    assert run.returncode == 2
    assert "progres-line" in run.err


def test_a_derivation_missing_its_arguments_is_refused() -> None:
    """Arity is checked at the seam, not discovered as an empty result."""
    run = _derive("progress-line")
    assert run.returncode == 2
    assert "progress-line" in run.err


def test_a_derivation_carrying_extra_arguments_is_refused() -> None:
    """Arity is exact. A trailing flag must not be swallowed by the seam."""
    run = _derive("last-log-line", "/nonexistent/log", "-o", "/nonexistent/page.html")
    assert run.returncode == 2
    assert "last-log-line" in run.err


def test_an_output_path_alongside_a_derivation_is_refused() -> None:
    """`-o` before `--derive` parses, then means nothing -- so it is refused.

    Accepted-but-ignored is the class the seam exists to prove against; the
    seam does not get to carry it."""
    proc = subprocess.run(
        [str(_SCRIPT), "-o", "/nonexistent/page.html", "--derive", "progress-line", "/h", "/r"],
        capture_output=True,
        text=True,
        check=False,
        cwd=str(_REPO),
    )
    assert proc.returncode == 2
    assert "-o" in proc.stderr
