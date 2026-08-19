"""Random-playout harness for 500, plus a characterization pin.

500 has three trick structures: suit contracts (the joker + both bowers head
the trump suit, and the left bower changes effective suit), no-trumps (the
joker suitless until nominated, then the highest card of its suit), and the
misères (three-handed — the declarer's partner sits out — with inverse
scoring). The falsifiable check recomputes every trick's winner, every follow
decision and every lead decision from the cards played and the contract the
auction announced, so a wrong bower ordering, a missed effective-suit remap, a
wrong joker rule, a wrong misère seat-skip or a broken lead restriction turns
it red. Plus deck integrity (43 cards) and the champion invariant (the game
ends only on a contract win crossing +500 or a side out backwards at -500).

Observation-derived, not trace-derived (the Skat and Doppelkopf precedent).
Every fact it consumes rides observer 0's stream: the hands are marked by the
three kitty deals, the plays are the `move` events into `trick_pile`, the
tricks are the drains into the capture piles, and the CONTRACT is what the
auction ANNOUNCED — a public decision every seat hears, which makes it a fact
of the table rather than of the engine. The `play` / `trick` / `trick_end`
TRACE events this used to read are emitted by the game-local winner Primitive
alone; deriving from observations instead is strictly stronger, because a
divergence between what the engine recorded and what observers saw would now
BREAK this oracle rather than being invisible to it.

Non-vacuity is asserted, not hoped for, and the assertion is DERIVED: the
announcements say how many tricks each hand owes (ten for a suit or no-trump
contract; one to ten for a misère, which stops the moment the declarer takes
one; none for a hand thrown in), and `_check_seed` pins the observed counts
against that before any recomputation loop runs. Without it, an emptied
observation stream would leave every loop iterating zero times — a green run
proving nothing (the empty-input-set class, decisions.md "Closed-domain
completeness"). `test_every_joker_role_is_reached` is the second half: the
recomputation branches on the joker's and the bowers' roles, so a sweep that
never played one would leave that branch — and the Trick Order row that
selects it — unexercised while every assertion above stayed green.

The recomputation stays INDEPENDENT of the language's trick machinery: it
never calls `follows_lead` or `highest_by_trick_order`, and re-implements the
Pagat rules in Python below.

Ledger note — what the observation stream cannot pin
----------------------------------------------------
1. The capture piles are keyed by TEAM (`captured[team]`), so a drain names
   the winning team, not the winning seat. The seat is pinned by ROUTING
   instead — the winner leads the next trick, which is the next play — so
   every trick but a hand's LAST one is pinned to the seat. A hand's last
   trick is pinned to the team only, and a misère's last trick is pinned
   further (a misère that ran short ended because the DECLARER took that
   trick). Residual: on the last trick of a suit or no-trump hand, a
   recomputation that named the winner's PARTNER would pass — one trick in
   ten, bounded, and recorded here.
2. A hand's holdings are reconstructed from the cards actually played, so
   for a misère that ended early the reconstruction is a SUBSET of what each
   seat held. Follow and lead legality are then checked against a subset,
   which can only MISS a violation, never invent one. Every suit and
   no-trump hand plays all forty cards, so the reconstruction is exact
   there.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player

FIVE_HUNDRED = Path(__file__).parent.parent / "docs" / "games" / "five-hundred.cardlang"

TRICKS_PER_HAND = 10
KITTY_DEALS_PER_HAND = 3

_RANK = {"A": 11, "K": 10, "Q": 9, "J": 8, "10": 7, "9": 6, "8": 5, "7": 4, "6": 3, "5": 2, "4": 1}
_MATE = {"spades": "clubs", "clubs": "spades", "hearts": "diamonds", "diamonds": "hearts"}

# A rendered card back to a Card. The observation stream carries the printed
# text — what a seat at the table reads off the pile — never an engine value.
_SUITS = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}
_JOKER = "Joker:joker"


def _parse(text: str) -> Card:
    if text == _JOKER:
        return Card("Joker", "joker")
    return Card(text[:-1], _SUITS[text[-1]])


# --- the Pagat rules, re-implemented independently of the engine -----------


def _is_trump(c: Card, trump: str) -> bool:
    return c.suit == "joker" or c.suit == trump or (c.rank == "J" and c.suit == _MATE[trump])


def _cls(c: Card, trump: str | None, joker_suit: str | None) -> str:
    if trump is not None:
        return "trump" if _is_trump(c, trump) else c.suit
    if c.suit == "joker":
        return joker_suit if joker_suit is not None else "joker"
    return c.suit


def _winner(
    group: list[tuple[Player, Card]], trump: str | None, joker_suit: str | None
) -> Player:
    led = _cls(group[0][1], trump, joker_suit)
    if trump is not None:
        trumps = [(p, c) for p, c in group if _is_trump(c, trump)]
        if trumps:

            def strength(c: Card) -> int:
                if c.suit == "joker":
                    return 1000
                if c.rank == "J" and c.suit == trump:
                    return 999
                if c.rank == "J" and c.suit == _MATE[trump]:
                    return 998
                return _RANK[c.rank]

            return max(trumps, key=lambda pc: strength(pc[1]))[0]
        of_led = [(p, c) for p, c in group if c.suit == led]
        return max(of_led, key=lambda pc: _RANK[pc[1].rank])[0]
    jokers = [(p, c) for p, c in group if c.suit == "joker"]
    if jokers and joker_suit is None:
        return jokers[0][0]
    of_led = [(p, c) for p, c in group if _cls(c, trump, joker_suit) == led]
    return max(of_led, key=lambda pc: 100 if pc[1].suit == "joker" else _RANK[pc[1].rank])[0]


def _follow_reason(
    pool: list[Card],
    led: Card,
    c: Card,
    trump: str | None,
    misere: bool,
    joker_suit: str | None,
) -> tuple[bool, str]:
    """Whether `c` was a legal follow, and WHICH rule decided it — the reason
    is what `test_every_joker_role_is_reached` counts, so the misère
    forced-joker arm cannot go unexercised unnoticed."""
    cls = _cls(led, trump, joker_suit)
    if any(_cls(x, trump, joker_suit) == cls for x in pool):
        return _cls(c, trump, joker_suit) == cls, "in-class"
    # Pagat: void in the led class, a misère holder of the un-nominated joker
    # must play it.
    if misere and joker_suit is None and any(x.suit == "joker" for x in pool):
        return c.suit == "joker", "forced-joker"
    return True, "void"


def _lead_ok(pool: list[Card], c: Card, trump: str | None, joker_suit: str | None) -> bool:
    """In the no-trump family an un-nominated joker may not be led before the
    holder's last card (five-hundred.md, "Chosen ruleset (modelling notes)")."""
    if trump is not None or c.suit != "joker":
        return True
    return joker_suit is not None or len(pool) == 1


# --- what a seat at the table writes down ---------------------------------

# The announcements that are not a bid: they never name a contract.
_NOT_A_BID = frozenset({"pass", "decline_nomination"})
_NOMINATE = "nominate_joker_suit("
_SUBMIT = "submit_bid("


@dataclass
class _Hand:
    """One deal, as the table saw it. `declarer is None` means the hand was
    thrown in — all four passed, so no kitty was taken and no trick played."""

    declarer: Player | None = None
    trump: str | None = None
    misere: bool = False
    joker_suit: str | None = None
    exposed: bool = False
    plays: list[tuple[Player, Card]] = field(default_factory=list)
    # (winning team, the drained cards) — the pile's payload is in ZONE
    # order, not play order, so it is compared as a multiset.
    tricks: list[tuple[int, tuple[str, ...]]] = field(default_factory=list)


class _Table:
    def __init__(self) -> None:
        self.hands: list[_Hand] = []
        self._kitty_deals = 0
        self._pending: list[tuple[Player, Card]] = []

    @property
    def _hand(self) -> _Hand:
        assert self.hands, "a table event arrived before any hand was dealt"
        return self.hands[-1]

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        # Observer 0's stream only: the trick pile and the capture piles
        # project identity to every observer and an announcement is heard by
        # every seat, so seat 0 sees exactly what every other seat does.
        if player != 0:
            return
        if event[0] == "announce":
            self._announced(Player(int(event[1])), str(event[2]))
        elif event[0] == "move":
            self._moved(event)

    def _announced(self, who: Player, said: str) -> None:
        if said in _NOT_A_BID:
            return
        if said.startswith(_NOMINATE):
            self._hand.joker_suit = said[len(_NOMINATE) : -1]
            return
        # A bid. The auction is strictly ascending, so the LAST bid stands and
        # its speaker is the declarer.
        hand = self._hand
        hand.declarer = who
        hand.misere = said in ("bid_misere", "bid_open_misere")
        # `submit_bid(clubs)` names its strain; the bare spelling is the
        # no-trump strain, which the announcement renders with no argument.
        hand.trump = said[len(_SUBMIT) : -1] if said.startswith(_SUBMIT) else None

    def _moved(self, event: tuple[Any, ...]) -> None:
        _, src, _src_view, dst, dst_view = event
        src, dst = str(src), str(dst)
        if src == "deck" and dst == "kitty":
            # Three kitty deals per hand, and the only ones: the first of each
            # three is where a hand begins.
            if self._kitty_deals % KITTY_DEALS_PER_HAND == 0:
                self.hands.append(_Hand())
                self._pending.clear()
            self._kitty_deals += 1
        elif dst == "trick_pile" and src.startswith(("hand[", "exposed[")):
            (card_str,) = dst_view  # one card per play
            play = (Player(int(src[src.index("[") + 1 : -1])), _parse(card_str))
            self._hand.plays.append(play)
            self._pending.append(play)
        elif src == "trick_pile" and dst.startswith("captured["):
            self._hand.tricks.append(
                (int(dst[len("captured[") : -1]), tuple(str(c) for c in _src_view))
            )
            self._pending.clear()
        elif src.startswith("hand[") and dst.startswith("exposed["):
            self._hand.exposed = True


def _play(game: Any, seed: int) -> tuple[_Table, dict[str, int], list[dict[int, int]], Any]:
    table = _Table()
    census: dict[str, int] = {}
    hand_scores: list[dict[int, int]] = []
    rs_box: list[Any] = []

    def tracer(event: str, data: Any) -> None:
        if event == "hand_end" and rs_box:
            hand_scores.append(dict(rs_box[0].get("score")))
        elif event == "game_end":
            census.update(data)

    rng = random.Random(seed)
    result = play_game(
        game,
        rng,
        tracer,
        random_chooser(rng),
        observer=table.observe,
        on_first_decision=lambda rs: rs_box.append(rs),
    )
    return table, census, hand_scores, result


def _five_hundred() -> Any:
    return check_source(FIVE_HUNDRED)


def _check_seed(game: Any, seed: int) -> Counter[str]:
    table, census, hand_scores, result = _play(game, seed)
    team_of = {p: ti for ti, members in enumerate(game.teams) for p in members}

    assert census["total"] == 43, f"seed {seed}: {census}"

    # Exactly one champion, fixed by the scoring rules: a contract win
    # crossing +500, or the other side out backwards at -500.
    final = hand_scores[-1]
    assert result.winner is not None
    loser = 1 - result.winner
    assert final[result.winner] >= 500 or final[loser] <= -500, f"seed {seed}: {final}"

    # Non-vacuity, pinned against the announcements rather than against
    # itself, and BEFORE the recomputation below: an observation stream that
    # went empty fails here instead of leaving every loop iterating nothing.
    played = [h for h in table.hands if h.declarer is not None]
    assert played, (
        f"seed {seed}: no hand reached a contract ({len(table.hands)} dealt), so "
        f"every count below would read 0 == 0 and this block would prove nothing"
    )
    for i, h in enumerate(played):
        size = 3 if h.misere else 4
        if h.misere:
            # A misère stops the moment the declarer takes a trick, so a short
            # hand's last trick is his — a count AND a routing claim.
            assert 1 <= len(h.tricks) <= TRICKS_PER_HAND, f"seed {seed} hand {i}"
            if len(h.tricks) < TRICKS_PER_HAND:
                assert h.declarer is not None
                assert h.tricks[-1][0] == team_of[h.declarer], (
                    f"seed {seed} hand {i}: a misère ended after "
                    f"{len(h.tricks)} tricks without the declarer taking one"
                )
        else:
            assert len(h.tricks) == TRICKS_PER_HAND, f"seed {seed} hand {i}"
        assert len(h.plays) == size * len(h.tricks), f"seed {seed} hand {i}"

    roles: Counter[str] = Counter()
    for i, h in enumerate(played):
        size = 3 if h.misere else 4
        assert h.declarer is not None
        roles["contract_" + ("misere" if h.misere else ("trump" if h.trump else "notrump"))] += 1
        if h.exposed:
            roles["open_misere_exposed"] += 1

        # The holdings reconstruct from the cards actually played (exact for
        # every hand that ran its full ten tricks — see the ledger note).
        pool: dict[Player, list[Card]] = {}
        for p, c in h.plays:
            pool.setdefault(p, []).append(c)
        assert len(pool) == size, f"seed {seed} hand {i}: {sorted(pool)}"
        assert len({(c.rank, c.suit) for _, c in h.plays}) == len(h.plays), (
            f"seed {seed} hand {i}: a card was played twice"
        )
        if not h.misere:
            assert all(len(cs) == TRICKS_PER_HAND for cs in pool.values()), f"seed {seed} hand {i}"
        else:
            assert h.declarer + 2 not in pool and h.declarer - 2 not in pool, (
                f"seed {seed} hand {i}: the declarer's partner played in a misère"
            )

        for t, (team, drained) in enumerate(h.tricks):
            group = h.plays[size * t : size * (t + 1)]
            assert len({p for p, _ in group}) == size, f"seed {seed} hand {i} trick {t}"
            # The drain's payload is in ZONE order, so only the multiset matches.
            assert Counter(str(c) for _, c in group) == Counter(drained), (
                f"seed {seed} hand {i} trick {t}"
            )

            winner = _winner(group, h.trump, h.joker_suit)
            assert team_of[winner] == team, (
                f"seed {seed} hand {i} trick {t}: recomputed {winner} "
                f"(team {team_of[winner]}), the pile drained to team {team}"
            )
            # Routing pins the SEAT: the winner leads the next trick.
            if t + 1 < len(h.tricks):
                assert h.plays[size * (t + 1)][0] == winner, (
                    f"seed {seed} hand {i} trick {t}: {winner} won but did not lead"
                )

            led_p, led_c = group[0]
            assert _lead_ok(pool[led_p], led_c, h.trump, h.joker_suit), (
                f"seed {seed} hand {i} trick {t}: {led_p} led {led_c} illegally"
            )
            for p, c in group[1:]:
                ok, reason = _follow_reason(
                    pool[p], led_c, c, h.trump, h.misere, h.joker_suit
                )
                assert ok, (
                    f"seed {seed} hand {i} trick {t}: {p} broke follow with {c} "
                    f"(led {led_c}, trump {h.trump}, joker {h.joker_suit}, {reason})"
                )
                roles["follow_" + reason] += 1

            for p, c in group:
                roles.update(_card_roles(c, h.trump, h.joker_suit, p == led_p))
                pool[p].remove(c)
    return roles


def _card_roles(
    c: Card, trump: str | None, joker_suit: str | None, led: bool
) -> list[str]:
    """The roles a played card fills that the recomputation BRANCHES on — the
    census `test_every_joker_role_is_reached` reads."""
    roles: list[str] = []
    if trump is not None:
        if c.suit == "joker":
            roles.append("trump_joker")
        elif c.rank == "J" and c.suit == trump:
            roles.append("right_bower")
        elif c.rank == "J" and c.suit == _MATE[trump]:
            roles.append("left_bower")
    elif c.suit == "joker":
        roles.append("nt_joker_nominated" if joker_suit is not None else "nt_joker_free")
        if led:
            roles.append("led_joker_nominated" if joker_suit is not None else "led_joker_free")
    return roles


def test_40_random_games_satisfy_invariants() -> None:
    game = _five_hundred()
    for seed in range(40):
        _check_seed(game, seed)


def test_every_joker_role_is_reached() -> None:
    """The recomputation branches on the joker's and the bowers' roles, and
    each branch is a different Trick Order row arm: the joker as the top
    trump, the two bowers' promotion above the ace, the un-nominated joker
    that wins any trick under no-trumps (including when it is itself led),
    the nominated joker remapped into its suit, and the misère forced-joker
    follow. A sweep that never played one would leave that arm entirely
    unchecked while every assertion above stayed green."""
    game = _five_hundred()
    roles: Counter[str] = Counter()
    for seed in range(40):
        roles += _check_seed(game, seed)
    for cell in (
        "contract_trump",
        "contract_notrump",
        "contract_misere",
        "trump_joker",
        "right_bower",
        "left_bower",
        "nt_joker_free",
        "nt_joker_nominated",
        "led_joker_free",
        "led_joker_nominated",
        "follow_in-class",
        "follow_void",
        "follow_forced-joker",
    ):
        assert roles[cell] > 0, f"{cell} never occurred: {roles}"


def test_seed0_characterization() -> None:
    # Byte-identity pin for a whole game: any change to the constructs'
    # decision sequence (auction ring order, guard-filtered candidate order,
    # chosen-movement pool order, offer order) moves this vector. Measured
    # hash-independent (identical under PYTHONHASHSEED 0/1/7): every
    # collection on the decision path is ordered (seating rings, hand-order
    # pools, the declaration-order action space). The vector also depends on
    # the canonical gather order (`move all cards to deck` collects zones in
    # sorted-name order), which feeds the pre-shuffle deck permutation.
    table, _census, hand_scores, result = _play(_five_hundred(), 0)
    assert result.winner == 1
    assert hand_scores == [{0: -520, 1: 70}]
    assert len(table.hands) == 1
    hand = table.hands[0]
    assert len(hand.tricks) == 10
    assert (hand.declarer, hand.trump, hand.misere, hand.joker_suit) == (0, None, False, None)
