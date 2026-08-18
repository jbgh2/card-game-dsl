"""The OpenSpiel-readiness proof machinery (SP1 spec, "The proof").

Every fully-kernel game gets the same proofs, one test module per game
(`test_<game>.py` in this package, kept total against the adapter's registry
by `test_coverage.py`):

1. pyspiel API conformance (random_sim_test, or a bounded random API walk for
   games whose full sim is prohibitively long — see
   `GameSpec.conformance_steps`).
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P — and offer P identical
   legal actions, rendering to identical text (legal-action agreement).
   Run over the `SWAP_SEEDS` manifest, several replaying pairs per seed.
3. Soundness converse: perturbing what P CAN see changes P's state — the
   replay-level own-hand probe plus the per-visible-fact matrix enumerated
   from the zone declarations (partition.check_visible_facts).
4. Perfect recall: each player's observation log is append-only along a game.
5. Seed/undrawn-randomness non-observability: reseeding the generator and
   permuting all-hidden stocks leaves every information state byte-identical
   (a structural pin — it bites only if rendering ever couples to the
   generator or to hidden-stock order).
6. Adapter agreement: the registered pyspiel game renders the same partition
   the DSL-level proofs certify — current player, legal actions, their
   rendered text, and every information state; games whose greedy line
   terminates walk to the end and assert the terminal returns agree too.

Passing runs record their coverage (partition.RECORDS; see conftest.py);
failing checks report their witness — the perturbed fact and the
information-state fragment that wrongly agrees or differs.

A game module declares its harness configuration as a `GameSpec` on a
`TestReadiness(ReadinessProofs)` subclass. Per-game rationale — depths,
hidden zones, driving-policy quirks — lives in that module, next to the
game's dedicated observational tests.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # registers on import
from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import (
    DecisionNode,
    TerminalNode,
    load,
    returns_for,
    run,
)
from cardlang.runtime.driver import play_game

from .partition import (
    all_hidden,
    check_visible_facts,
    first_divergence,
    format_failures,
    record,
    zone_instances,
)

GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"


def _instance_key(rs: Any, family: str, raw: str) -> Any:
    """The live instance key matching a rendered label part (`captured[2]` ->
    the seat 2, whatever type the family is keyed by)."""
    for key in rs.zones.families[family]:
        if str(key) == raw:
            return key
    raise AssertionError(f"no instance {raw!r} of family {family!r}")


def _instance_labels(rs: Any, zones: tuple[str, ...]) -> list[str]:
    """Each declared provenance zone as concrete instance labels: a single
    zone is itself, a family becomes one label per live instance."""
    out: list[str] = []
    for name in zones:
        if rs.zones.is_family(name):
            out.extend(f"{name}[{key}]" for key in sorted(rs.zones.families[name]))
        else:
            out.append(name)
    return out


@cache
def _checked_game_nodes(path: str) -> tuple[object, ...]:
    """Every node of a corpus game's CHECKED AST — post-resolve, so a
    `NameRef`'s `ref_kind` is the classification the resolver stamped rather
    than something this walk re-derives. Cached: the specs ask repeatedly and
    checking a game is pure."""
    from cardlang.pipeline import check_dsl
    from cardlang.resolve import _walk

    game = check_dsl(Path(path).read_text(), Path(path).name)
    return tuple(_walk(game))

# (short_name, filename), deterministic order — the registry the per-game
# modules must cover (test_coverage.py).
REGISTERED_GAMES = sorted(ogame.GAMES.items())


# The swap proof's COVERAGE MANIFEST: the seeds every game's indistinguishability
# check runs at. Five rather than one because a single seed fixes one deal, one
# greedy line and one pause player, and none of those is the property — a leak
# that only opens when a particular seat holds a particular shape would sit
# under a one-seed proof indefinitely.
#
# Uniform across the corpus, and that is a measured claim, not an assumption:
# the swap geometry has hard preconditions (a 2-player game needs its depth
# pause to coincide with the first decider; every game needs a swappable pair
# that replays legally), and most seeds fail one of them for some game. These
# five are the first that clear EVERY game running this proof, and seeds 3 and 5
# additionally clear Cheat's constructive certificate, which uses the same
# manifest. A per-game override was the alternative and was rejected: it would
# let one game quietly degrade to a single seed while the coverage record still
# read "five".
SWAP_SEEDS: tuple[int, ...] = (3, 5, 14, 15, 18)

# How many legally-replaying swap pairs to check per (game, seed). The first
# pair alone was the previous coverage, and "the first pair that happens to
# replay" is a sample of one from sets that run past 250 candidates. Bounded
# rather than exhaustive because the cost is one full replay per pair; the
# number checked and the number available both go into the coverage record, so
# the cap is visible rather than implied.
SWAP_PAIRS_PER_SEED = 3

# What a DECLARED one-seed proof runs (`test_coverage.ONE_SEED_SWAP_PROOFS`):
# the manifest's head. A prefix rather than a separate number, so an exemption
# cannot drift onto a seed the manifest no longer contains — and the proof still
# takes `seed` as a parameter, so the exemption is visible in the signature and
# in the test id instead of being an argument silently missing.
ONE_SEED = SWAP_SEEDS[:1]


def manifest(seeds: tuple[int, ...] = SWAP_SEEDS) -> list[Any]:
    """The manifest as parametrization, with everything past the head marked
    `slow` — the fast development pass, without a second definition of what the
    manifest is.

    The default stays the COMPLETE run. `pytest -q` selects every seed, which is
    what CI runs and what CLAUDE.md's verification rule names; the short pass is
    `pytest -q -m "not slow"` and covers one seed per proof, which is exactly the
    coverage that existed before the manifest. Inverting that — fast by default,
    complete behind a flag — is the arrangement to avoid: the rule "run the full
    `pytest -q`" would quietly stop being true, and a partial green is the kind
    of evidence this package exists to refuse.
    """
    return [seeds[0], *(pytest.param(s, marks=pytest.mark.slow) for s in seeds[1:])]


def action_strings(space: Any, actions: list[int]) -> list[str]:
    """The rendered action text for `actions` — the bytes a prompt shows.

    SHADOW-GUARD HELPER. Its guard is `test_action_strings.py`, which pins that
    `CardlangState._action_to_string` reads nothing of the world: given that,
    equal ids give equal strings, so the world-pair assertions calling this
    cannot fail on their own — measured, under that module's named mutation.
    They state the composition at the point where the partition claim is made,
    so a reader of the swap proof can see that the ids agreeing is not the
    whole claim about what an observer is shown.

    The one CALLER that is not a Shadow Guard is the adapter-agreement proof, which
    compares this against `state.action_to_string` — two implementations, so it
    discriminates.
    """
    return [space.to_string(a) for a in actions]


@dataclass(frozen=True)
class GameSpec:
    """One game's harness configuration. The defaults fit most games; the
    rationale for any override belongs in the game's own test module."""

    short_name: str
    filename: str

    # The zone family hiding each player's cards — what the swap tests
    # perturb. Most games hide a `hand`.
    hidden_zone: str = "hand"

    # Steps to replay before the indistinguishability check. Deep enough that
    # real decisions and movements happened; shallow enough that opponents
    # still hold swappable cards.
    depth: int = 12

    # 2-player games only: the hidden un-dealt stock the swap pairs the
    # opponent's hand against. The default is the `deck`.
    stock_zone: str = "deck"

    # 2-player games only: how many leading stock cards to exclude from the
    # swap pool.
    stock_swap_skip: int = 0

    # None = full `pyspiel.random_sim_test`, which re-simulates the whole
    # (seed, history) state after every action — O(n^2) in game length. Games
    # whose full sim is prohibitively long set a step count and get a bounded
    # random API walk instead (the sanctioned SP1 bridge-fallback precedent):
    # that many random legal actions checking current_player/legal-actions
    # consistency, info-state string non-crash, chance-node handling, and
    # terminal handling if reached.
    #
    # A bound is a BUDGET WITH A CHECKED CLAIM: `test_conformance_bounds.py`
    # asserts that the walk applies every verb of the game's declared action
    # space (`ActionSpace.verbs()`) except those listed below. Without that
    # claim a bound set too low under-covers SILENTLY — nothing notices when a
    # walk stops reaching a mechanic. Derive a bound as the worst
    # last-new-verb step observed across several rngs, plus margin; the pinned
    # `Random(7)` line is what the assertion then checks.
    conformance_steps: int | None = None

    # The PINNED COMPLEMENT of that claim: (verb, why) for every verb the walk
    # does not apply — typically a mechanic a uniform random policy reaches too
    # rarely to bound affordably, exercised elsewhere. The reason travels with
    # the verb rather than in prose someone must find, and is asserted
    # non-empty. The pin is TIGHT in both directions: a verb here that the walk
    # DOES reach fails just as loudly as one missing that is not here, so
    # neither the list nor the bound can drift silently. Only meaningful with a
    # bound: an unbounded game plays a full random_sim_test and declares none.
    conformance_verbs_unreached: tuple[tuple[str, str], ...] = ()

    # Which equivalence class a hidden swap must stay within so the swapped
    # world is genuinely indistinguishable to the observer (the swap must not
    # change any PUBLIC observation). "suit": follow-suit trick games (default,
    # today's behavior). "rank": rank-probing games (Go Fish — a public ask's
    # transfer COUNT is observed, so only same-rank swaps preserve it).
    # "any": no public card/rank observation (a pure betting vocabulary).
    swap_axis: Literal["suit", "rank", "any"] = "suit"

    @property
    def all_provenance_zones(self) -> tuple[str, ...]:
        """The proof's whole domain: every fully public zone whose Arrival
        Record a consumer reads in this game — derived from TWO sources, both
        registries, neither hand-listed.

        The CALL-FORM half walks this game's checked AST for every call in
        `ARRIVAL_RECORD_CALLS` and reads the zone name off its pile argument.
        That walk is only sound because resolve GUARANTEES the argument is a
        static zone reference (`_check_arrival_record_pile_args`, issue #250
        PR 1) — before that guard the argument could be any expression and the
        name was unknowable without running the game, which is why this half
        used to be a hand-listed `provenance_zones` field on each spec. A
        hand-listed field is a check narrower than its ledger: a game that
        grew a second consumer kept proving the first one only.

        The PRIMITIVE half is derived from `PRIMITIVE_READS.arrival_zones`
        (the rows whose game_file is this spec's), so a Primitive declaring
        `arrival_zones` joins the soundness proof automatically. It empties as
        the Primitives retire.

        A game with neither half records a vacuous cell rather than silently
        passing (most games consume no provenance today — the query surface is
        issue #253's)."""
        from cardlang.ast import nodes as n
        from cardlang.builtins.functions import ARRIVAL_RECORD_CALLS
        from cardlang.runtime.reads import PRIMITIVE_READS

        derived = {
            zone
            for row in PRIMITIVE_READS
            if row.game_file == self.filename
            for zone in row.arrival_zones
        }
        for call in _checked_game_nodes(self.path):
            if not isinstance(call, n.Call) or call.func not in ARRIVAL_RECORD_CALLS:
                continue
            arg = call.args[ARRIVAL_RECORD_CALLS[call.func]]
            if isinstance(arg, n.NameRef) and arg.ref_kind == "zone":
                derived.add(arg.name)
            elif isinstance(arg, n.Subscript) and isinstance(arg.obj, n.NameRef):
                derived.add(arg.obj.name)
        return tuple(sorted(derived))

    # Where the provenance walk starts. The proof walks 40 greedy nodes from
    # here and REFUSES a run that compared zero record entries, so a game
    # whose line reaches its first play late must say so: Skat's greedy line
    # climbs the whole Reizen ladder and first plays to the trick at step
    # 127 on every manifest seed (measured 2026-08-15).
    provenance_depth: int = 0

    # Total greedy (legal[0]) steps within which this game's line reaches
    # TerminalNode — measured across EVERY seed in `SWAP_SEEDS`, with headroom.
    # Across the whole manifest because line length varies with the deal, and
    # by a lot: Schnapsen's runs 64-188 over the five seeds, so a cap read off
    # one deal under-covers the others.
    #
    # Set it and the adapter-agreement
    # proof walks the line to the end and ASSERTS the DSL and pyspiel terminal
    # returns agree (it fails loudly if the line stops terminating, rather
    # than silently skipping). None = the greedy line does not terminate in
    # affordable steps (the multi-hand score-target games — Bridge, Hearts,
    # Oh Hell, Seven-Card Stud, Skat, Tichu, all still past 400 greedy
    # steps — and Coup, whose greedy line is legally unbounded at
    # interactive scope), and the walk stops at `depth` with
    # `terminal=False` in the coverage record.
    adapter_terminal_steps: int | None = None

    @property
    def path(self) -> str:
        return str(GAMES_DIR / self.filename)

    @property
    def unreached_verbs(self) -> frozenset[str]:
        return frozenset(v for v, _ in self.conformance_verbs_unreached)

    def swap_pairs(self, hand1: list[Any], hand2: list[Any]) -> list[Any]:
        """Swappable hidden-card pairs that keep the swapped world indistinguishable."""
        if self.swap_axis == "rank":
            return [(x, y) for x in hand1 for y in hand2 if x.rank == y.rank and x.suit != y.suit]
        elif self.swap_axis == "any":
            return [(x, y) for x in hand1 for y in hand2 if x != y]
        elif self.swap_axis == "suit":
            three_d = ("3", "diamonds")
            return [
                (x, y)
                for x in hand1
                for y in hand2
                if x.suit == y.suit
                and x != y
                # keep the 3♦ fixed: Big Two's opening filter keys on that exact card
                and (x.rank, x.suit) != three_d
                and (y.rank, y.suit) != three_d
            ]
        else:
            raise ValueError(f"unknown swap_axis {self.swap_axis!r}")


@dataclass(frozen=True)
class BoundedWalk:
    """What one bounded conformance walk observed. Gathering facts rather than
    asserting them lets the API-conformance proof and the bound's coverage grid
    read the SAME walk — the walk is O(n^2) in its own length, so running it
    twice is the whole cost of the check."""

    # (verb, the step that first applied it), ascending — the derivation a
    # bound is set from, kept as data rather than re-measured by hand: the
    # last entry's step is the smallest bound that still covers this line, and
    # the distance from there to `conformance_steps` is the margin.
    first_applied: tuple[tuple[str, int], ...]
    violations: tuple[str, ...]
    steps: int
    terminal: bool

    @property
    def verbs_applied(self) -> frozenset[str]:
        return frozenset(v for v, _ in self.first_applied)

    @property
    def last_new_verb(self) -> int | None:
        return self.first_applied[-1][1] if self.first_applied else None


@cache
def bounded_walk(short_name: str, path: str, steps: int) -> BoundedWalk:
    """`steps` random legal actions from a pinned rng, checking the pyspiel API
    invariants and recording the verb of every action APPLIED (offered-only
    would not exercise the mechanic behind the verb, which is what a bound is
    bought to reach). Cached: one walk per game per session."""
    _, space = load(path)
    game = pyspiel.load_game(short_name)
    rng = random.Random(7)
    state = game.new_initial_state()
    applied: dict[str, int] = {}
    violations: list[str] = []

    def check(ok: bool, msg: str) -> None:
        if not ok:
            violations.append(f"step {taken}: {msg}")

    taken = walked = 0
    terminal = False
    for taken in range(steps):
        if state.is_terminal():
            terminal = True
            check(
                len(state.returns()) == game.num_players(),
                f"terminal returns has {len(state.returns())} entries, "
                f"expected {game.num_players()}",
            )
            break
        if state.is_chance_node():
            outcomes = state.chance_outcomes()
            check(
                abs(sum(p for _, p in outcomes) - 1.0) < 1e-9,
                "chance outcome probabilities do not sum to 1",
            )
            action = rng.choice([a for a, _ in outcomes])
        else:
            player = state.current_player()
            check(0 <= player < game.num_players(), f"current_player {player} out of range")
            legal = state.legal_actions(player)
            check(bool(legal), "a decision node must offer at least one action")
            check(legal == sorted(set(legal)), "legal actions must be sorted, unique")
            check(
                all(0 <= a < game.num_distinct_actions() for a in legal),
                "a legal action is outside the action space",
            )
            check(bool(state.information_state_string(player)), "empty information state")
            if not legal:
                break
            action = rng.choice(legal)
            applied.setdefault(space.verb_of(action), taken)
        state.apply_action(action)
        walked += 1
    return BoundedWalk(
        tuple(sorted(applied.items(), key=lambda kv: kv[1])),
        tuple(violations),
        walked,
        terminal,
    )


class _GreedyCap(Exception):
    """The greedy line ran past its cap without terminating."""


@cache
def greedy_line(path: str, seed: int, cap: int) -> tuple[tuple[int, ...], list[float] | None]:
    """The `legal[0]` line, walked ONCE and linearly: the action ids it takes,
    and the terminal returns if it ends within `cap`.

    Identical to the line a caller gets by repeatedly replaying a growing
    history and taking `DecisionNode.legal[0]` — `legal` is `sorted({encode(c) for c in
    pool})`, so its head is the lowest-encoded candidate, which is what the
    chooser below picks. `test_adapter_agrees_with_the_dsl_information_state`
    asserts that agreement on the prefix it walks both ways, so the equivalence
    is checked rather than argued.

    Walking it linearly matters because the replay-per-step form is quadratic:
    every `run(path, seed, history)` re-simulates from step 0, so a 418-step
    line costs 418 re-simulations (44.4s on belote) to learn a line one
    simulation already knows.

    red under: pick `max` instead of `min` — every game with
    `adapter_terminal_steps` fails the prefix cross-check at step 0."""
    game, space = load(path)
    ids: list[int] = []

    def chooser(player: int, candidates: list[Any], k: int) -> list[Any]:
        pool = list(candidates)
        picked: list[Any] = []
        for _ in range(k):
            aid = min(space.encode(c) for c in pool)
            choice = space.match(aid, pool)
            pool.remove(choice)
            picked.append(choice)
            ids.append(aid)
            if len(ids) > cap:
                raise _GreedyCap
        return picked

    try:
        result = play_game(game, random.Random(seed), chooser=chooser)
    except _GreedyCap:
        return tuple(ids), None
    return tuple(ids), returns_for(game, result)


def verb_status(verb: str, applied: frozenset[str], exempt: frozenset[str]) -> str:
    """One declared verb's coverage cell, total over the 2x2 of (the walk
    applied it?, the spec exempts it?):

      applied & not exempt -> "covered"    the bound reaches the mechanic
      not applied & exempt -> "exempt"     declared missing, with a reason
      applied & exempt     -> "stale"      the reason outlived itself
      neither              -> "uncovered"  the bound under-covers SILENTLY

    Only the first two pass. "stale" is the cell that makes the exemption list
    self-cleaning: a verb the walk starts reaching fails until its exemption
    (and the prose justifying it) comes out."""
    if verb in applied:
        return "stale" if verb in exempt else "covered"
    return "exempt" if verb in exempt else "uncovered"


def pin_failures(spec: GameSpec, declared: frozenset[str]) -> list[str]:
    """Everything wrong with a spec's unreached-verb pin that the per-verb grid
    cannot see, because each is a way the pin fails to correspond to any cell:
    an entry naming a verb the game does not declare (no cell can ever clear
    it), an entry with no reason (an unexplained hole reads as a covered one),
    and any entry at all on an unbounded game (nothing walks, so nothing checks
    it). A pure function so the probes can exercise each arm on a synthetic
    spec — these guards fire on no game in the corpus, and a guard nothing
    executes is not a guard."""
    out: list[str] = []
    if spec.conformance_steps is None:
        if spec.conformance_verbs_unreached:
            out.append(
                "conformance_verbs_unreached is only checkable against a "
                "bounded walk; this game runs the full random_sim_test"
            )
        return out
    unknown = sorted(spec.unreached_verbs - declared)
    if unknown:
        out.append(
            f"conformance_verbs_unreached names {unknown}, which the action "
            f"space does not declare — no cell can ever clear them"
        )
    unreasoned = sorted(v for v, why in spec.conformance_verbs_unreached if not why.strip())
    if unreasoned:
        out.append(
            f"{unreasoned} are recorded as unreached with no reason — an "
            f"unexplained hole reads as a covered one"
        )
    return out


def _advance(path: str, seed: int, depth: int) -> tuple[list[int], DecisionNode]:
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, DecisionNode):  # short game: back off one step
            history.pop()
            break
        r = nxt
    return history, r


def _side_zone(rs: Any, side: tuple[str, int | None]) -> Any:
    """A swap side: a (family, key) pair (a per-player zone) or (name, None)
    (a single zone, e.g. Cribbage's `deck` — the other side of a 2-player
    swap when there is no second opponent hand to pair against)."""
    name, key = side
    return rs.zones.single(name) if key is None else rs.zones.instance(name, key)


def _swap_fn(side1: tuple[str, int | None], side2: tuple[str, int | None], x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = _side_zone(rs, side1), _side_zone(rs, side2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


class ReadinessProofs:
    """The readiness proofs, run against one game's `spec`. A game's
    module subclasses this as `class TestReadiness(ReadinessProofs)` with its
    `GameSpec` as the `spec` class attribute."""

    spec: ClassVar[GameSpec]

    def test_pyspiel_conformance(self) -> None:
        spec = self.spec
        steps = spec.conformance_steps
        if steps is None:
            game = pyspiel.load_game(spec.short_name)
            pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)
            return
        walk = bounded_walk(spec.short_name, spec.path, steps)
        assert not walk.violations, (
            f"{spec.short_name}: pyspiel API conformance failed on the bounded "
            f"walk:\n  " + "\n  ".join(walk.violations)
        )

    @pytest.mark.parametrize("seed", manifest())
    def test_indistinguishability_under_hidden_swap(self, seed: int) -> None:
        spec = self.spec
        path = spec.path
        _, space = load(path)
        hz = spec.hidden_zone
        history, pause_a = _advance(path, seed, spec.depth)
        p = pause_a.player
        first = run(path, seed, ())
        assert isinstance(first, DecisionNode)
        d0 = first.player  # the swap must not touch the first decider (stale candidates)

        others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
        if len(others) >= 2:
            opp1, opp2 = others[0], others[1]
            # Skip pairs the replay rejects (a rule keyed on the specific card).
            hand1 = pause_a.rs.zones.instance(hz, opp1).cards
            hand2 = pause_a.rs.zones.instance(hz, opp2).cards
            candidates = spec.swap_pairs(hand1, hand2)
            side1: tuple[str, int | None] = (hz, opp1)
            side2: tuple[str, int | None] = (hz, opp2)
            who = f"players {opp1},{opp2}"
        else:
            # 2-player games: there is only ever one opponent, so the harness
            # swaps between that opponent's hand and the un-dealt deck instead —
            # both hidden from P throughout the replayed prefix. This only works
            # when the pause coincides with the first decider (`p == d0`), so the
            # swap (fired at the very first decision) never mutates a decider
            # whose candidates were already computed from the un-swapped world.
            assert p == d0, (
                f"{spec.short_name}: with 2 players the harness needs the depth pause "
                f"to coincide with the first decider (p == d0) — adjust the spec's depth"
            )
            assert len(others) == 1, f"{spec.short_name}: expected exactly one other player"
            opp = others[0]
            hand = pause_a.rs.zones.instance(hz, opp).cards
            deck = pause_a.rs.zones.single(spec.stock_zone).cards[spec.stock_swap_skip:]
            candidates = spec.swap_pairs(hand, deck)
            side1 = (hz, opp)
            side2 = (spec.stock_zone, None)
            who = f"player {opp}'s hand <-> the undealt {spec.stock_zone}"

        assert candidates, "no swap pair available; lower the spec's depth for this game"

        info_a = information_state(p, pause_a.rs, pause_a.obs_logs[p])
        strings_a = action_strings(space, pause_a.legal)
        last_err: ValueError | None = None
        proved: list[str] = []
        for x, y in candidates:
            if len(proved) >= SWAP_PAIRS_PER_SEED:
                break
            try:
                pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(side1, side2, x, y))
            except ValueError as e:
                # this pair made a recorded action illegal (ActionSpace.match's
                # "not among the live candidates", or a zone .remove failure);
                # try the next pair, but remember why in case none work.
                last_err = e
                continue
            assert isinstance(pause_b, DecisionNode)
            info_b = information_state(p, pause_b.rs, pause_b.obs_logs[p])
            assert info_a == info_b, (
                f"{spec.short_name}: swapping hidden {x}<->{y} ({who}) "
                f"CHANGED P{p}'s information state — the info-set leaks.\n"
                f"worlds: seed={seed} depth={len(history)} swap=({x},{y})\n"
                f"witness: {first_divergence(info_a, info_b)}"
            )
            # Legal-action agreement: two worlds in the same information set
            # for the player to move must offer identical legal actions —
            # otherwise the offered moves are themselves a leak channel, one
            # OpenSpiel does not police.
            assert pause_b.player == p, (
                f"{spec.short_name}: the hidden swap moved the turn to "
                f"P{pause_b.player} — whose turn it is leaks hidden content"
            )
            assert pause_b.legal == pause_a.legal, (
                f"{spec.short_name}: same information set, different legal actions "
                f"— swap ({x},{y}) changed the offer for P{p}: "
                f"only-in-A={sorted(set(pause_a.legal) - set(pause_b.legal))} "
                f"only-in-B={sorted(set(pause_b.legal) - set(pause_a.legal))}"
            )
            # ...and the same offer must READ the same. Shadow Guard; the guard is
            # `test_action_strings.py` (see `action_strings`).
            assert action_strings(space, pause_b.legal) == strings_a, (
                f"{spec.short_name}: same legal actions, different rendered text "
                f"for P{p} — the action strings the prompt shows are a leak channel"
            )
            proved.append(f"{x}<->{y}")
        assert proved, (
            f"{spec.short_name}: no swap pair produced a legal replay at seed "
            f"{seed}; last replay error: {last_err!r}"
        )
        record(
            spec.short_name,
            "swap",
            seed=seed,
            depth=len(history),
            axis=spec.swap_axis,
            pairs=";".join(proved),
            pairs_proved=len(proved),
            pairs_cap=SWAP_PAIRS_PER_SEED,
            candidates=len(candidates),
            legal_agreement=True,
            string_agreement=True,
        )

    @pytest.mark.parametrize("seed", manifest())
    def test_soundness_own_view_changes_the_state(self, seed: int) -> None:
        """The observer's own hand is theirs to see: move a card out of it and
        their information state MUST change.

        The pair does not have to preserve indistinguishability — this proof
        wants the opposite, a perturbation the observer CAN see — so the
        spec's swap axis is a preference here, not a requirement. It is tried
        first (so a game's declared axis still describes the probe wherever it
        applies), and any distinct pair serves when it yields none: Go Fish
        pairs same-rank only, and at some deals the two hands share no rank,
        which would block a proof that never needed the constraint. Which one
        was used goes into the coverage record rather than being absorbed
        silently.
        """
        spec = self.spec
        path = spec.path
        hz = spec.hidden_zone
        r0 = run(path, seed, ())
        assert isinstance(r0, DecisionNode)
        p = r0.player
        opp = next(q for q in range(len(r0.obs_logs)) if q != p)
        own = r0.rs.zones.instance(hz, p).cards
        theirs = r0.rs.zones.instance(hz, opp).cards
        pairs = spec.swap_pairs(own, theirs)
        axis: str = spec.swap_axis
        if not pairs:
            pairs = [(a, b) for a in own for b in theirs if a != b]
            axis = f"any (the {spec.swap_axis} axis yields no pair at this deal)"
        assert pairs, (
            f"{spec.short_name}: the two hands hold no distinct pair at seed "
            f"{seed} — nothing can perturb the observer's own view"
        )
        x, y = pairs[0]
        info_a = information_state(p, r0.rs, r0.obs_logs[p])
        r1 = run(path, seed, (), on_first_decision=_swap_fn((hz, p), (hz, opp), x, y))
        assert isinstance(r1, DecisionNode)
        info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
        # The pause player is the same (no actions replayed); their own hand changed.
        assert r1.player == p and info_a != info_b, (
            f"{spec.short_name}: the info-state is insensitive to the player's own hand"
        )
        record(spec.short_name, "own_view", seed=seed, axis=axis, pair=f"{x}<->{y}")

    @pytest.mark.parametrize("seed", manifest())
    def test_soundness_every_visible_fact_is_in_the_state(self, seed: int) -> None:
        """Soundness, generalized (structural-infoset-proofs, 'nothing
        over-hidden'): one perturbation per visible fact, for EVERY observer,
        enumerated from the zone declarations — every zone projection the
        observer is entitled to, every public state variable, every
        observation event. The complement is checked too: a perturbation of
        content the observer is NOT entitled to (a count-preserving swap in a
        count_only zone, any change in a trivial zone) must NOT move their
        information state. Perturbations are applied to the paused world
        snapshot directly (mutate -> recompute -> restore), so no replay
        legality constraints apply; the replay-level soundness probe above
        stays as the end-to-end complement."""
        spec = self.spec
        _, pause = _advance(spec.path, seed, spec.depth)
        totals = {"zone_identity": 0, "zone_count_only": 0, "zone_trivial": 0,
                  "state_vars": 0, "obs_events": 0}
        for observer in range(len(pause.obs_logs)):
            failures, counts = check_visible_facts(
                pause.rs, pause.obs_logs[observer], observer
            )
            assert not failures, format_failures(spec.short_name, observer, failures)
            assert sum(counts.values()) > 0, (
                f"{spec.short_name}: the fact enumeration for P{observer} was empty"
            )
            for k, v in counts.items():
                totals[k] += v
        record(spec.short_name, "facts", seed=seed, observers=len(pause.obs_logs),
               depth=spec.depth, **totals)

    @pytest.mark.parametrize("seed", manifest())
    def test_seed_and_undrawn_randomness_are_not_observable(self, seed: int) -> None:
        """No information state may be sensitive to the root chance seed
        beyond what dealt-and-observed cards already reveal, nor to rng draws
        not yet made — including the rules-level rng gates carrying the
        Tichu/Coup scope reductions, which draw from the same generator
        (structural-infoset-proofs, 'Seed and undrawn-randomness
        non-observability'). Two direct perturbations at a paused world:
        replace the live generator outright (a different seed's entire future
        stream), and reverse the order of every all-hidden stock (the pending
        draw order). Every player's information state must be byte-identical
        under both."""
        spec = self.spec
        _, pause = _advance(spec.path, seed, spec.depth)
        players = range(len(pause.obs_logs))
        before = {
            q: information_state(q, pause.rs, pause.obs_logs[q]) for q in players
        }

        pause.rs.rng = random.Random(0xC0FFEE)
        stocks: list[str] = []
        for name, key, zone in zone_instances(pause.rs):
            if all_hidden(pause.rs, name) and len(zone.cards) >= 2:
                zone.cards.reverse()
                stocks.append(name if key is None else f"{name}[{key}]")

        for q in players:
            after = information_state(q, pause.rs, pause.obs_logs[q])
            assert after == before[q], (
                f"{spec.short_name}: P{q}'s information state is sensitive to "
                f"undrawn randomness (reseeded rng; reversed {stocks})\n"
                f"witness: {first_divergence(before[q], after)}"
            )
        record(
            spec.short_name,
            "rng",
            seed=seed,
            depth=spec.depth,
            reseeded=True,
            stocks_reversed=len(stocks),
            vacuous_stock=(len(stocks) == 0),
        )

    @pytest.mark.parametrize("seed", manifest())
    def test_provenance_is_derivable_from_every_observers_stream(
        self, seed: int
    ) -> None:
        """The soundness rows of issue #256's no-leak criterion: for every
        zone a consumer reads the Arrival Record of
        (`spec.all_provenance_zones`, derived from the checked AST and the
        Primitive reads rows),
        the engine's (deciding actor, card) sequence equals what EVERY
        observer derives from their own observation log — so the record adds
        nothing beyond what observation entails, which is the executable
        form of "per-observer provenance is derived, never
        stored-then-stripped". Games with no provenance consumer record a
        vacuous cell honestly.

        red under: mis-attribute one recorded arrival (e.g. shift
        `record_actor` by one seat at execute._movement's single-destination
        site) — every observer's derivation disagrees with the record at the
        first play (executed 2026-08-15; see the change's completeness
        ledger in tests/test_arrival_record.py)."""
        spec = self.spec
        zones = spec.all_provenance_zones  # AST-derived call half + registry-derived Primitive half
        if not zones:
            record(spec.short_name, "provenance", seed=seed, zones=0, vacuous=True)
            return
        from .partition import derive_arrivals

        # Walk the greedy line and certify at EVERY node, counting record
        # entries actually compared: one pause can legitimately catch the
        # pile empty (doppelkopf's opening announcement lap), and an
        # empty-vs-empty comparison certifies nothing — the count below is
        # the proof's own vacuity guard. The walk starts at the spec's
        # provenance_depth (Skat's first play sits past its whole auction).
        history, r0 = _advance(spec.path, seed, spec.provenance_depth)
        r: DecisionNode | Any = r0
        entries_compared = 0
        nodes = 0
        while isinstance(r, DecisionNode) and nodes < 40:
            # A declared zone may be a FAMILY (`highest_by_trick_order(piles[p])`
            # is designed surface), and the AST derivation can only see the
            # family's name -- which instance a call reads is a runtime value.
            # So expand here, where the live instances exist, and compare per
            # instance. Comparing the family as one label would derive [] and
            # certify nothing.
            for zone_label in _instance_labels(r.rs, zones):
                name, _, key = zone_label.partition("[")
                zone = (
                    r.rs.zones.instance(name, _instance_key(r.rs, name, key[:-1]))
                    if key
                    else r.rs.zones.single(name)
                )
                engine = [(a.actor, str(a.card)) for a in zone.arrivals]
                entries_compared += len(engine)
                for observer in range(len(r.obs_logs)):
                    derived = derive_arrivals(
                        r.rs, r.obs_logs[observer], zone_label
                    )
                    assert derived == engine, (
                        f"{spec.short_name}: step {nodes}: P{observer}'s "
                        f"stream derives {derived} for '{zone_label}' but "
                        f"the engine record holds {engine} — the record "
                        f"exposes provenance observation does not entail "
                        f"(or the emission lost a fact)"
                    )
            history.append(r.legal[0])
            r = run(spec.path, seed, tuple(history))
            nodes += 1
        assert entries_compared > 0, (
            f"{spec.short_name}: the greedy line never put a card in "
            f"{zones} within {nodes} steps — the certificate "
            f"was vacuous; deepen the walk"
        )
        record(
            spec.short_name,
            "provenance",
            seed=seed,
            zones=len(zones),
            nodes=nodes,
            entries_compared=entries_compared,
            vacuous=False,
        )

    @pytest.mark.parametrize("seed", manifest())
    def test_wash_hidden_stock_order_is_not_provenance(self, seed: int) -> None:
        """The wash pin (issue #256): washing is an invariance, not an
        operation. At a paused world — the standing residue of every mixing
        event replayed so far (the initial shuffle always; inter-hand
        face-down gathers where the depth crosses a hand) — permute every
        all-hidden stock by a rotation (a DIFFERENT permutation from the
        rng proof's reversal, so the two pins cannot share a blind spot) and
        assert every observer's information state is byte-identical. Legal
        actions are covered by composition, stated here because the direct
        form is not executable: the replay hook fires after the first
        decider's candidates are computed (driver.py's staleness contract),
        so a pause's legal set cannot be recomputed post-mutation — but the
        swap proof's legal-action agreement certifies legal actions are a
        function of the information state, and this pin certifies the
        information state is invariant, so the legal-action set is too.

        red under: append the deck's raw card order to the information
        state (infostate.py) — the rotation moves every observer's state
        (executed 2026-08-15; see tests/test_arrival_record.py's ledger)."""
        spec = self.spec
        _, pause = _advance(spec.path, seed, spec.depth)
        players = range(len(pause.obs_logs))
        before = {
            q: information_state(q, pause.rs, pause.obs_logs[q]) for q in players
        }
        rotated: list[str] = []
        for name, key, zone in zone_instances(pause.rs):
            if all_hidden(pause.rs, name) and len(zone.cards) >= 2:
                zone.cards[:] = zone.cards[1:] + zone.cards[:1]
                rotated.append(name if key is None else f"{name}[{key}]")
        for q in players:
            after = information_state(q, pause.rs, pause.obs_logs[q])
            assert after == before[q], (
                f"{spec.short_name}: P{q}'s information state moved under a "
                f"hidden-stock rotation (rotated {rotated}) — provenance or "
                f"order is leaking through a projection\n"
                f"witness: {first_divergence(before[q], after)}"
            )
        record(
            spec.short_name,
            "wash",
            seed=seed,
            depth=spec.depth,
            stocks_rotated=len(rotated),
            vacuous_stock=(len(rotated) == 0),
            legal_by_composition=True,
        )

    @pytest.mark.parametrize("seed", manifest())
    def test_perfect_recall_logs_are_append_only(self, seed: int) -> None:
        spec = self.spec
        path = spec.path
        history: list[int] = []
        r = run(path, seed, ())
        prev: dict[int, list[tuple[Any, ...]]] = {}
        steps = 0
        while isinstance(r, DecisionNode) and steps < 40:
            for q, log in r.obs_logs.items():
                if q in prev:
                    assert log[: len(prev[q])] == prev[q], (
                        f"{spec.short_name}: P{q}'s observation log rewrote history"
                    )
                prev[q] = list(log)
            history.append(r.legal[0])
            r = run(path, seed, tuple(history))
            steps += 1

    @pytest.mark.parametrize("seed", manifest())
    def test_adapter_agrees_with_the_dsl_information_state(self, seed: int) -> None:
        """The readiness proofs run at the DSL level; the partition OpenSpiel
        algorithms actually consume is the registered game's. Walk one line
        and assert the two renderings agree at every step — current player,
        legal actions, and every player's information-state string. Because
        the pyspiel state re-simulates independently of this test's own `run`
        calls, the comparison doubles as a per-game determinism check: two
        independent replays of the same (seed, history) must render
        byte-identically.

        When the spec sets `adapter_terminal_steps` (games whose greedy line
        terminates), the walk then continues cheaply to the
        end of the game and asserts the DSL and pyspiel TERMINAL RETURNS
        agree; reaching TerminalNode within the cap is itself asserted, so the
        returns comparison cannot rot into dead code. The remaining games
        (multi-hand score targets whose greedy line exceeds any affordable
        cap) record `terminal=False` in the coverage record — their returns
        surface is exercised only by the conformance sim."""
        spec = self.spec
        game = pyspiel.load_game(spec.short_name)
        _, space = load(spec.path)
        state = game.new_initial_state()
        assert state.is_chance_node()
        state.apply_action(seed)

        history: list[int] = []
        r = run(spec.path, seed, ())
        steps = 0
        while isinstance(r, DecisionNode) and steps < spec.depth:
            assert not state.is_terminal()
            assert state.current_player() == r.player, (
                f"{spec.short_name}: step {steps}: adapter player "
                f"{state.current_player()} != DSL player {r.player}"
            )
            assert state.legal_actions() == r.legal, (
                f"{spec.short_name}: step {steps}: adapter legal actions disagree"
            )
            # The prompt-facing bytes, from the two implementations. Unlike the
            # world-pair sites this one is discriminating: `action_to_string`
            # goes through the pyspiel state — the call
            # `experiments/llm_eval/referee.py` makes — while `to_string` goes
            # through the DSL-level action space, so an adapter that decorated
            # or localized its rendering would diverge here and nowhere else.
            assert [state.action_to_string(r.player, a) for a in state.legal_actions()] == (
                action_strings(space, r.legal)
            ), (
                f"{spec.short_name}: step {steps}: adapter and DSL action "
                f"renderings disagree — the strings a prompt shows are not the "
                f"strings the DSL-level proofs reason about"
            )
            for q in range(len(r.obs_logs)):
                expected = information_state(q, r.rs, r.obs_logs[q])
                got = state.information_state_string(q)
                assert got == expected, (
                    f"{spec.short_name}: step {steps}: adapter info state for "
                    f"P{q} diverged\nwitness: {first_divergence(expected, got)}"
                )
            action = r.legal[0]
            state.apply_action(action)
            history.append(action)
            r = run(spec.path, seed, tuple(history))
            steps += 1
        cap = spec.adapter_terminal_steps
        dsl_returns = r.returns if isinstance(r, TerminalNode) else None
        if cap is not None:
            # Continue the greedy line to the end of the game. The line comes
            # from ONE linear walk rather than a replay per step (`greedy_line`
            # explains why), and its prefix is asserted to be the very line the
            # expensive phase above walked — so the terminal returns compared
            # below belong to the line whose information states were checked,
            # not merely to a line derived the same way.
            line, returns = greedy_line(spec.path, seed, cap)
            assert list(line[: len(history)]) == history, (
                f"{spec.short_name}: the linear greedy walk diverges from the "
                f"replayed one at step "
                f"{next(i for i, (a, b) in enumerate(zip(line, history)) if a != b)}"
            )
            assert returns is not None, (
                f"{spec.short_name}: greedy line no longer reaches TerminalNode "
                f"within adapter_terminal_steps={cap} — re-measure the line "
                f"and adjust the spec (do not silently drop the returns check)"
            )
            for action in line[len(history):]:
                state.apply_action(action)
            steps = len(line)
            dsl_returns = returns
        if dsl_returns is not None:
            assert state.is_terminal(), (
                f"{spec.short_name}: DSL line terminal but adapter is not"
            )
            assert state.returns() == dsl_returns, (
                f"{spec.short_name}: terminal returns disagree — "
                f"adapter {state.returns()} != DSL {dsl_returns}"
            )
        record(spec.short_name, "adapter", seed=seed, steps=steps,
               terminal=dsl_returns is not None,
               returns_compared=dsl_returns is not None,
               action_strings_compared=True)
