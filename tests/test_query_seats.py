"""The Checker Query's per-seat answer agrees with what the engine shows each seat.

Completeness ledger (decisions.md "Closed-domain completeness"):

property:        At a movement site, the projection the query says each kind
                 of seat sees each side through is the projection of the
                 `move` events the OpenSpiel adapter's information state
                 (`infostate.derive`) holds for that seat from that site, and
                 a seat the query says learns nothing holds none; and the pick
                 table the query reads (`observe.PICK_SHOWN`) is what every
                 registered game emits after each decision of each construct.
domain:          The agreement sites are `AGREEMENT_SITES`, each a movement
                 whose zone pair no other site of its game moves between, so
                 a `move` event's two labels name the site: a hidden hand
                 passed and played (Hearts), cards played face down (Cheat),
                 a dealt hand (Hearts), and a piece placed on a board square
                 no seat holds (Tic-tac-toe). The pick table's rows are
                 `delegation.CONSTRUCTS`; every construct a registered game's
                 bounded seeded line asks is held to its row.
registry:        the constructs -- `cardlang.runtime.delegation.CONSTRUCTS`;
                 the games -- `cardlang.openspiel.registry.GAMES`; the seat
                 view -- `cardlang.openspiel.infostate.derive`.
held by:         Derived and Pinned: the query and the emitter read one
                 projection function and one visibility rule
                 (`observe.movement_seen`), but which seat holds a zone
                 instance is decided by the query statically and by the
                 runtime from the instance's key, so the agreement is run.
does not prove:  agreement at a site a seeded line does not reach, nor for a
                 construct no registered game asks within the bound: such a
                 construct's row is asserted by no playout, and
                 `test_every_construct_is_asked_somewhere` names it.
"""

from __future__ import annotations

import random
from collections import defaultdict
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.openspiel.infostate import derive
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.pipeline import check_source
from cardlang.query import Observer, Seats, ask_path
from cardlang.runtime import observe
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.delegation import CONSTRUCTS
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.state import IllegalMove, RuntimeState

REPO = Path(__file__).resolve().parent.parent
GAMES_DIR = REPO / "docs" / "games"

_SEEDS = (1, 2, 3)
_DECISIONS = 120


class _Enough(Exception):
    pass


@dataclass(frozen=True)
class Site:
    path: Path
    line: int
    column: int
    source: str
    destination: str


AGREEMENT_SITES: dict[str, Site] = {
    "hearts pass": Site(GAMES_DIR / "hearts.cardlang", 65, 9, "hand", "hand"),
    "hearts trick": Site(GAMES_DIR / "hearts.cardlang", 90, 9, "hand", "trick_pile"),
    "hearts deal": Site(GAMES_DIR / "hearts.cardlang", 53, 7, "deck", "hand"),
    "cheat face-down play": Site(GAMES_DIR / "cheat.cardlang", 137, 5, "hand", "played"),
    "tic-tac-toe placement": Site(GAMES_DIR / "tic-tac-toe.cardlang", 55, 5, "reserve", "square"),
}


@cache
def _logs(path: Path, seed: int) -> tuple[tuple[tuple[Any, ...], ...], ...]:
    """Each seat's observation log on one bounded seeded line, as the
    adapter's Seat View derives it."""
    game = check_source(path)
    rng = random.Random(seed)
    uniform = random_chooser(rng)
    logs: dict[int, list[tuple[Any, ...]]] = defaultdict(list)
    world: list[RuntimeState] = []
    made = [0]

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        if made[0] >= _DECISIONS:
            raise _Enough
        made[0] += 1
        return uniform(player, candidates, count)

    try:
        play_game(
            game,
            rng,
            None,
            chooser=choose,
            observer=lambda p, event: logs[p].append(event),
            on_first_decision=world.append,
        )
    except (_Enough, GameDescriptionError, IllegalMove):
        pass
    assert world, f"{path.name} reached no decision"
    return tuple(
        derive(seat, world[0], logs[seat]).obs_log for seat in range(game.players.count)
    )


def _zone(label: str) -> str:
    return label.split("[", 1)[0]


def _key(label: str) -> str | None:
    return label[label.index("[") + 1 : -1] if "[" in label else None


def _shape(projection: str | None) -> type | None:
    return {"identity": tuple, "count_only": int, "trivial": type(None), None: None}[projection]


def _seat_holds(path: Path, zone: str, label: str, seat: int) -> bool:
    """The oracle's own reading: a seat holds a family instance keyed by its
    seat number, in a zone indexed by seat."""
    decl = next(z for z in check_source(path).zones if z.name == zone)
    return decl.index == "player" and _key(label) == str(seat)


def _observer(seats: Seats, holds_source: bool, holds_destination: bool) -> Observer:
    return next(
        o
        for o in seats.observers
        if (o.holds_source, o.holds_destination) == (holds_source, holds_destination)
    )


@pytest.mark.parametrize("seed", _SEEDS)
@pytest.mark.parametrize("name", sorted(AGREEMENT_SITES))
def test_the_query_s_seats_are_the_adapter_s(name: str, seed: int) -> None:
    """red under: in `query._observers`, project the source through
    `zone_projection(..., not on_s)` (the holder and the others swapped);
    and, on the emitter's side, `observe._is_owner` answering False for
    every seat."""
    site = AGREEMENT_SITES[name]
    answer = ask_path(site.path, site.line, site.column)
    assert isinstance(answer.seats, Seats), answer
    logs = _logs(site.path, seed)
    moves_by_seat: list[list[tuple[Any, ...]]] = [
        [
            e
            for e in log
            if e[0] == "move" and _zone(e[1]) == site.source and _zone(e[3]) == site.destination
        ]
        for log in logs
    ]
    assert any(moves_by_seat), f"{name}: the line never reached the site"
    for seat, events in enumerate(moves_by_seat):
        for _kind, src, src_view, dst, dst_view in events:
            obs = _observer(
                answer.seats,
                _seat_holds(site.path, site.source, src, seat),
                _seat_holds(site.path, site.destination, dst, seat),
            )
            assert obs.learns, f"{name}: seat {seat} saw {src}->{dst}, the query says it learns nothing"
            assert isinstance(src_view, _shape(obs.source) or object), (name, seat, src, src_view, obs)
            assert isinstance(dst_view, _shape(obs.destination) or object), (name, seat, dst, dst_view, obs)
    # A seat the query says learns nothing of the site receives no event of it.
    seen_by = {seat for seat, events in enumerate(moves_by_seat) if events}
    if all(o.learns for o in answer.seats.observers if not o.holds_source and not o.holds_destination):
        assert seen_by == set(range(len(logs))), f"{name}: some seat saw nothing"


# --- the pick table --------------------------------------------------------------


@cache
def _decisions(file_name: str) -> tuple[tuple[str, bool, bool], ...]:
    """Each decision of one bounded seeded line: its construct, whether its
    decider's pick was announced before the next decision was asked, and
    whether a card moved in that stretch."""
    game, _ = load(str(GAMES_DIR / file_name))
    rng = random.Random(_SEEDS[0])
    uniform = random_chooser(rng)
    stream: list[tuple[int, tuple[Any, ...]]] = []
    made = [0]

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        if made[0] >= _DECISIONS:
            raise _Enough
        made[0] += 1
        return uniform(player, candidates, count)

    try:
        play_game(game, rng, None, chooser=choose, observer=lambda p, e: stream.append((p, e)))
    except (_Enough, GameDescriptionError, IllegalMove):
        pass
    # A decision counts once its pick is made (its decider's `chose`): the
    # line is cut inside the Chooser, before the last ask is answered.
    out: list[tuple[str, bool, bool]] = []
    current: tuple[int, str] | None = None
    announced = moved = picked = False
    for seat, event in [*stream, (-1, ("asked", "", "", 1, None))]:
        if event[0] == "asked":
            if current is not None and picked:
                out.append((current[1], announced, moved))
            current, announced, moved, picked = (seat, event[2]), False, False, False
        elif current is not None and event[0] == "chose" and seat == current[0]:
            picked = True
        elif current is not None and event[0] == "announce" and event[1] == current[0]:
            announced = True
        elif current is not None and event[0] == "move":
            moved = True
    return tuple(out)


def test_the_pick_table_names_every_construct() -> None:
    """red under: delete the `"joint"` row of `observe.PICK_SHOWN`."""
    assert set(observe.PICK_SHOWN) == set(CONSTRUCTS)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_every_pick_is_shown_as_the_table_says(short_name: str) -> None:
    """red under: set `observe.PICK_SHOWN["offer"] = "moved"`."""
    for construct, announced, moved in _decisions(GAMES[short_name]):
        shown = observe.PICK_SHOWN[construct]
        if shown == "announced":
            assert announced, f"{short_name}: a {construct} pick was not announced"
        elif shown == "moved":
            assert not announced, f"{short_name}: a {construct} pick was announced"
        else:
            assert announced or moved, f"{short_name}: a {construct} pick was neither announced nor moved"


def test_every_construct_is_asked_somewhere() -> None:
    """The constructs the sweep holds to the table, and the ones no
    registered game's line asks."""
    asked = {construct for name in GAMES.values() for construct, _a, _m in _decisions(name)}
    assert asked == set(CONSTRUCTS) - _UNASKED, sorted(asked)


# Designed but witness-gated (`delegation.DECISION_POINTS`).
_UNASKED: frozenset[str] = frozenset()

