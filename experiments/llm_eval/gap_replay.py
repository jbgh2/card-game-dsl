"""The replay check behind the posterior sampler: a sampled world, dealt into
the engine and played out, must leave the observer seeing exactly what they saw.

`gap_sampler` invents worlds — a deal for the hands it cannot see, and a card
for every face-down play it never saw — from the observation log alone. This is
the check that says it invented a world the observer genuinely cannot rule out:
install the world's deal at the first decision, replay the world's own action
line, and require the observer's rendered information state to come back
byte-identical with the same legal actions. The same assert-backed shape
`tests/openspiel_ready/worlds.py` uses, for the same reason: a wrong sampler
fails loudly instead of quietly certifying a world that is distinguishable.

The seed is the line's own. Only the hands the observer cannot see are
overwritten: the deal into the observer's own hand is an event in their log,
emitted before any mutation can reach it, so a world whose observer was dealt
something else is distinguishable for a reason that has nothing to do with the
sampler. What the seed then decides is exactly the observer's own hand, which
the world must agree with anyway — and the check says so rather than assuming
it.

Contract
--------
Assumes: a `World` from `gap_sampler` for the information state passed beside
it, the seed that line was played under, and a game whose per-player hidden
zone is `HAND` and whose challenge window offers `WINDOW_MOVES`.
Establishes: nothing, or a raise. A return means the engine, driven through
`cardlang.openspiel.replay`, renders that observer that information state in
that world, and offers the same actions there.
Illegal after: treating a sampled world as a world the observer cannot
distinguish without having replayed it.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from functools import cache
from typing import Any

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .gap_sampler import World
from .infostate import parse

#: The engine modules this check is written against — the re-simulation entry
#: point and the information-state renderer. Named here so
#: `tests/test_gap_sampler.py` can hold the seam to exactly these two: a check
#: that reached into the runtime would be measuring something other than what
#: the adapter shows a seat.
ENGINE_IMPORTS: tuple[str, ...] = (
    "cardlang.openspiel.infostate",
    "cardlang.openspiel.replay",
)

#: Cheat's per-player hidden zone family, and the moves its challenge window
#: offers — the same axes `tests/openspiel_ready/worlds.py` takes as arguments.
HAND = "hand"
WINDOW_MOVES: tuple[str, ...] = ("allow", "call_cheat")


@cache
def _deck(game_path: str, seed: int) -> dict[str, Any]:
    """Every card of this game's deal, keyed by its rendering.

    Read off the live world at the first decision rather than built from the
    deck declaration: the sampler names cards as the strings an information
    state shows, and the replay needs the values the action space encodes. One
    short replay answers both, and keeps this module off the runtime's
    value layer.
    """
    node = run(game_path, seed, ())
    if not isinstance(node, DecisionNode):
        raise AssertionError(f"{game_path} reaches no decision at all under seed {seed}")
    zones = node.rs.zones
    cards: dict[str, Any] = {}
    for name in zones.singles:
        for card in zones.single(name).cards:
            cards[str(card)] = card
    for name, keys in zones.families.items():
        for key in keys:
            for card in zones.instance(name, key).cards:
                cards[str(card)] = card
    return cards


def _install(
    world: World, game_path: str, seed: int, observer: int
) -> Callable[[Any], None]:
    """The deal-time mutation: every hidden hand holds what the world says.

    The observer's own hand is left as the seed dealt it and REQUIRED to be
    what the world says — the deal event in their log already named those
    cards, so this is the one hand a world does not get to choose.
    """

    def install(rs: Any) -> None:
        hands = {seat: rs.zones.instance(HAND, seat) for seat in sorted(rs.zones.families[HAND])}
        if len(hands) != len(world.deal):
            raise AssertionError(
                f"the world deals {len(world.deal)} hands where the game has {len(hands)}"
            )
        deck = _deck(game_path, seed)
        for seat, hand in hands.items():
            wanted = world.deal[seat]
            dealt = sorted(str(card) for card in hand.cards)
            if len(wanted) != len(dealt):
                raise AssertionError(
                    f"the world deals {len(wanted)} cards to seat {seat} where the "
                    f"game deals {len(dealt)} — every count the observer "
                    f"projects would move"
                )
            missing = sorted(set(wanted) - set(deck))
            if missing:
                raise AssertionError(f"the world names cards this deck has none of: {missing}")
            if seat == observer and sorted(wanted) != dealt:
                raise AssertionError(
                    f"the world deals the observer {sorted(wanted)} where seed "
                    f"{seed} dealt {dealt} — the observer's own deal is theirs to "
                    f"know, not the sampler's to choose"
                )
        for seat, hand in hands.items():
            if seat == observer:
                continue
            for card in list(hand.cards):
                hand.remove(card)
            for card in world.deal[seat]:
                hand.add(deck[card])

    return install


def _history(space: Any, world: World, deck: dict[str, Any]) -> tuple[int, ...]:
    """The world's action line as global action ids.

    A card action is encoded by IDENTITY through the action space, which is what
    makes the line the world's own: the same decision in two worlds names two
    different cards and so two different ids.
    """
    ids: list[int] = []
    for kind, value in world.actions:
        if kind == "card":
            card = deck.get(str(value))
            if card is None:
                raise AssertionError(f"the world plays {value!r}, which this deck has none of")
            ids.append(int(space.encode(card)))
        elif kind == "count":
            ids.append(int(space.encode(int(value))))
        elif kind == "name":
            ids.append(int(space.encode(str(value))))
        else:
            raise AssertionError(f"action item {kind!r} is not one this replay encodes")
    return tuple(ids)


def replay_check(
    infostate: str,
    world: World,
    game_path: str,
    *,
    seed: int,
    legal: Sequence[int] | None = None,
) -> None:
    """Replay `world` and assert the observer cannot tell it from the original.

    Raises `AssertionError` when the observer's information state or legal
    actions differ, and lets the engine's own replay guard raise where the
    world's action line is not legal in it — which is the same verdict reached
    one layer earlier.
    """
    observer = parse(infostate).player
    _, space = load(game_path)
    node = run(
        game_path,
        seed,
        _history(space, world, _deck(game_path, seed)),
        on_first_decision=_install(world, game_path, seed, observer),
    )
    if not isinstance(node, DecisionNode):
        raise AssertionError(
            "the world's action line ends the game where the original stands at a "
            "window — it is not this window's line"
        )
    if node.player != observer:
        raise AssertionError(
            f"the replayed line stops at seat {node.player}, not the observer "
            f"({observer})"
        )
    rendered = information_state(observer, node.rs, node.obs_logs[observer])
    if rendered != infostate:
        raise AssertionError(
            "the sampled world is distinguishable from the original:\n"
            f"  original: {infostate}\n"
            f"  replayed: {rendered}"
        )
    expected = (
        sorted(legal)
        if legal is not None
        else sorted(int(space.encode(move)) for move in WINDOW_MOVES)
    )
    if sorted(node.legal) != expected:
        raise AssertionError(
            f"the replayed window offers {sorted(node.legal)}, not {expected}"
        )


def make_checker(
    infostate: str,
    game_path: str,
    *,
    seed: int,
    legal: Sequence[int] | None = None,
) -> Callable[[World], None]:
    """`replay_check` bound to one window — the shape `gap_sampler.estimate`
    takes, so the sampler can be handed a checker without importing one."""

    def check(world: World) -> None:
        replay_check(infostate, world, game_path, seed=seed, legal=legal)

    return check
