"""Big Two's precaution rule held to Pagat's text by an independent oracle.

The rule (https://www.pagat.com/climbing/bigtwo.html, "Scoring"): "When
playing for money, if the person playing after you has only one card left,
you should take precautions … If single cards are being played, you should
play your highest card. If it is your turn to lead, you should lead a
combination more than one card if possible; otherwise you should lead your
highest card. If you ignore these precautions, and as a result the person
after you wins by playing their single card, you have to pay the losses of
all three players."

property:        Every hand of a played match scores as the page says: when
                 the winner goes out on a single card on the ask after the
                 seat before them, and that seat ignored the precaution, that
                 seat alone takes every loser's penalty; every other hand
                 scores 1/2/3 per card left.
domain:          Whole matches of `docs/games/big-two.cardlang`, every ask's
                 live hand and standing play read where the climb round
                 asks, every choice where the chooser makes it; the precaution
                 judged on the seat asked just before the winner's last play,
                 in all three of its situations — a lead, a pass and a single
                 in a trick of singles.
registry:        the combination oracle: tests/test_bigtwo_combinations.py
                 (`classify`, `legal_plays`), which shares nothing with the
                 game file; turn order: the game's `direction:`.
held by:         this differential (a Pin): the rule is written in the game
                 file, and no type could state it.
does not prove:  That the rule's reading of "singles are being played" is the
                 page's when a pass precedes the winner's own lead; this
                 module reads it so, as the game file does, and the shared
                 reading is the judgement both rest on.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_source
from cardlang.runtime import mechanics
from cardlang.runtime.driver import play_game
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState

from cardlang.runtime.values import RANKS, SUITS, Card
from tests.test_bigtwo_combinations import classify, legal_plays

BIG_TWO = Path(__file__).resolve().parent.parent / "docs" / "games" / "big-two.cardlang"


def _penalty(cards_left: int) -> int:
    """The basic 1/2/3-per-card penalty, restated from the page."""
    return cards_left * (1 if cards_left <= 9 else 2 if cards_left <= 12 else 3)


def _single(card: Card) -> tuple[int, ...]:
    found = classify(frozenset({card}))
    assert found is not None
    return found[1]


@dataclass
class _Ask:
    seat: int
    hand: frozenset[Card]
    standing: frozenset[Card] | None  # None: the seat leads
    choice: frozenset[Card] | None = None  # None: a pass


@dataclass
class _Hand:
    asks: list[_Ask] = field(default_factory=list)


def _liable(asks: list[_Ask], seats: int, step: int) -> int | None:
    """The page's verdict on one finished hand: the seat that pays everyone's
    losses, or None."""
    last = asks[-1]
    if len(asks) < 2 or last.choice is None or len(last.choice) != 1 or len(last.hand) != 1:
        return None
    before = asks[-2]
    if (before.seat + step) % seats != last.seat:
        return None
    held = sorted(before.hand, key=_single)
    if before.standing is None:
        if before.choice is None or len(before.choice) != 1:
            return None
        (led,) = before.choice
        could_combine = any(len(k) > 1 for k in legal_plays(list(before.hand)))
        return before.seat if could_combine or _single(held[-1]) > _single(led) else None
    if len(before.standing) != 1:
        return None
    (standing,) = before.standing
    if before.choice is None:
        return before.seat if _single(held[-1]) > _single(standing) else None
    if len(before.choice) != 1:
        return None
    (played,) = before.choice
    return before.seat if _single(held[-1]) > _single(played) else None


def test_every_hand_scores_as_the_page_says(monkeypatch: pytest.MonkeyPatch) -> None:
    """red under: the game file paying the liable seat only its own penalty."""
    game = check_source(BIG_TWO)
    step = -1 if game.direction == "counterclockwise" else 1
    seats = game.players.count
    asked = mechanics.ClimbForm.candidates
    pending: list[_Ask] = []
    hand = _Hand()
    situations: dict[tuple[str, bool], int] = {}

    def recorded(self: mechanics.ClimbForm, actor: int, state: Any, ctx: Any) -> list[Any]:
        current = state["current"]
        cards = self.hands[actor].cards
        pending.append(_Ask(-1, frozenset(cards), None if current is None else frozenset(current.cards)))
        return asked(self, actor, state, ctx)

    rng = random.Random(0)

    def chooser(player: int, candidates: list[Any], n: int) -> list[Any]:
        """A uniform draw, except that a seat leading while the next seat holds
        one card leads its highest single half the time: the one line where
        only the combination it could have led makes it liable, which a
        uniform draw almost never plays."""
        (ask,) = pending
        pending.clear()
        (picked,) = rng.sample(candidates, n)
        held = {a.seat: len(a.hand) - (len(a.choice) if a.choice else 0) for a in hand.asks}
        if ask.standing is None and held.get((player + step) % seats) == 1 and rng.random() < 0.5:
            top = max(ask.hand, key=_single)
            picked = next(c for c in candidates if c != "pass" and tuple(c.cards) == (top,))
        ask.seat = player
        ask.choice = None if picked == "pass" else frozenset(picked.cards)
        hand.asks.append(ask)
        return [picked]

    scores: list[dict[int, int]] = [{p: 0 for p in range(seats)}]

    def tracer(event: str, data: Any) -> None:
        if event != "hand_end":
            return
        asks = hand.asks
        left = {p: 13 for p in range(seats)}
        for ask in asks:
            left[ask.seat] = len(ask.hand) - (len(ask.choice) if ask.choice else 0)
        liable = _liable(asks, seats, step)
        penalties = {p: _penalty(n) for p, n in left.items()}
        if liable is None:
            expected = penalties
        else:
            expected = {p: (sum(penalties.values()) if p == liable else 0) for p in penalties}
        before = scores[-1]
        got = {p: data[p] - before[p] for p in before}
        assert got == expected, (liable, [(a.seat, len(a.hand), a.standing, a.choice) for a in asks[-3:]])
        scores.append(dict(data))
        kind = _situation(asks, seats, step)
        if kind == "lead" and liable is not None and _led_highest(asks[-2]):
            kind = "lead, highest single, could combine"
        if kind is not None:
            situations[(kind, liable is not None)] = situations.get((kind, liable is not None), 0) + 1
        hand.asks = []

    monkeypatch.setattr(mechanics.ClimbForm, "candidates", recorded)
    for seed in range(10):
        scores[:] = [{p: 0 for p in range(seats)}]
        hand.asks = []
        rng.seed(seed)
        play_game(game, random.Random(seed), tracer, chooser=chooser)
    # Each situation the rule judges is reached, both ways.
    cells = {(kind, verdict) for kind in ("lead", "pass", "single") for verdict in (True, False)}
    cells.add(("lead, highest single, could combine", True))
    assert cells <= set(situations), sorted(cells - set(situations))


def _led_highest(ask: _Ask) -> bool:
    """The seat led its highest single, so only the combination it could
    have led makes it liable."""
    assert ask.choice is not None
    (led,) = ask.choice
    return max(ask.hand, key=_single) == led


def _situation(asks: list[_Ask], seats: int, step: int) -> str | None:
    """Which of the rule's three situations the winner's last play followed —
    the seat before them leading a single, passing on a single, or playing a
    single on a single — or None when the precaution was not owed."""
    if len(asks) < 2:
        return None
    last, before = asks[-1], asks[-2]
    if last.choice is None or len(last.choice) != 1 or len(last.hand) != 1:
        return None
    if (before.seat + step) % seats != last.seat:
        return None
    if before.standing is None:
        return "lead" if before.choice is not None and len(before.choice) == 1 else None
    if len(before.standing) != 1:
        return None
    if before.choice is None:
        return "pass"
    return "single" if len(before.choice) == 1 else None


# --- the game file's own functions, against the oracle ------------------------
#
# The combination a leader could have led is judged by `combination_held`;
# a pair decides it on nearly every line play reaches, so its five-card arms
# are reached here, on hands built for each shape.

_DECK = [Card(r, s) for s in SUITS for r in RANKS]


def _no_choice(actor: int, candidates: list[object], k: int) -> list[object]:
    raise AssertionError("the precaution functions make no decision")


def _function(name: str) -> n.FunctionDef:
    return next(f for f in check_source(BIG_TWO).functions if f.name == name)


class _Paused(Exception):
    pass


@cache
def _live_state() -> RuntimeState:
    """The driver's own runtime state for the game file, taken at its first
    decision — every table a function reads built exactly as play builds it."""
    taken: list[RuntimeState] = []

    def take(rs: RuntimeState) -> None:
        taken.append(rs)
        raise _Paused

    with pytest.raises(_Paused):
        play_game(check_source(BIG_TWO), random.Random(0), on_first_decision=take)
    return taken[0]


def _call(name: str, shown: list[Card], **args: object) -> object:
    """The game file's function `name`, evaluated in the driver's live state
    with `shown[0]` holding `shown`."""
    rs = _live_state()
    zone = rs.zones.instance("shown", 0)
    zone.take_all()
    zone.add_all(list(shown))
    return evaluate(_function(name).body, Ctx(rs=rs, chooser=_no_choice, locals=dict(args)))


def test_the_files_single_strength_is_the_pages_single_order() -> None:
    """red under: `single_strength` weighting the suit above the rank."""
    by_file = sorted(_DECK, key=lambda c: _call("single_strength", [], c=c))  # type: ignore[arg-type, return-value]
    assert by_file == sorted(_DECK, key=_single)


def _shaped_hands() -> list[tuple[list[Card], Card]]:
    """(shown cards, led single) over every shape the leader could have led:
    pairs, five of a suit, five in sequence (the wheel and the ace-high
    straight among them), and pairless hands short of five of anything."""
    rng = random.Random(962)
    out: list[tuple[list[Card], Card]] = []
    naturals = ["A", "2", "3", "4", "5", "6", "7", "8", "9", "10", "J", "Q", "K", "A"]
    for start in range(10):
        window = naturals[start : start + 5]
        for missing in range(5):
            cards = [Card(r, rng.choice(SUITS)) for i, r in enumerate(window) if i != missing]
            led = Card(window[missing], rng.choice(SUITS))
            out.append((cards, led))  # a straight completed by the led card
            out.append((cards[:3], led))  # four of a sequence: no straight
    for suit in SUITS:
        ranks = rng.sample(RANKS, 6)
        out.append(([Card(r, suit) for r in ranks[:4]], Card(ranks[4], suit)))  # a flush with the led card
        out.append(([Card(r, suit) for r in ranks[:3]], Card(ranks[4], suit)))  # four of a suit: none
    for _ in range(300):
        size = rng.randrange(1, 9)
        drawn = rng.sample(_DECK, size + 1)
        out.append((drawn[:-1], drawn[-1]))
    return out


def test_the_files_combination_check_is_the_pages() -> None:
    """red under: deleting the straight arms of `combination_held`."""
    seen = {"straight": 0, "flush": 0, "pair": 0, "none": 0}
    for shown, led in _shaped_hands():
        x = _call("single_strength", [], c=led)
        kinds = {
            found[0]
            for k in legal_plays([*shown, led])
            if len(k) > 1 and (found := classify(k)) is not None
        }
        expected = bool(kinds)
        got = _call("combination_held", shown, p=0, x=x)
        assert got == expected, (shown, led, kinds)
        if kinds & {"straight", "straightflush"} and not kinds & {"pair", "flush"}:
            seen["straight"] += 1
        elif "flush" in kinds and "pair" not in kinds:
            seen["flush"] += 1
        elif kinds:
            seen["pair"] += 1
        else:
            seen["none"] += 1
    assert all(seen.values()), seen


def test_the_files_stronger_card_check_is_the_pages() -> None:
    rng = random.Random(9622)
    for _ in range(200):
        drawn = rng.sample(_DECK, rng.randrange(1, 14))
        shown, probe = drawn[:-1], drawn[-1]
        s = _call("single_strength", [], c=probe)
        expected = any(_single(c) > _single(probe) for c in shown)
        assert _call("stronger_held", shown, p=0, s=s) == expected
