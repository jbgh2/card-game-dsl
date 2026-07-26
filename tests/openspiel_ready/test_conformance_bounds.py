"""Every conformance bound is a budget with a CHECKED coverage claim.

`GameSpec.conformance_steps` bounds the pyspiel API walk for games whose full
`random_sim_test` is prohibitively long (the adapter re-simulates the whole
(seed, history) state per action — issue #139 owns that O(n^2)). Every such
bound was hand-picked, and the defect that made them worth revisiting is not
that they were wrong: it is that **a bound set too low under-covers silently**.
Nothing anywhere noticed when a walk stopped reaching a mechanic, so the
numbers could only ever be defended by the cost that motivated them.

This module inverts that failure mode. The claim attached to a bound is:

    within `conformance_steps`, the walk APPLIES every verb of the game's
    declared action space, except the verbs the spec names as unreached.

Applied, not merely offered: the bound is bought to drive the mechanic behind
the verb through the adapter, and an offered-but-never-chosen action never
enters `apply_action`.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every registered game's conformance bound carries a coverage claim
           that FAILS LOUDLY when the bound stops covering, and every
           exemption from that claim is tight (it cannot outlive its reason).
domain:    `harness.REGISTERED_GAMES` — the adapter's own registry, so a newly
           registered game is in-domain the day it registers (`test_coverage.py`
           pins one proof module per registry entry) — crossed with that
           game's `ActionSpace.verbs()`, derived from the action space's blocks
           rather than listed here. The bound-mode axis is total by
           construction: `conformance_steps` is `int | None`, and both values
           are handled below.
registry:  `cardlang.openspiel.encoding.ActionSpace` — `verbs()` is computed
           from the same four blocks `decode` partitions, so a game that gains
           a move type gains its verb cell without an edit here.
covered:   the grid IS the coverage — one parametrized cell per (game, verb)
           pair, plus one per game for the pin's own well-formedness and for
           the bound mode. `harness.verb_status` is total over the 2x2 of
           (applied, recorded-unreached) and all four of its cells are probed
           below. Every unreached cell carries its reason IN the spec, checked
           non-empty, so no cell can be dark.
residual:  (a) UNBOUNDED games (`conformance_steps=None`) get no verb claim.
           There is no bound to justify — the full `random_sim_test` plays one
           random line to Terminal, and pyspiel chooses its actions internally,
           so the walk is not observable from here. What IS asserted for them
           is that they record no unreached verbs, so the two modes stay
           disjoint and a claim can never sit unchecked.
           (b) Verb granularity stops where the ENCODING stops: the card,
           integer and combination blocks carry a parameter value, not a move
           name (`encoding.CARD_VERB` and friends), so `<combo>` is one cell
           for Big Two rather than one per combination kind. Recovering the
           finer classification needs an enumerable kind set on the combo
           codec seam, which only the table-backed engines have. This ledger
           owns the record: it is a property of the action encoding, not
           deferred work — a game's combination kinds are exercised by its
           playout suite, and the adapter surface a conformance walk tests is
           per-block.
           (c) Two `<card>` cells are unreachable BY CONSTRUCTION rather than
           by depth — Big Two encodes every play through the combo block, and
           Seven-Card Stud never makes a card-valued decision at all, so both
           reserve a card block no state can offer. Recorded as unreached with
           that reason; issue #157 owns deriving the block away.

The bound each game carries is not derived here: coverage says how LOW a bound
may go, never how high, and depth beyond the coverage frontier is still real
API conformance (`cheat` walks 400 steps for 1.3s). What this module removes is
the silence — a bound may be cut for cost, and the cells say immediately what
the cut costs in coverage.
"""

from __future__ import annotations

import importlib
from typing import Any, Iterator

import pytest

from cardlang.openspiel.replay import load

from .harness import GameSpec, REGISTERED_GAMES, bounded_walk, verb_status
from .partition import record


def _spec(short_name: str) -> GameSpec:
    mod = importlib.import_module(
        ".test_" + short_name.removeprefix("cardlang_"), package=__package__
    )
    spec: GameSpec = mod.TestReadiness.spec
    return spec


SPECS: list[tuple[str, GameSpec]] = [(short, _spec(short)) for short, _ in REGISTERED_GAMES]
BOUNDED: list[tuple[str, GameSpec]] = [
    (s, spec) for s, spec in SPECS if spec.conformance_steps is not None
]


def _declared(spec: GameSpec) -> frozenset[str]:
    _, space = load(spec.path)
    return space.verbs()


def _cells() -> Iterator[Any]:
    for short, spec in BOUNDED:
        for verb in sorted(_declared(spec)):
            yield pytest.param(short, spec, verb, id=f"{short.removeprefix('cardlang_')}-{verb}")


@pytest.mark.parametrize(("short_name", "spec", "verb"), list(_cells()))
def test_the_bound_covers_every_declared_verb(
    short_name: str, spec: GameSpec, verb: str
) -> None:
    assert spec.conformance_steps is not None
    walk = bounded_walk(short_name, spec.path, spec.conformance_steps)
    status = verb_status(verb, walk.verbs_applied, spec.unreached_verbs)
    assert status in ("covered", "exempt"), {
        "uncovered": (
            f"{short_name}: the bounded walk never applies `{verb}` within "
            f"conformance_steps={spec.conformance_steps} (it applies "
            f"{sorted(walk.verbs_applied)}, the last new one at step "
            f"{walk.last_new_verb}) — the bound under-covers. Raise it until "
            f"the walk reaches the verb, or record `{verb}` in "
            f"conformance_verbs_unreached with the reason and where the "
            f"mechanic IS exercised."
        ),
        "stale": (
            f"{short_name}: `{verb}` is recorded in conformance_verbs_unreached "
            f"but the walk applies it at step {dict(walk.first_applied).get(verb)} "
            f"— drop the entry; its reason has outlived itself."
        ),
    }[status]


@pytest.mark.parametrize(
    ("short_name", "spec"), [pytest.param(s, sp, id=s.removeprefix("cardlang_")) for s, sp in SPECS]
)
def test_exemptions_are_declared_verbs_of_a_bounded_walk(
    short_name: str, spec: GameSpec
) -> None:
    """The three halves the per-verb grid cannot see: an entry naming a verb the
    game does not declare (a typo, or a move type since renamed — it would sit
    in the list forever, matching no cell), an entry with no reason, and any
    entry at all on an unbounded game (nothing walks, so nothing checks it)."""
    if spec.conformance_steps is None:
        assert not spec.conformance_verbs_unreached, (
            f"{short_name}: conformance_verbs_unreached is only checkable "
            f"against a bounded walk; this game runs the full random_sim_test"
        )
        return
    unknown = sorted(spec.unreached_verbs - _declared(spec))
    assert not unknown, (
        f"{short_name}: conformance_verbs_unreached names {unknown}, which the "
        f"action space does not declare — no cell can ever clear them"
    )
    unreasoned = sorted(v for v, why in spec.conformance_verbs_unreached if not why.strip())
    assert not unreasoned, (
        f"{short_name}: {unreasoned} are recorded as unreached with no reason "
        f"— an unexplained hole reads as a covered one"
    )


@pytest.mark.parametrize(
    ("short_name", "spec"),
    [pytest.param(s, sp, id=s.removeprefix("cardlang_")) for s, sp in BOUNDED],
)
def test_record_the_bound_and_what_it_reached(short_name: str, spec: GameSpec) -> None:
    """A passing run records what its bound bought (partition.RECORDS), so the
    numbers are citable rather than folklore."""
    assert spec.conformance_steps is not None
    walk = bounded_walk(short_name, spec.path, spec.conformance_steps)
    declared = _declared(spec)
    record(
        short_name,
        "bound",
        steps=spec.conformance_steps,
        walked=walk.steps,
        terminal=walk.terminal,
        verbs=f"{len(walk.verbs_applied)}/{len(declared)}",
        last_new_verb=walk.last_new_verb,
        unreached=",".join(sorted(spec.unreached_verbs)) or "-",
    )


# --- misuse probes: verb_status is total, and every cell is reachable ------


def test_verb_status_covers_the_applied_exempt_square() -> None:
    """All four cells of the 2x2, named. A classifier that collapsed `stale`
    into `exempt` would let an exemption outlive its reason silently — the
    exact failure class this module exists to remove."""
    a, e = frozenset({"play"}), frozenset({"pass"})
    assert verb_status("play", a, frozenset()) == "covered"
    assert verb_status("pass", a, e) == "exempt"
    assert verb_status("play", a, frozenset({"play"})) == "stale"
    assert verb_status("draw", a, e) == "uncovered"
