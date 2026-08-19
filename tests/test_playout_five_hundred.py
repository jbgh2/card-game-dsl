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

Where every fact comes from, and why that source
------------------------------------------------
1. OBSERVATIONS (observer 0's stream) — the hands, marked by the three kitty
   deals; the plays, the `move` events into `trick_pile`; the tricks, the
   drains into the capture piles; and the CONTRACT, which is what the auction
   ANNOUNCED. These are the facts the oracle JUDGES: a public decision every
   seat hears is a fact of the table rather than of the engine, so a
   divergence between what the engine did and what observers saw breaks this
   module rather than being invisible to it. The `play` / `trick` /
   `trick_end` TRACE events it used to read instead were emitted by the
   game-local winner Primitive alone, and went silent when that Primitive
   retired while every recomputation loop kept passing on nothing (issue
   #373) — which is the whole reason for this list.
2. The OFFERED SET at each card decision — the acting seat's own legal
   actions, as OpenSpiel would hand them to it. A legality rule is a rule
   about this set, so it is what the rules are checked against.
3. ENGINE STATE, at exactly one point: the acting seat's hand and lay-down
   zones, read live to recompute what the offer SHOULD have been. Both sides
   of that comparison have to come from outside the filter or it only sees
   one direction — an expectation derived from the offer equals the offer, so
   a filter that WITHHELD legal cards would compare equal to itself. This is
   a harness, not a player, and reading the true hand is what makes the
   comparison two-sided; the rule this module lives under is that no claim
   may rest on a trace that can retire (2 and 3 cannot), never that engine
   state is off limits.

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
   seat held. That is why the LEGALITY rules are judged on the candidate sets
   the acting seats were offered (`_Table.offered`) and not on the reconstructed
   pool: a rule binds the offer, and a rule the engine stopped enforcing still
   yields legal-looking plays wherever the chooser obeyed it anyway. The pool
   checks stay as the second reading, and can only MISS a violation there,
   never invent one. Every suit and no-trump hand plays all forty cards, so
   the reconstruction is exact there.
3. `_NOT_A_BID` is a hand-listed axis: the announcements that are not a bid,
   written here rather than derived from the game file's `move_type`s, so a
   new non-bid move type would be read as a bid and silently rewrite the
   contract. Nothing pins the two equal today. Recorded, not fixed: issue
   #380 (the same list is spelled again in
   tests/openspiel_ready/test_five_hundred.py, and the fix is one derivation
   serving both).
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from itertools import pairwise
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
    """Whether the card PLAYED was a legal follow, and which rule decided it.

    This is the weaker of the module's two legality readings and is labelled
    as such: it can only judge the one card that came out of the candidate
    set, so it is silent wherever a deleted rule still produced a legal play,
    and its `forced-joker` reason counts obedience rather than enforcement.
    `_Table._follow_offer` is the reading with teeth — it judges the SET."""
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
        self.offers: Counter[str] = Counter()
        self.offer_failures: list[str] = []
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

    # --- the legality rules, judged on the OFFER against the true holding ---
    #
    # A legality rule is a rule about the CANDIDATE SET, not about the one card
    # that came out of it, and the two are not the same claim: a rule the engine
    # stopped enforcing still yields a legal-looking play whenever the chooser
    # happens to pick a legal card, which is how a rule can be deleted with
    # every play still checking out.
    #
    # Both SIDES of the comparison have to come from outside the filter, or the
    # check only sees one direction. The expected set is therefore recomputed
    # from the acting seat's FULL HOLDING -- read off the live zones, engine
    # state, see the module docstring -- and never from the candidates: an
    # expectation derived from the offer equals the offer, so a filter that
    # withholds legal cards would compare equal to itself. Measured: with the
    # expectation taken from the candidates, a filter dropping one in-class card
    # under-offered 310 times over these forty seeds and every one of them
    # passed.

    def offered(
        self, rs: Any, player: Player, candidates: list[Card], n: int
    ) -> None:
        if n != 1 or not candidates or not all(isinstance(c, Card) for c in candidates):
            return  # not a card play: the auction, an offer, the 3-card discard
        if not self.hands or self._hand.declarer is None:
            return  # no contract yet: nothing to judge legality against
        h = self._hand
        # The seat plays from its hand, or -- once an open misere has exposed
        # the declarer -- from its lay-down; exactly one of the two is non-empty
        # during play, so the union is the pool the movement draws from.
        pool = [
            *rs.zones.instance("hand", player).cards,
            *rs.zones.instance("exposed", player).cards,
        ]
        offer = sorted(str(c) for c in candidates)
        expected = sorted(
            str(c)
            for c in (
                self._legal_leads(pool, h)
                if not self._pending
                else self._legal_follows(pool, h)
            )
        )
        if offer != expected:
            self.offer_failures.append(
                f"{self._where}: P{player} was offered {offer}, but the rules "
                f"recomputed over its holding {sorted(str(c) for c in pool)} "
                f"give {expected}"
                + ("" if self._pending else " (leading)")
                + (
                    f" (led {self._pending[0][1]}, trump {h.trump}, "
                    f"joker {h.joker_suit}, misere {h.misere})"
                    if self._pending
                    else ""
                )
            )

    @property
    def _where(self) -> str:
        return f"hand {len(self.hands) - 1} trick {len(self._hand.tricks)}"

    def _legal_leads(self, pool: list[Card], h: _Hand) -> list[Card]:
        """Anything may be led, except that in the no-trump family an
        un-nominated joker is held back until it is the leader's last card."""
        if h.trump is not None or h.joker_suit is not None or len(pool) == 1:
            self.offers["lead_plain"] += 1
            return pool
        if any(c.suit == "joker" for c in pool):
            self.offers["lead_joker_withheld"] += 1
            return [c for c in pool if c.suit != "joker"]
        self.offers["lead_plain"] += 1
        return pool

    def _legal_follows(self, pool: list[Card], h: _Hand) -> list[Card]:
        """Strict follow within the led class; void, anything goes -- except
        that in a misere a void holder of the un-nominated joker must play it."""
        led = self._pending[0][1]
        cls = _cls(led, h.trump, h.joker_suit)
        in_class = [c for c in pool if _cls(c, h.trump, h.joker_suit) == cls]
        if in_class:
            self.offers["offer_in_class"] += 1
            return in_class
        if h.misere and h.joker_suit is None and any(c.suit == "joker" for c in pool):
            self.offers["offer_forced_joker"] += 1
            return [c for c in pool if c.suit == "joker"]
        self.offers["offer_void"] += 1
        return pool


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
    pick = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if rs_box:
            table.offered(rs_box[0], player, candidates, n)
        return pick(player, candidates, n)

    result = play_game(
        game,
        rng,
        tracer,
        chooser,
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

    # The legality rules, judged on the CANDIDATE SETS the acting seats were
    # offered rather than on the cards that came out of them (see `_Table.offered`).
    assert not table.offer_failures, (
        f"seed {seed}: " + "\n  ".join(table.offer_failures[:4])
    )

    # Non-vacuity, pinned against the announcements rather than against
    # itself, and BEFORE the recomputation below: an observation stream that
    # went empty fails here instead of leaving every loop iterating nothing.
    #
    # A hand with PLAYS but no declarer is the first thing checked, because it
    # is the shape that partial loss takes: lose one hand's announcements and
    # the hand looks thrown in, and every claim below silently skips it. Only
    # a hand that never reached a contract has no plays, so "plays without a
    # declarer" is exactly "this hand's announcements went missing" -- and it
    # must be judged over EVERY hand, before any filter that would drop it.
    # (Measured 2026-08-19: 0 of the 50 hands over these 40 seeds is genuinely
    # thrown in, so the thrown-in exemption below is a rules allowance with no
    # live instance today; its only reachable effect would be absorbing loss,
    # which is what this guard removes.)
    lost = [
        i
        for i, h in enumerate(table.hands)
        if h.declarer is None and (h.plays or h.tricks)
    ]
    assert not lost, (
        f"seed {seed}: hand(s) {lost} of {len(table.hands)} were played but no "
        f"contract was announced in them -- the observation stream lost those "
        f"announcements, and every claim below would skip the hand as thrown in"
    )
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
    roles += table.offers
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
    unchecked while every assertion above stayed green.

    The `offer_*` and `lead_joker_*` cells are the OFFERED-SET half, and they
    are the ones that guard a RULE rather than an occurrence: a cell counting
    played cards fires only where the rule was obeyed, so it survives the
    rule's deletion wherever the chooser happened to obey it anyway. Each of
    these counts a decision where the rule bound the candidate set."""
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
        # the offered-set arms
        "offer_in_class",
        "offer_void",
        "offer_forced_joker",
        "lead_plain",
        "lead_joker_withheld",
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


# The hoist's own hazard, and the seeds that make it visible.
#
# `trump_suit` / `joker_suit` are GAME-scoped so the Trick Order rows can read
# them (a `trick_order` block is a game clause). Phase-scoped state is
# re-initialized by the language on every phase entry; game-scoped state is
# not, so that guarantee is now two hand-written assignments in `phase play`,
# and the contract of one hand survives into the next if either is dropped.
#
# Only `joker_suit`'s clear is READ by a playout, and only in a hand sequence
# that nominates the joker and then plays a hand that does not. Measured over
# seeds 0-599 (2026-08-19): five seeds have that shape -- 321, 353, 416, 585,
# 592, none below 200, so neither the forty-seed sweep above nor the 200-seed
# stream pin can reach it. Of those five only THREE redden when the clear is
# deleted, because the stale nomination has to change a candidate set as well
# as exist: the joker must fall to a seat that is obliged in the led class.
# That is why the seeds below are chosen by the executed red-under and not by
# the structural filter, and why the shape is asserted rather than assumed --
# a game-file change that moved these lines could leave three seeds that no
# longer nominate at all, and this cell would pass on nothing.
_NOMINATION_CLEAR_SEEDS = (353, 585, 592)


def test_the_nomination_clears_between_hands() -> None:
    """`phase play`'s `joker_suit := none`, given a witness.

    Each seed plays a hand that nominates the joker and a later hand that does
    not; the second hand's legality must be computed with no nomination
    standing. Deleting the clear puts the joker back in the old suit, which the
    candidate-set reading catches as a card offered outside the led class."""
    game = _five_hundred()
    for seed in _NOMINATION_CLEAR_SEEDS:
        table, _census, _scores, _result = _play(game, seed)
        hands = [h for h in table.hands if h.declarer is not None]
        assert any(
            a.joker_suit is not None and b.joker_suit is None
            for a, b in pairwise(hands)
        ), (
            f"seed {seed} no longer nominates the joker in one hand and plays "
            f"another without a nomination, so it cannot exercise the clear -- "
            f"re-derive the witness seeds (see this cell's comment)"
        )
        _check_seed(game, seed)
