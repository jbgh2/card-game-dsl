"""The spend log and the windows a `token_budget` cap is counted over.

A cap is a ceiling over spend, and it sees what a durable record holds plus
what the live providers have billed since. These cross the registries that
decide what a ceiling counts — `run_eval.CAPS` and `spend.WINDOW_KINDS` — against every
state the record can be in, so a window that admits the wrong lines fails here
rather than on a bill.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a `token_budget` cap fires exactly when the spend its window
                 admits, plus everything the live providers have billed and
                 not yet written, reaches it — and not before. Every window
                 spelling outside the registry is refused at construction,
                 naming the registry; a spend log that cannot be read refuses
                 rather than counting less than was spent; and every path that
                 bills the API writes to the log it is counted from.
domain:          `run_eval.CAPS` x `spend.WINDOW_KINDS` x the states a record
                 can be in when a cap is checked (no log, spend billed but not
                 yet written, written by this invocation, written by another
                 one within each window's reach), crossed for both outcomes at
                 each cell — the cap fires at its own boundary and does not
                 fire above it. Crossed again with every way a line can fail to
                 be countable, over the windows that read the file. The misuse
                 probes cross the window spellings and the `spend_log:` values
                 a config author plausibly writes.

                 Three boundaries, each stated positively rather than missing.
                 A cap is counted over ONE log: `spend_log:` is what points
                 several configs at one, and no window reaches across two
                 files. A relative `results_dir` or `spend_log` resolves
                 against the working directory, as every other path in this
                 rig does, so two invocations from two directories are two
                 records and two ceilings. And `invocation` is answered in
                 memory rather than from the file, so the damaged-line rows
                 exclude it by construction — which is the point of answering
                 it there.
registry:        run_eval.py::CAPS (the cap axis, held to `Budget`'s own
                 non-window fields by
                 test_every_cap_field_is_a_registered_cap);
                 spend.py::WINDOW_KINDS (the window axis) with
                 spend.py::WINDOW_SPELLINGS the one spelling per kind the grid
                 reads; spend.py::ROLLING_SPELLING (the parametric spelling);
                 spend.py::ENTRY_FIELDS (the line's fields, read by both the
                 writer and the reader). Per-model summation:
                 test_runner.py::test_budget_sums_across_every_model_in_the_registry.
                 The runner's end-to-end behaviour under a crossed window:
                 test_runner.py::test_a_second_invocation_stops_where_the_first_left_off.
does not prove:  two things about how much a green here bounds. First, that
                 the log holds everything an account was billed: it holds what
                 `providers.Usage` counts, and `Usage` is fed from the `Reply`
                 a completed call returns — so an SDK-internal retry, and a
                 call billed by the API that raises before its usage is added,
                 are spend no window can see (issue #422). Second, that a
                 shared ceiling binds exactly: check and spend are not atomic,
                 and the cross-invocation rows run two `SpendLog` objects and
                 two sequential `main()` calls in one process, never two
                 concurrent ones. N processes can each clear one check and
                 each play a game, so the ceiling binds to within one game per
                 process. A cap is a floor on spend in both directions.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from .. import spend as spend_mod
from ..layout import spend_log_path
from ..providers import FakeProvider, Provider, Usage
from ..run_eval import CAPS, Budget, budget_of, spend_log
from ..spend import (
    ENTRY_FIELDS,
    ROLLING_SPELLING,
    STAMP_FORMAT,
    WINDOW_KINDS,
    WINDOW_SPELLINGS,
    Billed,
    Spend,
    SpendLog,
    Window,
    billed_since,
    parse_window,
    registry_spend,
    snapshot,
    spent,
)

def _shipped() -> list[Path]:
    """Every committed run configuration, not only the Cheat one.

    Globbed rather than listed, so a fourth config joins every pin below with
    no edit here — a hand-listed set reaches whichever files its author had in
    mind.
    """
    found = sorted(Path("experiments/llm_eval").glob("config*.yaml"))
    assert len(found) > 1, "the config glob found one file or none"
    return found


def _shipped_trees() -> list[Path]:
    """The results tree each shipped config writes into, and so the directory
    each one's spend log defaults to."""
    trees = sorted(
        {
            Path(yaml.safe_load(c.read_text(encoding="utf-8"))["results_dir"])
            for c in _shipped()
        }
    )
    assert len(trees) > 1, "the shipped configs resolve to one tree or none"
    return trees


#: A fixed instant, so nothing here races midnight. Every stamped entry is
#: placed relative to it and every cap check is made at it.
NOW = datetime(2026, 8, 23, 12, 0, 0, tzinfo=timezone.utc)

#: The rolling window the grid uses. Thirty days, so "three days ago" is
#: inside it and outside the calendar day — the two time-sensed windows are
#: separated by a state rather than by an offset that could collapse.
ROLLING = "720h"

#: One spelling per window kind, the grid's window axis. Derived from the
#: registry and overridden only for the parametric kind, whose spelling is a
#: number and cannot be its own name.
WINDOWS: dict[str, str] = {**WINDOW_SPELLINGS, "rolling": ROLLING}

#: Where the spend a cap might count is sitting when the cap is checked.
#: `absent` is the honest zero (a tree nothing has run in); `live` is billed
#: by a provider and not yet written, which is the only thing the in-memory
#: registry ever knew about.
STATES: tuple[str, ...] = ("absent", "live", "mine", "recent", "days_ago", "long_ago")

#: Whether the window counts the state's spend. THE authored column: each cell
#: is a decision about what a ceiling means, not a derivation from the code
#: that implements it.
ADMITS: dict[tuple[str, str], bool] = {
    ("invocation", "absent"): False,
    ("invocation", "live"): True,
    ("invocation", "mine"): True,
    ("invocation", "recent"): False,
    ("invocation", "days_ago"): False,
    ("invocation", "long_ago"): False,
    ("day", "absent"): False,
    ("day", "live"): True,
    ("day", "mine"): True,
    ("day", "recent"): True,
    ("day", "days_ago"): False,
    ("day", "long_ago"): False,
    ("rolling", "absent"): False,
    ("rolling", "live"): True,
    ("rolling", "mine"): True,
    ("rolling", "recent"): True,
    ("rolling", "days_ago"): True,
    ("rolling", "long_ago"): False,
    ("all", "absent"): False,
    ("all", "live"): True,
    ("all", "mine"): True,
    ("all", "recent"): True,
    ("all", "days_ago"): True,
    ("all", "long_ago"): True,
}

#: How much spend crosses each cap, in that cap's own dimension.
LIMITS: dict[str, float] = {
    "max_input_tokens": 100,
    "max_output_tokens": 100,
    "max_cost_usd": 1.0,
}

#: A model whose price makes a dollar figure exact: $1.00 per million input
#: tokens, so `max_cost_usd` has a live-spend witness that is not a rounding.
PRICED = "claude-haiku-4-5"

_WHEN: dict[str, datetime] = {
    "mine": NOW,
    "recent": NOW,
    "days_ago": NOW - timedelta(days=3),
    "long_ago": NOW - timedelta(days=400),
}


def _spend_of(cap: str, amount: float) -> Spend:
    """`amount` placed in the dimension `cap` bounds, and nowhere else.

    Which dimension that is comes from `CAPS`, not from a list here: a
    hand-written second copy of the mapping could drift from the one
    `Budget.exceeded` reads.
    """
    placed: dict[str, Any] = {CAPS[cap]: amount}
    return Spend(**placed)


def _live_registry(cap: str, amount: float) -> dict[str, Provider]:
    """A provider carrying `amount` of the cap's dimension, billed and unwritten.

    Dollars come from real tokens at a real price rather than being set
    directly, because that is the only way the registry can carry them.
    """
    provider = FakeProvider(replies=["{}"])
    provider.model = PRICED
    if cap == "max_input_tokens":
        provider.usage = Usage(calls=1, input_tokens=int(amount))
    elif cap == "max_output_tokens":
        provider.usage = Usage(calls=1, output_tokens=int(amount))
    else:
        provider.usage = Usage(calls=1, input_tokens=int(amount * 1_000_000))
    return {"m": provider}


def _stage(
    tmp_path: Path, state: str, cap: str, amount: float
) -> tuple[SpendLog, dict[str, Provider]]:
    """A log and a registry holding `amount` of the cap's dimension in `state`."""
    log = SpendLog(tmp_path / "spend" / "log.jsonl")
    if state == "absent":
        return log, {}
    if state == "live":
        return log, _live_registry(cap, amount)
    billed = [
        Billed(model_ref="m", model=PRICED, calls=1, spend=_spend_of(cap, amount))
    ]
    if state == "mine":
        log.record("r", "t", billed, now=_WHEN[state])
        return log, {}
    # Another invocation's line: written through a log with its own session,
    # onto the same path, which is exactly what a second `run_eval` does.
    other = SpendLog(log.path)
    other.record("r", "t", billed, now=_WHEN[state])
    return log, {}


@pytest.mark.parametrize("cap", sorted(CAPS))
@pytest.mark.parametrize("state", STATES)
@pytest.mark.parametrize("kind", WINDOW_KINDS)
def test_the_window_counts_what_it_admits_and_nothing_else(
    tmp_path: Path, kind: str, state: str, cap: str
) -> None:
    """The grid. A cap fires at its boundary over the spend its window admits.

    Both directions at every cell: an admitted cell must also NOT fire when
    the ceiling is above the spend, and a refused cell must have the spend
    genuinely present — otherwise a cell could read green because the fixture
    staged nothing.
    """
    amount = LIMITS[cap]
    log, registry = _stage(tmp_path, state, cap, amount)
    at: dict[str, Any] = {cap: amount, "window": WINDOWS[kind]}
    above: dict[str, Any] = {cap: amount * 10, "window": WINDOWS[kind]}
    budget, lifted = Budget(**at), Budget(**above)

    counted = ADMITS[(kind, state)]
    pending = registry_spend(registry)
    assert budget.exceeded(log, pending, now=NOW) == (cap if counted else None)
    assert lifted.exceeded(log, pending, now=NOW) is None, (
        "a ceiling well above the spend fired anyway"
    )
    if state != "absent":
        staged = SpendLog(log.path).total(Window("all"), now=NOW) + pending
        assert staged != Spend(), f"{state} staged no spend — the cell proves nothing"


def test_the_admits_table_covers_the_whole_cross() -> None:
    """The authored column is total over the cross it decides.

    One axis is derived and one is not, and the difference is real: a kind
    added to `spend.WINDOW_KINDS` reddens this, while a new record-state is a
    judgment nothing in the code can force. Stating that is what keeps the
    second half from reading as machinery it is not.

    red under: appending a fifth kind to `spend.WINDOW_KINDS`.
    """
    assert set(ADMITS) == {(k, s) for k in WINDOW_KINDS for s in STATES}
    assert set(WINDOWS) == set(WINDOW_KINDS)
    assert set(LIMITS) == set(CAPS)


def test_every_cap_field_is_a_registered_cap() -> None:
    """`CAPS` is the whole set of things `token_budget` bounds.

    `Budget.exceeded` iterates `CAPS`, so a cap field missing from it is a
    config key that reads as a ceiling and evaluates as nothing.

    red under: adding `max_wall_seconds: float = 0.0` to `Budget`.
    """
    # By SUBTRACTION, not by a naming convention: a fourth ceiling spelled
    # `dollar_ceiling` would slip past a `max_`-prefixed filter and stay a
    # config key nothing evaluates. Here it fails until someone classifies it.
    not_a_cap = {"window", "counts"}
    declared = {f.name for f in fields(Budget)} - not_a_cap
    assert declared == set(CAPS)


# --- misuse probes: the spellings a config author plausibly writes ----------


@pytest.mark.parametrize(
    "spelling",
    [
        "rolling",  # the KIND name; `<N>h` is its only spelling
        "invocations",  # plural drift
        "session",  # a plausible synonym for `invocation`
        "campaign",  # the window a `spend_log:` of its own gives you instead
        "24",  # no unit
        "24H",  # one name, one shape
        "24 h",  # spaced
        "1.5h",  # fractional
        "0h",  # a window admitting nothing, spelled as if it did
        "-3h",  # signed
        "h",  # a unit with no number
        "all ",  # trailing space
        "",  # empty
    ],
)
def test_an_unknown_window_spelling_is_refused(spelling: str) -> None:
    """Loud, and naming the registry.

    Defaulting instead would read the operator's widening as the narrowest
    window there is, which is the ceiling they were trying to change.
    """
    with pytest.raises(ValueError, match="token_budget.window"):
        parse_window(spelling)


@pytest.mark.parametrize("value", [24, None, 24.0, ["all"], {"kind": "all"}])
def test_a_non_string_window_is_refused_by_type(value: object) -> None:
    """YAML makes `window: 24` an int, and a `str` annotation cannot see it."""
    with pytest.raises(ValueError, match="must be a string"):
        parse_window(value)


@pytest.mark.parametrize("kind", WINDOW_KINDS)
def test_every_registered_kind_has_a_spelling_that_parses_back(kind: str) -> None:
    """The registry and the parser agree, in both directions."""
    parsed = parse_window(WINDOWS[kind])
    assert parsed.kind == kind
    assert parse_window(parsed.spelling()) == parsed


@pytest.mark.parametrize("hours", [1, 2, 24, 720, 8760])
def test_a_rolling_window_reaches_exactly_its_hours(tmp_path: Path, hours: int) -> None:
    """The parametric member of the axis, at its own boundary."""
    log = SpendLog(tmp_path / "log.jsonl")
    inside = SpendLog(log.path)
    inside.record(
        "r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=7))],
        now=NOW - timedelta(hours=hours) + timedelta(minutes=1),
    )
    window = parse_window(f"{hours}h")
    assert log.total(window, now=NOW) == Spend(input_tokens=7)

    outside = SpendLog(log.path)
    outside.record(
        "r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=5))],
        now=NOW - timedelta(hours=hours, minutes=1),
    )
    assert log.total(window, now=NOW) == Spend(input_tokens=7), (
        "a line older than the window was counted"
    )
    assert log.total(Window("all"), now=NOW) == Spend(input_tokens=12)


def test_the_rolling_spelling_admits_only_whole_hours_from_one() -> None:
    """The pattern IS the domain, so it is asserted rather than described.

    red under: relaxing `ROLLING_SPELLING` to `[0-9]+h`.
    """
    assert ROLLING_SPELLING.fullmatch("1h")
    assert ROLLING_SPELLING.fullmatch("720h")
    assert not ROLLING_SPELLING.fullmatch("0h")
    assert not ROLLING_SPELLING.fullmatch("01h")


# --- the log itself ---------------------------------------------------------


def test_a_second_log_on_one_path_sees_the_first(tmp_path: Path) -> None:
    """The mechanism a shared ceiling rests on.

    Every cap check re-reads the file, and each append is one write of whole
    lines onto a handle opened for append — so an invocation running beside
    this one against the same tree is counted, rather than each getting a
    ceiling of its own.
    """
    path = tmp_path / "log.jsonl"
    first, second = SpendLog(path), SpendLog(path)
    first.record("r1", "t", [Billed("m", PRICED, 1, Spend(input_tokens=10))])
    second.record("r2", "t", [Billed("m", PRICED, 1, Spend(input_tokens=25))])

    assert second.total(Window("all")) == Spend(input_tokens=35)
    # And `invocation` still separates them, or it would not be a window.
    assert second.total(Window("invocation")) == Spend(input_tokens=25)
    assert first.total(Window("invocation")) == Spend(input_tokens=10)


def test_the_short_circuit_agrees_with_the_line_it_skips(tmp_path: Path) -> None:
    """`invocation` answered in memory is the same answer the file gives.

    `total` returns `appended` without opening the file, so `admits`'
    `invocation` arm is reached by nothing else — and the equivalence the
    short-circuit rests on ("the two agree by construction") is a claim like
    any other. This is what holds it, and it is why the `session` field on
    every line is not dead weight.

    red under: dropping the `self.appended = ...` update from
    `SpendLog.record`.
    """
    path = tmp_path / "log.jsonl"
    first, second = SpendLog(path), SpendLog(path)
    first.record("r", "t", [Billed("m", PRICED, 1, Spend(1, 2, 0.5))])
    second.record("r", "t", [Billed("m", PRICED, 1, Spend(30, 40, 9.0))])
    first.record("r", "t", [Billed("m", PRICED, 1, Spend(7, 0, 0.25))])

    for log in (first, second):
        from_file = Spend()
        for entry in SpendLog(path).entries():
            if Window("invocation").admits(entry, now=NOW, session=log.session):
                from_file = from_file + Spend(
                    entry["input_tokens"], entry["output_tokens"], entry["cost_usd"]
                )
        assert log.total(Window("invocation")) == from_file
    # And the two sessions really are distinguished, or this compares one
    # number with itself.
    assert first.total(Window("invocation")) != second.total(Window("invocation"))


def _damaged(field_name: str, kind: str) -> list[str]:
    """A line missing `field_name`, and one carrying the wrong kind there.

    Derived from the entry table rather than written out, so a field added to
    a line joins this sweep with no edit.
    """
    good = json.loads(_LINE)
    missing = {k: v for k, v in good.items() if k != field_name}
    wrong = {**good, field_name: (None if kind == "text" else "lots")}
    return [json.dumps(missing), json.dumps(wrong)]


_LINE = json.dumps(
    {
        "ts": NOW.strftime(STAMP_FORMAT),
        "session": "abc",
        "run": "r",
        "matchup": "t",
        "model_ref": "m",
        "model": PRICED,
        "calls": 1,
        "input_tokens": 10,
        "output_tokens": 2,
        "cost_usd": 0.5,
    }
)


@pytest.mark.parametrize(
    "text",
    [
        "{not json",  # a half-written line
        "[1, 2, 3]",  # JSON, but not an entry
        '"a string"',
        "null",
        *[bad for name, kind in ENTRY_FIELDS.items() for bad in _damaged(name, kind)],
    ],
)
@pytest.mark.parametrize("kind", [k for k in WINDOW_KINDS if k != "invocation"])
def test_a_line_a_total_cannot_read_refuses(tmp_path: Path, kind: str, text: str) -> None:
    """Every way a line can fail to be countable, under every window that
    reads the file.

    All of them end in a total LOWER than what was billed, which widens the
    ceiling — so all of them refuse, and none is left to a `.get` default.
    Crossed with the window because a window reads different fields: `day` and
    `<N>h` read `ts`, `all` reads neither, and a line damaged only in a field
    this window ignores is still a line whose tokens the total is about to
    add.

    `invocation` is excluded by construction, not overlooked — see below.
    """
    log = SpendLog(tmp_path / "log.jsonl")
    log.path.parent.mkdir(parents=True, exist_ok=True)
    log.path.write_text(_LINE + "\n" + text + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=str(log.path)):
        log.total(parse_window(WINDOWS[kind]), now=NOW)


@pytest.mark.parametrize("text", ["{not json", '{"ts": null}'])
def test_a_damaged_line_cannot_reach_the_default_window(
    tmp_path: Path, text: str
) -> None:
    """`invocation` is answered from what this object wrote, so it never opens
    the file — and a run under the shipped default cannot be stopped by a line
    another invocation left half-written.

    Which is the whole reason the default is answered in memory: reading the
    file back would re-derive what `record` already established, and would put
    every existing config at the mercy of a file its ceiling needs nothing
    from.

    red under: deleting the `invocation` short-circuit at the top of
    `SpendLog.total`.
    """
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=7))])
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write(text + "\n")
    assert log.total(Window("invocation"), now=NOW) == Spend(input_tokens=7)
    # And the same line is still fatal to a window that DOES read the file,
    # or this would be a test of a log with nothing wrong with it.
    with pytest.raises(ValueError, match=str(log.path)):
        log.total(Window("all"), now=NOW)


def test_the_undamaged_line_the_probes_are_built_from_reads_clean(
    tmp_path: Path,
) -> None:
    """Or every row above would pass on the fixture rather than the damage."""
    log = SpendLog(tmp_path / "log.jsonl")
    log.path.parent.mkdir(parents=True, exist_ok=True)
    log.path.write_text(_LINE + "\n", encoding="utf-8")
    assert log.total(Window("all"), now=NOW) == Spend(10, 2, 0.5)


def test_a_recorded_line_carries_exactly_the_fields_a_reader_admits(
    tmp_path: Path,
) -> None:
    """Writer and reader read one table, so a line cannot be written in a
    shape the total then refuses.

    red under: dropping any key from `spend._line`'s returned dict.
    """
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(1, 2, 0.5))])
    assert set(next(iter(log.entries()))) == set(ENTRY_FIELDS)


def test_a_kind_outside_the_registry_is_refused_at_construction() -> None:
    """`parse_window` guards the spellings a config writes; the type guards
    itself, because `Window` is constructible directly and a window nobody
    parsed would otherwise admit whatever its last branch admits."""
    with pytest.raises(ValueError, match="no window kind"):
        Window("month")
    with pytest.raises(ValueError, match="rolling"):
        Window("rolling")  # the kind name is not a window; `<N>h` is
    with pytest.raises(ValueError, match="rolling"):
        Window("day", hours=3)


def test_a_registered_kind_with_no_arm_refuses(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The other half: a kind the registry GAINS without an arm in `admits`.

    Two guards, two classes — the constructor cannot catch this one, because
    by then the kind is registered. Widening the registry is exactly what a
    future author does, and the fall-through it would otherwise land in
    admits almost nothing.

    red under: making the `rolling` arm of `Window.admits` the fall-through
    again (deleting its `if` and the raise below it).
    """
    monkeypatch.setattr(spend_mod, "WINDOW_KINDS", (*WINDOW_KINDS, "month"))
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=1))])
    with pytest.raises(ValueError, match="no window arm"):
        log.total(Window("month"), now=NOW)


def test_an_absent_log_is_zero_not_an_error(tmp_path: Path) -> None:
    """A tree nothing has run in has spent nothing, which is a real reading."""
    log = SpendLog(tmp_path / "nothing" / "log.jsonl")
    assert log.total(Window("all")) == Spend()
    assert list(log.entries()) == []


def test_a_recorded_line_carries_the_dollars_it_was_billed(tmp_path: Path) -> None:
    """Stamped, not recomputed: `providers.PRICES` is today's list price, and a
    total re-derived from tokens would restate what a past run cost."""
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("cheap", PRICED, 3, Spend(1, 2, 0.25))])
    entry = next(iter(log.entries()))
    assert entry["cost_usd"] == 0.25
    assert (entry["model_ref"], entry["model"], entry["calls"]) == ("cheap", PRICED, 3)
    assert entry["session"] == log.session
    assert datetime.strptime(entry["ts"], STAMP_FORMAT)


def test_nothing_billed_writes_no_line(tmp_path: Path) -> None:
    """Offline matchups run a lot; a zero line per game would be the log's bulk."""
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("m", PRICED, 0, Spend())])
    assert not log.path.exists()
    assert log.appended == Spend()


def test_the_pending_residual_is_measured_from_the_callers_own_mark(
    tmp_path: Path,
) -> None:
    """Billed-and-not-yet-written is the caller's fact, not the log's.

    A model reference names a config entry, not a provider's lifetime: `smoke`
    and a later matchup bill through two different providers under one name.
    A log that tracked the residual per reference would measure the second
    against the first and hand back a NEGATIVE spend, cancelling real money
    out of the total.

    red under: returning `Spend()` from `spend.spent`, the summation the
    caller hands over.
    """
    log = SpendLog(tmp_path / "log.jsonl")
    smoked = _live_registry("max_input_tokens", 1000)
    log.record("smoke", "smoke", billed_since(smoked, snapshot({})))
    assert log.appended.input_tokens == 1000

    # A SECOND provider under the same reference, as a later matchup builds.
    later = _live_registry("max_input_tokens", 50)
    pending = spent(billed_since(later, snapshot({})))
    assert pending.input_tokens == 50, "the later run's own spend, in full"
    assert log.total(Window("all")) + pending == Spend(
        input_tokens=1050, cost_usd=0.00105
    )


# --- where the log sits, and which readers can reach it ---------------------


def test_the_log_is_outside_every_transcript_glob(tmp_path: Path) -> None:
    """A spend line read as a game record is a matchup that never played.

    Every reader of a results tree globs `*.jsonl` — `verify._transcripts`,
    `promote._matchups_of`, and `compare` and `study` through the first. The
    log's own directory is what keeps it out of all of them.

    red under: returning `results_dir / "spend_log.jsonl"` from
    `layout.spend_log_path`.
    """
    from ..promote import _matchups_of
    from ..verify import _transcripts

    tree = tmp_path / "results"
    archive = tree / "transcripts"
    archive.mkdir(parents=True)
    (archive / "real.jsonl").write_text("{}\n", encoding="utf-8")
    log = SpendLog(spend_log_path(tree))
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=1))])

    assert log.path.exists()
    assert [p.name for p in _transcripts(archive)] == ["real.jsonl"]
    assert sorted(_matchups_of(tree)) == ["real"]
    assert sorted(_transcripts(tree)) == [], "the tree root holds no transcripts"


@pytest.mark.parametrize("path", _shipped_trees(), ids=lambda p: p.name)
def test_the_default_log_is_ignored_in_every_shipped_tree(path: Path) -> None:
    """git does not track it, wherever the shipped configs put their results.

    Asked of git rather than read off the rules, because the three trees do
    not carry the same ones: two have a recursive `*.jsonl` that would keep
    working under any directory name, and `results_kuhn` has no ignore file of
    its own at all — so the tree where a rename would expose a billing record
    is exactly the one a spot-check of the other two would clear.

    red under: renaming `layout.SPEND`.
    """
    log = spend_log_path(path)
    done = subprocess.run(
        ["git", "check-ignore", "-q", str(log)],
        cwd=Path(__file__).resolve().parents[3],
        check=False,
    )
    assert done.returncode == 0, f"{log} is not ignored — it would be committable"


def test_the_log_defaults_into_the_results_tree_and_can_be_shared(
    tmp_path: Path,
) -> None:
    """One log per tree unless a config says otherwise.

    `spend_log:` exists because a tree is one GAME's output while an account
    is one bill: three configs naming three trees would otherwise carry three
    independent ceilings.
    """
    tree = tmp_path / "results"
    assert spend_log(config={}, results_dir=tree).path == spend_log_path(tree)
    shared = tmp_path / "campaign.jsonl"
    assert spend_log({"spend_log": str(shared)}, tree).path == shared


def test_a_spend_log_that_is_not_a_path_is_refused(tmp_path: Path) -> None:
    """The key names a file. A value that cannot be one fails at the first
    append otherwise — which is after a run has already spent money."""
    tree = tmp_path / "results"
    a_directory = tmp_path / "somewhere"
    a_directory.mkdir()
    for value, needle in [
        (7, "must be a path"),
        (None, "must be a path"),
        ("", "must be a path"),
        ("   ", "must be a path"),
        (["a.jsonl"], "must be a path"),
        (str(a_directory), "is a directory"),
    ]:
        with pytest.raises(ValueError, match=needle):
            spend_log({"spend_log": value}, tree)


def _smoke_config(tmp_path: Path, model_extra: dict[str, Any] | None = None) -> Path:
    """A config whose matchup names fake models, for `--smoke`."""
    models: dict[str, Any] = {
        "m": {
            "kind": "fake",
            "model": "fake",
            "replies": ['{"action": 0, "reasoning": "smoke"}'],
        }
    }
    models.update(model_extra or {})
    agents: list[dict[str, Any]] = [
        {"kind": "llm", "name": ref, "model": ref} for ref in models
    ]
    agents += [{"kind": "random"}] * (4 - len(agents))
    config = {
        "game": "cardlang_cheat",
        "results_dir": str(tmp_path),
        "models": models,
        "token_budget": {"max_output_tokens": 1, "window": "all"},
        "matchups": [{"name": "t", "n": 1, "agents": agents}],
    }
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    return path


def test_a_smoke_call_is_recorded_and_is_not_capped(tmp_path: Path) -> None:
    """The second billing path, which the runner's own tests never reach.

    Two claims that pull opposite ways, so both are asserted here. Every path
    that bills writes to the log — `smoke` included, or a window counts less
    than the account did. And `smoke` is the one billing path a cap does NOT
    gate: it is the diagnostic an operator reaches for once a ceiling has
    stopped the work, and the ceiling staged here is already crossed.

    red under: deleting the `log.record(...)` in `smoke`'s `finally`.
    """
    from ..run_eval import main

    config = _smoke_config(tmp_path)
    log = SpendLog(spend_log_path(tmp_path))
    log.record("earlier", "t", [Billed("m", PRICED, 1, Spend(output_tokens=10**6))])
    before = log.total(Window("all"))

    assert main(["--config", str(config), "--smoke"]) == 0, "a crossed cap blocked smoke"
    after = SpendLog(log.path).total(Window("all"))
    assert after.output_tokens > before.output_tokens, "the smoke call went unrecorded"


def test_a_smoke_that_dies_partway_still_records_what_it_billed(
    tmp_path: Path,
) -> None:
    """Building a later model can raise, and the models smoked before it have
    already spent.

    red under: moving `smoke`'s `log.record(...)` out of its `finally` and
    onto the normal path.
    """
    from ..run_eval import main

    config = _smoke_config(tmp_path, {"z_broken": {"kind": "not-a-kind", "model": "f"}})
    with pytest.raises(ValueError, match="unknown provider kind"):
        main(["--config", str(config), "--smoke"])
    spent_anyway = SpendLog(spend_log_path(tmp_path)).total(Window("all"))
    assert spent_anyway.output_tokens > 0, "the models that did smoke went unrecorded"


@pytest.mark.parametrize("damage", ["{not json", '{"ts": "yesterday"}'])
def test_an_unreadable_log_dies_before_a_game_is_paid_for(
    tmp_path: Path, damage: str
) -> None:
    """The log is reached and read in pre-flight, not at the first cap check.

    A window that reads the file refuses a damaged line — correctly, since
    counting it as zero would widen the ceiling — and that refusal has to land
    before a run starts. Reaching it at the loop top instead means an operator
    learns the log is broken after a game has been played and billed.

    red under: deleting `log.total(budget.counts)` from `main`'s pre-flight.
    """
    from ..run_eval import main

    log = SpendLog(spend_log_path(tmp_path))
    log.record("earlier", "t", [Billed("m", PRICED, 1, Spend(input_tokens=1))])
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write(damage + "\n")

    config = _smoke_config(tmp_path)
    assert main(["--config", str(config)]) == 2
    assert not (tmp_path / "runs").exists(), "a run directory was made anyway"


def test_a_log_whose_directory_cannot_be_made_dies_in_pre_flight(
    tmp_path: Path,
) -> None:
    """The other half of reaching the log early: a path it can never write to.

    `spend_log:` takes an arbitrary path, and one whose parent is a FILE fails
    at the first append — which is after a game has been played.

    red under: deleting `log.path.parent.mkdir(...)` from `main`'s pre-flight.
    """
    from ..run_eval import main

    blocker = tmp_path / "not-a-directory"
    blocker.write_text("", encoding="utf-8")
    config = json.loads(_smoke_config(tmp_path).read_text(encoding="utf-8"))
    config["spend_log"] = str(blocker / "spend" / "log.jsonl")
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")

    assert main(["--config", str(path)]) == 2
    assert not (tmp_path / "runs").exists()


@pytest.mark.parametrize(
    ("block", "needle"),
    [
        ({"max_dollars": 5}, "nothing evaluates"),          # a plausible synonym
        ({"max_cost": 5}, "nothing evaluates"),             # the cap, half-spelled
        ({"maxcostusd": 5}, "nothing evaluates"),           # separators dropped
        ({"max_cost_usd": "5 dollars"}, "not a number"),    # a quantity as prose
        ({"max_cost_usd": None}, "not a number"),           # YAML's bare `~`
        ({"max_input_tokens": True}, "not a number"),       # `yes` in YAML
        ({"max_cost_usd": -1}, "negative ceiling"),         # a ceiling below zero
        ({"max_input_tokens": -1}, "negative ceiling"),
    ],
)
def test_a_token_budget_key_or_value_outside_the_registry_is_refused(
    block: dict[str, Any], needle: str
) -> None:
    """The block's own Owner Guard, naming the registry.

    `Budget(**block)` refuses an unknown KEY on its own, but as a `TypeError`
    about a dataclass argument — a message that names neither the config nor
    the three caps that exist. It accepts a non-numeric or negative VALUE
    outright, and a truthy string then compares against a float and stops the
    run at its first check, while a negative ceiling stops it before its first
    game while reading like a large one.

    red under: replacing `budget_of`'s body with `return
    Budget(**config.get("token_budget", {}))`.
    """
    with pytest.raises(ValueError, match=needle) as caught:
        budget_of({"token_budget": block})
    if needle == "nothing evaluates":
        for cap in CAPS:
            assert cap in str(caught.value), "the refusal does not name the registry"


def test_a_token_budget_that_is_not_a_block_is_refused() -> None:
    """`token_budget: 60` is the shape an author writes when they think the
    key is the ceiling."""
    with pytest.raises(ValueError, match="block of caps"):
        budget_of({"token_budget": 60})


def test_a_bad_token_budget_in_a_config_dies_before_anything_runs(
    tmp_path: Path,
) -> None:
    """And it lands in pre-flight, at exit 2, with no run directory — an
    all-matchup run would otherwise surface it after the expensive matchups
    are paid for."""
    from ..run_eval import main

    config = json.loads(_smoke_config(tmp_path).read_text(encoding="utf-8"))
    config["token_budget"] = {"max_dollars": 5}
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert main(["--config", str(path)]) == 2
    assert not (tmp_path / "runs").exists()


def test_a_bad_spend_log_in_a_config_dies_before_anything_runs(
    tmp_path: Path,
) -> None:
    """Pre-flight, at exit 2, alongside the model and budget refusals."""
    from ..run_eval import main

    (tmp_path / "adir").mkdir()
    config = {
        "game": "cardlang_cheat",
        "results_dir": str(tmp_path),
        "spend_log": str(tmp_path / "adir"),
        "models": {},
        "matchups": [
            {"name": "t", "n": 1, "agents": [{"kind": "rule"}] + [{"kind": "random"}] * 3}
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert main(["--config", str(path)]) == 2
    assert not (tmp_path / "runs").exists()


# --- the shipped configs ----------------------------------------------------


@pytest.mark.parametrize("path", _shipped(), ids=lambda p: p.name)
def test_a_shipped_config_names_only_keys_a_budget_evaluates(path: Path) -> None:
    """A `token_budget` key outside the registry is a ceiling nothing reads.

    `Budget(**token_budget)` raises on an unknown key, but for a committed
    file that is a fact about a run somebody has to start — and on an
    all-matchup run it surfaces only after the expensive matchups are paid
    for. Here it is a fact about the file.
    """
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    budget: dict[str, Any] = config.get("token_budget", {})
    assert set(budget) <= set(CAPS) | {"window"}, f"{path.name}: unknown budget keys"
    if "window" in budget:
        parse_window(budget["window"])


@pytest.mark.parametrize("path", _shipped(), ids=lambda p: p.name)
def test_a_shipped_config_bounds_something(path: Path) -> None:
    """A `token_budget` block naming no cap is a ceiling of none.

    red under: emptying `token_budget` in any shipped config.
    """
    config = yaml.safe_load(path.read_text(encoding="utf-8"))
    budget: dict[str, Any] = config.get("token_budget", {})
    assert any(budget.get(cap) for cap in CAPS), f"{path.name}: no cap is set"


def test_an_unknown_window_in_a_config_dies_before_anything_runs(
    tmp_path: Path,
) -> None:
    """Pre-flight, at exit 2, with nothing constructed and no run directory."""
    from ..run_eval import main

    config = {
        "game": "cardlang_cheat",
        "results_dir": str(tmp_path),
        "models": {},
        "token_budget": {"max_cost_usd": 5.0, "window": "fortnight"},
        "matchups": [
            {"name": "t", "n": 1, "agents": [{"kind": "rule"}] + [{"kind": "random"}] * 3}
        ],
    }
    path = tmp_path / "config.yaml"
    path.write_text(json.dumps(config), encoding="utf-8")
    assert main(["--config", str(path)]) == 2
    assert not (tmp_path / "runs").exists()
