"""The Arrival Record's completeness grid — kernel attribution (issue #256).

property:   every card movement the kernel performs retains (deciding actor,
            card, source Zone Address) as the destination zone's Arrival
            Record, in arrival order; at every decision boundary of every
            corpus game, every zone's record multiset equals its card
            multiset (so no movement path can grow or shrink a zone without
            maintaining the record); the record stores VALUES only — no
            object identity — so observationally-equivalent duplicate copies
            are interchangeable inside it by construction.
domain:     every Zone-content mutation path in the engine crossed with
            every corpus game. The site census is NOT enumerated here by
            hand: the multiset invariant below is the executable form of the
            census — a single missed add/remove path in execute.py,
            mechanics.py, or driver.py breaks equality at the first decision
            boundary after that path runs, for whichever games reach it. The
            corpus glob is the game axis, so a new game joins the domain
            automatically.
registry:   `Zone` (cardlang/runtime/state.py) owns the record and its
            maintenance; the movement sites pass provenance; the corpus is
            docs/games/*.cardlang (the same glob the playout suites walk).
covered:    (a) the invariant walk: per game x manifest-head seed, every
            zone's record-vs-cards multiset equality at every decision
            node, plus actor/src well-formedness (actor is a seat or None;
            src is a Zone Address or None). The walk cannot discriminate
            seat 0 from a DEFAULTED 0 — that property is carried by
            construction (`require_actor` binds the chooser's seat on
            every chosen path, and non-chosen paths record
            `ctx.current_player`, which IS None when unbound) and
            discriminated observably on consumed zones by the provenance
            soundness rows (a wrong or defaulted actor disagrees with
            every observer's derivation — the executed reddening's exact
            shape);
            (b) value-purity: the record contains Card values equal to the
            zone's cards — no id(), no copy index (the copy-swap pins in
            tests/openspiel_ready/ carry the executed reddening for this);
            (c) arrival-order truth for the trick piles the consumers read:
            at every doko/skat/500/schnapsen winner call the pairs the
            record holds are asserted against the plays the trace events
            report (the trace is emitted FROM the same primitives, so this
            cell's independent half is the schnapsen reconstruction in
            tests/test_playout_schnapsen.py, which derives plays from
            observation events alone).
sampled:    one seed per game here (the playout suites and goldens carry
            the multi-seed load); the full openspiel_ready manifest
            exercises the same walk indirectly through its replays.
residual:   `arrival_zones` for zone FAMILIES — no consumer in this change
            reads a family's record; the query surface over recorded facts
            is issue #253's set of decisions, so the family cell records
            there (issue #253), and the bind-time guard refuses the cell
            loudly meanwhile. Cribbage's `peg_origin_of` re-derivation is
            issue #253 e5's named consumer, not this grid's. The
            actor-vs-source-owner divergence has no corpus witness (bridge
            omits the dummy; decisions.md "Delegated play" holds the
            unwired design), so the walk asserts the two-fact record, never
            their coincidence. The wash pin's legal-action half under
            STOCK permutation holds by composition (the swap proof's
            legal-action agreement x the pin's info-state invariance), not
            by direct execution — the replay hook fires after the first
            decider's candidates are computed, so a pause's legal set
            cannot be recomputed post-mutation; the composition is stated
            in the pin's own docstring and its `legal_by_composition`
            coverage field. The face-down-gather mixing kind is covered
            where a manifest pause sits past a hand boundary (the pauses
            are hand-1 depths for most games); the shuffle kind is covered
            at every pause by construction — both recorded per game in the
            wash pin's coverage row, honest rather than claimed. The
            `highest_trump_or_led_suit` call form carries NO
            completed-trick count guard — unlike the retired per-game
            winners, whose `recorded_plays(expected)` count came from each
            game's own trick structure, a generic pile winner has no
            expected count to assert, so a designer hand-rolling a trick
            and calling it mid-trick gets a plausible winner-so-far,
            silently. Deliberately not built this round (no corpus witness
            names the right guard shape — an expected-count argument is a
            surface decision); the work is issue #350, and THIS LEDGER
            ROW owns the record of the gap until it lands.

misuse probes: tests/rejections/arrival_winner_old_arity.{cardlang,expected}
            (the pre-#256 leader-argument spelling — rejected at typecheck
            arity, never accepted-and-ignored) and
            arrival_winner_missing_trump.{cardlang,expected} (the trump-less
            call). The runtime-channel probes are this module's call-form
            and reads-surface cells above.

Born red 2026-08-15 (pre-implementation): Zone had no `arrivals`; the walk
failed on AttributeError for every game, the reads cells on the missing
`arrival_zones` column, the call-form cells on NOT_A_BUILTIN — 39 failed,
0 passed, captured before the first engine edit.

Reddening record (each born-green proof's mutation, EXECUTED 2026-08-15,
plant -> red -> revert):
  - provenance rows (tests/openspiel_ready/harness.py): record_actor shifted
    one seat at execute._movement's single-destination site -> doppelkopf
    fired at step 15: "P0's stream derives [(1, '9♣')] ... but the engine
    record holds [(2, '9♣')]". The proof also walks the line and asserts a
    positive entries_compared count, because its first form passed the plant
    vacuously at an empty-pile pause — the count is the vacuity guard that
    finding bought.
  - wash pin (harness.py): hidden-stock raw order appended to the
    information state (infostate.py) -> schnapsen fired: "P0's information
    state moved under a hidden-stock rotation (rotated ['talon'])" with the
    rotated order in the witness.
  - copy-purity pin (tests/openspiel_ready/test_arrival_purity.py): Arrival
    given an `oid: int` field populated with id(card) in Zone.add -> every
    duplicate-deck game fired ("the Arrival Record differs between two
    replays of the same world — it holds per-object identity"), canasta and
    breakthrough witnesses captured.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card

GAMES_DIR = Path(__file__).parent.parent / "docs" / "games"

# The four consumers' games walk first (they read the record); the rest of
# the corpus rides the same invariant so a missed site anywhere fails.
CONSUMER_GAMES = (
    "doppelkopf.cardlang",
    "skat.cardlang",
    "five-hundred.cardlang",
    "schnapsen.cardlang",
)
ALL_GAMES = tuple(sorted(p.name for p in GAMES_DIR.glob("*.cardlang")))


def _walk_invariant(rs: RuntimeState) -> list[str]:
    """Every zone's Arrival Record against its cards — the executable census.

    Returns human-readable violations rather than asserting, so one walk
    reports every broken zone at once.
    """
    failures: list[str] = []
    zones: list[tuple[str, Any]] = [
        (name, z) for name, z in rs.zones.singles.items()
    ] + [
        (f"{name}[{key}]", z)
        for name, fam in rs.zones.families.items()
        for key, z in fam.items()
    ]
    for label, zone in zones:
        record = zone.arrivals  # AttributeError here IS the born-red state
        rec_cards = sorted(str(a.card) for a in record)
        live_cards = sorted(str(c) for c in zone.cards)
        if rec_cards != live_cards:
            failures.append(
                f"{label}: record {rec_cards} != cards {live_cards}"
            )
        for a in record:
            if not isinstance(a.card, Card):
                failures.append(f"{label}: non-Card in record: {a.card!r}")
            if a.actor is not None and a.actor not in rs.seating.players:
                failures.append(
                    f"{label}: arrival actor {a.actor!r} is not a seat"
                )
            if a.src is not None:
                name, _key = a.src
                if not isinstance(name, str):
                    failures.append(
                        f"{label}: arrival src {a.src!r} is not a Zone Address"
                    )
    return failures


@pytest.mark.parametrize("game_file", CONSUMER_GAMES)
def test_arrival_record_matches_zone_contents_at_every_decision(
    game_file: str,
) -> None:
    """The multiset invariant, checked at every decision node of one seeded
    playout — the walk that makes the site census executable."""
    game = check_source(GAMES_DIR / game_file)
    violations: list[str] = []
    checks = 0

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal checks
        rs = rs_box[0]
        if rs is not None:
            found = _walk_invariant(rs)
            if found:
                violations.extend(f"decision {checks}: {v}" for v in found)
            checks += 1
        pool = list(candidates)
        rng = pick_rng
        return [pool.pop(rng.randrange(len(pool))) for _ in range(k)]

    rs_box: list[RuntimeState | None] = [None]
    pick_rng = random.Random(99)
    play_game(
        game,
        random.Random(11),
        chooser=chooser,
        on_first_decision=lambda rs: rs_box.__setitem__(0, rs),
    )
    assert checks > 0, f"{game_file}: the walk never ran — empty input set"
    assert not violations, (
        f"{game_file}: the Arrival Record diverged from zone contents:\n  "
        + "\n  ".join(violations[:20])
    )


# --- the consumption surface: GameReads.arrivals, bounded by the row -------
#
# The decision-context Owner Guard's structural form: a row may declare
# `arrival_zones` only for zones whose type projects identity to EVERY
# observer (ZONE_PROJECTIONS: owner and others both "identity") — provenance
# of a concealed zone is not observation-derivable, so no primitive may range
# over it, legality context or otherwise. Validation is at BIND time, loud.


def _rs_for(game_file: str, seed: int = 11) -> RuntimeState:
    """A live paused world for one game (the reads-surface probes' fixture)."""
    game = check_source(GAMES_DIR / game_file)
    box: list[RuntimeState] = []

    class _Stop(Exception):
        pass

    def on_first(rs: RuntimeState) -> None:
        box.append(rs)
        raise _Stop

    try:
        play_game(game, random.Random(seed), on_first_decision=on_first)
    except _Stop:
        pass
    assert box, f"{game_file}: no decision reached — empty input set"
    return box[0]


def test_declared_arrival_zone_materializes_actor_card_pairs() -> None:
    """A row declaring `arrival_zones` gets `GameReads.arrivals[name]` as
    deep-frozen (actor, card) pairs in arrival order."""
    from cardlang.runtime import reads

    rs = _rs_for("doppelkopf.cardlang")
    row = reads.PrimitiveReads(
        module="cardlang/runtime/doko.py",
        game_file="doppelkopf.cardlang",
        single_zones=frozenset({"trick_pile"}),
        arrival_zones=frozenset({"trick_pile"}),
    )
    gr = reads.game_reads(rs, row)
    pairs = gr.arrivals["trick_pile"]
    assert isinstance(pairs, tuple)  # deep-frozen, ordered
    # At the first decision the pile is empty; the shape is the contract.
    assert pairs == ()


def test_arrival_zone_of_concealed_type_is_refused_at_bind() -> None:
    """arrival_zones naming a zone whose type is not identity-to-all is the
    decision-context leak; refused loud at bind, naming the projection rule."""
    from cardlang.runtime import reads

    rs = _rs_for("schnapsen.cardlang")
    row = reads.PrimitiveReads(
        module="cardlang/runtime/schnapsen.py",
        game_file="schnapsen.cardlang",
        single_zones=frozenset({"talon"}),
        arrival_zones=frozenset({"talon"}),  # FaceDownPile: count_only to all
    )
    with pytest.raises(reads.PrimitiveReadError, match="identity to every observer"):
        reads.game_reads(rs, row)


def test_arrival_zone_must_be_a_declared_single_zone() -> None:
    """arrival_zones is bounded by the row's own declared single zones — an
    out-of-row name is the ordinary undeclared-read refusal, and a zone
    FAMILY is the recorded residual (issue #253 owns the query surface)."""
    from cardlang.runtime import reads

    rs = _rs_for("doppelkopf.cardlang")
    row = reads.PrimitiveReads(
        module="cardlang/runtime/doko.py",
        game_file="doppelkopf.cardlang",
        arrival_zones=frozenset({"trick_pile"}),  # not in single_zones
    )
    with pytest.raises(reads.PrimitiveReadError, match="single_zones"):
        reads.game_reads(rs, row)


# --- the call form: highest_trump_or_led_suit(zone, trump) -----------------
#
# The schnapsen retirement's replacement is a Builtin (generic: the standard
# trump-game trick winner), guarded in the runtime's channel. Cells: the
# public/concealed axis, the empty pile, the undecided (None-actor) pile,
# and the non-zone argument.


def _call_builtin(rs: RuntimeState, name: str, args: list[Any]) -> Any:
    from cardlang.runtime import builtins
    from cardlang.runtime.state import Ctx

    ctx = Ctx(rs=rs, chooser=lambda p, c, k: c[:k])
    result = builtins.call(name, args, ctx)
    assert result is not builtins.NOT_A_BUILTIN, f"{name} is not a Builtin"
    return result


def test_call_form_refuses_a_concealed_zone() -> None:
    from cardlang.runtime.errors import OwnerGuardError

    rs = _rs_for("schnapsen.cardlang")
    talon = rs.zones.single("talon")
    with pytest.raises(OwnerGuardError, match="identity to every observer"):
        _call_builtin(rs, "highest_trump_or_led_suit", [talon, None])


def test_call_form_refuses_an_empty_pile() -> None:
    from cardlang.runtime.errors import OwnerGuardError

    rs = _rs_for("schnapsen.cardlang")
    pile = rs.zones.single("trick_pile")
    assert not pile.cards  # first decision: nothing led yet
    with pytest.raises(OwnerGuardError, match="empty"):
        _call_builtin(rs, "highest_trump_or_led_suit", [pile, None])


def test_call_form_refuses_a_pile_nobody_played_to() -> None:
    """A public pile whose arrivals carry no deciding actor (an engine deal)
    has no winner to name — loud, never a silent seat."""
    from cardlang.runtime.errors import OwnerGuardError

    rs = _rs_for("schnapsen.cardlang")
    ind = rs.zones.single("trump_indicator")  # Discard fed by a deal
    assert ind.cards, "the trump indicator holds the turned card"
    with pytest.raises(OwnerGuardError, match="deciding actor"):
        _call_builtin(rs, "highest_trump_or_led_suit", [ind, None])


def test_call_form_refuses_a_non_zone_argument() -> None:
    from cardlang.runtime.errors import OwnerGuardError

    rs = _rs_for("schnapsen.cardlang")
    with pytest.raises(OwnerGuardError, match="not a zone"):
        _call_builtin(rs, "highest_trump_or_led_suit", [Card("A", "spades"), None])


def test_call_form_names_the_recorded_winner() -> None:
    """The green cell: a public pile with two recorded plays yields the same
    winner the retired schnapsen primitive computed — pairs in arrival order,
    led suit from the first arrival, the game's rank order."""
    rs = _rs_for("schnapsen.cardlang")
    pile = rs.zones.single("trick_pile")
    h0 = rs.zones.instance("hand", 0)
    h1 = rs.zones.instance("hand", 1)
    c0, c1 = h0.cards[0], h1.cards[0]
    h0.remove(c0)
    pile.add(c0, actor=0, src=("hand", 0))
    h1.remove(c1)
    pile.add(c1, actor=1, src=("hand", 1))
    winner = _call_builtin(rs, "highest_trump_or_led_suit", [pile, None])
    rank = rs.rank_index
    if c1.suit == c0.suit:
        expect = 1 if rank[c1.rank] > rank[c0.rank] else 0
    else:
        expect = 0  # off-suit answer never wins without trump
    assert winner == expect


@pytest.mark.parametrize("game_file", [g for g in ALL_GAMES if g not in CONSUMER_GAMES])
def test_arrival_record_invariant_holds_corpus_wide(game_file: str) -> None:
    """The same walk over the rest of the corpus: the invariant is
    engine-global, so every game's movement paths are in the domain whether
    or not anything consumes the record there. Bounded at 300 decisions per
    game (a full random tichu playout alone runs past 20000), with the
    invariant checked at every one — the consumer games above carry the
    full-game walks."""

    class _Stop(Exception):
        pass

    game = check_source(GAMES_DIR / game_file)
    violations: list[str] = []
    checks = 0
    rs_box: list[RuntimeState | None] = [None]
    pick_rng = random.Random(99)

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        nonlocal checks
        rs = rs_box[0]
        if rs is not None:
            found = _walk_invariant(rs)
            if found:
                violations.extend(f"decision {checks}: {v}" for v in found)
            checks += 1
            if checks >= 300:
                raise _Stop
        pool = list(candidates)
        return [pool.pop(pick_rng.randrange(len(pool))) for _ in range(k)]

    try:
        play_game(
            game,
            random.Random(7),
            chooser=chooser,
            on_first_decision=lambda rs: rs_box.__setitem__(0, rs),
        )
    except _Stop:
        pass
    assert checks > 0, f"{game_file}: the walk never ran — empty input set"
    assert not violations, (
        f"{game_file}: the Arrival Record diverged from zone contents:\n  "
        + "\n  ".join(violations[:20])
    )
