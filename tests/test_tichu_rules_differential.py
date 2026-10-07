"""Tichu held to its rules source by an execution differential, decision by decision.

Rules: the Fata Morgana English edition and its FAQ
(https://fatamorgana.ch/fatamorgana/tichu/english-rules,
https://fatamorgana.ch/fatamorgana/tichu/faq), with the operator's rulings
where the text leaves a choice: the dealer is the previous hand's first
player out, seat 0 dealing the first hand (issue #781); the eighth card's
grand tichu poll asks exactly two laps (issue #785); the post-push small
tichu poll runs from the dealer before anyone learns who leads, and the
in-trick poll only once the hand's first lead is made (issue #786).

The referee below restates those rules and never imports them from the
engine: what a card-set may be played as, what beats what, the wish, the
bombs a window offers, who may call and when the calls are polled, who
leads, who takes a trick, the Dragon's gift, the finishing order, the
tailender, the double victory, the hand's score and the game's end. It
plays whole games under `tichu_reference_policy` as the chooser and an
observer. At every decision it compares the engine's whole menu with its
own derivation from the live hand and the plays it has itself made — each
play as a reading (cards, kind, length, key), never as a bare card-set, and
each call, gift and push as the exact set of choices the rules give — and
who is asked; at every hand end it recomputes the score delta. Who is asked
in a climbing trick's ring and bomb window is held by
tests/test_tichu_bombs.py and the order of grand tichu calls by
tests/test_tichu_grand_order.py; the referee holds who is asked everywhere
else: the lead, the small tichu polls, the wish, the Dragon's gift and the
push. The engine is read for the world only — the hands, the
standing play, the scores, and the cards it moves — never for a legal set,
a winner or a score.

`CHECKS` is the registry of what the referee checks: each divergence it can
note, mapped to the reach counters that show the check ran. The clean run
fails on any divergence and on any reach counter left at zero, so no check
passes because play never reached it; `_note` refuses a key `CHECKS` does
not name, and a static test pins the registry to the referee's own call
sites in both directions.

`PLANTED` is the reddening record: each row reverts one rule in a copy of
the game file and names the divergence that must fire. A planted run stops
at the first divergence, so each row costs a hand or two, not a game.

Contract:
- Assumes: the chooser sees each decision of docs/games/tichu.cardlang with
  the candidate shapes the game offers today — `Play` combinations, `pass`,
  `no_bomb`, the wish tokens, the call and Dragon move types, and the push's
  three-card draw — and the observer sees every card movement from seat 0's
  view.
- Establishes: on a green, every divergence key in `CHECKS` stayed at zero
  over `SEEDS`, and every check's reach counters are positive.

Completeness ledger:
  property : the engine's offers and scores equal the rules' at every
             decision and every hand end reached
  domain   : `CHECKS` (the referee's notes), pinned to its `_note` call sites
  reach    : the clean run's reach floor, per check
  reddening: `PLANTED`, one row per rule family the game file states. The
             combination engine's own rules are held by
             tests/test_tichu_combinations.py, the bomb window's chain of asks
             by tests/test_tichu_bombs.py, the order of grand tichu calls by
             tests/test_tichu_grand_order.py and the secrecy of the lead by
             tests/test_tichu_lead_secrecy.py; this module rechecks their
             offered sets in play but plants no fault in Python primitives.
             The push (`push.candidates_not_the_whole_hand`) and the winners
             (`game.winner_not_the_higher_score`) carry no planted row: no
             one-line mutation of the game file breaks either while the game
             still checks.

What a green does not prove: anything about decisions the reference policy
does not reach at this width beyond the reach floor's counters; a second-lap
grand tichu call on eight cards (tests/test_tichu_grand_order.py aims a run
at it); anything at the OpenSpiel seam (tests/openspiel_ready/test_tichu.py).
"""

from __future__ import annotations

import ast
import functools
import random
from collections import Counter
from itertools import combinations
from pathlib import Path
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.tichu_combinations import Play
from cardlang.runtime.values import Card, Player, build_deck
from tests.test_playout_tichu import tichu_reference_policy

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
SEEDS = range(2)

# --- the rules, restated -----------------------------------------------------

VAL = {str(v): v for v in range(2, 11)} | {"J": 11, "Q": 12, "K": 13, "A": 14}
POINTS = {"K": 10, "10": 10, "5": 5, "Dragon": 25, "Phoenix": -25}
TEAM = {0: 0, 1: 1, 2: 0, 3: 1}
WISH_RANK = {f"wish_{r}": v for r, v in VAL.items()}
# The Phoenix single's key depends on what it is played over; it is reported
# as this sentinel and judged by `_beats`.
PHOENIX_SINGLE = -1.0

Reading = tuple[str, int, float]  # (kind, length, key)


@functools.lru_cache(maxsize=None)
def _readings(cards: frozenset[Card]) -> frozenset[Reading]:
    """Every (kind, length, key) the rules let this card-set be played as."""
    size = len(cards)
    ranks = [x.rank for x in cards]
    phoenix = "Phoenix" in ranks
    mahjong = "Mahjong" in ranks
    if size == 1:
        rank = ranks[0]
        if rank == "Dog":
            return frozenset({("dog", 1, 0.0)})
        if rank == "Dragon":
            return frozenset({("single", 1, 15.0)})
        if rank == "Mahjong":
            return frozenset({("single", 1, 1.0)})
        if rank == "Phoenix":
            return frozenset({("single", 1, PHOENIX_SINGLE)})
        return frozenset({("single", 1, float(VAL[rank]))})
    if "Dog" in ranks or "Dragon" in ranks:
        return frozenset()
    naturals = [VAL[x.rank] for x in cards if x.rank in VAL]
    out: set[Reading] = set()
    # Bombs: four of a rank, or five or more consecutive ranks of one suit;
    # no special card is ever part of one.
    if not phoenix and not mahjong:
        if size == 4 and len(set(naturals)) == 1:
            out.add(("bomb", 4, float(naturals[0])))
        if (
            size >= 5
            and len({x.suit for x in cards}) == 1
            and sorted(naturals) == list(range(min(naturals), min(naturals) + size))
        ):
            out.add(("bomb", size, float(max(naturals))))
    # A suited run of natural cards is a bomb, never an ordinary straight.
    flush = any(kind == "bomb" and length >= 5 for kind, length, _ in out)
    # The Phoenix stands for any one card from 2 to Ace.
    fills = [[*naturals, v] for v in range(2, 15)] if phoenix else [naturals]
    for values in fills:
        counts = Counter(values)
        if not mahjong:
            if size in (2, 3) and len(counts) == 1:
                out.add(({2: "pair", 3: "triple"}[size], size, float(values[0])))
            if size == 5 and sorted(counts.values()) == [2, 3]:
                out.add(("fullhouse", 5, float(next(k for k, v in counts.items() if v == 3))))
            if size >= 4 and size % 2 == 0 and set(counts.values()) == {2}:
                keys = sorted(counts)
                if keys == list(range(keys[0], keys[0] + len(keys))):
                    out.add(("pairseq", size // 2, float(keys[-1])))
        run = sorted(values + ([1] if mahjong else []))
        if not flush and size >= 5 and len(set(run)) == size and run == list(range(run[0], run[0] + size)):
            out.add(("straight", size, float(run[-1])))
    return frozenset(out)


def _beats(reading: Reading, size: int, standing: Play | None) -> bool:
    if standing is None:
        return True
    kind, length, key = reading
    if kind == "dog":
        return False  # the Dog is led, never played on anything
    if kind == "bomb":
        if standing.kind != "bomb":
            return True
        return (size, key) > (len(standing.cards), standing.key)
    if standing.kind == "bomb":
        return False
    if kind != standing.kind or length != standing.length:
        return False
    if kind == "single" and key == PHOENIX_SINGLE:
        # The Phoenix beats any single but the Dragon.
        return not any(x.rank == "Dragon" for x in standing.cards)
    return key > standing.key


@functools.lru_cache(maxsize=None)
def _legal(hand: frozenset[Card], standing: Play | None) -> frozenset[frozenset[Card]]:
    """The card-sets the rules let `hand` play over `standing` (None: a lead)."""
    out: set[frozenset[Card]] = set()
    sizes: list[int] = list(range(1, len(hand) + 1))
    if standing is not None and standing.kind != "bomb":
        # A follow matches the standing play's size, or is a bomb.
        sizes = sorted({len(standing.cards), *range(4, len(hand) + 1)})
    for size in sizes:
        for combo in combinations(sorted(hand, key=str), size):
            cards = frozenset(combo)
            if any(_beats(r, size, standing) for r in _readings(cards)):
                out.add(cards)
    return frozenset(out)


Offer = tuple[frozenset[Card], str, int, float]  # (cards, kind, length, key)


@functools.lru_cache(maxsize=None)
def _offers(hand: frozenset[Card], standing: Play | None) -> frozenset[Offer]:
    """Every play the rules let `hand` make over `standing`: each legal
    card-set under each reading of it that beats the standing play."""
    out: set[Offer] = set()
    for cards in _legal(hand, standing):
        for kind, length, key in _readings(cards):
            if _beats((kind, length, key), len(cards), standing):
                if key == PHOENIX_SINGLE:
                    # The Phoenix single counts half a rank above the single
                    # it is played on, and 1.5 when led.
                    key = 1.5 if standing is None else standing.key + 0.5
                out.add((cards, kind, length, key))
    return frozenset(out)


def _as_offers(plays: list[Play]) -> frozenset[Offer]:
    return frozenset((frozenset(p.cards), p.kind, p.length, p.key) for p in plays)


def _show_offers(offers: set[Offer] | frozenset[Offer]) -> list[str]:
    return [f"{kind}/{length}@{key:g} {_show(cards)}" for cards, kind, length, key in sorted(offers, key=str)][:4]


def _holds(cards: tuple[Card, ...] | frozenset[Card], rank: int) -> bool:
    return any(VAL.get(x.rank) == rank for x in cards)


def _show(cards: tuple[Card, ...] | frozenset[Card]) -> str:
    return " ".join(f"{x.rank}{x.suit[0] if x.suit != 'special' else ''}" for x in sorted(cards, key=str))


# --- what the referee checks ---------------------------------------------------

# Each divergence the referee can note, mapped to the reach counters that
# show the check ran in the clean run.
CHECKS: dict[str, tuple[str, ...]] = {
    "hand.score_delta_differs": ("hand.score_delta_agrees", "hands.double_victory", "hands.with_a_tailender"),
    "hand.ended_without_a_single_tailender": ("hands.with_a_tailender",),
    "trick.captured_by_someone_else": ("tricks.captured",),
    "dragon.trick_given_to_own_team": ("dragon.given_away",),
    "dragon.offer_wrong": ("decisions.dragon",),
    "dragon.trick_taken_without_the_winners_choice": ("tricks.captured", "dragon.given_away"),
    "grand.offered_after_the_eighth_card": ("decisions.grand_poll",),
    "grand.offer_wrong_for_seat": ("decisions.grand_poll", "grand.offers_to_a_seat_that_called"),
    "small.offer_wrong_for_seat": ("decisions.small_poll", "small.calls_in_a_trick"),
    "small.asked_a_seat_that_may_not_call": ("decisions.small_poll",),
    "small.poll_while_nobody_may_call": ("decisions.small_poll",),
    "small.no_poll_though_a_seat_may_call": ("small.polls_before_the_push", "small.polls_before_an_in_trick_ask"),
    "small.poll_not_started_from_the_asked_seat": (
        "small.polls_before_the_push",
        "small.polls_after_the_push_before_the_first_lead",
        "small.polls_before_an_in_trick_ask",
    ),
    "small.lap_not_closed_by_every_seat_that_may_call": (
        "small.polls_before_an_in_trick_ask",
        "small.calls_after_a_play_in_the_same_trick",
    ),
    "small.poll_before_a_grand_poll": ("decisions.grand_poll",),
    "small.poll_before_a_push": ("decisions.push",),
    "small.poll_before_a_dragon": ("decisions.dragon",),
    "small.poll_before_a_wish": ("decisions.wish",),
    "small.poll_with_no_ask_after_it": ("hands",),
    "wish.offered_to_a_seat_that_did_not_just_play_the_mahjong": ("decisions.wish",),
    "wish.token_set_wrong": ("decisions.wish",),
    "wish.not_asked_after_the_mahjong": ("decisions.wish",),
    "wish.compelled_set_differs": ("decisions.compelled_by_the_wish",),
    "wish.pass_offered_though_the_wish_can_be_fulfilled": ("decisions.compelled_by_the_wish",),
    "push.candidates_not_the_whole_hand": ("decisions.push",),
    "push.seats_not_each_asked_once": ("decisions.push",),
    "climb.decision_with_one_or_no_holder": ("decisions.lead", "decisions.follow"),
    "climb.decision_after_a_double_victory": ("hands.double_victory",),
    "climb.offered_set_differs": ("decisions.lead", "decisions.follow"),
    "climb.pass_offered_on_the_lead": ("decisions.lead",),
    "climb.no_pass_on_a_follow": ("decisions.follow",),
    "window.asked_with_nothing_standing": ("decisions.window",),
    "window.asked_over_the_dog": ("decisions.window", "tricks.dog"),
    "window.offers_pass": ("decisions.window",),
    "window.bombs_differ": ("decisions.window", "window.bombs_played"),
    "lead.first_trick_not_led_by_the_mahjong_holder": ("hands",),
    "lead.wrong_seat_leads": ("lead.checked", "lead.checked_after_the_dog", "lead.checked_past_a_seat_that_is_out"),
    "game.ended_below_1000": ("games",),
    "game.winner_not_the_higher_score": ("games",),
}

# The decisions before which no small tichu poll may run, by the referee's
# name for the decision (the FAQ's three windows are before the push, after
# it, and inside the tricks).
POLL_FORBIDDEN_BEFORE = {
    "grand_poll": "small.poll_before_a_grand_poll",
    "push": "small.poll_before_a_push",
    "dragon": "small.poll_before_a_dragon",
    "wish": "small.poll_before_a_wish",
}


class Diverged(Exception):
    """A planted run's first divergence."""

    def __init__(self, key: str, detail: str) -> None:
        super().__init__(f"{key}: {detail}")
        self.key = key


class Referee:
    """The chooser and observer that hold one game to the rules."""

    def __init__(self, seed: int, *, stop: bool = False) -> None:
        self.rng = random.Random(1000 + seed)
        self.base = tichu_reference_policy(self.rng)
        self.stop = stop
        self.counts: Counter[str] = Counter()
        self.examples: dict[str, list[str]] = {}
        self.rs: RuntimeState | None = None
        self.hand_no = 0
        self.hand_over = False
        self.scores_at_hand_start: dict[int, int] | None = None
        # The dealer: the previous hand's first player out; seat 0 deals the
        # first hand (issue #781).
        self.dealer: Player = 0
        self.out: list[Player] = []
        self._reset_hand()

    # -- bookkeeping -----------------------------------------------------------

    def _note(self, key: str, detail: str = "") -> None:
        assert key in CHECKS, f"the referee noted {key!r}, which CHECKS does not name"
        if self.stop:
            raise Diverged(key, detail)
        self.counts[key] += 1
        if detail and len(self.examples.setdefault(key, [])) < 3:
            self.examples[key].append(detail)

    def attach(self, rs: RuntimeState) -> None:
        self.rs = rs

    def _state(self) -> RuntimeState:
        assert self.rs is not None
        return self.rs

    def _hand(self, p: Player) -> list[Card]:
        return list(self._state().zones.families["hand"][p].cards)

    def _holders(self) -> list[Player]:
        return [p for p in range(4) if self._hand(p)]

    def _reset_hand(self) -> None:
        if self.out:
            self.dealer = self.out[0]
        self.out = []
        self.called: dict[Player, int] = {}
        self.played: set[Player] = set()
        self.wish: int | None = None
        self.pile: dict[Player, list[Card]] = {p: [] for p in range(4)}
        self.trick_last: Player | None = None
        self.trick_top: Play | None = None
        self.pushes: Counter[Player] = Counter()
        self.trick_open = False
        self.trick_cards: list[Card] = []
        self.last_was_dog = False
        self.pending_dragon: Player | None = None
        self.awaiting_wish: Player | None = None
        self.first_lead_checked = False
        self.hand_cards_at_end: dict[Player, list[Card]] = {}
        # The small tichu asks since the last decision that was not one.
        self.block: list[tuple[Player, str]] = []
        self.pushed = False

    def _double_victory(self) -> bool:
        return len(self.out) >= 2 and TEAM[self.out[0]] == TEAM[self.out[1]]

    # -- small tichu: who may call, and when the calls are polled ---------------

    def _may_call(self) -> set[Player]:
        """A seat may call until it plays its first card, once per hand."""
        return {p for p in range(4) if p not in self.called and p not in self.played}

    def _close_poll(self, kind: str, actor: Player) -> None:
        """Judge the small tichu asks made before this decision of `kind`."""
        block, self.block = self.block, []
        in_trick = kind in ("lead", "follow", "window")
        pre_push = kind == "push" and not self.pushed
        if not (in_trick or pre_push):
            if block and kind in POLL_FORBIDDEN_BEFORE:
                self._note(POLL_FORBIDDEN_BEFORE[kind], f"P{actor} block={block}")
            return
        now = self._may_call()
        callers = {s for s, what in block if what == "call"}
        at_start = now | callers
        # The poll before the hand's first lead is the FAQ's post-push window,
        # "without information about the lead": it runs from the dealer, and
        # no poll before the first lead runs from the leader (issue #786).
        first_lead = kind == "lead" and not self.played
        if first_lead:
            self.counts["small.polls_after_the_push_before_the_first_lead"] += 1
        anchor = self.dealer if (pre_push or first_lead) else actor
        if not at_start:
            if block:
                self._note("small.poll_while_nobody_may_call", f"{kind} P{actor} block={block}")
            return
        self.counts["small.polls_before_an_in_trick_ask" if in_trick else "small.polls_before_the_push"] += 1
        if not block:
            self._note("small.no_poll_though_a_seat_may_call", f"{kind} P{actor} may call={sorted(at_start)}")
            return
        first = next(q for q in self._state().seating.turn_order_from(anchor) if q in at_start)
        if block[0][0] != first:
            self._note(
                "small.poll_not_started_from_the_asked_seat", f"{kind} P{actor} first={block[0][0]} want={first}"
            )
        # A call re-opens the lap; the poll closes once every seat that may
        # still call has declined once since the last call.
        last_call = max((i for i, (_, what) in enumerate(block) if what == "call"), default=-1)
        tail = block[last_call + 1 :]
        if {s for s, _ in tail} != now or len(tail) != len(now):
            self._note(
                "small.lap_not_closed_by_every_seat_that_may_call",
                f"{kind} P{actor} tail={tail} may call={sorted(now)}",
            )

    # -- the hand's score ---------------------------------------------------------

    def settle(self, observed: dict[int, int] | None) -> None:
        """The rules' score delta for the hand just played, against the game's."""
        if self.block:
            self._note("small.poll_with_no_ask_after_it", f"block={self.block}")
            self.block = []
        self.counts["hands"] += 1
        # Every seat pushes once a hand.
        if self.pushes != Counter(range(4)):
            self._note("push.seats_not_each_asked_once", f"pushes={dict(self.pushes)}")
        delta = {0: 0, 1: 0}
        if self._double_victory():
            # A double victory scores a flat 200 and no card points.
            self.counts["hands.double_victory"] += 1
            delta[TEAM[self.out[0]]] += 200
        else:
            live = [p for p in range(4) if p not in self.out]
            if len(live) != 1:
                self._note("hand.ended_without_a_single_tailender", f"out={self.out}")
                return
            self.counts["hands.with_a_tailender"] += 1
            tail = live[0]
            points = {p: sum(POINTS.get(x.rank, 0) for x in self.pile[p]) for p in range(4)}
            in_hand = sum(POINTS.get(x.rank, 0) for x in self.hand_cards_at_end.get(tail, []))
            for p in range(4):
                if p != tail:
                    delta[TEAM[p]] += points[p]
            # The tailender's tricks go to the first player out, the cards
            # left in their hand to the opponents.
            delta[TEAM[self.out[0]]] += points[tail]
            delta[1 - TEAM[tail]] += in_hand
        # A call scores its value if the caller goes out first, else loses it.
        for p, value in self.called.items():
            delta[TEAM[p]] += value if (self.out and self.out[0] == p) else -value
        if observed is not None:
            if observed != delta:
                self._note(
                    "hand.score_delta_differs", f"rules {delta} game {observed} out={self.out} calls={self.called}"
                )
            else:
                self.counts["hand.score_delta_agrees"] += 1

    # -- the observer: tricks taken, and the tailender's hand -------------------

    def observer(self, player: Player, event: tuple[Any, ...]) -> None:
        if player != 0 or event[0] != "move":
            return
        _, src, _, dst, _ = event
        source, target = str(src), str(dst)
        if (
            target == "deck"
            and not self.hand_over
            and self.hand_no > 0
            and source.startswith(("captured", "discard", "hand", "trick"))
        ):
            self.hand_over = True  # the next hand's gather has begun
        if source == "trick_pile":
            if target.startswith("captured["):
                taker = int(target[len("captured[") : -1])
                if self.pending_dragon is not None:
                    # A Dragon-won trick goes to an opponent of the winner's choice.
                    if TEAM[taker] == TEAM[self.pending_dragon]:
                        self._note("dragon.trick_given_to_own_team", f"P{self.pending_dragon} gave to P{taker}")
                    self.counts["dragon.given_away"] += 1
                    self.pending_dragon = None
                else:
                    if self._dragon_on_top():
                        self._note(
                            "dragon.trick_taken_without_the_winners_choice", f"won by P{self.trick_last}, taken by P{taker}"
                        )
                    if taker != self.trick_last:
                        self._note("trick.captured_by_someone_else", f"won by P{self.trick_last}, taken by P{taker}")
                self.pile[taker].extend(self.trick_cards)
                self.counts["tricks.captured"] += 1
            elif target == "discard":
                self.counts["tricks.dog"] += 1
            self.trick_open = False
            self.trick_cards = []
            self.trick_top = None
        if source.startswith("hand[") and target.startswith("captured["):
            tail = int(source[len("hand[") : -1])
            self.hand_cards_at_end[tail] = self._hand(tail) or self.hand_cards_at_end.get(tail, [])

    # -- the chooser: every decision, against the rules ---------------------------

    def __call__(self, player: Player, cands: list[Any], count: int) -> list[Any]:
        rs = self._state()
        if self.hand_over:
            self.hand_over = False
            self.hand_no += 1
            score = dict(rs.get("score"))
            if self.scores_at_hand_start is not None:
                self.settle({t: score[t] - self.scores_at_hand_start[t] for t in (0, 1)})
            self.scores_at_hand_start = score
            self._reset_hand()
        if self.hand_no == 0:
            self.hand_no = 1
            self.scores_at_hand_start = dict(rs.get("score"))
        names = {x[0] for x in cands if isinstance(x, tuple) and x}
        tokens = {x for x in cands if isinstance(x, str)}
        plays = [x for x in cands if isinstance(x, Play)]
        hand = self._hand(player)

        if names & {"call_grand_tichu", "decline_grand"}:
            return self._grand(player, cands, count, names, hand)
        if names & {"call_tichu", "no_call"}:
            return self._small(player, cands, count, names)
        if names & {"dragon_to_left", "dragon_to_right"}:
            return self._dragon(player, cands, count, names)
        if tokens and all(s.startswith("wish_") or s == "no_wish" for s in tokens):
            return self._wish(player, tokens)
        if count == 3 and cands and not plays:
            # The push: three cards from the whole fourteen-card hand.
            self._close_poll("push", player)
            self.pushed = True
            self.pushes[player] += 1
            self.counts["decisions.push"] += 1
            if sorted(map(str, cands)) != sorted(map(str, hand)) or len(hand) != 14:
                self._note("push.candidates_not_the_whole_hand", f"P{player} offered {len(cands)}")
            return self.rng.sample(cands, 3)
        if self.awaiting_wish is not None:
            self._note("wish.not_asked_after_the_mahjong", f"P{self.awaiting_wish}")
            self.awaiting_wish = None
        return self._climb(player, cands, count, tokens, plays, hand)

    def _grand(self, player: Player, cands: list[Any], count: int, names: set[Any], hand: list[Card]) -> list[Any]:
        self._close_poll("grand_poll", player)
        self.counts["decisions.grand_poll"] += 1
        # Grand tichu is called before taking the ninth card, once per hand.
        if len(hand) > 8:
            self._note("grand.offered_after_the_eighth_card", f"P{player} on {len(hand)} cards")
        if player in self.called:
            self.counts["grand.offers_to_a_seat_that_called"] += 1
        want = {"call_grand_tichu", "decline_grand"} if player not in self.called else {"decline_grand"}
        if names != want or len(cands) != len(want):
            self._note("grand.offer_wrong_for_seat", f"P{player} offered {sorted(names)} called={self.called}")
        pick = self.base(player, cands, count)
        if pick[0][0] == "call_grand_tichu":
            self.called[player] = 200
        return pick

    def _small(self, player: Player, cands: list[Any], count: int, names: set[Any]) -> list[Any]:
        self.counts["decisions.small_poll"] += 1
        may = player in self._may_call()
        want = {"call_tichu", "no_call"} if may else {"no_call"}
        if names != want or len(cands) != len(want):
            self._note(
                "small.offer_wrong_for_seat",
                f"P{player} offered {sorted(names)} called={self.called} played={player in self.played}"
                f" cards={len(self._hand(player))}",
            )
        if not may:
            self._note("small.asked_a_seat_that_may_not_call", f"P{player}")
        pick = self.base(player, cands, count)
        if pick[0][0] == "call_tichu":
            self.called[player] = 100
            self.block.append((player, "call"))
            if self.pushed:
                self.counts["small.calls_in_a_trick"] += 1
                if self.trick_open:
                    self.counts["small.calls_after_a_play_in_the_same_trick"] += 1
        else:
            self.block.append((player, "decline"))
        return pick

    def _dragon(self, player: Player, cands: list[Any], count: int, names: set[Any]) -> list[Any]:
        # The player who wins a trick with the Dragon gives it to the
        # opponent of their choice, on either side.
        self._close_poll("dragon", player)
        self.counts["decisions.dragon"] += 1
        if (
            names != {"dragon_to_left", "dragon_to_right"}
            or len(cands) != 2
            or player != self.trick_last
            or not self._dragon_on_top()
        ):
            top = self.trick_top
            self._note(
                "dragon.offer_wrong",
                f"P{player} offered {sorted(names)}; trick won by P{self.trick_last} with {_show(top.cards) if top else '-'}",
            )
        self.pending_dragon = player
        return self.base(player, cands, count)

    def _dragon_on_top(self) -> bool:
        top = self.trick_top
        return top is not None and [x.rank for x in top.cards] == ["Dragon"]

    def _wish(self, player: Player, tokens: set[str]) -> list[Any]:
        # The Mahjong's player may wish for a rank from 2 to Ace, or wish for
        # nothing, straight after playing it.
        self._close_poll("wish", player)
        self.counts["decisions.wish"] += 1
        if self.awaiting_wish != player:
            self._note(
                "wish.offered_to_a_seat_that_did_not_just_play_the_mahjong",
                f"P{player}, Mahjong played by {self.awaiting_wish}",
            )
        if tokens != {*WISH_RANK, "no_wish"}:
            self._note("wish.token_set_wrong", str(sorted(tokens)))
        self.awaiting_wish = None
        pick = self.rng.choice(sorted(tokens))
        self.wish = WISH_RANK.get(pick)
        return [pick]

    def _climb(
        self, player: Player, cands: list[Any], count: int, tokens: set[str], plays: list[Play], hand: list[Card]
    ) -> list[Any]:
        rs = self._state()
        standing: Play | None = rs.mech_state[-1]["current"]
        in_window = "no_bomb" in tokens
        if len(self._holders()) <= 1:
            self._note("climb.decision_with_one_or_no_holder", f"P{player}")
        if self._double_victory():
            self._note("climb.decision_after_a_double_victory", f"out={self.out}")
        offered = _as_offers(plays)
        self._close_poll("window" if in_window else ("lead" if standing is None else "follow"), player)
        held = frozenset(hand)

        if in_window:
            # Out of turn, a player may only bomb, over anything but the Dog.
            self.counts["decisions.window"] += 1
            if standing is None:
                self._note("window.asked_with_nothing_standing", f"P{player}")
            elif standing.kind == "dog":
                self._note("window.asked_over_the_dog", f"P{player}")
            if "pass" in tokens:
                self._note("window.offers_pass", f"P{player}")
            want = {o for o in _offers(held, standing) if o[1] == "bomb"}
            if offered != want:
                self._note(
                    "window.bombs_differ",
                    f"P{player} extra={_show_offers(offered - want)} missing={_show_offers(want - offered)}",
                )
            pick: list[Any] = (
                [plays[self.rng.randrange(len(plays))]] if plays and self.rng.random() < 0.5 else ["no_bomb"]
            )
            if isinstance(pick[0], Play):
                self.counts["window.bombs_played"] += 1
                self._played(player, pick[0])
            return pick

        leading = standing is None
        self.counts["decisions.lead" if leading else "decisions.follow"] += 1
        if leading:
            self._check_leader(player)
        legal = set(_offers(held, standing))
        # A wish in force compels a play holding the wished rank whenever the
        # player has a legal one; then passing is not allowed.
        wish = self.wish
        compelled = {o for o in legal if _holds(o[0], wish)} if wish is not None else set()
        if compelled:
            self.counts["decisions.compelled_by_the_wish"] += 1
            if offered != compelled:
                self._note(
                    "wish.compelled_set_differs",
                    f"P{player} wish {wish} extra={_show_offers(offered - compelled)}"
                    f" missing={_show_offers(compelled - offered)}",
                )
            if "pass" in tokens:
                self._note("wish.pass_offered_though_the_wish_can_be_fulfilled", f"P{player} wish {wish}")
        else:
            if offered != legal:
                self._note(
                    "climb.offered_set_differs",
                    f"P{player} lead={leading} standing={_show(standing.cards) if standing else '-'}"
                    f" extra={_show_offers(offered - legal)} missing={_show_offers(legal - offered)}",
                )
            if leading and "pass" in tokens:
                self._note("climb.pass_offered_on_the_lead", f"P{player}")
            if not leading and "pass" not in tokens:
                self._note("climb.no_pass_on_a_follow", f"P{player}")
        pick = self.base(player, cands, count)
        if isinstance(pick[0], Play):
            self._played(player, pick[0])
        return pick

    def _check_leader(self, player: Player) -> None:
        if not self.first_lead_checked:
            # The Mahjong's holder leads the hand's first trick.
            self.first_lead_checked = True
            if not any(x.rank == "Mahjong" for x in self._hand(player)):
                self._note("lead.first_trick_not_led_by_the_mahjong_holder", f"P{player}")
            return
        if self.trick_last is None:
            return
        # The trick's last player leads next; after the Dog, the Dog player's
        # partner. Either way onward round the ring to the first seat that
        # still holds cards.
        start = (self.trick_last + 2) % 4 if self.last_was_dog else self.trick_last
        want = next((q for q in self._state().seating.turn_order_from(start) if self._hand(q)), None)
        self.counts["lead.checked"] += 1
        if self.last_was_dog:
            self.counts["lead.checked_after_the_dog"] += 1
        if not self._hand(start):
            self.counts["lead.checked_past_a_seat_that_is_out"] += 1
        if player != want:
            self._note("lead.wrong_seat_leads", f"P{player} expected P{want} after the Dog={self.last_was_dog}")

    def _played(self, player: Player, play: Play) -> None:
        cards_left = len(self._hand(player))
        self.played.add(player)
        if not self.trick_open:
            self.trick_open = True
            self.trick_cards = []
        self.trick_cards.extend(play.cards)
        self.trick_last = player
        self.trick_top = play
        self.last_was_dog = play.kind == "dog"
        if self.wish is not None and _holds(play.cards, self.wish):
            self.wish = None
        if any(x.rank == "Mahjong" for x in play.cards):
            self.awaiting_wish = player
        if cards_left == len(play.cards):
            self.out.append(player)
            rest = [p for p in range(4) if p != player and self._hand(p)]
            if len(rest) <= 1 or self._double_victory():
                self.awaiting_wish = None  # the hand ends on this play; no wish follows
                for p in rest:
                    self.hand_cards_at_end[p] = self._hand(p)


# --- running it ----------------------------------------------------------------


def referee_games(game: n.Game, seeds: range, *, stop: bool = False) -> Referee:
    """Play one game per seed under one referee's counts; with `stop`, the
    first divergence raises `Diverged`."""
    total = Referee(0)
    for seed in seeds:
        ref = Referee(seed, stop=stop)
        result = play_game(game, random.Random(seed), None, ref, ref.observer, on_first_decision=ref.attach)
        start = ref.scores_at_hand_start
        ref.settle({k: result.scores[k] - start[k] for k in (0, 1)} if start is not None else None)
        ref.counts["games"] += 1
        top = max(result.scores.values())
        if top < 1000:
            ref._note("game.ended_below_1000", str(result.scores))
        if result.winners != {p for p, t in TEAM.items() if result.scores[t] == top}:
            ref._note("game.winner_not_the_higher_score", str(result))
        total.counts.update(ref.counts)
        for key, found in ref.examples.items():
            total.examples.setdefault(key, []).extend(f"seed {seed}: {x}" for x in found)
    return total


@functools.lru_cache(maxsize=None)
def _clean_run() -> Referee:
    return referee_games(check_dsl(TICHU.read_text(), str(TICHU)), SEEDS)


def test_tichu_plays_its_rules() -> None:
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
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                noted.add(first.value)
            else:
                # `_note(POLL_FORBIDDEN_BEFORE[kind], …)`: the table's values.
                noted |= set(POLL_FORBIDDEN_BEFORE.values())
    assert noted == set(CHECKS)


def test_an_offer_is_judged_by_its_reading_not_only_its_cards() -> None:
    """A suited run of natural cards is a bomb and never an ordinary
    straight, so the same cards offered as a straight are a divergence even
    though the card-set is legal.

    red under: `_readings` adding the straight reading beside the bomb, or
    the referee comparing card-sets instead of offers."""
    hearts = [c for c in build_deck("tichu56") if c.suit == "hearts" and c.rank in ("5", "6", "7", "8", "9")]
    run = frozenset(hearts)
    assert _readings(run) == {("bomb", 5, 9.0)}
    as_straight = Play("straight", 5, 9, tuple(hearts))
    assert _as_offers([as_straight]) - _offers(run, None)


# --- the reddening record --------------------------------------------------------

# Each row reverts one rule in a copy of the game file: the rule, the edits
# (each `old` occurs exactly once), and the divergences any one of which
# must fire.
PLANTED: list[tuple[str, list[tuple[str, str]], set[str]]] = [
    (
        "card points: a King scores 5",
        [("K: 10  Dragon", "K: 5  Dragon")],
        {"hand.score_delta_differs"},
    ),
    (
        "the tailender keeps their own tricks",
        [("move all cards from captured[last] to captured[out_first]\n", "")],
        {"hand.score_delta_differs"},
    ),
    (
        "a double victory scores 100",
        [("score[team_of(out_first)] += 200", "score[team_of(out_first)] += 100")],
        {"hand.score_delta_differs"},
    ),
    (
        "a failed call scores its value",
        [("else { score[team_of(p)] -= called[p] }", "else { score[team_of(p)] += called[p] }")],
        {"hand.score_delta_differs"},
    ),
    (
        "the dealer leads the first trick",
        [("leader := player_holding(Mahjong of special)", "leader := dealer")],
        {"lead.first_trick_not_led_by_the_mahjong_holder"},
    ),
    (
        "the Dog's player leads after the Dog",
        [
            (
                "leader := the player where player is not winner and team_of(player) is team_of(winner)",
                "leader := winner",
            )
        ],
        {"lead.wrong_seat_leads"},
    ),
    (
        "the trick's leader takes the trick",
        [("move all cards from trick_pile to captured[winner]", "move all cards from trick_pile to captured[leader]")],
        {"trick.captured_by_someone_else"},
    ),
    (
        "the Dragon's left gift stays with the winner",
        [("captured[actor offset_by left]", "captured[actor]")],
        {"dragon.trick_given_to_own_team"},
    ),
    (
        "the Dragon's winner may only give it to the left",
        [
            (
                # The right gift stays offered where no play reaches it: a move
                # type nothing offers is the checker's to refuse, and this row
                # is the referee's.
                "offer to winner one of [dragon_to_left, dragon_to_right]",
                "offer to winner one of [dragon_to_left]\n"
                "        if false { offer to winner one of [dragon_to_right] }",
            )
        ],
        {"dragon.offer_wrong", "dragon.trick_taken_without_the_winners_choice"},
    ),
    (
        "the Dragon's trick stays with its winner",
        [("if tichu_dragon_won() {", "if false {")],
        {"dragon.trick_taken_without_the_winners_choice"},
    ),
    (
        "the wish ends with its trick",
        [("wish := tichu_wish_after_trick()", "wish := 0")],
        {"wish.compelled_set_differs", "wish.pass_offered_though_the_wish_can_be_fulfilled"},
    ),
    (
        "a seat may call small tichu after its first card",
        [("(number of cards in hand[p]) is 14", "(number of cards in hand[p]) >= 13")],
        {"small.offer_wrong_for_seat"},
    ),
    (
        "the in-trick poll runs before the first lead (issue #786)",
        [("if tichu_window_open() and lead_made() {", "if tichu_window_open() {")],
        {"small.poll_not_started_from_the_asked_seat", "small.lap_not_closed_by_every_seat_that_may_call"},
    ),
    (
        "grand tichu is offered on the ninth card",
        [("repeat until dealt >= 8 {", "repeat until dealt >= 9 {"), ("deal 6 cards from deck", "deal 5 cards from deck")],
        {"grand.offered_after_the_eighth_card"},
    ),
    (
        "the game ends below 1000",
        [("score[team] >= 1000", "score[team] >= 1")],
        {"game.ended_below_1000"},
    ),
]


def _planted(edits: list[tuple[str, str]]) -> str:
    text = TICHU.read_text()
    for old, new in edits:
        assert text.count(old) == 1, f"{old!r} occurs {text.count(old)} times in tichu.cardlang"
        text = text.replace(old, new)
    return text


@pytest.mark.parametrize("rule, edits, fires", PLANTED, ids=[row[0] for row in PLANTED])
def test_a_planted_fault_is_caught(rule: str, edits: list[tuple[str, str]], fires: set[str]) -> None:
    assert fires <= set(CHECKS)
    game = check_dsl(_planted(edits), f"tichu.cardlang ({rule})")
    with pytest.raises(Diverged) as caught:
        referee_games(game, range(4), stop=True)
    assert caught.value.key in fires, str(caught.value)
