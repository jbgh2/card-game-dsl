"""Skat held to its rules source by an execution differential, decision by decision.

Rules: Pagat's Skat (https://www.pagat.com/schafkopf/skat.html), the main
description — the official German and International rules of 1st January
1999 — at a three-player table. The session length is the 36 deals Pagat's
tournament section gives a three-player table, under the main description's
scoring. Where Pagat is silent the referee says so beside the rule it
assumes.

The referee below restates those rules and never imports them from the
engine: who deals, who speaks and who answers in each part of the auction,
the bid ladder, the throw-in, the contracts the declarer may choose and the
announcements a hand game may add, which cards a seat may play, who takes a
trick, when a Null hand ends, what each seat may see, and the declarer's
score. It plays whole games as the chooser and the observer of every seat.
At every decision it compares the engine's whole menu, and who is asked,
with its own derivation from the live hands and the line it has itself
chosen; at every hand end it recomputes the score delta; on every observed
card movement it checks that the observing seat may see the identities it
is shown. The engine is read for the world only — the hands and the skat —
never for a legal set, a winner or a score.

`CHECKS` is the registry of what the referee checks: each divergence it can
note, mapped to the reach counters that show the check ran. The clean run
fails on any divergence and on any reach counter left at zero, so no check
passes because play never reached it; `_note` refuses a key `CHECKS` does
not name, and a static test pins the registry to the referee's own call
sites in both directions. The auction's top rung is reached only by an
aimed policy (`EAGER_SEEDS`, where every seat bids and holds whenever it
may), because a uniform auction never climbs the whole ladder.

`PLANTED` is the reddening record: each row reverts one rule in a copy of
the game file and names the divergence that must fire. A planted run stops
at the first divergence.

Contract:
- Assumes: the chooser sees each decision of docs/games/skat.cardlang with
  the candidate shapes the game offers today — the auction and declaration
  move types as `(name, arg)` tuples, a card play as one `Card` of the
  playing seat's source zone, the skat discard as two `Card`s of the
  declarer's twelve — and the observer sees every card movement from every
  seat's view.
- Establishes: on a green, every divergence key in `CHECKS` stayed at zero
  over `SEEDS` and `EAGER_SEEDS`, and every check's reach counters are
  positive.

Completeness ledger:
  property : the engine's offers, askers, trick winners, visibility and
             scores equal the rules' at every decision, card movement and
             hand end reached
  domain   : `CHECKS` (the referee's notes), pinned to its `_note` call sites
  reach    : the clean run's reach floor, per check
  reddening: `PLANTED`, one row per rule family the game file states. The
             bid ladder and the matador count are game-local Primitives
             (cardlang/runtime/skat.py); this module recomputes both in play
             but plants no fault in Python.

What a green does not prove: anything about decisions the policies do not
reach at this width beyond the reach floor's counters; that the skat stays
hidden from a seat's whole information state rather than from its card
movements (tests/test_skat_skat_secrecy.py holds that, two worlds at a time);
anything at the OpenSpiel seam (tests/openspiel_ready/test_skat.py).
"""

from __future__ import annotations

import ast
import functools
import random
from collections import Counter
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card, Player

SKAT = Path(__file__).parent.parent / "docs" / "games" / "skat.cardlang"
SEEDS = range(6)
EAGER_SEEDS = range(2)
DEALS = 36
SEATS = (0, 1, 2)

# --- the rules, restated -----------------------------------------------------

POINTS = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}
PLAIN_ORDER = {"A": 7, "10": 6, "K": 5, "Q": 4, "9": 3, "8": 2, "7": 1}
NULL_ORDER = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
JACKS = ("clubs", "spades", "hearts", "diamonds")  # highest first
BASE = {"diamonds": 9, "hearts": 10, "spades": 11, "clubs": 12, "grand": 24}
# Null's fixed values, by (hand, ouvert).
NULL_VALUE = {(False, False): 23, (True, False): 35, (False, True): 46, (True, True): 59}
# Announcement levels: each implies the ones below it (Pagat: "an open
# contract includes announcements of Schneider and Schwarz").
NONE, SCHNEIDER, SCHWARZ, OUVERT = 0, 1, 2, 3


def _ladder() -> tuple[int, ...]:
    """Every bid is the value of some possible game: a Suit game's
    multiplier runs from 2 (with or against 1, game) to 18 (eleven
    matadors, game, hand, Schneider and Schwarz each made and announced,
    open), Grand's to 11 (four matadors), plus the four Null values."""
    values = {BASE[s] * m for s in ("diamonds", "hearts", "spades", "clubs") for m in range(2, 19)}
    values |= {BASE["grand"] * m for m in range(2, 12)}
    values |= set(NULL_VALUE.values())
    return tuple(sorted(values))


LADDER = _ladder()


def _next_bid(bid: int) -> int | None:
    return next((v for v in LADDER if v > bid), None)


def _is_trump(c: Card, contract: str) -> bool:
    if contract == "null":
        return False
    return c.rank == "J" or c.suit == contract


def _follow_class(c: Card, contract: str) -> str:
    return "trump" if _is_trump(c, contract) else c.suit


def _strength(c: Card, contract: str) -> int:
    if contract == "null":
        return NULL_ORDER[c.rank]
    if c.rank == "J":
        return 100 + (4 - JACKS.index(c.suit))
    return (50 if _is_trump(c, contract) else 0) + PLAIN_ORDER[c.rank]


def _trick_winner(trick: list[tuple[Player, Card]], contract: str) -> Player:
    led = _follow_class(trick[0][1], contract)
    trumps = [pc for pc in trick if _is_trump(pc[1], contract)]
    pool = trumps or [pc for pc in trick if _follow_class(pc[1], contract) == led]
    return max(pool, key=lambda pc: _strength(pc[1], contract))[0]


def _legal_plays(hand: list[Card], trick: list[tuple[Player, Card]], contract: str) -> set[Card]:
    if not trick:
        return set(hand)
    led = _follow_class(trick[0][1], contract)
    follow = {c for c in hand if _follow_class(c, contract) == led}
    return follow or set(hand)


def _matadors(cards: list[Card], contract: str) -> int:
    """With or against: the unbroken run from the club Jack down the trump
    order, in the declarer's original hand plus the skat."""
    order = [Card("J", s) for s in JACKS]
    if contract != "grand":
        order += [Card(r, contract) for r in ("A", "10", "K", "Q", "9", "8", "7")]
    held = [c in cards for c in order]
    run = 0
    for h in held:
        if h != held[0]:
            break
        run += 1
    return run


def rules_delta(
    *,
    contract: str,
    hand_game: bool,
    level: int,
    bid: int,
    original: list[Card],
    points: int,
    tricks: int,
) -> int:
    """The declarer's score delta for one played hand. `original` is the
    declarer's dealt ten plus the dealt skat; `points` counts the declarer's
    tricks plus the skat as it lies at the end; `tricks` is the declarer's
    trick count."""
    if contract == "null":
        value = NULL_VALUE[(hand_game, level == OUVERT)]
        if tricks == 0 and value >= bid:
            return value
        # Pagat's overbid rule names "the least multiple of the base value of
        # the game actually played which would have fulfilled the bid", and
        # names no base value for Null; its fixed value stands in for one.
        return -2 * (value if value >= bid else value * -(-bid // value))
    base = BASE[contract]
    schneider = points >= 90 or points <= 30 or level >= SCHNEIDER
    schwarz = tricks in (0, 10) or level >= SCHWARZ
    multiplier = (
        _matadors(original, contract)
        + 1
        + hand_game
        + schneider
        + (level >= SCHNEIDER)
        + schwarz
        + (level >= SCHWARZ)
        + (level >= OUVERT)
    )
    value = base * multiplier
    made = points >= 61 and (level < SCHNEIDER or points >= 90) and (level < SCHWARZ or tricks == 10)
    if made and value >= bid:
        return value
    return -2 * (value if value >= bid else base * -(-bid // base))


# --- the engine's vocabulary, read as the rules' choices ----------------------

GAME_TYPES = {
    "choose_suit_game": "suit",
    "declare_grand": "grand",
    "declare_null": "null",
    "declare_null_ouvert": "null_ouvert",
}
ANNOUNCEMENTS = {
    "no_announcement": NONE,
    "announce_schneider": SCHNEIDER,
    "announce_schwarz": SCHWARZ,
    "announce_ouvert": OUVERT,
}
_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _parse(card_str: str) -> Card:
    return Card(card_str[:-1], _SUITS[card_str[-1]])


# --- the registry: each divergence, and the counters that show it was checked --

CHECKS: dict[str, tuple[str, ...]] = {
    "deal.dealer_does_not_rotate": ("deals",),
    "deal.hand_not_ten_cards_and_a_skat_of_two": ("deals",),
    "auction.wrong_seat_asked": ("auction.asks",),
    "auction.offer_wrong_for_seat": ("auction.speaker_asks", "auction.responder_asks"),
    "auction.bid_not_the_next_game_value": ("auction.bids_checked",),
    "auction.responder_not_asked_after_the_last_rung": ("auction.top_rung_reached",),
    "auction.declarer_wrong": ("auction.declarers",),
    "auction.all_pass_offer_wrong": ("auction.all_passed",),
    "declare.offered_to_a_non_declarer": ("declare.asks",),
    "declare.skat_offer_wrong": ("declare.skat_choices",),
    "declare.discard_not_from_the_twelve": ("declare.discards",),
    "declare.game_types_differ": ("declare.game_type_choices",),
    "declare.suits_differ": ("declare.suit_choices",),
    "declare.announcements_differ": ("declare.announcement_choices",),
    "declare.announcements_not_offered": ("declare.hand_suit_or_grand",),
    "play.wrong_seat_leads": ("play.leads",),
    "play.wrong_seat_follows": ("play.follows",),
    "play.offer_differs": ("play.leads", "play.follows"),
    "play.trick_taken_by_the_wrong_seat": ("play.tricks",),
    "play.null_continues_after_the_declarer_takes_a_trick": ("play.null_hands_lost_in_play",),
    "play.hand_ends_early": ("play.hands_played_out",),
    "info.skat_seen": ("info.skat_movements",),
    "info.hand_seen_by_another_seat": ("info.hand_movements",),
    "info.ouvert_hand_not_shown": ("info.ouvert_first_leads",),
    "hand.score_delta_differs": (
        "hand.score_delta_agrees",
        "hands.suit",
        "hands.grand",
        "hands.null",
        "hands.null_hand",
        "hands.null_ouvert",
        "hands.null_ouvert_hand",
        "hands.hand_game",
        "hands.announced_schneider",
        "hands.announced_schwarz",
        "hands.announced_ouvert",
        "hands.overbid",
        "hands.lost",
        "hands.won",
    ),
    "hand.defender_score_moved": ("hand.score_delta_agrees",),
    "hand.thrown_in_scored": ("hands.thrown_in",),
    "game.not_thirty_six_deals": ("games",),
    "game.winner_not_the_highest_score": ("games",),
}


class Diverged(Exception):
    """A planted run's first divergence."""

    def __init__(self, key: str, detail: str) -> None:
        super().__init__(f"{key}: {detail}")
        self.key = key


class Referee:
    """The chooser and the observer that hold one game to the rules."""

    def __init__(self, seed: int, *, eager: bool = False, stop: bool = False) -> None:
        self.rng = random.Random(7000 + seed)
        self.eager = eager
        self.stop = stop
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = {}
        self.rs: RuntimeState | None = None
        self.deals = 0
        self.first_dealer: Player | None = None
        self.scores_at_deal: dict[int, int] | None = None
        self.gathering = True
        self._reset_hand()

    # -- bookkeeping -----------------------------------------------------------

    def _note(self, key: str, detail: str = "") -> None:
        assert key in CHECKS, f"the referee noted {key!r}, which CHECKS does not name"
        if self.stop:
            raise Diverged(key, f"deal {self.deals}: {detail}")
        self.counts[key] += 1
        if len(self.examples.setdefault(key, [])) < 3:
            self.examples[key].append(f"deal {self.deals}: {detail}")

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def _state(self) -> RuntimeState:
        assert self.rs is not None
        return self.rs

    def _held(self, p: Player) -> list[Card]:
        """Every card seat `p` holds, concealed or exposed."""
        zones = self._state().zones
        cards = list(zones.families["hand"][p].cards)
        if "open_hand" in zones.families:
            cards += list(zones.families["open_hand"][p].cards)
        return cards

    def _skat(self) -> list[Card]:
        return list(self._state().zones.singles["skat"].cards)

    def _reset_hand(self) -> None:
        self.stage = "deal"
        self.dealer: Player | None = None
        self.bid = 0
        self.part = 0
        self.speaker: Player | None = None
        self.responder: Player | None = None
        self.turn: Player | None = None
        self.survivor: Player | None = None
        self.declarer: Player | None = None
        self.thrown = False
        self.hand_game = False
        self.contract: str | None = None
        self.null_ouvert = False
        self.level = NONE
        self.announcement_asked = False
        self.top_rung_pending = False
        self.discard: list[Card] = []
        self.original: list[Card] = []
        self.trick: list[tuple[Player, Card]] = []
        self.leader: Player | None = None
        self.won: dict[Player, list[Card]] = {p: [] for p in SEATS}
        self.tricks: Counter[Player] = Counter()
        self.ended_by_null_trick = False
        self.known_to: dict[Player, set[Card]] = {p: set() for p in SEATS}

    # -- the hand's start and end --------------------------------------------------

    def _start_deal(self) -> None:
        """The first decision of a deal: the deal is complete, the hands and the
        skat are the rules' sizes, and the dealer is the previous deal's left."""
        rs = self._state()
        self.deals += 1
        self.counts["deals"] += 1
        sizes = [len(self._held(p)) for p in SEATS]
        if sizes != [10, 10, 10] or len(self._skat()) != 2:
            self._note("deal.hand_not_ten_cards_and_a_skat_of_two", f"hands {sizes} skat {len(self._skat())}")
        self.original_hands = {p: list(self._held(p)) for p in SEATS}
        self.original_skat = self._skat()
        self.scores_at_deal = dict(rs.get("score"))
        self.stage = "auction"

    def _seat(self, offset: int) -> Player:
        assert self.dealer is not None
        return Player((self.dealer + offset) % 3)

    def settle(self, scores: dict[int, int]) -> None:
        """The rules' score delta for the deal just played, against the game's."""
        if self.scores_at_deal is None:
            return
        delta = {p: scores[p] - self.scores_at_deal[p] for p in SEATS}
        self.scores_at_deal = None
        if self.thrown:
            self.counts["hands.thrown_in"] += 1
            if any(delta.values()):
                self._note("hand.thrown_in_scored", f"delta {delta}")
            return
        if self.declarer is None or self.contract is None:
            return
        d = self.declarer
        if not self.ended_by_null_trick:
            if sum(self.tricks.values()) != 10:
                self._note("play.hand_ends_early", f"{sum(self.tricks.values())} tricks")
            else:
                self.counts["play.hands_played_out"] += 1
        for p in SEATS:
            if p != d and delta[p]:
                self._note("hand.defender_score_moved", f"P{p} moved {delta[p]}")
        contract = "null" if self.contract == "null_ouvert" else self.contract
        level = OUVERT if self.contract == "null_ouvert" else self.level
        skat_now = self.original_skat if self.hand_game else self.discard
        points = sum(POINTS[c.rank] for c in self.won[d] + skat_now)
        want = rules_delta(
            contract=contract,
            hand_game=self.hand_game,
            level=level,
            bid=self.bid,
            original=self.original_hands[d] + self.original_skat,
            points=points,
            tricks=self.tricks[d],
        )
        self._count_hand(contract, level, want)
        if delta[d] != want:
            self._note(
                "hand.score_delta_differs",
                f"{self.contract} hand={self.hand_game} level={level} bid={self.bid} "
                f"points={points} tricks={self.tricks[d]} rules {want} game {delta[d]}",
            )
        else:
            self.counts["hand.score_delta_agrees"] += 1

    def _count_hand(self, contract: str, level: int, want: int) -> None:
        if contract == "null":
            key = "hands.null" + ("_ouvert" if level == OUVERT else "") + ("_hand" if self.hand_game else "")
            self.counts[key] += 1
        else:
            self.counts["hands.grand" if contract == "grand" else "hands.suit"] += 1
            for lvl, name in ((SCHNEIDER, "schneider"), (SCHWARZ, "schwarz"), (OUVERT, "ouvert")):
                if level == lvl:
                    self.counts[f"hands.announced_{name}"] += 1
        if self.hand_game:
            self.counts["hands.hand_game"] += 1
        self.counts["hands.won" if want > 0 else "hands.lost"] += 1
        if want < 0 and self.bid > self._value_bound(contract, level):
            self.counts["hands.overbid"] += 1

    def _value_bound(self, contract: str, level: int) -> int:
        """A floor under the game value, enough to count an overbid hand."""
        if contract == "null":
            return NULL_VALUE[(self.hand_game, level == OUVERT)]
        return BASE[contract] * (1 + 1 + self.hand_game + 2 * level - (level == OUVERT))

    # -- the observer: what each seat is shown, and the tricks -------------------

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if event[0] != "move":
            return
        _, src, src_view, dst, dst_view = event
        source, target = str(src), str(dst)
        if target == "deck":
            if not self.gathering and player == 0:
                # The next deal's gather: the hand just played is scored.
                self.gathering = True
                self.settle(dict(self._state().get("score")))
            return
        if source == "deck":
            if self.gathering and player == 0:
                self.gathering = False
                self._reset_hand()
            return
        shown = [_parse(x) for x in (dst_view if isinstance(dst_view, tuple) else ())]
        shown += [_parse(x) for x in (src_view if isinstance(src_view, tuple) else ())]
        self._check_shown(player, source, target, shown)
        if player == 0 and source == "trick_pile" and target.startswith("captured["):
            self._trick_taken(Player(int(target[len("captured[") : -1])))

    def _check_shown(self, player: Player, source: str, target: str, shown: list[Card]) -> None:
        if "skat" in (source, target):
            self.counts["info.skat_movements"] += 1
            # Only the declarer, picking the skat up and laying the discard
            # away, ever sees a skat card before the play is over.
            if shown and not (player == self.declarer and not self.hand_game):
                self._note("info.skat_seen", f"P{player} saw {source}->{target} {shown}")
            return
        for zone in (source, target):
            if zone.startswith("hand["):
                owner = int(zone[len("hand[") : -1])
                self.counts["info.hand_movements"] += 1
                # A card leaving a hand for the trick is played face up; an
                # ouvert declarer's cards are laid face up for every seat.
                public = target == "trick_pile" or (target.startswith("open_hand[") and self._ouvert())
                if shown and owner != player and not public:
                    self._note("info.hand_seen_by_another_seat", f"P{player} saw {source}->{target} {shown}")
        if target.startswith("open_hand["):
            self.known_to[player] |= set(shown)

    def _ouvert(self) -> bool:
        return self.level == OUVERT or self.contract == "null_ouvert"

    def _trick_taken(self, taker: Player) -> None:
        contract = "null" if self.contract == "null_ouvert" else self.contract
        assert contract is not None
        self.counts["play.tricks"] += 1
        if len(self.trick) != 3:
            self._note("play.trick_taken_by_the_wrong_seat", f"a trick of {len(self.trick)} cards")
        else:
            want = _trick_winner(self.trick, contract)
            if taker != want:
                self._note("play.trick_taken_by_the_wrong_seat", f"{self.trick} taken by P{taker}, rules P{want}")
        self.won[taker] += [c for _, c in self.trick]
        self.tricks[taker] += 1
        self.trick = []
        self.leader = taker
        if contract == "null" and taker == self.declarer:
            # "If you take a trick, you have lost and the play of the hand
            # ceases at that point."
            self.ended_by_null_trick = True
            self.counts["play.null_hands_lost_in_play"] += 1

    # -- the chooser: every decision, against the rules ---------------------------

    def __call__(self, player: Player, cands: list[Any], count: int) -> list[Any]:
        if self.stage == "deal":
            self._start_deal()
        names = {x[0] for x in cands if isinstance(x, tuple) and x}
        cards = [x for x in cands if isinstance(x, Card)]
        if names & {"bid", "yes", "pass"}:
            return self._auction(player, cands, names)
        if names & {"play_at_eighteen", "throw_in"}:
            return self._all_passed(player, cands, names)
        if names & {"pick_up_skat", "declare_hand"}:
            return self._skat_choice(player, cands, names)
        if names & set(GAME_TYPES):
            return self._game_type(player, cands, names)
        if names & {"declare_suit"}:
            return self._suit(player, cands)
        if names & set(ANNOUNCEMENTS):
            return self._announce(player, cands, names)
        if count == 2:
            return self._discard(player, cards)
        return self._play(player, cards)

    # The auction ------------------------------------------------------------------

    def _auction(self, player: Player, cands: list[Any], names: set[str]) -> list[Any]:
        if self.part == 0:
            # The first ask of a deal names the dealer: middlehand speaks first.
            self.dealer = Player((player - 2) % 3)
            if self.first_dealer is None:
                self.first_dealer = self.dealer
            want_dealer = (self.first_dealer + self.deals - 1) % 3
            if self.dealer != want_dealer:
                self._note("deal.dealer_does_not_rotate", f"middlehand P{player}, want dealer P{want_dealer}")
                self.dealer = Player(want_dealer)
            self.part = 1
            self.speaker, self.responder = self._seat(2), self._seat(1)
            self.turn = self.speaker
        self.counts["auction.asks"] += 1
        self._check_bid()
        if self.top_rung_pending and player != self.turn:
            # The engine moved on past the last rung without the responder's
            # answer; read on along the engine's line, the responder holding.
            self._note("auction.responder_not_asked_after_the_last_rung", f"bid {self.bid}, P{self.turn} not asked")
            self.top_rung_pending = False
            assert self.responder is not None
            self._part_over(self.responder)
        if player != self.turn:
            self._note("auction.wrong_seat_asked", f"P{player} asked, P{self.turn} to speak (part {self.part})")
        if self.turn == self.speaker:
            self.counts["auction.speaker_asks"] += 1
            want = {"pass"} | ({"bid"} if _next_bid(self.bid) is not None else set())
        else:
            self.counts["auction.responder_asks"] += 1
            want = {"yes", "pass"}
        if names != want:
            self._note("auction.offer_wrong_for_seat", f"P{player} offered {sorted(names)}, rules {sorted(want)}")
        pick = self._auction_pick(cands, names)
        said = pick[0][0]
        if said == "bid":
            nxt = _next_bid(self.bid)
            assert nxt is not None
            self.bid = nxt
            if _next_bid(self.bid) is None:
                self.counts["auction.top_rung_reached"] += 1
                self.top_rung_pending = True
            self.turn = self.responder
        elif said == "yes":
            self.top_rung_pending = False
            self.turn = self.speaker
        else:
            self.top_rung_pending = False
            assert self.speaker is not None and self.responder is not None
            survivor = self.responder if player == self.speaker else self.speaker
            self._part_over(survivor)
        return pick

    def _check_bid(self) -> None:
        """The standing bid on the table is the rules' rung: each bid is the
        next game value above the last."""
        if self.bid:
            self.counts["auction.bids_checked"] += 1
            standing = self._state().get("working_bid")
            if standing != self.bid:
                self._note("auction.bid_not_the_next_game_value", f"table {standing}, rules {self.bid}")
                self.bid = int(standing)

    def _auction_pick(self, cands: list[Any], names: set[str]) -> list[Any]:
        if self.eager:
            for word in ("bid", "yes"):
                if word in names:
                    return [next(c for c in cands if c[0] == word)]
        return [self.rng.choice(cands)]

    def _part_over(self, survivor: Player) -> None:
        if self.part == 1:
            self.part = 2
            self.speaker, self.responder = self._seat(0), survivor
            self.turn = self.speaker
            return
        self.part = 3
        self.survivor = survivor
        self.stage = "declare"

    def _expect_auction_over(self) -> None:
        """A decision after the auction: the auction must have ended as the rules
        end it, with the speaker unable to go on."""
        if self.part == 3:
            return
        # The engine stopped asking: a speaker with no rung left may be skipped
        # (their pass is forced), but a responder owes an answer to the last bid.
        if self.top_rung_pending:
            self._note("auction.responder_not_asked_after_the_last_rung", f"bid {self.bid}, P{self.turn} not asked")
            self.top_rung_pending = False
            assert self.speaker is not None and self.responder is not None
            # Read on as if the responder had held: the engine's own line.
            self.turn = self.speaker
        while self.part != 3:
            assert self.turn == self.speaker and self.responder is not None
            if _next_bid(self.bid) is not None:
                self._note("auction.wrong_seat_asked", f"part {self.part} ended with P{self.turn} still able to bid")
            self._part_over(self.responder)

    def _all_passed(self, player: Player, cands: list[Any], names: set[str]) -> list[Any]:
        self._expect_auction_over()
        self.counts["auction.all_passed"] += 1
        forehand = self._seat(1)
        if self.bid != 0 or player != forehand or names != {"play_at_eighteen", "throw_in"}:
            self._note(
                "auction.all_pass_offer_wrong", f"P{player} offered {sorted(names)} at bid {self.bid}, forehand P{forehand}"
            )
        pick = [self.rng.choice(cands)]
        if pick[0][0] == "throw_in":
            self.thrown = True
            self.stage = "deal"
        else:
            self.bid = 18
        self.declarer = player
        return pick

    # The declaration ---------------------------------------------------------------

    def _declarer_asked(self, player: Player) -> None:
        self.counts["declare.asks"] += 1
        if self.declarer is None:
            self._check_bid()
            self._expect_auction_over()
            self.counts["auction.declarers"] += 1
            if self.bid == 0:
                # Forehand must have been asked to play at 18 or throw in.
                self._note("auction.all_pass_offer_wrong", "the all-pass choice was not offered")
            self.declarer = self.survivor
            if player != self.survivor:
                self._note("auction.declarer_wrong", f"P{player} declares, rules P{self.survivor} at {self.bid}")
        if player != self.declarer:
            self._note("declare.offered_to_a_non_declarer", f"P{player} asked, declarer P{self.declarer}")

    def _skat_choice(self, player: Player, cands: list[Any], names: set[str]) -> list[Any]:
        self._declarer_asked(player)
        self.counts["declare.skat_choices"] += 1
        if names != {"pick_up_skat", "declare_hand"}:
            self._note("declare.skat_offer_wrong", f"offered {sorted(names)}")
        pick = [self.rng.choice(cands)]
        self.hand_game = pick[0][0] == "declare_hand"
        return pick

    def _discard(self, player: Player, cards: list[Card]) -> list[Any]:
        self.counts["declare.discards"] += 1
        twelve = set(self.original_hands[player] + self.original_skat)
        if player != self.declarer or self.hand_game or set(cards) != twelve or len(cards) != 12:
            self._note("declare.discard_not_from_the_twelve", f"P{player} offered {len(cards)} cards")
        pick = self.rng.sample(cards, 2)
        self.discard = list(pick)
        return pick

    def _game_type(self, player: Player, cands: list[Any], names: set[str]) -> list[Any]:
        self._declarer_asked(player)
        self.counts["declare.game_type_choices"] += 1
        offered = {GAME_TYPES[x] for x in names if x in GAME_TYPES}
        want = {"suit", "grand", "null", "null_ouvert"}
        if offered != want or names - set(GAME_TYPES):
            self._note("declare.game_types_differ", f"offered {sorted(offered)}, rules {sorted(want)}")
        pick = [self.rng.choice(cands)]
        chosen = GAME_TYPES[pick[0][0]]
        self.contract = None if chosen == "suit" else chosen
        if chosen != "suit":
            self._contract_fixed()
        return pick

    def _suit(self, player: Player, cands: list[Any]) -> list[Any]:
        self._declarer_asked(player)
        self.counts["declare.suit_choices"] += 1
        offered = {x[1] for x in cands}
        if offered != set(JACKS) or len(cands) != 4 or self.contract is not None:
            self._note("declare.suits_differ", f"offered {sorted(map(str, offered))}")
        pick = [self.rng.choice(cands)]
        self.contract = str(pick[0][1])
        self._contract_fixed()
        return pick

    def _contract_fixed(self) -> None:
        if self.contract == "null_ouvert":
            self.null_ouvert = True
        self.stage = "announce" if self.hand_game and self.contract not in ("null", "null_ouvert") else "play"

    def _announce(self, player: Player, cands: list[Any], names: set[str]) -> list[Any]:
        self._declarer_asked(player)
        self.counts["declare.announcement_choices"] += 1
        if self.stage != "announce" or names != set(ANNOUNCEMENTS):
            self._note("declare.announcements_differ", f"offered {sorted(names)} at {self.stage}")
        self.announcement_asked = True
        pick = [self.rng.choice(cands)]
        self.level = ANNOUNCEMENTS[pick[0][0]]
        self.stage = "play"
        return pick

    # The play -------------------------------------------------------------------------

    def _play(self, player: Player, cards: list[Card]) -> list[Any]:
        contract = "null" if self.contract == "null_ouvert" else self.contract
        if self.stage == "announce":
            self.counts["declare.hand_suit_or_grand"] += 1
            self._note("declare.announcements_not_offered", f"{self.contract} hand, first lead with no announcement asked")
            self.stage = "play"
        elif self.hand_game and contract not in ("null", None) and self.leader is None:
            self.counts["declare.hand_suit_or_grand"] += 1
        assert contract is not None, "a card is played before the contract is known"
        if self.ended_by_null_trick:
            self._note("play.null_continues_after_the_declarer_takes_a_trick", f"P{player} asked to play")
            self.ended_by_null_trick = False
        if self.leader is None:
            self.leader = self._seat(1)  # forehand leads the first trick
            if self._ouvert():
                self.counts["info.ouvert_first_leads"] += 1
                assert self.declarer is not None
                hand = set(self._held(self.declarer))
                for p in SEATS:
                    if p != self.declarer and not hand <= self.known_to[p]:
                        self._note("info.ouvert_hand_not_shown", f"P{p} has not seen the declarer's hand")
        if not self.trick:
            self.counts["play.leads"] += 1
            if player != self.leader:
                self._note("play.wrong_seat_leads", f"P{player} leads, rules P{self.leader}")
        else:
            self.counts["play.follows"] += 1
            want = Player((self.trick[-1][0] + 1) % 3)
            if player != want:
                self._note("play.wrong_seat_follows", f"P{player} plays, rules P{want}")
        legal = _legal_plays(self._held(player), self.trick, contract)
        if set(cards) != legal or len(cards) != len(legal):
            self._note(
                "play.offer_differs",
                f"P{player} offered {sorted(map(str, cards))}, rules {sorted(map(str, legal))}",
            )
        pick = self.rng.choice(cards)
        self.trick.append((player, pick))
        return [pick]


# --- running it ----------------------------------------------------------------


def referee_games(game: n.Game, seeds: range, *, eager: bool = False, stop: bool = False) -> Referee:
    """Play one game per seed under one referee's counts; with `stop`, the
    first divergence raises `Diverged`."""
    total = Referee(0)
    for seed in seeds:
        ref = Referee(seed, eager=eager, stop=stop)

        result = play_game(game, random.Random(seed), None, ref, ref.observer, on_first_decision=ref.attach)
        ref.settle(dict(result.scores))
        ref.counts["games"] += 1
        if ref.deals != DEALS:
            ref._note("game.not_thirty_six_deals", f"{ref.deals} deals")
        top = max(result.scores.values())
        if result.winners != {p for p, s in result.scores.items() if s == top}:
            ref._note("game.winner_not_the_highest_score", str(result))
        total.counts.update(ref.counts)
        for key, found in ref.examples.items():
            total.examples.setdefault(key, []).extend(f"seed {seed}: {x}" for x in found)
    return total


@functools.lru_cache(maxsize=None)
def _clean_run() -> Referee:
    game = check_dsl(SKAT.read_text(), str(SKAT))
    ref = referee_games(game, SEEDS)
    eager = referee_games(game, EAGER_SEEDS, eager=True)
    ref.counts.update(eager.counts)
    for key, found in eager.examples.items():
        ref.examples.setdefault(key, []).extend(f"eager {x}" for x in found)
    return ref


def test_skat_plays_its_rules() -> None:
    ref = _clean_run()
    diverged = {k: ref.examples.get(k, [])[:3] for k in CHECKS if ref.counts[k]}
    assert not diverged, diverged


def test_every_check_was_reached() -> None:
    counts = _clean_run().counts
    unreached = {k: [r for r in reach if not counts[r]] for k, reach in CHECKS.items()}
    assert not {k: v for k, v in unreached.items() if v}, unreached


def test_checks_name_exactly_the_referees_notes() -> None:
    """`CHECKS` and the referee's `_note` call sites name the same keys, so no
    check runs unregistered and no registered check is never made."""
    tree = ast.parse(Path(__file__).read_text())
    noted: set[str] = set()
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "_note"
            and node.args
        ):
            first = node.args[0]
            assert isinstance(first, ast.Constant) and isinstance(first.value, str)
            noted.add(first.value)
    assert noted == set(CHECKS)


def test_the_ladder_is_the_rules_game_values() -> None:
    """The bid ladder is every reachable game value: Pagat's opening rungs,
    and the top rung a Grand with four matadors played open.

    red under: `_ladder` dropping the Null values or capping a multiplier
    one short."""
    assert LADDER[:20] == (18, 20, 22, 23, 24, 27, 30, 33, 35, 36, 40, 44, 45, 46, 48, 50, 54, 55, 59, 60)
    assert LADDER[-1] == 24 * 11


def test_the_scoring_restates_pagats_examples() -> None:
    """Pagat's worked examples, through `rules_delta`.

    red under: dropping the overbid rule's least multiple, or the declarer's
    own Schneider."""
    clubs = [Card(r, s) for r, s in (("J", "hearts"), ("J", "diamonds"), ("10", "clubs"), ("K", "clubs"))]
    # Clubs Hand, bid 46, with 1 (the skat held the club Jack): game value 36
    # is under the bid, so M loses twice 48, the least multiple of 12 >= 46.
    with_one = clubs + [Card("J", "clubs")]
    assert rules_delta(
        contract="clubs", hand_game=True, level=NONE, bid=46, original=with_one, points=74, tricks=6
    ) == -96
    # The same hand with 95 card points: Schneider lifts it to 48 >= 46.
    assert rules_delta(
        contract="clubs", hand_game=True, level=NONE, bid=46, original=with_one, points=95, tricks=8
    ) == 48
    # Spades without 2 taking 28 card points: without 2, game 3, Schneider 4.
    without_two = [Card("J", "hearts"), Card("A", "spades")]
    assert rules_delta(
        contract="spades", hand_game=False, level=NONE, bid=18, original=without_two, points=28, tricks=2
    ) == -88
    # Null Ouvert Hand lost: twice 59.
    assert rules_delta(
        contract="null", hand_game=True, level=OUVERT, bid=18, original=[], points=0, tricks=1
    ) == -118


# --- the reddening record --------------------------------------------------------

# Each row reverts one rule in a copy of the game file: the rule, the edits
# (each `old` occurs exactly once), and the divergences any one of which
# must fire.
PLANTED: list[tuple[str, list[tuple[str, str]], set[str]]] = [
    (
        "the dealer does not rotate",
        [("dealer := dealer offset_by left", "dealer := dealer")],
        {"deal.dealer_does_not_rotate"},
    ),
    (
        "the last rung ends the exchange before the responder answers",
        [
            (
                "            until passer is not none {\n        offer to bidder one of [bid, yes, pass]\n      }\n      let w1",
                "            until passer is not none or skat_next_bid(working_bid) is 0 {\n"
                "        offer to bidder one of [bid, yes, pass]\n      }\n      let w1",
            )
        ],
        {"auction.responder_not_asked_after_the_last_rung"},
    ),
    (
        "Null Ouvert is not offered",
        [
            (
                # The move type stays offered where no play reaches it: a move
                # type nothing offers is the checker's to refuse, and this row
                # is the referee's.
                "offer to declarer one of [choose_suit_game, declare_grand, declare_null, declare_null_ouvert]",
                "offer to declarer one of [choose_suit_game, declare_grand, declare_null]\n"
                "      if false { offer to declarer one of [declare_null_ouvert] }",
            )
        ],
        {"declare.game_types_differ"},
    ),
    (
        "a hand game announces nothing",
        [("if hand_mode and not is_null {", "if false {")],
        {"declare.announcements_not_offered"},
    ),
    (
        "a Null hand plays on after the declarer takes a trick",
        [("\n                   or (is_null and declarer_tricks > 0) {", " {")],
        {"play.null_continues_after_the_declarer_takes_a_trick"},
    ),
    (
        "the ouvert hand is laid down face down",
        [("open_hand[player] : PublicHand<player>", "open_hand[player] : Hand<player>")],
        {"info.ouvert_hand_not_shown"},
    ),
    (
        "the skat lies face up",
        [("skat             : FaceDownPile", "skat             : Discard")],
        {"info.skat_seen"},
    ),
    (
        "forehand does not lead the first trick",
        [("leader := dealer offset_by left              // forehand", "leader := dealer              // forehand")],
        {"play.wrong_seat_leads"},
    ),
    (
        "a seat may renounce",
        [("if can_follow(p) then follows_lead(c, trick_pile)", "if false then follows_lead(c, trick_pile)")],
        {"play.offer_differs"},
    ),
    (
        "the trick's leader takes it",
        [("move all cards from trick_pile to captured[w]", "move all cards from trick_pile to captured[leader]")],
        {"play.trick_taken_by_the_wrong_seat"},
    ),
    (
        "a thrown-in hand scores",
        [("effect { thrown := true }", "effect {\n    thrown := true\n    score[actor] -= 1\n  }")],
        {"hand.thrown_in_scored"},
    ),
    (
        "Grand's base value is 20",
        [("if is_grand then 24", "if is_grand then 20")],
        {"hand.score_delta_differs"},
    ),
    (
        "Null Ouvert Hand is worth 69",
        [("(if hand_mode then 59 else 46)", "(if hand_mode then 69 else 46)")],
        {"hand.score_delta_differs"},
    ),
    (
        "the declarer's own Schneider does not count",
        [("pts >= 90 or pts <= 30 or schneider_announced", "pts >= 90 or schneider_announced")],
        {"hand.score_delta_differs"},
    ),
    (
        "an announced Schneider not made still wins",
        [("(pts >= 90 or not schneider_announced)", "(true or not schneider_announced)")],
        {"hand.score_delta_differs"},
    ),
    (
        "an overbid game loses twice its own value",
        [("else base * (working_bid divided by base rounded up)", "else game_value")],
        {"hand.score_delta_differs"},
    ),
]


def _planted(edits: list[tuple[str, str]]) -> str:
    text = SKAT.read_text()
    for old, new in edits:
        assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times in skat.cardlang"
        text = text.replace(old, new)
    return text


@pytest.mark.parametrize("rule, edits, fires", PLANTED, ids=[row[0] for row in PLANTED])
def test_a_planted_fault_is_caught(rule: str, edits: list[tuple[str, str]], fires: set[str]) -> None:
    assert fires <= set(CHECKS)
    game = check_dsl(_planted(edits), f"skat.cardlang ({rule})")
    with pytest.raises(Diverged) as caught:
        referee_games(game, range(4), stop=True)
        referee_games(game, range(1), eager=True, stop=True)
    assert caught.value.key in fires, str(caught.value)
