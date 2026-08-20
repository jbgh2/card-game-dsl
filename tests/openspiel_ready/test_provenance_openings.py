"""Every `provenance_opening` is a driving judgment with a CHECKED claim.

`GameSpec.provenance_opening` names moves the provenance walk plays before it
goes greedy, for the game whose greedy line provably never reaches a zone whose
[[arrival-record]] a consumer reads. French Tarot is the case that created the
field: `pass` sorts below every bid, so `legal[0]` throws all 36 hands in and no
card is ever played, and the migration that gave `trick_pile` an AST-visible
consumer (issue #250 PR 5) turned that from a vacuous certificate into a RED
one. The field converts it into a real certificate.

A driving judgment can be wrong in ways the proof it serves cannot see, which
is what this module is for. The proof asks only "did the line reach the zone";
it cannot ask whether the opening was NEEDED, whether it names moves this game
has, or whether it is doing anything at all. Each of those is a cell below.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:  every registered game's `provenance_opening` is legal where it is
           played, is needed, and is declared only where a provenance domain
           exists to need it -- and every one of those claims FAILS LOUDLY.
domain:    `harness.REGISTERED_GAMES` -- the adapter's own registry, so a newly
           registered game is in-domain the day it registers -- crossed with
           {declares an opening, declares none} (total by construction: the
           field is a tuple, empty or not) and with the two properties a
           declaration can get wrong: it must ENCODE AND BE LEGAL at each of
           its own turns, and it must be NEEDED (`harness.opening_status`'s
           2x2 over needed x declared). The provenance-domain gate is the
           third arm: `GameSpec.all_provenance_zones` empty means the field is
           never consulted at all, so an opening there is dead.
registry:  `harness.REGISTERED_GAMES` for the game axis, resolved to each
           module's real `TestReadiness.spec` the way `test_coverage.py`
           already resolves it (a default-constructed spec would read every
           field as its default and check nothing);
           `GameSpec.all_provenance_zones` for the domain gate, itself derived
           from `ARRIVAL_RECORD_CALLS` + `PRIMITIVE_READS`;
           `cardlang.openspiel.encoding.ActionSpace` for what a move name may
           be, consulted through `encode` rather than re-listed here.
covered:   the grid IS the coverage -- one cell per registered game for the
           opening's legality, one per game for the needed/declared square,
           one per game for the domain gate; plus `harness.opening_status`'s
           own 2x2, and the three refusal probes over a synthetic spec with
           their control. Every arm of `harness.opening_actions` has a probe:
           a name the space cannot encode, a move illegal at its turn, and a
           game that ends mid-opening.
sampled:   the needed/declared square is measured at ONE seed (the manifest
           head). Whether an opening is needed is a property of the greedy
           line's SHAPE -- which action id sorts first at each turn -- and the
           deal moves neither the action ids nor the sort. Measured rather
           than argued: over the whole manifest French Tarot's first decider
           is P2 with the same five legal ids and the same `legal[0]=78` on
           every seed (2026-08-19). The LEGALITY arm is not sampled at all --
           the proof calls `opening_actions` once per manifest seed, so a seat
           or a guard that moved with the deal reddens there.
residual:  (a) An opening of length >= 2, and the `provenance_depth` offset it
           crosses with, are implemented and only degenerately executed: no
           spec declares either shape beside the other, and `replay.run` is
           uncached, so each extra opening move is a full re-simulation per
           seed. The probes below drive both multi-move arms on a synthetic
           spec, which is where the cost is one game rather than the manifest.
           R4, this ledger owns the record.
           (b) A LEGAL BUT WRONG opening -- a different move that also reaches
           the zone -- passes every cell here, because every claim this module
           can make about it is true. Guarded by disclosure instead: the
           coverage record carries the MOVES (`harness.render_opening`), so
           which line was certified is citable rather than inferred from a
           count. R4, this ledger owns the record.
           (c) The opening-prefixed line is walked by the DSL replay only; the
           adapter-agreement proof walks the plain greedy line, so for a game
           whose greedy line never plays a card the DSL/pyspiel agreement is
           proven over the all-pass line alone. That is the adapter proof's
           own scope rather than this field's, and it is unchanged by the
           field's existence. R4, this ledger owns the record.
           (d) Parameter shapes the field's `tuple[str, str | None]` type
           cannot express (a Card-, Player- or position-valued move parameter,
           or an arity >= 2 move) are refused by strict mypy at the spec site
           rather than by a designed diagnostic. Deliberate: the field drives
           an OPENING, and the moves that open a game are the nullary and
           string-parameterized ones. A recorded constraint, not work -- this
           ledger owns it, per CLAUDE.md's carve-out.
           (e) The provenance record has two shapes -- a vacuous cell carries
           `{seed, zones, vacuous}`, a real one adds `{opening, depth, nodes,
           entries_compared}` -- and `test_partition_record_modes.py` pins the
           record's executor-invariance, not its key sets, so a key dropped
           from one branch reddens nothing. Pre-dates this field and is a
           property of `partition.record`'s free-form `**detail`; R4, this
           ledger owns the record.

Born red: the classifier's square was authored against a stub returning
`"covered"` for every cell and run before `opening_status` existed --
"AssertionError: assert 'covered' == 'stale'", the cell whose collapse is the
whole failure class (executed 2026-08-19). The per-game cells' capacity to
fail is the commanded mutation recorded on each.
"""

from __future__ import annotations

import ast
import importlib
import inspect
from pathlib import Path
from typing import Any

import pytest

from .harness import (
    ONE_SEED,
    REGISTERED_GAMES,
    GameSpec,
    opening_actions,
    opening_status,
    provenance_walk,
    render_opening,
)


def _spec(short_name: str) -> GameSpec:
    """The game's REAL spec, importlib-resolved. A default-constructed
    `GameSpec(short, filename)` reads every judgment field as its default and
    would check nothing -- `test_coverage.py` makes the same move for the same
    reason."""
    mod = importlib.import_module(
        ".test_" + short_name.removeprefix("cardlang_"), package=__package__
    )
    spec: GameSpec = mod.TestReadiness.spec
    return spec


_ALL: list[GameSpec] = [_spec(short) for short, _ in REGISTERED_GAMES]


def _params(specs: list[GameSpec]) -> list[Any]:
    return [
        pytest.param(s, id=s.short_name.removeprefix("cardlang_")) for s in specs
    ]


SPECS: list[Any] = _params(_ALL)
# The two arms of the domain gate, DERIVED rather than listed: a game whose
# `all_provenance_zones` is empty never reaches `opening_actions` at all, so the
# needed/declared square is meaningless for it and the gate cell owns it
# instead. Splitting the parametrization rather than skipping inside one keeps
# every cell a cell that runs.
WITH_DOMAIN: list[Any] = _params([s for s in _ALL if s.all_provenance_zones])
WITHOUT_DOMAIN: list[Any] = _params([s for s in _ALL if not s.all_provenance_zones])
SEED = ONE_SEED[0]


@pytest.mark.parametrize("spec", SPECS)
def test_a_declared_opening_is_legal_at_every_one_of_its_turns(spec: GameSpec) -> None:
    """The empty arm asserts emptiness; the declared arm drives the opening and
    lets `opening_actions`' three refusals fire.

    red under (commanded, executed 2026-08-19 and reverted): french-tarot's
    `provenance_opening` set to a second `bid_petite`, illegal once a bid
    stands -- "cardlang_french_tarot: opening move ('bid_petite', None) is not
    legal at P1's turn 1"."""
    actions = opening_actions(spec, SEED)
    assert len(actions) == len(spec.provenance_opening), (
        f"{spec.short_name}: the opening encoded {len(actions)} actions for "
        f"{len(spec.provenance_opening)} declared moves"
    )


@pytest.mark.parametrize("spec", WITH_DOMAIN)
def test_an_opening_is_declared_exactly_where_the_greedy_line_needs_one(
    spec: GameSpec,
) -> None:
    """The needed/declared square, per game. `needed` is MEASURED: the plain
    greedy line is walked with no opening and its compared-entry count read.

    The `stale` direction is the one nothing else in this package covers -- the
    proof stays green over an opening that stopped being necessary, because a
    line that reaches the zone reaches it either way.

    red under (commanded, executed 2026-08-19 and reverted): french-tarot's
    `provenance_opening` emptied -- this cell reads `missing` and fails naming
    the game, alongside the proof's own vacuity guard."""
    zones = spec.all_provenance_zones
    without = provenance_walk(spec, SEED, zones, [])
    status = opening_status(
        needed=without.entries_compared == 0, declared=bool(spec.provenance_opening)
    )
    assert status == ("covered" if spec.provenance_opening else "none"), {
        "stale": (
            f"{spec.short_name} declares `provenance_opening="
            f"{render_opening(spec)}`, but the plain greedy line already "
            f"compares {without.entries_compared} record entries in "
            f"{without.nodes} nodes — the opening has outlived its reason; "
            f"drop it"
        ),
        "missing": (
            f"{spec.short_name}: the plain greedy line reaches "
            f"{zones} never within {without.nodes} nodes, so the provenance "
            f"certificate is vacuous — declare a `provenance_opening` that "
            f"drives the game to a state where the zone fills"
        ),
    }[status]


@pytest.mark.parametrize("spec", WITHOUT_DOMAIN)
def test_an_opening_is_declared_only_where_something_would_consult_it(
    spec: GameSpec,
) -> None:
    """The domain gate. With no provenance domain the proof returns before
    `opening_actions` is ever called, so a declared opening is never encoded,
    never legality-checked, and never recorded — a dead knob, and the one
    state in which every other cell here is silent.

    Since the domain is AST-derived, a DSL edit that drops the last
    Arrival-Record consumer kills the field without touching it, which is
    exactly how this cell goes from impossible to live.

    red under (commanded, executed 2026-08-19 and reverted): the same
    `("bid_petite", None)` opening copied onto `test_bridge.py`'s spec, a game
    with no provenance consumer."""
    assert not spec.provenance_opening, (
        f"{spec.short_name} declares `provenance_opening="
        f"{render_opening(spec)}` but derives no provenance domain, so the "
        f"proof returns before the opening is read — nothing encodes it, "
        f"nothing checks it is legal, and nothing records it"
    )


def test_opening_status_covers_the_needed_declared_square() -> None:
    """All four cells of the 2x2, named. A classifier that collapsed `stale`
    into `covered` would let an opening outlive its reason silently — the
    failure class this module exists to remove, and the one the sibling
    conformance pin already refuses for its own declarations.

    Born red against a stub returning `"covered"` for every cell:
    "AssertionError: assert 'covered' == 'stale'"."""
    assert opening_status(needed=True, declared=True) == "covered"
    assert opening_status(needed=False, declared=True) == "stale"
    assert opening_status(needed=True, declared=False) == "missing"
    assert opening_status(needed=False, declared=False) == "none"


def test_only_the_provenance_walk_is_given_an_opening() -> None:
    """The field's scoping, derived from the code rather than asserted in its
    comment. The swap, facts, rng and wash proofs pause at `spec.depth`, whose
    per-game value is reasoned about the greedy line as it stands (French
    Tarot's depth-3 sits inside the still-open first auction, before the
    thrown-in hand's reshuffle), so an opening reaching those call sites would
    silently move every one of those pauses.

    Read off `_advance`'s call sites in the parsed harness: exactly one passes
    a fourth argument. Prose said this; nothing checked it.

    red under (executed 2026-08-19, reverted): pass `opening_actions(spec,
    seed)` to the swap proof's `_advance` as well — "2 of the `_advance` call
    sites pass an opening"."""
    src = Path(inspect.getsourcefile(provenance_walk) or "").read_text()
    calls = [
        node
        for node in ast.walk(ast.parse(src))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "_advance"
    ]
    assert calls, "no `_advance` call sites found — the scrape has drifted"
    with_opening = [c for c in calls if len(c.args) + len(c.keywords) > 3]
    assert len(with_opening) == 1, (
        f"{len(with_opening)} of the {len(calls)} `_advance` call sites pass an "
        f"opening; only the provenance walk may, or a declared opening moves "
        f"the swap/facts/rng/wash pauses too"
    )


# --- misuse probes ---------------------------------------------------------
#
# `opening_actions`' three refusals fire on no registered spec — the corpus's
# one opening is well-formed — so each gets a synthetic spec that trips exactly
# it. A guard nothing executes is not a guard (`harness.pin_failures`' own
# rule, applied to this field's guards).


def _probe(*moves: tuple[str, str | None]) -> list[int]:
    return opening_actions(
        GameSpec(
            "cardlang_probe", "french-tarot.cardlang", provenance_opening=moves
        ),
        SEED,
    )


def test_a_well_formed_opening_has_no_complaints() -> None:
    """The control: without it, an `opening_actions` that refused everything
    would pass all three probes below. Two moves, so the multi-move arm the
    corpus does not reach is executed here (ledger residual (a))."""
    assert len(_probe(("bid_petite", None), ("pass", None))) == 2


def test_an_opening_naming_a_move_the_space_cannot_encode_is_refused() -> None:
    """The renamed / mistyped move type, through the action space's own
    channel — but carrying this package's voice, which the bare `KeyError:
    ('bid_nonesuch', None)` did not."""
    with pytest.raises(KeyError) as ei:
        _probe(("bid_nonesuch", None))
    assert "does not encode" in str(ei.value) and "cardlang_probe" in str(ei.value)


def test_an_opening_move_illegal_at_its_turn_is_refused() -> None:
    """`bid_petite` twice: legal at the opener's turn, guarded off at the
    next seat's once a bid stands."""
    with pytest.raises(AssertionError) as ei:
        _probe(("bid_petite", None), ("bid_petite", None))
    assert "is not legal at P" in str(ei.value)


def test_an_opening_that_outlives_the_game_is_refused() -> None:
    """The third arm, which had no executed record: an opening longer than the
    line it drives. Four passes throw the hand in and the auction's ring
    closes, so a fifth move has no decision node to be played at.

    French Tarot re-deals rather than ending, so this probe uses the shortest
    line the corpus has: Kuhn Poker, where check-check is a showdown and the
    whole game is two decisions."""
    with pytest.raises(AssertionError) as ei:
        opening_actions(
            GameSpec(
                "cardlang_probe",
                "kuhn-poker.cardlang",
                provenance_opening=(("check", None),) * 3,
            ),
            SEED,
        )
    assert "the game ended after 2 of the 3 opening moves" in str(ei.value)
