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
sampled:   the claim is made on ONE line — the walk's pinned `Random(7)`. A
           verb reachable on other lines but not this one reads as unreached
           here, which is why an unreached entry states where the mechanic IS
           exercised rather than asserting it is unreachable. Sampling one line
           is what makes the check deterministic and free; the per-game margin
           between the last new verb and the bound is the guard against a game
           change shifting the line (`last_new_verb` in the coverage record).
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
from collections.abc import Iterator
from typing import Any

import pytest

from cardlang.openspiel.replay import load

from .harness import (
    REGISTERED_GAMES,
    GameSpec,
    bounded_walk,
    pin_failures,
    verb_status,
)
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
def test_the_unreached_pin_is_well_formed(
    short_name: str, spec: GameSpec
) -> None:
    """The well-formedness the per-verb grid cannot see (`harness.pin_failures`,
    whose arms are probed one by one below)."""
    declared = _declared(spec) if spec.conformance_steps is not None else frozenset()
    failures = pin_failures(spec, declared)
    assert not failures, f"{short_name}: " + "; ".join(failures)


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


# --- misuse probes ---------------------------------------------------------
#
# The guards above fire on no game in the corpus — every registered spec is
# well-formed, so their assertions run green without ever having been shown a
# violation. A guard nothing executes is not a guard, so each arm gets a
# synthetic spec that trips exactly it.


def test_verb_status_covers_the_applied_exempt_square() -> None:
    """All four cells of the 2x2, named. A classifier that collapsed `stale`
    into `exempt` would let a recorded-unreached verb outlive its reason
    silently — the exact failure class this module exists to remove."""
    a, e = frozenset({"play"}), frozenset({"pass"})
    assert verb_status("play", a, frozenset()) == "covered"
    assert verb_status("pass", a, e) == "exempt"
    assert verb_status("play", a, frozenset({"play"})) == "stale"
    assert verb_status("draw", a, e) == "uncovered"


def _probe(steps: int | None, entries: tuple[tuple[str, str], ...]) -> list[str]:
    return pin_failures(
        GameSpec(
            "cardlang_probe",
            "hearts.cardlang",
            conformance_steps=steps,
            conformance_verbs_unreached=entries,
        ),
        frozenset({"<card>", "pass"}),
    )


def test_a_well_formed_pin_has_no_complaints() -> None:
    """The control: without it, a `pin_failures` that returned a complaint for
    everything would pass all three probes below."""
    assert _probe(120, (("pass", "the auction never passes on this line"),)) == []


def test_a_pin_naming_an_undeclared_verb_is_rejected() -> None:
    """The renamed / mistyped move type: the entry matches no cell, so nothing
    else in this module would ever look at it again."""
    failures = _probe(120, (("pas", "typo for pass"),))
    assert len(failures) == 1 and "does not declare" in failures[0]


def test_a_pin_with_no_reason_is_rejected() -> None:
    failures = _probe(120, (("pass", "   "),))
    assert len(failures) == 1 and "no reason" in failures[0]


def test_a_pin_on_an_unbounded_game_is_rejected() -> None:
    """Nothing walks an unbounded game from here, so an entry on one is a
    claim no run can contradict."""
    failures = _probe(None, (("pass", "a reason nothing checks"),))
    assert len(failures) == 1 and "bounded walk" in failures[0]
