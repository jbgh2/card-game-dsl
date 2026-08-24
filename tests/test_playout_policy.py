"""The [[playout-policy]]'s dispatch is total over the Candidate shapes the
[[chooser]] seam can hand it.

A Playout Policy exists to make playouts reach branches a uniform draw leaves
unexercised. The failure mode that would make it worthless is quiet: a policy
that ranks the one Candidate shape its author had in mind and silently falls
through to a uniform draw for every other shape looks identical, from the
outside, to one that considered them — same green suite, same plausible
playouts, no diagnostic anywhere. That is accepted-but-ignored wearing a
policy's clothes. So the policy carries a registry naming every Candidate kind
it classifies and whether that kind is ranked or delegated, a kind outside the
registry is refused rather than delegated, and this grid is what makes the
registry a claim instead of a comment.

property:   for every Candidate kind the seam can carry, the Playout Policy
            either applies a declared ranking or delegates to the injected
            uniform draw, and which one it does is what
            `playout_policy.CANDIDATE_RANKERS` says it is — never an
            unrecorded fallthrough. A shape in neither is refused loudly at
            the seam. Ranking applies only at `n == 1`: a multi-card draw is a
            different decision (a pass, a discard) with no state-free ranking,
            so it delegates whatever its element kind. The ranking reads only
            zones the deciding seat owns, at the key `zone_observer_key` says
            it owns.
domain:     Candidate kind x arity. Kinds: `playout_policy.CANDIDATE_RANKERS`,
            whose keys are pinned equal to the arms of
            `playout_policy.candidate_kind` by
            `test_every_dispatch_arm_returns_a_registered_kind` — so the table
            cannot drift from the dispatch it describes. Arity: the two arms
            `n == 1` and `n > 1`, the split the ranking rule is stated over.
registry:   kinds and their dispositions -- `playout_policy.CANDIDATE_RANKERS`
            (a ranker, or None for an explicit delegation). Reconciled against
            the seam's live traffic by
            `test_the_corpus_reaches_every_registered_kind`, which derives the
            shapes by EXECUTING every `docs/games/*.cardlang` rather than
            reading them; against the runtime's own decision-value domain by
            `test_every_registered_kind_is_a_declared_decision_value`
            (`cardlang.runtime.observe.render`); and against the OpenSpiel
            encoder by `test_the_bool_refusal_matches_the_encoder`.
            Zone ownership: `cardlang.domains.zone_observer_key`.
does not prove:  that the kind table covers every shape the seam could ever
            carry -- only every shape the corpus reaches today, plus those
            `observe.render` declares. A new call site introducing a new
            element shape is caught by the refusal at play time
            (`test_an_unregistered_candidate_shape_is_refused`), not by this
            grid: the seam's call sites have no static registry to derive
            from, which `docs/glossary/chooser.md` records as finding F-20.

            Nor does it prove the policy is *good*. The ranked subset is a
            proper subset of the kinds, so on a game whose decisions are all
            delegated kinds the Playout Policy and the uniform chooser are the
            same function. The reach it buys is measured, per game, in
            `tests/test_playout_spades.py` -- not here.

            The `n <= 0` arm is not a cell. It is reachable (a simultaneous
            pass never checks its count's sign) and it is a defect upstream of
            this seam, filed as issue #416; the policy delegates it to
            `random_chooser` rather than shadowing a guard that belongs to the
            movement executor.
"""

from __future__ import annotations

import ast
import inspect
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.domains import zone_observer_key
from cardlang.openspiel.encoding import ActionSpace
from cardlang.pipeline import check_source
from cardlang.runtime import observe
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, CardSet
from cardlang.stdlib.zones import ZONE_PROJECTIONS
from tests.playout_policy import (
    CANDIDATE_KINDS,
    CANDIDATE_RANKERS,
    RANKED_KINDS,
    PlayoutPolicy,
    candidate_kind,
    is_length_guard,
)

GAMES = Path(__file__).parent.parent / "docs" / "games"
SPADES = GAMES / "spades.cardlang"

ARITIES = ("n == 1", "n > 1")

# One live value per registered kind. Authored, not derived — the grid needs a
# concrete Candidate to hand the policy, and the reconciliations below are what
# keep this table honest when the registry grows.
REPRESENTATIVE: dict[str, Any] = {
    "integer": 3,
    "card": Card("A", "spades"),
    "card_group": CardSet((Card("A", "spades"), Card("K", "spades"))),
    "move": ("pass", None),
    "token": "pass",
}

# The authored expected column: kind x arity -> what the policy must do.
# Written before the module existed. `integer` at a single draw is the one
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


class _Paused(Exception):
    """Unwinds `play_game` once a probe has what it came for."""


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
    to `CANDIDATE_RANKERS` without a decided cell reddens here rather than
    quietly running under whatever the dispatch happens to do."""
    derived = {(k, a) for k in CANDIDATE_KINDS for a in ARITIES}
    assert set(EXPECTED) == derived
    assert set(REPRESENTATIVE) == set(CANDIDATE_KINDS)


def test_the_ranked_subset_is_derived_from_the_one_table() -> None:
    """`RANKED_KINDS` is exactly the rows carrying a ranker, and the grid's
    ranked cells are exactly those at `n == 1`. A kind cannot be declared
    ranked without a ranker to rank it: the two are the same row."""
    assert RANKED_KINDS == {k for k, r in CANDIDATE_RANKERS.items() if r is not None}
    assert {k for (k, _), v in EXPECTED.items() if v == "ranked"} == RANKED_KINDS
    assert all(EXPECTED[(k, "n > 1")] == "delegated" for k in RANKED_KINDS)


def test_every_dispatch_arm_returns_a_registered_kind() -> None:
    """The dispatch chain is the definition site of the kind names, so the
    table is pinned to the ARMS and not the other way round.

    Without this, adding an arm that returns a name the table lacks ships a
    kind no grid cell covers and no refusal catches — every test green, and
    the module's "the registry below is the whole claim" quietly false.

    red under: add `if isinstance(value, frozenset): return "card_frozenset"`
    to `playout_policy.candidate_kind`, and this reddens naming that kind.
    """
    tree = ast.parse(inspect.getsource(candidate_kind))
    returned = {
        node.value.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Return)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    assert returned, "scraped no return literals — the scrape lost its target"
    assert returned == set(CANDIDATE_KINDS), (
        f"dispatch arms return {sorted(returned)} but the table registers "
        f"{sorted(CANDIDATE_KINDS)} — an arm with no row is a kind no cell covers"
    )


# --- the registry's reconciliations ----------------------------------------


def test_the_corpus_reaches_every_registered_kind() -> None:
    """Derived by EXECUTION, not by reading: play every corpus game under a
    chooser that classifies each Candidate it is offered.

    Two directions, and the second is what keeps this from being a tautology.
    Soundness: an unregistered shape makes `candidate_kind` raise, and that
    refusal is deliberately NOT caught — catching `OwnerGuardError` here would
    swallow the exact signal this test exists to surface, and a refusal planted
    on a live corpus shape would pass. Completeness: every registered kind is
    actually reached, so a row nothing in the corpus produces cannot sit in the
    table unexercised.

    red under: make `candidate_kind` refuse any registered kind (`token`, say)
    and this reddens — through the refusal propagating, not through a
    hand-written membership list.
    """
    seen: set[str] = set()
    for path in sorted(GAMES.glob("*.cardlang")):
        rng = random.Random(0)
        calls = [0]

        def watch(p: int, cands: list[Any], n: int) -> list[Any]:
            calls[0] += 1
            if calls[0] > 3000:
                raise _Paused()
            for c in cands:
                seen.add(candidate_kind(c))
            return rng.sample(cands, n)

        try:
            play_game(check_source(path), rng, chooser=watch)
        except _Paused:
            pass
        except OwnerGuardError as exc:
            # Only the game's own declared-length bound is an acceptable end to
            # a capped probe playout. Anything else — a classification refusal
            # above all — is the finding, so it propagates.
            if not is_length_guard(exc):
                raise
    assert seen == set(CANDIDATE_KINDS), (
        f"corpus reached {sorted(seen)}; registry declares {sorted(CANDIDATE_KINDS)}"
    )


def test_every_registered_kind_is_a_declared_decision_value() -> None:
    """Reconciliation against the runtime's own closed statement of what a
    decision value may be. `observe.render` raises on a shape it does not
    declare, so a kind this policy handles that `render` does not know would be
    a Candidate the observation layer cannot put in an information state."""
    for kind in CANDIDATE_KINDS:
        observe.render(REPRESENTATIVE[kind])  # raises AssertionError if undeclared


def test_the_bool_refusal_matches_the_encoder() -> None:
    """The third statement of the decision-value domain, executed rather than
    cited. `candidate_kind` refuses a bool because `ActionSpace.encode` does;
    were the encoder ever to accept one, the policy's stated reason would be
    false, and this reddens rather than the docstring quietly rotting."""
    with pytest.raises(ValueError, match="boolean is not an action value"):
        ActionSpace(None, [], [], None, [], None).encode(True)
    with pytest.raises(OwnerGuardError):
        candidate_kind(True)


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


def test_reattaching_to_a_second_world_is_refused(live: RuntimeState) -> None:
    """A policy reused across two `play_game` calls where the second omits
    `on_first_decision` would rank the second game against the FIRST game's
    finished world — whose hands are empty, so every declaration comes out 0.
    A confident constant wearing a ranked policy's clothes, and worse than the
    uniform degradation above because it still looks like it is deciding."""
    policy, _ = _attached(live)
    with pytest.raises(OwnerGuardError, match="already attached"):
        policy.attach(live)


def test_an_unregistered_candidate_shape_is_refused(live: RuntimeState) -> None:
    """A shape outside the registry is refused at the seam rather than
    delegated. Delegating it is the fallthrough this whole module exists to
    forbid: it would read, from every angle, as a considered decision."""
    policy, rng = _attached(live)
    with pytest.raises(OwnerGuardError, match="no declared Playout Policy"):
        policy(0, [object()], 1)
    assert rng.draws == 0


def test_a_boolean_is_refused_not_read_as_an_integer(live: RuntimeState) -> None:
    """`bool` is an `int` subclass, so a classifier testing `isinstance(c, int)`
    first would rank `True` as the integer 1 — a silent misread."""
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


# --- the info-set pin ------------------------------------------------------


def _private_families(rs: RuntimeState) -> set[str]:
    """The families whose library type shows identity to their owner and less
    to everyone else, computed here from the registry independently of the
    policy — so this pin cannot inherit the policy's own predicate."""
    return {
        name
        for name, ztype in rs.zones.zone_type.items()
        if ZONE_PROJECTIONS[ztype].owner == "identity"
        and ZONE_PROJECTIONS[ztype].others != "identity"
    }


def test_the_policy_reads_only_zones_the_deciding_seat_owns(
    live: RuntimeState,
) -> None:
    """The property that makes these playouts admissible as evidence at all.

    A policy that consulted another seat's hand would still produce playouts,
    and every other gate in this repo would stay green on them — the reach
    would be real and the game would not be. So the read is traced, and traced
    against the OWNERSHIP FUNCTION rather than the seat number:
    `zone_observer_key` decides which instance of a family an observer owns,
    and that is their TEAM in a team-indexed family. Asserting `key == seat`
    would restate the very bug it must catch — a policy keying `stash[0]` for
    seat 0 of a `HiddenPile<team>` family reads a zone whose projection to that
    seat is a bare count, and `key == seat` passes it.

    The recorder hooks every mapping accessor, not `__getitem__` alone: a leak
    through `.get` is the one an implementation reaches for first, since that
    is how the family itself is looked up a line earlier.

    red under: in `playout_policy._own_private_cards`, read a neighbour too --
    `out.extend(family.get((player + 1) % 4, family[key]).cards)` -- and this
    reddens naming the foreign key. (The Spades reach test also reddens under
    that plant; this one names WHICH seat was read, which is the property.)
    """
    reads: list[tuple[str, Any]] = []

    class Recording(dict):  # type: ignore[type-arg]
        """Records every read of a zone family, through any mapping accessor."""

        def __init__(self, name: str, inner: dict[Any, Any]) -> None:
            super().__init__(inner)
            self._name = name

        def __getitem__(self, key: Any) -> Any:
            reads.append((self._name, key))
            return super().__getitem__(key)

        def get(self, key: Any, default: Any = None) -> Any:
            reads.append((self._name, key))
            return super().get(key, default)

        def values(self) -> Any:
            reads.extend((self._name, k) for k in super().keys())
            return super().values()

        def items(self) -> Any:
            reads.extend((self._name, k) for k in super().keys())
            return super().items()

    original = live.zones.families
    private = _private_families(live)
    try:
        for seat in range(4):
            reads.clear()
            live.zones.families = {
                name: Recording(name, inner) for name, inner in original.items()
            }
            policy, _ = _attached(live)
            policy(seat, [0, 1, 2, 3], 1)
            assert reads, f"seat {seat}: the ranking read no zone at all"
            for name, key in reads:
                assert name in private, f"seat {seat} read shared zone {name!r}"
                index = live.zones.zone_index[name]
                assert index is not None, f"{name} was read as a family but has no index"
                owned = zone_observer_key(index, live, seat)
                assert key == owned, (
                    f"seat {seat} read {name}[{key}] but owns {name}[{owned}] — "
                    "a zone whose projection to this seat is not identity"
                )
    finally:
        live.zones.families = original


def test_the_same_seed_replays_identically() -> None:
    """One RNG source, so a seeded playout is reproducible.

    red under: in `playout_policy._rank_declaration`, draw the target from a
    second, unseeded stream -- `target = _likely_winners(rs, player) +
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
            # The declared-length arm is an outcome like any other, and pinning
            # it too keeps this from depending on a hand-picked seed that
            # happens to terminate.
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
