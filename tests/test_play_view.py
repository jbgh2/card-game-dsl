"""A seat's view as text a person reads, certified fact by fact.

property:        Every fact a Seat View carries shows in the text
                 `cardlang.play.view.render_view` makes of it, and no fact the
                 seat is not entitled to does. At positions inside a live
                 playout of every registered game, for every seat, the
                 per-visible-fact matrix changes each zone the seat sees and
                 each public state variable and finds the text changed,
                 changes each hidden zone's content and finds it unchanged,
                 and perturbs every field of every observation event, deletes
                 each event, swaps each neighbouring pair and appends one event
                 of each kind, finding the text changed each time — so the
                 whole log is rendered, in order, with every copy of a repeated
                 event. The pieces the text is built from are total over their
                 own domains: a line for every declared event kind, spelling
                 every field and refusing an event the payload table does not
                 describe; a spelling for each shape a projection answers,
                 refusing any other; a card order defined for every card a
                 component set holds and for one no set holds.
domain:          Kinds and fields: `EVENT_PAYLOADS`; the members of each
                 field's shape: `SHAPE_MEMBERS`
                 (tests/test_observation_payloads.py), each perturbed as the
                 matrix perturbs it (`PAYLOAD_PROBES`); zone shapes: the
                 alternatives of `ZoneView`; the card order: every card
                 `build_deck` builds for every component set, and
                 `partition.SYNTHETIC`, under every registered game's
                 declarations; positions: every registered game along one
                 seeded line, at each decision `_POSITIONS` names that the line
                 reaches, for every seat, from inside the Chooser, where every
                 phase frame stands. The pin must meet every event kind and
                 every projection level, or the coverage cell reddens.
registry:        event lines: `cardlang.play.events.EVENT_LINES`; kinds, fields
                 and shapes: `cardlang.runtime.observe.EVENT_PAYLOADS` and
                 `PAYLOAD_SHAPES`; the matrix and its probe tables:
                 `tests.openspiel_ready.partition` (`check_visible_facts`,
                 `ZONE_PROBES`, `PAYLOAD_PROBES`); cards:
                 `cardlang.runtime.values.COMPONENT_SETS`; games:
                 `cardlang.openspiel.registry.GAMES`; the spelling of a state
                 variable the text shares with the information state, and its
                 declared shapes: tests/test_openspiel_infostate.py.
does not prove:  That the text reads well. A text that shows every fact in an
                 unreadable arrangement passes; tests/test_play_view_format.py
                 pins the arrangement against moving, never against being
                 wrong. The turn line is not a Seat View fact, and nothing here
                 perturbs it: it shows only on the seat's own decision, and its
                 row is the swap proof's turn agreement
                 (tests/openspiel_ready/harness.py); whose turn it is on
                 another seat's decision is not rendered at all. No readiness
                 proof module renders this text except that swap proof, which
                 holds it equal across a hidden swap (the leak direction only):
                 the load-bearing pin is this module, at positions inside a
                 Chooser, which is where `demo` renders — the adapter's
                 decision nodes drop the phase-local state variables (issue
                 #612). The positions are one seeded line per game, bounded by
                 `_POSITIONS`, so a fact only a later position or another line
                 reaches is unprobed. The log's labels and card renderings show
                 as the log spells them and in the log's order (issue #666).
"""

from __future__ import annotations

import random
from collections.abc import Callable
from dataclasses import replace
from functools import cache
from itertools import product
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.openspiel.infostate import SeatView, derive
from cardlang.openspiel.registry import GAMES
from cardlang.openspiel.replay import load
from cardlang.play import events
from cardlang.play.events import EVENT_LINES, event_line
from cardlang.play.view import card_order, render_view
from cardlang.runtime.chooser import random_chooser, sequential_decisions
from cardlang.runtime.driver import play_game
from cardlang.runtime.errors import GameDescriptionError
from cardlang.runtime.observe import EVENT_PAYLOADS
from cardlang.runtime.state import IllegalMove, RuntimeState
from cardlang.runtime.values import COMPONENT_SETS, Card, build_deck
from tests.openspiel_ready.partition import (
    PAYLOAD_PROBES,
    SYNTHETIC,
    ZONE_PROBES,
    FactFailure,
    InfoFn,
    check_visible_facts,
)
from tests.test_observation_payloads import SHAPE_MEMBERS

GAMES_DIR = Path(__file__).parent.parent / "docs" / "games"


def _game(file_name: str) -> n.Game:
    game, _ = load(str(GAMES_DIR / file_name))
    return game


# ---------------------------------------------------------------------------
# The event lines: one per declared kind, every field spelled.
# ---------------------------------------------------------------------------


def test_every_declared_kind_has_a_line() -> None:
    """A kind the payload table gains arrives here as a kind with no line,
    rather than as an event the text shows nothing of."""
    assert set(EVENT_LINES) == set(EVENT_PAYLOADS)


def _event(kind: str, position: int, member: Any) -> tuple[Any, ...]:
    """A well-formed `kind` event holding `member` at field `position` and the
    first member of its shape at every other field."""
    row = EVENT_PAYLOADS[kind]
    return (
        kind,
        *(
            member if index == position else SHAPE_MEMBERS[shape][0]
            for index, shape in enumerate(row, start=1)
        ),
    )


@pytest.mark.parametrize(
    ("kind", "position", "member"),
    [
        (kind, position, member)
        for kind, row in sorted(EVENT_PAYLOADS.items())
        for position, shape in enumerate(row, start=1)
        for member in range(len(SHAPE_MEMBERS[shape]))
    ],
)
def test_a_line_spells_every_field(kind: str, position: int, member: int) -> None:
    """Each member of each field's shape, perturbed as the matrix perturbs it,
    changes the line: a line that leaves a field out, or spells two members
    of one shape alike, reddens the cell that names them.

    red under: leave any one field out of its kind's line in `EVENT_LINES`.
    """
    shape = EVENT_PAYLOADS[kind][position - 1]
    held = SHAPE_MEMBERS[shape][member]
    assert event_line(_event(kind, position, held)) != event_line(
        _event(kind, position, PAYLOAD_PROBES[shape](held))
    )


# Members a line could spell alike where the shapes' own members do not meet:
# a card chosen alone beside a group holding only that card (GOPS logs the two
# back to back), a flag beside the number it equals, nothing beside an empty
# group.
_NEAR_ALIKE: dict[str, tuple[Any, ...]] = {
    "seat": (),
    "label": (),
    "card": (),
    "view": ((), 0, ("9♣",), 1),
    "value": ("9♣", ("9♣",), 0, False, 1, True, (), None),
}


@pytest.mark.parametrize("kind", sorted(EVENT_PAYLOADS))
def test_distinct_events_of_a_kind_have_distinct_lines(kind: str) -> None:
    """Two events spelled alike would show two logs as one, hiding a
    difference the seat is entitled to — the matrix sees it only where the two
    happen to sit side by side, so every pair built from the shapes' members is
    held apart here.

    red under: spell a group of cards as its cards alone; a card chosen alone
    and a group of that one card then read alike.
    """
    fields = [
        SHAPE_MEMBERS[shape] + _NEAR_ALIKE[shape] for shape in EVENT_PAYLOADS[kind]
    ]
    built = {repr(event): event for event in ((kind, *held) for held in product(*fields))}
    lines = {event_line(event) for event in built.values()}
    assert len(lines) == len(built)


@pytest.mark.parametrize(
    ("event", "words"),
    [
        (("nonesuch", 1), "is not declared"),
        (("chose",), "carries 1 field"),
        (("reveal", "Q♠", "hand[0]"), "field 1 of a 'reveal' event is a label"),
        (["chose", "pass"], "is not an observation event"),
    ],
    ids=["an undeclared kind", "a field short", "two fields swapped", "a list"],
)
def test_an_event_the_table_does_not_describe_has_no_line(event: Any, words: str) -> None:
    """Refused in the payload table's own words, before any line reads a
    field it has no reading for."""
    with pytest.raises(AssertionError, match=words):
        event_line(event)


# ---------------------------------------------------------------------------
# The zones: each projection's answer spelled, any other shape refused.
# ---------------------------------------------------------------------------


def _view(**fields: Any) -> SeatView:
    defaults: dict[str, Any] = {"player": 0, "zones": (), "state": (), "obs_log": ()}
    return SeatView(**{**defaults, **fields})


def _zone_row(text: str, label: str) -> str:
    return next(line.split(None, 1)[1] for line in text.splitlines() if line.split()[:1] == [label])


@pytest.mark.parametrize(
    ("shape", "spelled"),
    [
        ((Card("Q", "spades"), Card("2", "clubs")), "2♣ Q♠"),
        ((), "empty"),
        (1, "1 card"),
        (0, "0 cards"),
        (48, "48 cards"),
        (None, "unseen"),
    ],
    ids=["cards", "no cards seen", "one card counted", "none counted", "many counted", "nothing"],
)
def test_a_zone_spells_each_shape_a_projection_answers(shape: Any, spelled: str) -> None:
    text = render_view(_game("hearts.cardlang"), _view(zones=(("hand[0]", shape),)))
    assert _zone_row(text, "hand[0]") == spelled


def test_a_piece_game_counts_pieces() -> None:
    text = render_view(_game("tic-tac-toe.cardlang"), _view(zones=(("box", 5),)))
    assert _zone_row(text, "box") == "5 pieces"


@pytest.mark.parametrize(
    "wrong",
    [["Q♠"], {"Q♠"}, True, 1.0, ("Q♠",)],
    ids=["a list", "a set", "a flag", "a float", "card renderings"],
)
def test_a_zone_shape_no_projection_answers_is_refused(wrong: Any) -> None:
    """Spelled as the nearest shape, it would read as a projection that never
    happened."""
    with pytest.raises(AssertionError, match="no declared rendering"):
        render_view(_game("hearts.cardlang"), _view(zones=(("hand[0]", wrong),)))


# ---------------------------------------------------------------------------
# The card order: the game's own, total over every card.
# ---------------------------------------------------------------------------


_EVERY_CARD = sorted(
    {card for name in COMPONENT_SETS for card in build_deck(name)} | {SYNTHETIC}, key=str
)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_the_card_order_is_defined_for_every_card(short_name: str) -> None:
    """A seat can be shown a card its game's declarations do not name — the
    matrix swaps one in — so the order is total, and a card the declarations
    do not name sorts after every card they do.

    red under: a key that indexes the ranking or the suits without a place for
    a card outside them.
    """
    key = card_order(_game(GAMES[short_name]))
    ordered = sorted(_EVERY_CARD, key=key)
    assert ordered[-1] == SYNTHETIC
    assert sorted(reversed(_EVERY_CARD), key=key) == ordered


def test_a_hand_is_shown_in_the_games_ranking_suit_by_suit() -> None:
    """Hearts ranks aces high and its deck holds the suits clubs, diamonds,
    hearts, spades; a hand shows in that order, highest first within a suit."""
    held = (
        Card("2", "clubs"),
        Card("K", "spades"),
        Card("A", "clubs"),
        Card("10", "clubs"),
        Card("5", "diamonds"),
    )
    text = render_view(_game("hearts.cardlang"), _view(zones=(("hand[0]", held),)))
    assert _zone_row(text, "hand[0]") == "A♣ 10♣ 2♣ 5♦ K♠"


def test_a_game_with_no_ranking_shows_its_decks_own_order() -> None:
    held = (Card("Contessa", "court"), Card("Duke", "court"), Card("Captain", "court"))
    text = render_view(_game("coup.cardlang"), _view(zones=(("hand[0]", held),)))
    assert _zone_row(text, "hand[0]") == "Duke:court Captain:court Contessa:court"


# ---------------------------------------------------------------------------
# The rest of the text: state variables, the turn line, no World.
# ---------------------------------------------------------------------------


def test_a_state_variable_is_spelled_as_the_information_state_spells_it() -> None:
    text = render_view(_game("hearts.cardlang"), _view(state=(("score", {1: 20, 0: 10}),)))
    assert any(line.split() == ["score", "{0:10,1:20}"] for line in text.splitlines())


def test_the_turn_line_shows_only_on_the_seats_own_decision() -> None:
    game = _game("hearts.cardlang")
    assert "your turn to choose" in render_view(game, _view(), your_turn=True)
    assert "turn" not in render_view(game, _view(), your_turn=False)


def test_the_view_needs_no_world() -> None:
    """The text is a function of a Seat View and the game's declarations, and
    this is the cell that would stop being writable if it were not: no
    `RuntimeState` exists here.

    red under: give `render_view` a parameter only the World can supply.
    """
    view = _view(
        player=1,
        zones=(("hand[1]", (Card("5", "clubs"),)), ("hand[0]", 3), ("muck", None)),
        state=(("score", {0: 10, 1: 20}),),
        obs_log=(("chose", "5♣"),),
    )
    text = render_view(_game("hearts.cardlang"), view)
    assert "P1" in text and "5♣" in text and "3 cards" in text and "unseen" in text


# ---------------------------------------------------------------------------
# The load-bearing pin: every visible fact moves the text.
# ---------------------------------------------------------------------------


# The decisions along each game's line the pin probes at: the first few, where
# a deal has just landed, and a sparser run past them, where plays, bids and
# reveals have gathered in the log.
_POSITIONS = frozenset({0, 1, 2, 3, 5, 8, 13, 21, 34, 55})
_SEED = 5


class _Enough(Exception):
    """The line has run past the last position the pin probes."""


def _text(game: n.Game) -> InfoFn:
    def info(player: int, rs: RuntimeState, log: list[tuple[Any, ...]]) -> str:
        return render_view(game, derive(player, rs, log))

    return info


def _walk(
    file_name: str,
    at: Callable[[int, RuntimeState, dict[int, list[tuple[Any, ...]]]], None],
    last: int,
) -> None:
    """Play one seeded line of `file_name` the way `demo` plays it, calling `at`
    with the decision's index, the live World and every seat's log from inside
    the Chooser at each decision up to `last`."""
    game = _game(file_name)
    rng = random.Random(_SEED)
    uniform = random_chooser(rng)
    logs: dict[int, list[tuple[Any, ...]]] = {p: [] for p in range(game.players.low)}
    world: list[RuntimeState] = []
    made = [0]

    def observe(player: int, event: tuple[Any, ...]) -> None:
        logs[player].append(event)

    def choose(player: int, candidates: list[Any], count: int) -> list[Any]:
        taken = iter(uniform(player, candidates, count))

        def decide(_actor: int, _pool: list[Any]) -> Any:
            index = made[0]
            if index > last:
                raise _Enough
            made[0] += 1
            at(index, world[0], logs)
            return next(taken)

        return sequential_decisions(player, candidates, count, decide, observe)

    try:
        play_game(
            game, rng, None, chooser=choose, observer=observe, on_first_decision=world.append
        )
    except (_Enough, GameDescriptionError, IllegalMove):
        # A refusal ends the line where a uniform-random policy took it; the
        # positions probed before it stand.
        pass


def _described(index: int, seat: int, failure: FactFailure) -> str:
    return (
        f"decision {index}, P{seat}: {failure.fact} — expected {failure.expected}, "
        f"{failure.witness}"
    )


@cache
def _pinned(file_name: str) -> tuple[tuple[str, ...], tuple[tuple[str, int], ...], frozenset[str]]:
    """Every failure the matrix finds in the text along `file_name`'s line, what
    it probed, and the event kinds the probed logs held."""
    info = _text(_game(file_name))
    failures: list[str] = []
    totals: dict[str, int] = {}
    kinds: set[str] = set()

    def at(index: int, rs: RuntimeState, logs: dict[int, list[tuple[Any, ...]]]) -> None:
        if index not in _POSITIONS:
            return
        for seat, log in logs.items():
            found, counts = check_visible_facts(rs, log, seat, info_fn=info)
            failures.extend(_described(index, seat, f) for f in found)
            for key, count in counts.items():
                totals[key] = totals.get(key, 0) + count
            kinds.update(event[0] for event in log)

    _walk(file_name, at, max(_POSITIONS))
    return tuple(failures), tuple(sorted(totals.items())), frozenset(kinds)


@pytest.mark.parametrize("short_name", sorted(GAMES))
def test_every_visible_fact_moves_the_text(short_name: str) -> None:
    failures, totals, _ = _pinned(GAMES[short_name])
    assert dict(totals).get("obs_events", 0) > 0, (
        f"{short_name}: the line reached no position with an event to probe"
    )
    assert not failures, "\n".join(failures[:12])


def test_the_pin_meets_every_event_kind_and_every_projection_level() -> None:
    """The per-game cells are only as good as what their positions held."""
    kinds: set[str] = set()
    totals: dict[str, int] = {}
    for file_name in GAMES.values():
        _, counts, seen = _pinned(file_name)
        kinds |= seen
        for key, count in counts:
            totals[key] = totals.get(key, 0) + count
    assert kinds == set(EVENT_PAYLOADS), f"the pin met only {sorted(kinds)}"
    unmet = [level for level in ZONE_PROBES if totals.get(f"zone_{level}", 0) == 0]
    assert not unmet, f"the pin probed no zone projected {unmet}"


# ---------------------------------------------------------------------------
# The plants: each over-hiding text the pin exists to catch, caught.
# ---------------------------------------------------------------------------


def _failures_at(file_name: str, index: int, seat: int, info: InfoFn) -> list[FactFailure]:
    found: list[FactFailure] = []

    def at(at_index: int, rs: RuntimeState, logs: dict[int, list[tuple[Any, ...]]]) -> None:
        if at_index == index:
            found.extend(check_visible_facts(rs, logs[seat], seat, info_fn=info)[0])

    _walk(file_name, at, index)
    return found


def test_the_pin_catches_a_text_that_drops_a_zone_the_seat_sees() -> None:
    game = _game(GAMES["cardlang_kuhn_poker"])

    def without_own_hand(player: int, rs: RuntimeState, log: list[tuple[Any, ...]]) -> str:
        view = derive(player, rs, log)
        kept = tuple((label, zone) for label, zone in view.zones if label != "hand[0]")
        return render_view(game, replace(view, zones=kept))

    failures = _failures_at(GAMES["cardlang_kuhn_poker"], 0, 0, without_own_hand)
    assert failures and all("hand[0]" in f.fact for f in failures)


def test_the_pin_catches_an_event_line_that_drops_a_field(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    line = EVENT_LINES["move"]
    monkeypatch.setitem(
        events.EVENT_LINES,
        "move",
        lambda src, src_view, dst, dst_view, noun: line(src, src_view, dst, None, noun),
    )
    info = _text(_game(GAMES["cardlang_kuhn_poker"]))
    failures = _failures_at(GAMES["cardlang_kuhn_poker"], 0, 0, info)
    assert failures and all("field 4 (view)" in f.fact for f in failures)


def test_the_pin_catches_a_text_that_shows_only_the_latest_events() -> None:
    game = _game(GAMES["cardlang_kuhn_poker"])

    def latest_only(player: int, rs: RuntimeState, log: list[tuple[Any, ...]]) -> str:
        view = derive(player, rs, log)
        return render_view(game, replace(view, obs_log=view.obs_log[-1:]))

    failures = _failures_at(GAMES["cardlang_kuhn_poker"], 0, 0, latest_only)
    assert any("deleted event #0" in f.fact for f in failures)
