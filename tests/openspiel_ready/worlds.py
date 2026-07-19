"""Constructive indistinguishable-world generator
(structural-infoset-proofs, "The direction").

The swap harness SAMPLES worlds: it guesses a per-card swap axis (same suit,
same rank) and hopes the replay stays both legal and unobserved. This module
CONSTRUCTS them: it derives, from the replayed line itself, exactly which
cards are constrained, and permutes everything else — so validity is by
construction, not by luck, and the generated world is maximally distant (a
permutation over the whole genuinely-hidden set, not one pair).

The entitlement analysis. For an (observer, seed, history) a card is PINNED
iff any of:

- **decode pin** — its identity is named by a decision in the history
  (`ActionSpace.decode` of an action id that denotes a Card). These cards
  must sit exactly where world A's deal put them for the same actions to
  replay: a chosen-card action names its card, so moving that card at deal
  time makes the recorded action illegal (the replay wall raises).
- **log pin** — its identity appears in the observer's observation log at
  the pause: the deal of their own hand, a flip/reveal arrival in an
  identity zone, a pickup arriving in their own hand, their own `chose`
  draws. These are the facts the observer is entitled to; a world that
  moves one is distinguishable by definition.
- **projection pin** — its identity is in a zone the observer currently
  projects at `identity` (their own hand; any face-up zone). Subsumed by
  the log pin for any card that arrived via an emitting movement; kept as a
  separate class so the pin set never depends on that subsumption.

Every other card is genuinely hidden from the observer. The generator deals
world B by permuting the unpinned cards across the deal-time containers of
non-observer hands (per-container counts preserved), then replays the SAME
history. The caller asserts the observer's information state is
byte-identical and the pause offers the same legal actions.

Honest scope (recorded in structural-infoset-proofs.md): the pin derivation
is generic machinery, but its SUFFICIENCY — "every public emission that
reads hidden content names exactly the cards it read" — is a per-game
property. Cheat satisfies it: the challenge verdict is a Boolean over the
flipped cards, and the flip names exactly those cards, so decode/log pins
capture every constraint (guards elsewhere read only counts and public
state). Go Fish does NOT: an ask's public transfer count reads the target's
hidden rank composition without naming any card, so an unpinned permutation
there could change an observed count. The design is assert-backed either
way — a game outside the sufficiency condition fails the equality assert
loudly rather than certifying a wrong world.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cardlang.openspiel.replay import Pause, load, run
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, build_deck

from .partition import projection_for, zone_instances


@dataclass(frozen=True)
class WorldPlan:
    """The derived entitlement analysis for one (observer, seed, history)."""

    observer: int
    decode_pins: frozenset[Card]
    log_pins: frozenset[Card]
    projection_pins: frozenset[Card]
    # deal-time container label -> its unpinned (permutable) cards, in
    # deal order. Containers are the non-observer per-player hidden-zone
    # instances captured at the first decision.
    free: dict[str, list[Card]]

    @property
    def pinned(self) -> frozenset[Card]:
        return self.decode_pins | self.log_pins | self.projection_pins

    @property
    def free_cards(self) -> list[Card]:
        return [c for cards in self.free.values() for c in cards]


def _scan_log_pins(log: list[tuple[Any, ...]], by_render: dict[str, Card]) -> set[Card]:
    """Card identities named anywhere in an observation log — exact string
    match against the deck's renderings, walked through nested tuples (never
    substring matching: '10♦' contains no other card's rendering, but exact
    matching removes the question entirely)."""
    pins: set[Card] = set()

    def scan(x: Any) -> None:
        if isinstance(x, str):
            card = by_render.get(x)
            if card is not None:
                pins.add(card)
        elif isinstance(x, tuple):
            for y in x:
                scan(y)

    for event in log:
        scan(event)
    return pins


def plan_worlds(
    path: str, seed: int, history: tuple[int, ...], observer: int, hidden_zone: str
) -> tuple[Pause, WorldPlan]:
    """Replay world A and derive the entitlement analysis for `observer`.

    `hidden_zone` names the per-player zone family whose deal-time contents
    the permutation reassigns (the same axis the swap harness's GameSpec
    declares)."""
    game, space = load(path)
    pause = run(path, seed, history)
    assert isinstance(pause, Pause), "plan_worlds needs a paused (non-terminal) line"

    decode_pins = {
        decoded
        for decoded in (space.decode(a) for a in history)
        if isinstance(decoded, Card)
    }

    by_render = {str(c): c for c in build_deck(game.deck)}
    assert len(by_render) == len(build_deck(game.deck)), (
        "a repeated-copy deck renders two physical cards identically — the "
        "log-pin scan needs distinct renderings"
    )
    log_pins = _scan_log_pins(pause.obs_logs[observer], by_render)

    projection_pins: set[Card] = set()
    for name, key, zone in zone_instances(pause.rs):
        if projection_for(pause.rs, name, key, observer) == "identity":
            projection_pins.update(zone.cards)

    pinned = decode_pins | log_pins | projection_pins

    # Deal-time containers: capture the hidden-zone family at the first
    # decision of a fresh replay (after setup, before any recorded action).
    initial: dict[str, list[Card]] = {}

    def capture(rs: RuntimeState) -> None:
        for p in sorted(rs.zones.families[hidden_zone]):
            if p != observer:
                initial[f"{hidden_zone}[{p}]"] = list(
                    rs.zones.instance(hidden_zone, p).cards
                )

    r0 = run(path, seed, (), on_first_decision=capture)
    assert isinstance(r0, Pause)
    free = {
        label: [c for c in cards if c not in pinned]
        for label, cards in initial.items()
    }
    return pause, WorldPlan(
        observer=observer,
        decode_pins=frozenset(decode_pins),
        log_pins=frozenset(log_pins),
        projection_pins=frozenset(projection_pins),
        free=free,
    )


def permuted_replay(
    path: str,
    seed: int,
    history: tuple[int, ...],
    plan: WorldPlan,
    hidden_zone: str,
    rotation: int = 1,
) -> Pause:
    """Replay `history` in world B: the plan's free cards rotated across their
    deal-time containers (per-container counts preserved — every projection
    that shows a count is untouched by construction). `rotation` picks the
    permutation: the flattened free-card list shifts by the size of the first
    `rotation` container(s), so consecutive values yield distinct worlds.

    Raises ValueError if the constructed world fails the replay wall — which
    the entitlement analysis exists to make impossible; a raise here means a
    pin class is missing, and the caller's test should let it propagate."""
    labels = [label for label, cards in plan.free.items() if cards]
    assert len(labels) >= 2, (
        "constructive permutation needs free cards in at least two containers "
        f"— got {[(label, len(c)) for label, c in plan.free.items()]}; the "
        "world generator would be vacuous here (nothing crosses a container)"
    )
    flat = [c for label in labels for c in plan.free[label]]
    shift = sum(len(plan.free[label]) for label in labels[:rotation])
    shifted = flat[shift % len(flat):] + flat[: shift % len(flat)]
    assignment: dict[str, list[Card]] = {}
    i = 0
    for label in labels:
        k = len(plan.free[label])
        assignment[label] = shifted[i : i + k]
        i += k

    def mutate(rs: RuntimeState) -> None:
        for label in labels:
            p = int(label.split("[")[1].rstrip("]"))
            zone = rs.zones.instance(hidden_zone, p)
            for c in plan.free[label]:
                zone.remove(c)
            for c in assignment[label]:
                zone.add(c)

    pause_b = run(path, seed, history, on_first_decision=mutate)
    assert isinstance(pause_b, Pause), "world B ended where world A paused"
    return pause_b
