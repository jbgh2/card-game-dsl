"""Random-playout harness for Belote, plus a characterization pin.

Belote's falsifiable surface is broad because a whole hand recomputes from
what the table saw: the deal reconstructs from the cards each seat played
(conservation over the 32-card pack), follow legality is a pure function of
the trick prefix, the declared trump and the acting seat's team (the
five-obligation cascade -- the corpus's richest), the trick winner is a pure
function of the plays under the J-9 trump order, declarations recompute from
the reconstructed hand at the poll, and the settlement is a closed formula
over card points, the dix de der, capot, entitled declarations, and
Belote-Rebelote. This module replays every seed, recomputes ALL of it
independently -- an implementation of the Pagat rules as scoped in
docs/games/belote.md, written against the table's own record -- and asserts
the driver's final scores match exactly.

Where every fact comes from, and why that source
------------------------------------------------
1. OBSERVATIONS (observer 0's stream, its public half: `announce`, `move`,
   `reveal`). The hands are marked by the turn-up deal, and the turn-up's
   IDENTITY is public (`turnup : Discard`, identity to every observer), which
   is what makes a bare `take` -- a move that carries no parameter -- name a
   suit at all. The plays are the movements into `trick_pile`, the tricks are
   the drains into the capture piles, the auction / declaration /
   Belote-Rebelote announcements are what each seat heard, and the showings
   are `reveal` events. These are the facts the oracle JUDGES: a public
   decision every seat hears is a fact of the table rather than of the
   engine, so a divergence between what the engine did and what observers saw
   breaks this module rather than being invisible to it.

   What this module does NOT read is the `trick_end` TRACE, which is where it
   used to get the trump. That payload is the ROUND's configuration, not the
   table's: it is a harness channel, it moves when the round stops carrying a
   trump clause, and a claim resting on it is a claim that can go silently
   vacuous (issue #373 -- Skat's and 500's oracles did exactly that). The
   trump is now derived from the announcements themselves: round one's `take`
   means the turn-up's suit, round two's `take_suit(s)` names its own.
2. The OFFERED SET at each card decision -- the acting seat's own legal
   actions, as OpenSpiel would hand them to it. A legality rule is a rule
   about this set, so it is what the five-rule cascade is checked against.
   Judging the card PLAYED instead is the reading with no teeth: a rule the
   engine stopped enforcing still yields legal-looking plays wherever the
   chooser happened to obey it anyway.
3. ENGINE STATE, at exactly one point: the acting seat's `hand[p]` zone, read
   live to recompute what the offer SHOULD have been. Both sides of that
   comparison have to come from outside the filter or it only sees one
   direction -- an expectation derived from the offer equals the offer, so a
   cascade that WITHHELD legal cards would compare equal to itself. This is a
   harness, not a player, and reading the true hand is what makes the
   comparison two-sided; the rule this module lives under is that no claim
   may rest on a trace that can retire (2 and 3 cannot), never that engine
   state is off limits.

Non-vacuity is asserted, not hoped for, and the assertion is DERIVED from the
auction rather than hard-coded: a hand where somebody took owes eight tricks
of four plays each, and a hand where all eight announcements were passes owes
none. `_check_seed` pins the observed counts against that BEFORE any
recomputation loop runs. Without it an emptied observation stream would leave
every loop iterating zero times -- a green run proving nothing (the
empty-input-set class, decisions.md "Closed-domain completeness"). The
vocabulary census (`test_every_obligation_arm_is_reached`) is the second
half: the cascade has five rules and the recomputation branches on each of
their arms, so a sweep that never reached one would leave that arm unchecked
while every assertion above stayed green. Two of the census cells are RARE
enough that a 20-seed sweep does not reach them by luck, and they are reached
by NAMED witness seeds instead (`_RARE_ARM_SEEDS`) rather than left out of the
census -- a cell no seed reaches is an assertion that cannot fail, which is
the same defect this module's own guards exist to refuse.

The recomputation stays INDEPENDENT of the language's trick machinery: it
never calls `follows_lead` or `highest_by_trick_order`, and re-implements the
Pagat obligations in Python below.

Ledger note -- what the observation stream cannot pin
-----------------------------------------------------
1. The capture piles are keyed by TEAM (`captured[team]`), so a drain names
   the winning team, not the winning seat. The seat is pinned by ROUTING
   instead -- the winner leads the next trick -- which covers tricks 1..7 of
   every hand. The EIGHTH trick is pinned to the team only. Residual: on a
   hand's last trick a recomputation that named the winner's PARTNER would
   pass here -- one trick in eight, bounded, and harmless to the settlement,
   which reads only the last trick's TEAM for the dix de der. Recorded, not
   fixed.
2. The declaration poll's entitlement is checked from the ANNOUNCED content
   (move name + Rank parameter) against the hand reconstructed from the
   plays. A hand that stayed silent is checked only for the absence of an
   announcement and of a showing: this module does not assert that silence
   was CHOSEN rather than forced, because a player may always decline. The
   guard that a declaration states the best combination exactly is the one
   with teeth, and it is checked for every announcer.
3. `_VOCABULARY` is a hand-listed axis -- the announcements this module
   classifies -- written here rather than derived from the game file's
   `move_type`s, so a new move type could be read as neither a bid nor a poll
   answer and silently skipped. Guarded rather than derived:
   `_Table._announced` refuses an announcement it cannot classify, so the
   list cannot fall behind the game in silence.
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
from cardlang.runtime.values import SUITS, Card, Player

BELOTE = Path(__file__).parent.parent / "docs" / "games" / "belote.cardlang"

TRICKS_PER_HAND = 8
SEATS = 4

_TRUMP_HEIGHT = {"J": 8, "9": 7, "A": 6, "10": 5, "K": 4, "Q": 3, "8": 2, "7": 1}
_PLAIN_HEIGHT = {"A": 8, "10": 7, "K": 6, "Q": 5, "J": 4, "9": 3, "8": 2, "7": 1}
_NATURAL = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
_TRUMP_PTS = {"J": 20, "9": 14, "A": 11, "10": 10, "K": 4, "Q": 3, "8": 0, "7": 0}
_PLAIN_PTS = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}
_CARRE_HEIGHT = {"J": 6, "9": 5, "A": 4, "10": 3, "K": 2, "Q": 1}
_CARRE_POINTS = {"J": 200, "9": 150, "A": 100, "10": 100, "K": 100, "Q": 100}
# How many cards a combination of each class comprises -- what the showing
# reveals, one `reveal` per card.
_CLASS_SIZE = {1: 3, 2: 4, 3: 5, 4: 4}

TEAM_OF = {0: 0, 2: 0, 1: 1, 3: 1}

# A rendered card back to a Card. The observation stream carries the printed
# text -- what a seat at the table reads off the pile -- never an engine value.
_SUIT_GLYPH = {"♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades"}


def _parse(text: str) -> Card:
    return Card(text[:-1], _SUIT_GLYPH[text[-1]])


# --- the Pagat rules, re-implemented independently of the engine -----------


def _points(c: Card, trump: str) -> int:
    return _TRUMP_PTS[c.rank] if c.suit == trump else _PLAIN_PTS[c.rank]


def _winner(plays: list[tuple[Player, Card]], trump: str) -> Player:
    trumps = [(p, c) for p, c in plays if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: _TRUMP_HEIGHT[pc[1].rank])[0]
    led = plays[0][1].suit
    of_led = [(p, c) for p, c in plays if c.suit == led]
    return max(of_led, key=lambda pc: _PLAIN_HEIGHT[pc[1].rank])[0]


def _legal(
    prefix: list[tuple[Player, Card]],
    hand: list[Card],
    actor: Player,
    trump: str,
) -> tuple[list[Card], str]:
    """The legal set under the Pagat obligations (belote.md, "Play"), and
    which arm decided it -- written directly from the rulebook, independent of
    the runtime cascade. The arm label is what the census reads: it names the
    obligation that BOUND the offer, not merely a card that happened to
    occur."""
    if not prefix:
        return list(hand), "lead"
    led = prefix[0][1].suit
    best_trump = max(
        (_TRUMP_HEIGHT[c.rank] for _, c in prefix if c.suit == trump), default=0
    )
    higher = [c for c in hand if c.suit == trump and _TRUMP_HEIGHT[c.rank] > best_trump]
    trumps = [c for c in hand if c.suit == trump]

    if led == trump:
        # Beat the best trump if able ("whoever holds the trick"), else any
        # trump, else anything.
        if higher:
            return higher, "head-trump-lead"
        return (trumps, "trump-lead-cannot-head") if trumps else (list(hand), "void")

    of_led = [c for c in hand if c.suit == led]
    if of_led:
        return of_led, "follow"  # plain suits carry no head obligation
    opp_winning = TEAM_OF[_winner(prefix, trump)] != TEAM_OF[actor]
    trick_trumped = best_trump > 0
    if opp_winning:
        if trick_trumped:
            if higher:
                return higher, "over-trump"
            return (trumps, "under-trump-forced") if trumps else (list(hand), "void")
        return (trumps, "must-trump") if trumps else (list(hand), "void")
    if trick_trumped:
        # Partner winning with a trump: discard or over-trump, never
        # under-trump -- unless under-trumps are all that is left.
        allowed = [c for c in hand if c.suit != trump] + higher
        return (
            (allowed, "no-under-trump-vs-partner") if allowed else (list(hand), "void")
        )
    return list(hand), "partner-winning-free"


def _decompose(cards: list[Card], trump: str) -> list[tuple[int, int, bool, int]]:
    """(class, height, trump_flag, points) per combination -- the canonical
    decomposition of belote.md "Declarations", reimplemented independently."""
    combos: list[tuple[int, int, bool, int]] = []
    used: set[Card] = set()
    for rank in _CARRE_HEIGHT:
        of_rank = [c for c in cards if c.rank == rank]
        if len({c.suit for c in of_rank}) == 4:
            combos.append((4, _CARRE_HEIGHT[rank], False, _CARRE_POINTS[rank]))
            used.update(of_rank)
    for suit in SUITS:
        heights = sorted(
            (_NATURAL[c.rank] for c in cards if c.suit == suit and c not in used),
            reverse=True,
        )
        run = 1
        for i in range(1, len(heights) + 1):
            if i < len(heights) and heights[i] == heights[i - 1] - 1:
                run += 1
                continue
            n = min(run, 5)
            if n >= 3:
                top = heights[i - run]
                pts = {3: 20, 4: 50, 5: 100}[n]
                combos.append(({3: 1, 4: 2, 5: 3}[n], top, suit == trump, pts))
            run = 1
    return combos


# --- what a seat at the table writes down ---------------------------------

# Declaration move name -> (class, trump_flag); the Rank param is the height.
_DECLARE: dict[str, tuple[int, bool]] = {
    "declare_tierce": (1, False),
    "declare_tierce_trump": (1, True),
    "declare_quarte": (2, False),
    "declare_quarte_trump": (2, True),
    "declare_quinte": (3, False),
    "declare_quinte_trump": (3, True),
    "declare_carre": (4, False),
}
_POLL_NAMES = frozenset(_DECLARE) | {"no_declaration"}
_BELOTE_NAMES = frozenset({"say_belote", "no_belote"})
_BID_NAMES = frozenset({"take", "pass"})
_TAKE_SUIT = "take_suit("
# Every announcement this module classifies. Not derived from the game file;
# `_Table._announced` refuses anything outside it, so the list cannot fall
# silently behind the vocabulary (the ledger note above).
_VOCABULARY = _POLL_NAMES | _BELOTE_NAMES | _BID_NAMES | {"take_suit"}


@dataclass
class _Hand:
    """One deal, as the table saw it. `taker is None` means the hand was
    thrown in -- all eight announcements were passes, so no trick was
    played."""

    turnup: Card | None = None
    taker: Player | None = None
    trump: str | None = None
    named_suit: bool = False
    bids: list[tuple[Player, str]] = field(default_factory=list)
    plays: list[tuple[Player, Card]] = field(default_factory=list)
    # (winning team, the drained cards) -- the pile's payload is in ZONE
    # order, not play order, so it is compared as a multiset.
    tricks: list[tuple[int, tuple[str, ...]]] = field(default_factory=list)
    polls: list[tuple[Player, str, str | None]] = field(default_factory=list)
    belote: list[tuple[Player, str]] = field(default_factory=list)
    # The trick the Belote-Rebelote window was offered at, and every card
    # revealed (the partner royal, then the entitled side's showing).
    belote_trick: int | None = None
    reveals: list[tuple[str, Card]] = field(default_factory=list)


class _Table:
    """The public record, assembled from observer 0's stream, plus the
    candidate-set reading of the legality cascade."""

    def __init__(self) -> None:
        self.hands: list[_Hand] = []
        self.arms: Counter[str] = Counter()
        self.offer_failures: list[str] = []
        self._pending: list[tuple[Player, Card]] = []

    @property
    def _hand(self) -> _Hand:
        assert self.hands, "a table event arrived before any hand was dealt"
        return self.hands[-1]

    # --- the observation half ---------------------------------------------

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        # Observer 0's stream only, and only its PUBLIC events: the turn-up,
        # the trick pile and the capture piles all project identity to every
        # observer, an announcement is heard by every seat, and a reveal is
        # public by construction -- so seat 0 sees exactly what every other
        # seat does. (`chose` is seat 0's own private decision and is not read
        # here; the offered sets come through the chooser hook instead.)
        if player != 0:
            return
        if event[0] == "announce":
            self._announced(Player(int(event[1])), str(event[2]))
        elif event[0] == "move":
            self._moved(event)
        elif event[0] == "reveal":
            self._hand.reveals.append((str(event[1]), _parse(str(event[2]))))

    def _announced(self, who: Player, said: str) -> None:
        hand = self._hand
        name = said.partition("(")[0]
        param = said.partition("(")[2][:-1] or None
        if name in _BID_NAMES or name == "take_suit":
            hand.bids.append((who, name))
            if name == "take":
                assert hand.turnup is not None
                hand.taker, hand.trump = who, hand.turnup.suit
            elif name == "take_suit":
                assert param is not None
                hand.taker, hand.trump, hand.named_suit = who, param, True
            return
        if name in _POLL_NAMES:
            hand.polls.append((who, name, param))
            return
        if name in _BELOTE_NAMES:
            hand.belote.append((who, name))
            hand.belote_trick = len(hand.tricks)
            return
        raise AssertionError(
            f"unclassified announcement {said!r} from P{who}: this module's "
            f"vocabulary {sorted(_VOCABULARY)} has fallen behind belote.cardlang"
        )

    def _moved(self, event: tuple[Any, ...]) -> None:
        _, src, _src_view, dst, dst_view = event
        src, dst = str(src), str(dst)
        if src == "deck" and dst == "turnup":
            # One turn-up per hand, and the only movement into that zone: it
            # is where a hand begins, and its identity is what a bare `take`
            # names.
            self.hands.append(_Hand(turnup=_parse(str(dst_view[0]))))
            self._pending.clear()
        elif src.startswith("hand[") and dst == "trick_pile":
            (card_str,) = dst_view  # one card per play
            play = (Player(int(src[src.index("[") + 1 : -1])), _parse(str(card_str)))
            self._hand.plays.append(play)
            self._pending.append(play)
        elif src == "trick_pile" and dst.startswith("captured["):
            self._hand.tricks.append(
                (int(dst[len("captured[") : -1]), tuple(str(c) for c in _src_view))
            )
            self._pending.clear()

    # --- the legality rules, judged on the OFFER against the true holding ---
    #
    # A legality rule is a rule about the CANDIDATE SET, not about the one card
    # that came out of it, and the two are not the same claim: a rule the engine
    # stopped enforcing still yields a legal-looking play whenever the chooser
    # happens to pick a legal card, which is how a whole rule of the cascade can
    # be deleted with every play still checking out.
    #
    # Both SIDES of the comparison have to come from outside the filter, or the
    # check only sees one direction. The expected set is therefore recomputed
    # from the acting seat's live `hand[p]` zone -- engine state, see the module
    # docstring -- and never from the candidates: an expectation derived from
    # the offer equals the offer, so a cascade that withholds legal cards would
    # compare equal to itself.

    def offered(self, rs: Any, player: Player, candidates: list[Any], n: int) -> None:
        if n != 1 or not candidates or not all(isinstance(c, Card) for c in candidates):
            return  # not a card play: the auction, the poll, the Belote offer
        h = self._hand
        assert h.trump is not None, (
            "a card was played before any seat took: the auction's "
            "announcements went missing from the observation stream"
        )
        pool = list(rs.zones.instance("hand", player).cards)
        expected, arm = _legal(self._pending, pool, player, h.trump)
        self.arms[arm] += 1
        offer = sorted(str(c) for c in candidates)
        if offer != sorted(str(c) for c in expected):
            self.offer_failures.append(
                f"hand {len(self.hands) - 1} trick {len(h.tricks)}: P{player} "
                f"was offered {offer}, but the obligations recomputed over its "
                f"holding {sorted(str(c) for c in pool)} give "
                f"{sorted(str(c) for c in expected)} ({arm}; trump {h.trump}, "
                f"prefix {[(p, str(c)) for p, c in self._pending]})"
            )


def _play(game: Any, seed: int) -> tuple[_Table, Any]:
    table = _Table()
    rs_box: list[Any] = []
    rng = random.Random(seed)
    pick = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if rs_box:
            table.offered(rs_box[0], player, candidates, n)
        return pick(player, candidates, n)

    result = play_game(
        game,
        rng,
        None,
        chooser,
        observer=table.observe,
        on_first_decision=lambda rs: rs_box.append(rs),
    )
    return table, result


def _best_at_poll(h: _Hand, dealt: dict[Player, list[Card]], p: Player) -> Any:
    """`p`'s best combination at the declaration poll -- the hand as dealt,
    minus the card it played to trick one. `None` with no combination."""
    assert h.trump is not None
    trick1 = {q: c for q, c in h.plays[:SEATS]}
    combos = _decompose([c for c in dealt[p] if c != trick1[p]], h.trump)
    return max(combos) if combos else None


def _hand_value(h: _Hand, arms: Counter[str]) -> dict[int, int]:
    """The hand's settlement per team, recomputed from scratch per the Pagat
    rules as scoped in belote.md, over the table's own record."""
    assert h.trump is not None and h.taker is not None
    trump, taking = h.trump, TEAM_OF[h.taker]

    # The deal reconstructs from the plays; conservation over the pack.
    dealt: dict[Player, list[Card]] = {}
    for p, c in h.plays:
        dealt.setdefault(p, []).append(c)
    assert sorted(len(cs) for cs in dealt.values()) == [8, 8, 8, 8]
    assert Counter((c.rank, c.suit) for _, c in h.plays) == Counter(
        {(r, s): 1 for r in _TRUMP_HEIGHT for s in SUITS}
    ), "the 32 plays are not the full pack"
    # The turn-up came back into the taker's hand and was his to play.
    assert h.turnup is not None and h.turnup in dealt[h.taker], (
        f"the turn-up {h.turnup} never reached the taker P{h.taker}'s hand"
    )

    pts = {0: 0, 1: 0}
    tricks_won = {0: 0, 1: 0}
    for t, (team, drained) in enumerate(h.tricks):
        group = h.plays[SEATS * t : SEATS * (t + 1)]
        assert len({p for p, _ in group}) == SEATS, f"trick {t}: a seat played twice"
        # The drain's payload is in ZONE order, so only the multiset matches.
        assert Counter(str(c) for _, c in group) == Counter(drained), f"trick {t}"
        winner = _winner(group, trump)
        assert TEAM_OF[winner] == team, (
            f"trick {t}: recomputed {winner} (team {TEAM_OF[winner]}), the pile "
            f"drained to team {team}"
        )
        # Routing pins the SEAT: the winner leads the next trick (the ledger
        # note's residual is the eighth, which has no next).
        if t + 1 < TRICKS_PER_HAND:
            assert h.plays[SEATS * (t + 1)][0] == winner, (
                f"trick {t}: {winner} won but did not lead the next"
            )
        pts[team] += sum(_points(_parse(c), trump) for c in drained)
        tricks_won[team] += 1
        arms["trick"] += 1
    last_team = h.tricks[-1][0]

    # Declarations: recompute each seat's best combination from the hand at
    # the poll, check the ANNOUNCED content -- kind and trump status in the
    # move name, the top card as the Rank parameter -- states it exactly, walk
    # the announcements in poll order (strict > keeps the earlier announcer),
    # and apply the entitlement.
    assert [p for p, _, _ in h.polls] == [p for p, _ in h.plays[:SEATS]], (
        "the poll runs in the first trick's play order"
    )
    ann_pts = {0: 0, 1: 0}
    best_key = 0
    best_team: int | None = None
    for p, name, param in h.polls:
        if name == "no_declaration":
            arms["poll_silent"] += 1
            continue
        assert param is not None, f"{name} announced with no Rank parameter"
        best = _best_at_poll(h, dealt, p)
        assert best is not None, f"P{p} declared with no combination"
        cls, height, trumped, pts_best = best
        want_cls, want_trump = _DECLARE[name]
        heights = _CARRE_HEIGHT if want_cls == 4 else _NATURAL
        assert (cls, trumped) == (want_cls, want_trump) and heights[param] == height, (
            f"P{p} announced {name}({param}) but the best combination is "
            f"(class {cls}, height {height}, trump {trumped})"
        )
        ann_pts[TEAM_OF[p]] += pts_best
        arms["poll_declared"] += 1
        arms[f"poll_class_{cls}"] += 1
        key = cls * 100 + height * 2 + (1 if trumped else 0)
        if key > best_key:
            best_key, best_team = key, TEAM_OF[p]
    meld = {0: 0, 1: 0}
    if best_team is not None and tricks_won[best_team] > 0:
        meld[best_team] = ann_pts[best_team]

    # Belote-Rebelote: at most one window per hand, offered to the seat that
    # played the FIRST trump royal of its trick, and saying it banks 20 in
    # every settlement branch and reveals the partner royal.
    assert len(h.belote) <= 1, "the Belote-Rebelote window fired twice"
    bel = {0: 0, 1: 0}
    for p, name in h.belote:
        assert h.belote_trick is not None
        group = h.plays[SEATS * h.belote_trick : SEATS * (h.belote_trick + 1)]
        royals = [q for q, c in group if c.suit == trump and c.rank in ("K", "Q")]
        assert royals and royals[0] == p, (
            f"the window was offered to P{p}, but the first trump royal of "
            f"trick {h.belote_trick} was played by {royals[:1]}"
        )
        arms["belote_" + name] += 1
        if name == "say_belote":
            bel[TEAM_OF[p]] = 20

    # The showing: the entitled side's declared cards become public, one
    # `reveal` per card, and nobody else's do -- plus the one royal a
    # `say_belote` reveals from the announcer's own hand.
    shown: Counter[str] = Counter(z for z, _ in h.reveals if z.startswith("hand["))
    for p in sorted(dealt):
        want = sum(1 for q, name in h.belote if q == p and name == "say_belote")
        declared = next(
            (nm for q, nm, _ in h.polls if q == p and nm != "no_declaration"), None
        )
        if declared is not None and best_team == TEAM_OF[p]:
            best = _best_at_poll(h, dealt, p)
            assert best is not None
            want += _CLASS_SIZE[best[0]]
            arms["showed"] += 1
        assert shown.get(f"hand[{p}]", 0) == want, (
            f"P{p} revealed {shown.get(f'hand[{p}]', 0)} cards from hand, "
            f"expected {want} (showing + any Belote-Rebelote royal)"
        )

    total = {t: pts[t] + meld[t] + bel[t] for t in (0, 1)}
    if tricks_won[taking] == TRICKS_PER_HAND:
        total[taking] += 100
        arms["capot"] += 1
    else:
        total[last_team] += 10
    defending = 1 - taking
    if total[taking] >= total[defending]:
        arms["made"] += 1
        return {taking: total[taking], defending: total[defending]}
    arms["dedans"] += 1
    return {
        taking: bel[taking],
        defending: 162 + ann_pts[0] + ann_pts[1] + bel[defending],
    }


def _check_seed(game: Any, seed: int) -> Counter[str]:
    table, result = _play(game, seed)
    arms = Counter(table.arms)

    # The legality rules, judged on the CANDIDATE SETS the acting seats were
    # offered rather than on the cards that came out of them.
    assert not table.offer_failures, (
        f"seed {seed}: " + "\n  ".join(table.offer_failures[:4])
    )

    # Non-vacuity, DERIVED from the auction and asserted BEFORE any
    # recomputation below: an observation stream that went empty fails here
    # instead of leaving every loop iterating nothing.
    #
    # A hand with PLAYS but no taker is checked first, because it is the shape
    # partial loss takes: lose one hand's announcements and the hand looks
    # thrown in, and every claim below silently skips it.
    assert table.hands, f"seed {seed}: no hand was dealt at all"
    lost = [i for i, h in enumerate(table.hands) if h.taker is None and h.plays]
    assert not lost, (
        f"seed {seed}: hand(s) {lost} of {len(table.hands)} were played but no "
        f"seat took in them -- the observation stream lost those announcements, "
        f"and every claim below would skip the hand as thrown in"
    )
    played = [h for h in table.hands if h.taker is not None]
    assert played, (
        f"seed {seed}: no hand reached a contract ({len(table.hands)} dealt), so "
        f"every count below would read 0 == 0 and this block would prove nothing"
    )
    for i, h in enumerate(table.hands):
        owed = TRICKS_PER_HAND if h.taker is not None else 0
        assert len(h.tricks) == owed and len(h.plays) == SEATS * owed, (
            f"seed {seed} hand {i}: the auction owes {owed} tricks "
            f"({'taken' if h.taker is not None else 'thrown in'}), the stream "
            f"shows {len(h.tricks)} tricks / {len(h.plays)} plays"
        )
        if h.taker is None:
            assert len(h.bids) == 2 * SEATS and all(
                name == "pass" for _, name in h.bids
            ), f"seed {seed} hand {i}: a thrown-in hand is eight passes"
            arms["thrown"] += 1
        else:
            arms["named_suit" if h.named_suit else "took_turnup"] += 1

    totals = {0: 0, 1: 0}
    for h in played:
        for t, d in _hand_value(h, arms).items():
            totals[t] += d
    assert totals == result.scores, f"seed {seed}: {totals} != {result.scores}"
    assert max(result.scores.values()) >= 1000
    assert result.winner in [
        t for t, s in result.scores.items() if s == max(result.scores.values())
    ]
    return arms


def test_20_random_games_recompute_exactly() -> None:
    game = check_source(BELOTE)
    arms: Counter[str] = Counter()
    for seed in range(20):
        arms += _check_seed(game, seed)
    assert arms["made"] > 0 and arms["dedans"] > 0, arms


# The two census cells the 20-seed sweep does not reach by luck, and the seeds
# that do. Derived by execution (2026-08-19) rather than assumed, and each
# carries the count it contributes so a deal shift that moved the shape fails
# `test_the_rare_arm_seeds_still_carry_their_arm` naming the cell, instead of
# leaving the census green over an arm nothing reaches:
#
# * a THROWN-IN hand -- all eight announcements pass -- occurs once in the 615
#   hands of seeds 0-59, at seed 47. None at all in seeds 0-19, so before this
#   the `owed = 0` arm of `_check_seed` and its "eight passes" assertion ran
#   zero times: written, never executed.
# * a CAPOT -- the taking side wins all eight tricks -- occurs once in the 210
#   hands of seeds 0-19, at seed 4. Already inside the sweep, but named here
#   too, because a cell that depends on one hand in two hundred needs to say
#   WHICH hand or it rots into a coincidence nobody notices losing.
_RARE_ARM_SEEDS: dict[str, tuple[int, int]] = {"thrown": (47, 1), "capot": (4, 1)}

_CENSUS_SEEDS: tuple[int, ...] = (*range(20), _RARE_ARM_SEEDS["thrown"][0])


def test_the_rare_arm_seeds_still_carry_their_arm() -> None:
    """Each named witness seed still produces the arm it is named for.

    Without this the census would keep passing off the OTHER seeds while its
    rare cells quietly depended on nothing -- and the failure would read as
    "capot never occurred" with no hint that a named seed had drifted. Here it
    reads as the seed's own."""
    game = check_source(BELOTE)
    for cell, (seed, want) in _RARE_ARM_SEEDS.items():
        got = _check_seed(game, seed)[cell]
        assert got == want, (
            f"seed {seed} was named as the census witness for '{cell}' and now "
            f"produces {got}, not {want} — re-derive the seed (see "
            f"`_RARE_ARM_SEEDS`), do not drop the cell"
        )


def test_every_obligation_arm_is_reached() -> None:
    """Every arm of the five-rule cascade, and every vocabulary and
    settlement branch the recomputation takes, occurs over the sweep.

    The `_legal` arms are the cells that guard a RULE rather than an
    occurrence: each names the obligation that BOUND the candidate set at some
    decision, so a cell at zero would mean that rule was never exercised and
    its deletion could go unnoticed here. The rest are the arithmetic's own
    branches. The two rare ones ride named witness seeds (`_RARE_ARM_SEEDS`)
    rather than the sweep's luck.

    What is NOT a cell here, and why: the census counts what the
    RECOMPUTATION branches on, and `_hand_value`'s declaration classes
    (`poll_class_1..4`) are counted but not required — a hand holding a quinte
    or a carré is a deal accident, and the class arithmetic they select is
    already pinned by known-value tests over the decomposition
    (tests/test_belote_primitives.py). A cell whose only guard would be a rare
    deal belongs there, not here."""
    game = check_source(BELOTE)
    arms: Counter[str] = Counter()
    for seed in _CENSUS_SEEDS:
        arms += _check_seed(game, seed)
    for cell in (
        # the cascade's arms, judged on the offered set
        "lead",
        "follow",
        "head-trump-lead",
        "trump-lead-cannot-head",
        "must-trump",
        "over-trump",
        "under-trump-forced",
        "no-under-trump-vs-partner",
        "partner-winning-free",
        "void",
        # the vocabularies and the settlement
        "took_turnup",
        "named_suit",
        "thrown",
        "trick",
        "poll_declared",
        "poll_silent",
        "showed",
        "belote_say_belote",
        "belote_no_belote",
        "made",
        "dedans",
        "capot",
    ):
        assert arms[cell] > 0, f"{cell} never occurred: {arms}"


def test_seed0_characterization() -> None:
    # Byte-identity pin for one whole game: any change to the decision
    # sequence (bidding rings, the trick cascade's candidate order, the
    # declaration poll, the Belote-Rebelote window) moves this vector.
    # Measured hash-independent (identical under PYTHONHASHSEED 0-12):
    # every collection on the decision path is ordered (hand-order pools,
    # seating rings, sorted-name gathers).
    game = check_source(BELOTE)
    table, result = _play(game, 0)
    assert result.scores == {0: 1106, 1: 998}
    assert result.winner == 0
    hand = table.hands[0]
    assert (hand.taker, hand.trump, str(hand.turnup)) == (0, "diamonds", "Q♦")
    assert len(hand.tricks) == TRICKS_PER_HAND
