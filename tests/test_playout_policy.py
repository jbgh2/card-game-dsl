"""The [[playout-policy]]'s dispatch is total over the Candidate shapes the
[[chooser]] seam can hand it.

A Playout Policy exists to make playouts reach branches a uniform draw leaves
unexercised. The failure mode that would make it worthless is quiet: a policy
that ranks the one Candidate shape its author had in mind and silently falls
through to a uniform draw for every other shape looks identical, from the
outside, to one that considered them — same green suite, same plausible
playouts, no diagnostic anywhere. That is accepted-but-ignored wearing a
policy's clothes. So the policy carries a registry naming every Candidate kind
it classifies and whether that kind is *ranked* or *delegated*, a kind outside
the registry is refused rather than delegated, and this grid is what makes the
registry a claim instead of a comment.

property:   for every Candidate kind the seam can carry, the Playout Policy
            either applies a declared ranking or delegates to the injected
            uniform draw, and which one it does is what
            `policy.CANDIDATE_KINDS` / `policy.RANKED_KINDS` say it is — never
            an unrecorded fallthrough. A shape in neither is refused loudly at
            the seam. Ranking applies only at `n == 1`: a multi-card draw is a
            different decision (a pass, a discard) with no state-free ranking,
            so it delegates whatever its element kind.
domain:     Candidate kind x arity. Kinds: `policy.CANDIDATE_KINDS`, the arms
            of `policy.candidate_kind`. Arity: the two arms `n == 1` and
            `n > 1` — the split the ranking rule is stated over.
registry:   kinds -- `cardlang.runtime.policy.CANDIDATE_KINDS`; ranked subset
            -- `policy.RANKED_KINDS`. Pinned against the seam's live traffic by
            `test_every_candidate_shape_the_corpus_offers_classifies`, which
            derives the shapes by EXECUTING every `docs/games/*.cardlang`
            rather than reading them, and against the runtime's own decision
            value domain by `test_every_ranked_kind_is_a_declared_decision_value`
            (`cardlang.runtime.observe.render`).
does not prove:  that `CANDIDATE_KINDS` covers every shape the seam could ever
            carry -- only every shape the corpus reaches today plus those
            `observe.render` declares. A seventh call site introducing a new
            element shape is caught by the refusal at play time
            (`test_an_unregistered_candidate_shape_is_refused`), not by this
            grid; there is no static registry of the seam's call sites to
            derive from (`docs/glossary/chooser.md` records their absence as
            finding F-20).

            Nor does it prove the policy is *good*. Exactly one kind is ranked
            (`integer`), and the corpus games that reach `(integer, n == 1)`
            are Oh Hell and Spades. Every other kind delegates, so on a game
            that declares no integer the Playout Policy and the uniform chooser
            are the same function. The reach this buys is measured, per game,
            in `tests/test_playout_spades.py` -- not here.

            The `n <= 0` arm is not a cell. It is reachable (a simultaneous
            pass never checks its count's sign) and it is a defect upstream of
            this seam, filed as issue #416; the policy delegates it to
            `random_chooser` rather than shadowing a guard that belongs to the
            movement executor.
"""

from __future__ import annotations

import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.pipeline import check_source
from cardlang.runtime import observe
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.policy import (
    CANDIDATE_KINDS,
    RANKED_KINDS,
    PlayoutPolicy,
    candidate_kind,
)
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, CardSet
from cardlang.stdlib.zones import ZONE_PROJECTIONS

GAMES = Path(__file__).parent.parent / "docs" / "games"
SPADES = GAMES / "spades.cardlang"

ARITIES = ("n == 1", "n > 1")

# One live value per registered kind. Authored, not derived — the grid needs a
# concrete Candidate to hand the policy, and the reconciliation below is what
# keeps this table honest when the registry grows.
REPRESENTATIVE: dict[str, Any] = {
    "integer": 3,
    "card": Card("A", "spades"),
    "card_group": CardSet((Card("A", "spades"), Card("K", "spades"))),
    "move": ("pass", None),
    "token": "pass",
}

# The authored expected column: kind x arity -> what the policy must do.
# Written before `policy.py` existed. `integer` at a single draw is the one
# ranked cell; everything else delegates.
EXPECTED: dict[tuple[str, str], str] = {
    ("integer", "n == 1"): "ranked",
    ("integer", "n > 1"): "delegated",
    ("card", "n == 1"): "delegated",
    ("card", "n > 1"): "delegated",
    ("card_group", "n == 1"): "delegated",
    ("card_group", "n > 1"): "delegated",
    ("move", "n == 1"): "delegated",
    ("move", "n > 1"): "delegated",
    ("token", "n == 1"): "delegated",
    ("token", "n > 1"): "delegated",
}


class CountingRandom(random.Random):
    """A `random.Random` that counts the draws taken through it.

    This is the grid's discriminator: a ranked decision consults the
    Candidates and takes NO draw, a delegated one takes exactly one. Comparing
    returned values instead would be probabilistic — a ranked pick and a
    uniform pick coincide whenever the draw happens to land on the ranked
    value.
    """

    draws: int = 0

    def sample(self, population: Any, k: int, *, counts: Any = None) -> list[Any]:
        self.draws += 1
        return super().sample(population, k, counts=counts)


def _live_state() -> RuntimeState:
    """A real `RuntimeState`, paused at Spades' first decision (a bid, so every
    hand is dealt). The grid drives the policy with synthetic Candidate lists
    against a genuine world rather than a stub, so the ranked cell exercises
    the same zone reads a playout does."""
    box: dict[str, RuntimeState] = {}

    def grab(rs: RuntimeState) -> None:
        box["rs"] = rs
        raise _Paused()

    try:
        play_game(check_source(SPADES), random.Random(0), on_first_decision=grab)
    except _Paused:
        pass
    return box["rs"]


class _Paused(Exception):
    """Unwinds `play_game` once the live state has been captured."""


@pytest.fixture(scope="module")
def live() -> RuntimeState:
    return _live_state()


def _attached(rs: RuntimeState) -> tuple[PlayoutPolicy, CountingRandom]:
    rng = CountingRandom(0)
    policy = PlayoutPolicy(rng)
    policy.attach(rs)
    return policy, rng


# --- the grid -------------------------------------------------------------


@pytest.mark.parametrize(
    ("kind", "arity"),
    [(k, a) for k in sorted(CANDIDATE_KINDS) for a in ARITIES],
)
def test_dispatch_grid(kind: str, arity: str, live: RuntimeState) -> None:
    """Every registered kind, at both arities, does what EXPECTED says."""
    expected = EXPECTED[(kind, arity)]
    value = REPRESENTATIVE[kind]
    n = 1 if arity == "n == 1" else 2
    # Distinct positions, never a deduped set: decks with `copies` put equal
    # Card values in one zone, so a multi-pick draws n positions, not n values.
    candidates = [value] * 4 if kind != "integer" else [0, 1, 2, 3, 4, 5]
    policy, rng = _attached(live)

    picked = policy(0, list(candidates), n)

    assert len(picked) == n, f"{kind}/{arity}: returned {len(picked)} for n={n}"
    assert all(p in candidates for p in picked), f"{kind}/{arity}: invented a candidate"
    if expected == "ranked":
        assert rng.draws == 0, f"{kind}/{arity}: ranked cell took a uniform draw"
    else:
        assert rng.draws == 1, (
            f"{kind}/{arity}: expected one delegated draw, took {rng.draws} — "
            "an unrecorded ranking, or a second RNG source"
        )


def test_the_grid_covers_the_registry_exactly() -> None:
    """The expected column is reconciled against the registry, so a kind added
    to `CANDIDATE_KINDS` without a decided cell reddens here rather than
    quietly running under whatever the dispatch happens to do."""
    derived = {(k, a) for k in CANDIDATE_KINDS for a in ARITIES}
    assert set(EXPECTED) == derived
    assert set(REPRESENTATIVE) == set(CANDIDATE_KINDS)


def test_the_ranked_subset_is_the_registry_not_a_second_list() -> None:
    """`RANKED_KINDS` is a subset of `CANDIDATE_KINDS`, and the grid's ranked
    cells are exactly its members at `n == 1`."""
    assert RANKED_KINDS <= set(CANDIDATE_KINDS)
    ranked_cells = {k for (k, a), v in EXPECTED.items() if v == "ranked"}
    assert ranked_cells == RANKED_KINDS
    assert all(
        EXPECTED[(k, "n > 1")] == "delegated" for k in RANKED_KINDS
    ), "ranking is declared only at n == 1"


# --- the registry's two derivations ---------------------------------------


def test_every_candidate_shape_the_corpus_offers_classifies() -> None:
    """Derived by EXECUTION, not by reading: play every corpus game under a
    chooser that classifies each Candidate it is offered. Every shape the seam
    actually carries must land in a registered kind.

    Capped per game — this walks the whole corpus, and the property is a
    soundness one (every observed shape classifies), which a prefix preserves.
    """
    seen: set[str] = set()
    for path in sorted(GAMES.glob("*.cardlang")):
        rng = random.Random(0)
        calls = [0]

        def watch(p: int, cands: list[Any], n: int) -> list[Any]:
            calls[0] += 1
            if calls[0] > 400:
                raise _Paused()
            for c in cands:
                seen.add(candidate_kind(c))  # raises if unregistered
            return rng.sample(cands, n)

        try:
            play_game(check_source(path), rng, chooser=watch)
        except (_Paused, OwnerGuardError):
            pass
    # Non-vacuity: an empty census would pass the loop above while proving
    # nothing (tests/empty_axis.py's defect class).
    assert seen, "the corpus census observed no candidates at all"
    assert seen <= set(CANDIDATE_KINDS)
    assert "card" in seen and "move" in seen, f"census too thin: {sorted(seen)}"


def test_every_ranked_kind_is_a_declared_decision_value() -> None:
    """Reconciliation against the runtime's own closed statement of what a
    decision value may be. `observe.render` raises on a shape it does not
    declare, so a kind this policy ranks that `render` does not know would be
    a Candidate the observation layer cannot put in an information state."""
    for kind in CANDIDATE_KINDS:
        observe.render(REPRESENTATIVE[kind])  # raises AssertionError if undeclared


# --- misuse probes --------------------------------------------------------


def test_calling_before_attach_is_refused_not_silently_uniform() -> None:
    """The sharpest misuse: `PlayoutPolicy` needs the live world for its
    ranking, and a caller who wires `chooser=` but forgets
    `on_first_decision=` would otherwise get a policy that silently degrades
    to a uniform draw — plausible playouts, green suite, no reach. It refuses
    instead."""
    rng = CountingRandom(0)
    policy = PlayoutPolicy(rng)
    with pytest.raises(OwnerGuardError, match="attach"):
        policy(0, [1, 2, 3], 1)
    assert rng.draws == 0, "refused, but took a draw on the way out"


def test_an_unregistered_candidate_shape_is_refused(live: RuntimeState) -> None:
    """A shape outside the registry is refused at the seam rather than
    delegated. Delegating it is the fallthrough this whole module exists to
    forbid: it would read, from every angle, as a considered decision."""
    policy, rng = _attached(live)
    with pytest.raises(OwnerGuardError, match="no declared Playout Policy"):
        policy(0, [object()], 1)
    assert rng.draws == 0


def test_a_boolean_is_refused_not_read_as_an_integer(live: RuntimeState) -> None:
    """`bool` is an `int` subclass, so a classifier that tests `isinstance(c,
    int)` first would rank `True` as the integer 1 — a silent misread.

    This shape is also where the runtime's two existing statements of the
    decision-value domain disagree: `observe.render` accepts a bool (its
    `int | str` arm, named in its comment) while `ActionSpace.encode`
    explicitly rejects one ("boolean is not an action value"). No call site
    produces one today. The policy sides with the encoder, because a Candidate
    that cannot be encoded has no OpenSpiel action id.
    """
    policy, rng = _attached(live)
    with pytest.raises(OwnerGuardError, match="no declared Playout Policy"):
        policy(0, [True, False], 1)
    assert rng.draws == 0


def test_a_mixed_candidate_list_delegates_whole(live: RuntimeState) -> None:
    """Heterogeneous lists are real, not hypothetical: a climbing round offers
    combination `Play`s and the bare string `"pass"` in one list. Ranking the
    ranked-kind members and drawing among the rest would be a ranking nobody
    declared, so a list whose members are not all one ranked kind delegates
    entire."""
    policy, rng = _attached(live)
    mixed = [CardSet((Card("A", "spades"),)), "pass"]
    picked = policy(0, list(mixed), 1)
    assert rng.draws == 1
    assert picked[0] in mixed


def test_a_mixed_list_containing_the_ranked_kind_still_delegates(
    live: RuntimeState,
) -> None:
    """The same rule where it bites: an `integer` beside another kind must not
    be ranked as though the list were integers."""
    policy, rng = _attached(live)
    mixed: list[Any] = [1, Card("A", "spades")]
    picked = policy(0, list(mixed), 1)
    assert rng.draws == 1
    assert picked[0] in mixed


def test_the_policy_reads_only_the_deciding_seats_own_zones(
    live: RuntimeState,
) -> None:
    """The property that makes these playouts admissible as evidence at all.

    A policy that consulted another seat's hand would still produce playouts,
    and every other gate in this repo would stay green on them — the reach
    would be real and the game would not be. So the read is traced, not
    reasoned about: every `(family, seat)` the ranking touches must be the
    deciding seat's own, in a family whose projection hides it from everyone
    else.

    red under: in `policy._own_private_cards`, extend the qualifying families
    with a neighbour's key -- `out.extend(family[(player + 1) % 4].cards)` --
    and this reddens on the recorded pair while the dispatch grid and the
    Spades reach test both stay green.
    """
    reads: list[tuple[str, Any]] = []

    class Recording(dict):  # type: ignore[type-arg]
        def __init__(self, name: str, inner: dict[Any, Any]) -> None:
            super().__init__(inner)
            self._name = name

        def __getitem__(self, key: Any) -> Any:
            reads.append((self._name, key))
            return super().__getitem__(key)

    original = live.zones.families
    live.zones.families = {
        name: Recording(name, inner) for name, inner in original.items()
    }
    try:
        policy, _ = _attached(live)
        for seat in range(4):
            policy(seat, [0, 1, 2, 3], 1)
    finally:
        live.zones.families = original

    assert reads, "the ranking read no zone at all — the trace proves nothing"
    private = {
        name
        for name, ztype in live.zones.zone_type.items()
        if (v := ZONE_PROJECTIONS.get(ztype)) is not None
        and v.owner == "identity"
        and v.others != "identity"
    }
    seats = {seat for _, seat in reads}
    assert {name for name, _ in reads} <= private, f"read a shared zone: {reads}"
    # Each of the four calls may read only its own seat, so across the four
    # calls the recorded seats are exactly the four deciders — never a fifth,
    # and never one decider reading another.
    assert seats == {0, 1, 2, 3}, f"seats read: {sorted(seats)}"
    for seat in range(4):
        policy2, _ = _attached(live)
        reads.clear()
        live.zones.families = {
            name: Recording(name, inner) for name, inner in original.items()
        }
        try:
            policy2(seat, [0, 1, 2, 3], 1)
        finally:
            live.zones.families = original
        assert {s for _, s in reads} <= {seat}, (
            f"deciding seat {seat} read seats {sorted({s for _, s in reads})}"
        )


def test_the_same_seed_replays_identically() -> None:
    """One RNG source, so a seeded playout is reproducible.

    red under: in `PlayoutPolicy._rank_integer`, draw the target from a second,
    unseeded stream -- `target = _likely_winners(rs, player) +
    random.Random().randint(0, 1)` -- and the two runs diverge.

    Breaking a TIE from a fresh stream does not redden it, which is why the
    mutation is stated as the target and not the tie: the candidates of a
    `choose integer` are a contiguous range, so the distance to an integer
    target has a unique minimum and the tie set is a singleton. A pin's
    reddening edit has to plant the fault somewhere the code actually reaches.
    """
    game = check_source(SPADES)

    def outcome(seed: int) -> Any:
        rng = random.Random(seed)
        policy = PlayoutPolicy(rng)
        try:
            r = play_game(game, rng, chooser=policy, on_first_decision=policy.attach)
        except OwnerGuardError as exc:
            # The declared-max_length arm is an outcome like any other, and
            # pinning it too keeps this from depending on a hand-picked seed
            # that happens to terminate.
            return ("guard", str(exc))
        return ("result", r.scores, r.winner, r.hands_played)

    for seed in (0, 7, 11):
        assert outcome(seed) == outcome(seed), f"seed {seed} did not replay"


def test_duplicate_candidates_draw_by_position(live: RuntimeState) -> None:
    """Decks declared with `copies` put genuinely equal `Card` values in one
    zone, so a multi-pick must draw n POSITIONS, not n distinct values. A
    policy that routed candidates through a set would return one card here."""
    policy, _ = _attached(live)
    dupes = [Card("A", "spades")] * 3
    assert len(policy(0, list(dupes), 3)) == 3


def test_the_returned_object_is_the_one_handed_in(live: RuntimeState) -> None:
    """Identity, not merely equality. A climbing `Play` carries an
    `ends_trick` marker the engine duck-types off the returned object, so a
    structurally-equal replacement would silently lose it."""
    policy, _ = _attached(live)
    cards = [Card("A", "spades"), Card("K", "hearts"), Card("2", "clubs")]
    picked = policy(0, list(cards), 1)
    assert any(picked[0] is c for c in cards)
