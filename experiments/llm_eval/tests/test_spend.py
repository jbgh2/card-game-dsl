"""The spend log and the windows a `token_budget` cap is counted over.

The cap the rig ships is a ceiling over spend, and until a record outlived the
process it could only see one. These cross the two registries that decide what
a ceiling counts — `run_eval.CAPS` and `spend.WINDOW_KINDS` — against every
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
                 fire above it. The misuse probes cross the spellings a
                 config author plausibly writes.

                 Two boundaries, both stated positively rather than missing.
                 A cap is counted over ONE log: `spend_log:` is what points
                 several configs at one, and no window reaches across two
                 files. And a relative `results_dir` or `spend_log` resolves
                 against the working directory, as every other path in this
                 rig does, so two invocations from two directories are two
                 records and two ceilings.
registry:        run_eval.py::CAPS (the cap axis, pinned equal to `Budget`'s
                 own `max_` fields by
                 test_every_cap_field_is_a_registered_cap);
                 spend.py::WINDOW_KINDS (the window axis) with
                 spend.py::WINDOW_SPELLINGS the one spelling per kind the grid
                 reads; spend.py::ROLLING_SPELLING (the parametric spelling).
                 The pre-existing per-model summation:
                 test_runner.py::test_budget_sums_across_every_model_in_the_registry.
                 The runner's end-to-end behaviour under a crossed window:
                 test_runner.py::test_a_second_invocation_stops_where_the_first_left_off.
does not prove:  that the log holds everything an account was billed. It holds
                 what `providers.Usage` counts, and `Usage` is fed from the
                 `Reply` a completed call returns — so an SDK-internal retry,
                 and a call billed by the API that raises before its usage is
                 added, are spend no window here can see. The cap is therefore
                 a floor on spend, never a proof of it (issue #422).
"""

from __future__ import annotations

import json
from dataclasses import fields
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
import yaml

from ..layout import spend_log_path
from ..providers import FakeProvider, Provider, Usage
from ..run_eval import CAPS, Budget, spend_log
from ..spend import (
    ROLLING_SPELLING,
    STAMP_FORMAT,
    WINDOW_KINDS,
    WINDOW_SPELLINGS,
    Billed,
    Spend,
    SpendLog,
    Window,
    parse_window,
)

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
    """`amount` placed in the dimension `cap` bounds, and nowhere else."""
    if cap == "max_input_tokens":
        return Spend(input_tokens=int(amount))
    if cap == "max_output_tokens":
        return Spend(output_tokens=int(amount))
    return Spend(cost_usd=float(amount))


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
    assert budget.exceeded(registry, log, now=NOW) == (cap if counted else None)
    assert lifted.exceeded(registry, log, now=NOW) is None, (
        "a ceiling well above the spend fired anyway"
    )
    if state != "absent":
        staged = SpendLog(log.path).total(Window("all"), now=NOW) + log.unrecorded(
            registry
        )
        assert staged != Spend(), f"{state} staged no spend — the cell proves nothing"


def test_the_admits_table_covers_the_whole_cross() -> None:
    """The authored column is total over both derived axes.

    red under: dropping any line from `ADMITS`.
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
    declared = {f.name for f in fields(Budget) if f.name.startswith("max_")}
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


def test_an_unreadable_line_refuses_rather_than_undercounting(tmp_path: Path) -> None:
    """Reading past a damaged line would silently raise the ceiling."""
    log = SpendLog(tmp_path / "log.jsonl")
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=10))])
    with log.path.open("a", encoding="utf-8") as handle:
        handle.write("{not json\n")
    with pytest.raises(ValueError, match="not a spend entry"):
        log.total(Window("all"))


def test_a_json_line_that_is_not_an_object_refuses(tmp_path: Path) -> None:
    log = SpendLog(tmp_path / "log.jsonl")
    log.path.parent.mkdir(parents=True, exist_ok=True)
    log.path.write_text("[1, 2, 3]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="not a spend entry"):
        log.total(Window("all"))


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


def test_unrecorded_is_what_the_providers_billed_beyond_the_log(
    tmp_path: Path,
) -> None:
    """The residual term, which is what makes one expression cover every window.

    red under: returning `registry_spend(registry)` from `unrecorded`.
    """
    log = SpendLog(tmp_path / "log.jsonl")
    registry = _live_registry("max_input_tokens", 100)
    assert log.unrecorded(registry) == Spend(input_tokens=100, cost_usd=0.0001)
    log.record("r", "t", [Billed("m", PRICED, 1, Spend(input_tokens=100, cost_usd=0.0001))])
    assert log.unrecorded(registry) == Spend()


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


# --- the shipped configs ----------------------------------------------------


def _shipped() -> list[Path]:
    """Every committed run configuration, not only the Cheat one.

    Globbed rather than listed: the two pins that read a shipped config before
    this one each read `config.yaml` alone, so `config_kuhn.yaml` and
    `config_holdem.yaml` were unchecked by both.
    """
    found = sorted(Path("experiments/llm_eval").glob("config*.yaml"))
    assert len(found) > 1, "the config glob found one file or none"
    return found


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
