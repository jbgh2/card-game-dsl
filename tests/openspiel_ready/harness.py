"""The OpenSpiel-readiness proof machinery (SP1 spec, "The proof").

Every fully-kernel game gets the same proofs, one test module per game
(`test_<game>.py` in this package, kept total against the adapter's registry
by `test_coverage.py`):

1. pyspiel API conformance (random_sim_test, or a bounded random API walk for
   games whose full sim is prohibitively long — see
   `GameSpec.conformance_steps`).
2. INDISTINGUISHABILITY: two worlds differing only in cards hidden from P
   yield byte-identical information states for P — and offer P identical
   legal actions (legal-action agreement).
3. Soundness converse: perturbing what P CAN see changes P's state — the
   replay-level own-hand probe plus the per-visible-fact matrix enumerated
   from the zone declarations (partition.check_visible_facts).
4. Perfect recall: each player's observation log is append-only along a game.
5. Seed/undrawn-randomness non-observability: reseeding the generator and
   permuting all-hidden stocks leaves every information state byte-identical.
6. Adapter agreement: the registered pyspiel game renders the same partition
   the DSL-level proofs certify.

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
from pathlib import Path
from typing import Any, ClassVar, Literal

import pytest

pyspiel = pytest.importorskip("pyspiel")

import cardlang.openspiel.game as ogame  # noqa: E402  (registers on import)
from cardlang.openspiel.infostate import information_state  # noqa: E402
from cardlang.openspiel.replay import Pause, run  # noqa: E402

from .partition import (  # noqa: E402
    all_hidden,
    check_visible_facts,
    first_divergence,
    format_failures,
    record,
    zone_instances,
)

GAMES_DIR = Path(__file__).resolve().parent.parent.parent / "docs" / "games"

# (short_name, filename), deterministic order — the registry the per-game
# modules must cover (test_coverage.py).
REGISTERED_GAMES = sorted(ogame.GAMES.items())


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
    conformance_steps: int | None = None

    # Which equivalence class a hidden swap must stay within so the swapped
    # world is genuinely indistinguishable to the observer (the swap must not
    # change any PUBLIC observation). "suit": follow-suit trick games (default,
    # today's behavior). "rank": rank-probing games (Go Fish — a public ask's
    # transfer COUNT is observed, so only same-rank swaps preserve it).
    # "any": no public card/rank observation (a pure betting vocabulary).
    swap_axis: Literal["suit", "rank", "any"] = "suit"

    @property
    def path(self) -> str:
        return str(GAMES_DIR / self.filename)

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


def _advance(path: str, seed: int, depth: int) -> tuple[list[int], Pause]:
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, Pause)
    while len(history) < depth:
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        if not isinstance(nxt, Pause):  # short game: back off one step
            history.pop()
            break
        r = nxt
    return history, r


def _side_zone(rs: Any, side: tuple[str, "int | None"]) -> Any:
    """A swap side: a (family, key) pair (a per-player zone) or (name, None)
    (a single zone, e.g. Cribbage's `deck` — the other side of a 2-player
    swap when there is no second opponent hand to pair against)."""
    name, key = side
    return rs.zones.single(name) if key is None else rs.zones.instance(name, key)


def _swap_fn(side1: tuple[str, "int | None"], side2: tuple[str, "int | None"], x: Any, y: Any) -> Any:
    def swap(rs: Any) -> None:
        h1, h2 = _side_zone(rs, side1), _side_zone(rs, side2)
        h1.remove(x)
        h2.remove(y)
        h1.add(y)
        h2.add(x)

    return swap


class ReadinessProofs:
    """The four readiness proofs, run against one game's `spec`. A game's
    module subclasses this as `class TestReadiness(ReadinessProofs)` with its
    `GameSpec` as the `spec` class attribute."""

    spec: ClassVar[GameSpec]

    def test_pyspiel_conformance(self) -> None:
        game = pyspiel.load_game(self.spec.short_name)
        steps = self.spec.conformance_steps
        if steps is None:
            pyspiel.random_sim_test(game, num_sims=1, serialize=False, verbose=False)
            return
        rng = random.Random(7)
        state = game.new_initial_state()
        for _ in range(steps):
            if state.is_terminal():
                assert len(state.returns()) == game.num_players()
                break
            if state.is_chance_node():
                outcomes = state.chance_outcomes()
                assert abs(sum(p for _, p in outcomes) - 1.0) < 1e-9
                action = rng.choice([a for a, _ in outcomes])
            else:
                player = state.current_player()
                assert 0 <= player < game.num_players()
                legal = state.legal_actions(player)
                assert legal, "a decision node must offer at least one action"
                assert legal == sorted(set(legal)), "legal actions must be sorted, unique"
                assert all(0 <= a < game.num_distinct_actions() for a in legal)
                assert state.information_state_string(player)  # derives, non-crash
                action = rng.choice(legal)
            state.apply_action(action)

    def test_indistinguishability_under_hidden_swap(self) -> None:
        spec = self.spec
        path = spec.path
        seed = 5
        hz = spec.hidden_zone
        history, pause_a = _advance(path, seed, spec.depth)
        p = pause_a.player
        first = run(path, seed, ())
        assert isinstance(first, Pause)
        d0 = first.player  # the swap must not touch the first decider (stale candidates)

        others = [q for q in range(len(pause_a.obs_logs)) if q not in (p, d0)]
        if len(others) >= 2:
            opp1, opp2 = others[0], others[1]
            # Skip pairs the replay rejects (a rule keyed on the specific card).
            hand1 = pause_a.rs.zones.instance(hz, opp1).cards
            hand2 = pause_a.rs.zones.instance(hz, opp2).cards
            candidates = spec.swap_pairs(hand1, hand2)
            side1: tuple[str, "int | None"] = (hz, opp1)
            side2: tuple[str, "int | None"] = (hz, opp2)
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
        last_err: ValueError | None = None
        for x, y in candidates:
            try:
                pause_b = run(path, seed, tuple(history), on_first_decision=_swap_fn(side1, side2, x, y))
            except ValueError as e:
                # this pair made a recorded action illegal (ActionSpace.match's
                # "not among the live candidates", or a zone .remove failure);
                # try the next pair, but remember why in case none work.
                last_err = e
                continue
            assert isinstance(pause_b, Pause)
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
            record(
                spec.short_name,
                "swap",
                seed=seed,
                depth=len(history),
                axis=spec.swap_axis,
                pair=f"{x}<->{y}",
                pairs_skipped=candidates.index((x, y)),
                candidates=len(candidates),
                legal_agreement=True,
            )
            return  # one successful controlled swap proves the property
        pytest.fail(f"{spec.short_name}: no swap pair produced a legal replay; last replay error: {last_err!r}")

    def test_soundness_own_view_changes_the_state(self) -> None:
        spec = self.spec
        path = spec.path
        hz = spec.hidden_zone
        r0 = run(path, 5, ())
        assert isinstance(r0, Pause)
        p = r0.player
        opp = next(q for q in range(len(r0.obs_logs)) if q != p)
        own = r0.rs.zones.instance(hz, p).cards
        theirs = r0.rs.zones.instance(hz, opp).cards
        pairs = spec.swap_pairs(own, theirs)
        assert pairs, (
            f"{spec.short_name}: no swap pair for soundness at this seed/depth — "
            f"adjust the spec"
        )
        x, y = pairs[0]
        info_a = information_state(p, r0.rs, r0.obs_logs[p])
        r1 = run(path, 5, (), on_first_decision=_swap_fn((hz, p), (hz, opp), x, y))
        assert isinstance(r1, Pause)
        info_b = information_state(r1.player, r1.rs, r1.obs_logs[r1.player])
        # The pause player is the same (no actions replayed); their own hand changed.
        assert r1.player == p and info_a != info_b, (
            f"{spec.short_name}: the info-state is insensitive to the player's own hand"
        )

    def test_soundness_every_visible_fact_is_in_the_state(self) -> None:
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
        _, pause = _advance(spec.path, 5, spec.depth)
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
        record(spec.short_name, "facts", observers=len(pause.obs_logs),
               depth=spec.depth, **totals)

    def test_seed_and_undrawn_randomness_are_not_observable(self) -> None:
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
        _, pause = _advance(spec.path, 5, spec.depth)
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
            depth=spec.depth,
            reseeded=True,
            stocks_reversed=len(stocks),
            vacuous_stock=(len(stocks) == 0),
        )

    def test_perfect_recall_logs_are_append_only(self) -> None:
        spec = self.spec
        path = spec.path
        seed = 9
        history: list[int] = []
        r = run(path, seed, ())
        prev: dict[int, list[tuple[Any, ...]]] = {}
        steps = 0
        while isinstance(r, Pause) and steps < 40:
            for q, log in r.obs_logs.items():
                if q in prev:
                    assert log[: len(prev[q])] == prev[q], (
                        f"{spec.short_name}: P{q}'s observation log rewrote history"
                    )
                prev[q] = list(log)
            history.append(r.legal[0])
            r = run(path, seed, tuple(history))
            steps += 1

    def test_adapter_agrees_with_the_dsl_information_state(self) -> None:
        """The readiness proofs run at the DSL level; the partition OpenSpiel
        algorithms actually consume is the registered game's. Walk one line
        and assert the two renderings agree at every step — current player,
        legal actions, and every player's information-state string — and that
        the terminal returns agree if reached. Because the pyspiel state
        re-simulates independently of this test's own `run` calls, the
        comparison doubles as a per-game determinism check: two independent
        replays of the same (seed, history) must render byte-identically."""
        spec = self.spec
        seed = 5
        game = pyspiel.load_game(spec.short_name)
        state = game.new_initial_state()
        assert state.is_chance_node()
        state.apply_action(seed)

        history: list[int] = []
        r = run(spec.path, seed, ())
        steps = 0
        while isinstance(r, Pause) and steps < spec.depth:
            assert not state.is_terminal()
            assert state.current_player() == r.player, (
                f"{spec.short_name}: step {steps}: adapter player "
                f"{state.current_player()} != DSL player {r.player}"
            )
            assert state.legal_actions() == r.legal, (
                f"{spec.short_name}: step {steps}: adapter legal actions disagree"
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
        if not isinstance(r, Pause):
            assert state.is_terminal(), (
                f"{spec.short_name}: DSL line terminal but adapter is not"
            )
            assert state.returns() == r.returns
        record(spec.short_name, "adapter", seed=seed, steps=steps,
               terminal=not isinstance(r, Pause))
