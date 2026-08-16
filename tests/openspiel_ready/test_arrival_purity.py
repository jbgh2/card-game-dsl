"""The copy-swap pins (issue #256): the Arrival Record holds VALUES only.

The engine's ground truth over-distinguishes: Python object identity can
track a specific ♠Q copy through any mixing, and a player cannot. The
no-leak criterion's copy-swap clause — "exchanging the histories of two
same-face copies where observation cannot distinguish them changes nothing
any observer sees" — is, under this engine's value-typed `Card`, a
representational impossibility: equal copies produce equal `Arrival`
entries, so there is no exchange to perform. This module makes that
impossibility EXECUTABLE rather than argued: two independent replays of the
same (game, seed, history) build entirely distinct `Card` objects, so any
RUN-VARYING per-object identity in the record — an `id(card)` key, anything
allocation-derived — diverges between the runs, while a pure value record
serializes byte-identically. The pin's exact property is invariance under
rebuilding every object: a DETERMINISTIC per-copy tag (a build-order index
stamped identically each run) would replay identically and is outside this
pin's reach — no such carrier exists in the values-only engine (`Card` and
`Arrival` carry no field to hold one, and `deep_freeze` refuses new
shapes), so the guard for that hypothetical is the value types themselves,
not this comparison.

The game axis is DERIVED from the component registry, never hand-listed:
every registered game whose deck holds two or more equal (rank, suit)
values is in the domain (doppelkopf48, canasta108, pinochle48, coup15, and
the duplicated piece sets), so a new duplicate deck joins the pin
automatically. The issue names doppelkopf and canasta108 as the witnesses;
the class sweep covers their whole class.

red under: give `Arrival` an object-identity field (e.g. `oid: int = 0`
populated with `id(card)` in `Zone.add`) — every duplicate-deck game's two
runs serialize differently at the first deal (executed 2026-08-15; the run
is recorded in the change's completeness ledger, tests/test_arrival_record.py).
"""

from __future__ import annotations

from collections import Counter

import pytest

from cardlang.openspiel.replay import DecisionNode, load, run
from cardlang.runtime.values import build_deck

from .harness import GAMES_DIR, REGISTERED_GAMES
from .partition import record, zone_instances


def _duplicate_deck_games() -> list[tuple[str, str]]:
    """(short_name, filename) for every registered game whose component set
    holds duplicate equal values — the axis, derived from the deck census."""
    out: list[tuple[str, str]] = []
    for short_name, filename in REGISTERED_GAMES:
        game, _space = load(str(GAMES_DIR / filename))
        counts = Counter((c.rank, c.suit) for c in build_deck(game.deck))
        if any(n >= 2 for n in counts.values()):
            out.append((short_name, filename))
    return out


_DUP_GAMES = _duplicate_deck_games()


def test_the_duplicate_class_is_nonempty_and_holds_the_witnesses() -> None:
    """The derived axis contains the issue's two named witnesses — an empty
    or witness-less derivation would make every cell below vacuous."""
    names = {short for short, _ in _DUP_GAMES}
    assert "cardlang_doppelkopf" in names and "cardlang_canasta" in names, (
        f"the duplicate-deck derivation lost a named witness: {sorted(names)}"
    )


def _serialized_record(node: DecisionNode) -> dict[str, list[str]]:
    """Every zone's Arrival Record, serialized WHOLE (`repr` of each entry,
    not a projection of chosen fields) — so a planted identity field cannot
    hide from the comparison."""
    return {
        (name if key is None else f"{name}[{key}]"): [repr(a) for a in zone.arrivals]
        for name, key, zone in zone_instances(node.rs)
    }


@pytest.mark.parametrize("short_name,filename", _DUP_GAMES, ids=lambda v: v)
def test_record_is_invariant_under_replacing_copies(
    short_name: str, filename: str
) -> None:
    """Two independent replays of the same (seed, history): distinct Card
    objects, byte-identical records and information states. This is the
    copy-swap invariance in its strongest executable form — invariance under
    EVERY bijection of equal-valued objects at once, not one hand-picked
    exchange."""
    path = str(GAMES_DIR / filename)
    seed = 3
    # Walk a short greedy prefix so plays (not just deals) are on record.
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    for _ in range(8):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, DecisionNode):
            history.pop()
            break
        r = nxt

    a = run(path, seed, tuple(history))
    b = run(path, seed, tuple(history))
    assert isinstance(a, DecisionNode) and isinstance(b, DecisionNode)
    rec_a, rec_b = _serialized_record(a), _serialized_record(b)
    assert rec_a == rec_b, (
        f"{short_name}: the Arrival Record differs between two replays of "
        f"the same world — it holds per-object identity, which no observer "
        f"could hold: "
        + next(
            f"zone {z}: {rec_a[z]} != {rec_b[z]}"
            for z in rec_a
            if rec_a[z] != rec_b.get(z)
        )
    )
    assert any(rec_a[z] for z in rec_a), (
        f"{short_name}: no zone holds any arrival at the pause — the "
        f"comparison was vacuous (empty input set)"
    )
    for q in a.obs_logs:
        assert a.obs_logs[q] == b.obs_logs[q], (
            f"{short_name}: P{q}'s observation log differs between replays"
        )
    record(
        short_name,
        "copy_purity",
        seed=seed,
        depth=len(history),
        zones_compared=len(rec_a),
        entries=sum(len(v) for v in rec_a.values()),
    )
