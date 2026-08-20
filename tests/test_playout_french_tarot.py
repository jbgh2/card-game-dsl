"""Random-playout harness for French Tarot.

Tarot is the corpus's first non-uniform deck (78 cards: four 14-card suits, 21
atouts, the Excuse). A whole hand recomputes from what the table saw: the deal
reconstructs from the cards each seat played (conservation over the 78-card
pack), trick legality is a pure function of the trick prefix and the acting
seat's holding under the four-rule cascade, the trick winner is a pure function
of the plays (highest atout, else highest of the effective led suit, and the
Excuse never wins), and the settlement is a closed formula over card points,
the bouts threshold, the petit-au-bout bonus and the bid multiplier. This
module replays every seed, recomputes ALL of it independently -- an
implementation of the FFT rules as scoped in docs/games/french-tarot.md,
written against the table's own record -- and asserts the driver's final scores
match exactly.

Where every fact comes from, and why that source
------------------------------------------------
1. OBSERVATIONS (observer 0's stream, its public half: `announce` and `move`).
   The hands are marked by the deal into the chien, the auction is what every
   seat heard, the plays are the movements into `trick_pile`, and the tricks
   are the drains into the capture piles -- `captured[player] :
   PlayerPile<player>` projects identity to every observer, so seat 0 reads the
   winner's whole capture off the table exactly as every other seat does.
   These are the facts the oracle JUDGES: a public movement every seat sees is
   a fact of the table rather than of the engine.

   What this module does NOT read is the TRACE channel, which is where it used
   to get its plays, its tricks and its per-hand scores. A trace is a harness
   channel whose emitter can retire, and a claim resting on one is a claim that
   can go silently vacuous -- issue #373, whose witnesses were this module's
   own family: Skat's and 500's oracles kept passing while iterating zero times
   once their Primitive winner stopped emitting. Nothing below reads `trace`.
2. The OFFERED SET at each decision -- the acting seat's own candidates, as
   OpenSpiel would hand them to it. A legality rule is a rule about this set,
   so it is what the four-rule cascade is checked against. Judging the card
   PLAYED instead is the reading with no teeth: a rule the engine stopped
   enforcing still yields legal-looking plays wherever the chooser happened to
   obey it anyway.
3. ENGINE STATE, at exactly one point: the acting seat's `hand[p]` zone, read
   live to recompute what the offer SHOULD have been. Both sides of that
   comparison have to come from outside the filter or it only sees one
   direction -- an expectation derived from the offer equals the offer, so a
   cascade that WITHHELD legal cards would compare equal to itself. This is a
   harness, not a player, and reading the true hand is what makes the
   comparison two-sided; the rule this module lives under is that no claim may
   rest on a trace that can retire (2 and 3 cannot), never that engine state is
   off limits.

Non-vacuity is asserted, not hoped for, and the assertion is DERIVED from the
auction rather than hard-coded: a hand where somebody took owes eighteen tricks
of four plays each, and a hand where all four seats passed owes none.
`_check_seed` pins the observed counts against that BEFORE any recomputation
loop runs. Without it an emptied observation stream would leave every loop
iterating zero times -- a green run proving nothing (the empty-input-set class,
decisions.md "Closed-domain completeness"). The arm census
(`test_every_cascade_arm_is_reached`) is the second half: the cascade has four
rules and the recomputation branches on each path through them, so a sweep that
never reached one would leave that path unchecked while every assertion above
stayed green. The rare cells ride NAMED witness seeds (`_RARE_ARM_SEEDS`)
rather than the sweep's luck.

The recomputation stays INDEPENDENT of the language's trick machinery: it never
calls `follows_lead` or `highest_by_trick_order` and never imports
`cardlang.runtime.tarot`; the FFT rules are re-implemented in Python below.

Ledger note -- what the observation stream cannot pin
-----------------------------------------------------
1. The chien and the taker's discards are NOT read from any observer's stream:
   `chien : FaceDownPile` is count-only to everyone and `discard[player] :
   HiddenPile<player>` is count-only to a non-owner, which is the point of the
   fidelity stage. They are recovered by CONSERVATION instead -- the six cards
   of the 78 that no seat played -- which is public arithmetic and needs no
   privileged read. Which of the two zones those six sit in is decided by the
   announced bid level, so the settlement's chien branch is judged from public
   facts throughout.
2. The trick winner is read off the DRAIN's destination (`trick_pile ->
   captured[w]`) and cross-checked against ROUTING -- the winner leads the next
   trick -- for tricks 1..17 of every hand. The EIGHTEENTH has no next trick,
   so it is pinned by the drain alone. Not a residual for the settlement, which
   reads the capture piles rather than the seat, but a hypothetical mis-drain
   of the last trick would surface as a points discrepancy rather than as a
   routing one.
3. The auction is classified from the announcement vocabulary (`_BID_LEVEL`),
   hand-listed here rather than derived from the game file's `move_type`s.
   Guarded rather than derived: `_Table._announced` refuses an announcement it
   cannot classify, so the list cannot fall behind the game in silence.

red under -- each plant with the assertion it fired, executed 2026-08-19 on the
pre-migration tree and reverted. Every claim above carries one, because an
oracle rewritten off its old input is exactly where a check can go quietly
toothless:
* `MustOverTrump` dropped from `active_rules` --
  `test_random_games_recompute_exactly`, "assert not table.offer_failures":
  "seed 0: hand 0 trick 1: P2 was offered ['12★', '14★', '1★', '5★'] ... give
  ['12★', '14★'] (atout-lead-over-trump)".
* `MustTrumpIfVoid` dropped -- the same assertion: "hand 0 trick 7: P3 was
  offered [its whole hand] ... give ['15★', '16★', '18★', '4★', '9★']
  (void-must-trump)".
* `ExcuseIsExempt` dropped -- the same assertion, the other direction: "hand 0
  trick 0: P0 was offered ['3♣', '6♣', 'C♣', 'Q♣'] ... give [..., 'Excuse☆',
  ...] (follow)" -- the engine WITHHOLDING a legal card, which judging the card
  played could not see.
* `tarot_trick_winner` naming the lowest atout (`max` -> `min`) -- "seed 0 hand
  0 trick 1: recomputed winner P0, the pile drained to P3".
* the settlement's one-bout threshold moved by a point (51 -> 50) -- "seed 0:
  {0: 842, ...} != {0: 796, ...}", the whole-match score comparison.
* `_Table.observe` dropping every `announce` -- the non-vacuity guard, BEFORE
  any recomputation: "seed 0: hand(s) [0..35] of 36 were played but no seat
  took in them".
* `SEEDS = 2` -- `assert not thin`, naming every cascade arm now under
  `WITNESS_SEEDS`, `excuse-lead-must-trump` among them at one seed.
"""

from __future__ import annotations

import random
from collections import Counter
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player

TAROT = Path(__file__).parent.parent / "docs" / "games" / "french-tarot.cardlang"

HANDS = 36
SEATS = 4
TRICKS_PER_HAND = 18
CHIEN = 6

# --- the FFT rules, re-implemented independently of the engine -------------

_PLAIN_SUITS = ("clubs", "diamonds", "hearts", "spades")
_PLAIN_RANKS = ("K", "Q", "C", "J", "10", "9", "8", "7", "6", "5", "4", "3", "2", "1")
# In-suit strength of a plain card: K > Q > Cavalier > J > 10 > ... > 1.
_SUIT_STR = {"K": 14, "Q": 13, "C": 12, "J": 11}
# Doubled card points (french-tarot.md: printed K=4.5 Q=3.5 C=2.5 J=1.5, a bout
# 4.5, every other card half a point). Doubled so the table is integral; the
# halving happens once, in the settlement.
_DOUBLED_POINTS = {"K": 9, "Q": 7, "C": 5, "J": 3}
# Printed card points the taker must reach, by bouts captured.
_THRESHOLD = {3: 36, 2: 41, 1: 51, 0: 56}
_MULT = {1: 1, 2: 2, 3: 4, 4: 6}

_SUIT_GLYPH = {
    "♣": "clubs", "♦": "diamonds", "♥": "hearts", "♠": "spades",
    "★": "atouts", "☆": "excuse",
}


def _parse(text: str) -> Card:
    """A rendered card back to a Card. The observation stream carries the
    printed text -- what a seat at the table reads off the pile -- never an
    engine value."""
    return Card(text[:-1], _SUIT_GLYPH[text[-1]])


def _full_deck() -> Counter[tuple[str, str]]:
    """The 78-card tarot pack, written out rather than read from the engine's
    deck registry: conservation is what this module checks, so its expectation
    may not come from the thing under test."""
    cards = [(r, s) for s in _PLAIN_SUITS for r in _PLAIN_RANKS]
    cards += [(str(n), "atouts") for n in range(1, 22)]
    cards.append(("Excuse", "excuse"))
    return Counter(cards)


def _is_bout(c: Card) -> bool:
    """A bout (oudler): the Excuse, the 1 of atouts (petit), or the 21."""
    return c.suit == "excuse" or (c.suit == "atouts" and c.rank in ("1", "21"))


def _doubled_points(c: Card) -> int:
    return 9 if _is_bout(c) else _DOUBLED_POINTS.get(c.rank, 1)


def _suit_strength(c: Card) -> int:
    return _SUIT_STR.get(c.rank, 0) or int(c.rank)


def _effective_led(prefix: list[Card]) -> str | None:
    """The suit the trick demands: the first NON-Excuse card's. `None` while
    only the Excuse is down -- it leads to nothing, and the next card sets the
    suit."""
    for c in prefix:
        if c.suit != "excuse":
            return c.suit
    return None


def _winner(plays: list[tuple[Player, Card]]) -> Player:
    """Highest atout if any was played, else the highest card of the effective
    led suit. The Excuse is neither, so it never wins."""
    atouts = [(p, c) for p, c in plays if c.suit == "atouts"]
    if atouts:
        return max(atouts, key=lambda pc: int(pc[1].rank))[0]
    led = _effective_led([c for _, c in plays])
    assert led is not None, f"a complete trick of Excuses alone: {plays}"
    of_led = [(p, c) for p, c in plays if c.suit == led]
    return max(of_led, key=lambda pc: _suit_strength(pc[1]))[0]


def _legal(prefix: list[Card], hand: list[Card]) -> tuple[list[Card], str]:
    """The legal set under the four-rule cascade (french-tarot.md, "Play"), and
    which path through it decided the offer -- written from the rulebook,
    independent of the runtime cascade.

    The arm label names the obligations that BOUND the offer, not a card that
    happened to occur. `excuse-lead-must-trump` is the corpus's known
    divergence from Pagat (issue #357): with only the Excuse down nothing
    satisfies the follow demand, so the must-trump rule binds the next seat to
    its atouts where Pagat would let it play anything.
    """
    if not prefix:
        return list(hand), "lead"
    # ExcuseIsExempt: outside the cascade entirely, appended last, in hand
    # order.
    exempt = [c for c in hand if c.suit == "excuse"]
    working = [c for c in hand if c.suit != "excuse"]
    result = list(working)
    parts: list[str] = []

    led = _effective_led(prefix)
    followers = [c for c in working if c.suit == led] if led is not None else []
    if followers:  # MustFollowEffectiveSuit
        result = followers
        parts.append("atout-lead" if led == "atouts" else "follow")
    else:
        parts.append("excuse-lead" if led is None else "void")
    trumps = [c for c in result if c.suit == "atouts"]  # MustTrumpIfVoid
    if trumps:
        result = trumps
        if not followers:
            parts.append("must-trump")
    elif not followers:
        parts.append("no-trump")
    if any(c.suit == "atouts" for c in prefix):  # MustOverTrump
        best = max(int(c.rank) for c in prefix if c.suit == "atouts")
        higher = [c for c in result if c.suit == "atouts" and int(c.rank) > best]
        if higher:
            result = higher
            parts.append("over-trump")
        elif any(c.suit == "atouts" for c in result):
            parts.append("under-trump-forced")
    return result + exempt, "-".join(parts)


def _is_pref_discard(c: Card) -> bool:
    """The preferred chien discard: a plain-suit non-King."""
    return c.suit not in ("atouts", "excuse") and c.rank != "K"


def _discard_pool(hand: list[Card]) -> tuple[list[Card], str]:
    """The pool the taker discards six from, and which branch chose it."""
    pref = [c for c in hand if _is_pref_discard(c)]
    if len(pref) >= CHIEN:
        return pref, "discard-preferred"
    return [c for c in hand if not _is_bout(c)], "discard-fallback"


# --- what a seat at the table writes down ---------------------------------

# Every auction announcement this module classifies, and the level it names.
# Not derived from the game file; `_Table._announced` refuses anything outside
# it, so the list cannot fall silently behind the vocabulary (ledger note 3).
_BID_LEVEL: dict[str, int] = {
    "pass": 0,
    "bid_petite": 1,
    "bid_garde": 2,
    "bid_garde_sans": 3,
    "bid_garde_contre": 4,
}


@dataclass
class _Hand:
    """One deal, as the table saw it. `taker is None` means every seat passed,
    so the hand was thrown in and no trick was played."""

    taker: Player | None = None
    level: int = 0
    bids: list[tuple[Player, str]] = field(default_factory=list)
    plays: list[tuple[Player, Card]] = field(default_factory=list)
    # (winning seat, that trick's four cards in play order).
    tricks: list[tuple[Player, tuple[Card, ...]]] = field(default_factory=list)
    # Seat -> what ended in its capture pile, Excuse routing and the low-card
    # repayment included.
    captured: dict[Player, list[Card]] = field(default_factory=dict)


@dataclass(frozen=True)
class _Witness:
    """One offer made to a seat following a LED EXCUSE -- the shape issue #357
    names, recorded on the way past so the quirk is pinned from the same sweep
    the rest of the module runs."""

    holding: tuple[str, ...]
    offer: tuple[str, ...]
    holds_atout: bool


class _Table:
    """The public record, assembled from observer 0's stream, plus the
    candidate-set reading of the legality cascade."""

    def __init__(self) -> None:
        self.hands: list[_Hand] = []
        self.arms: Counter[str] = Counter()
        self.offer_failures: list[str] = []
        self.excuse_lead_witnesses: list[_Witness] = []
        self._pending: list[tuple[Player, Card]] = []

    @property
    def _hand(self) -> _Hand:
        assert self.hands, "a table event arrived before any hand was dealt"
        return self.hands[-1]

    # --- the observation half ---------------------------------------------

    def observe(self, player: Player, event: tuple[Any, ...]) -> None:
        # Observer 0's stream only, and only its PUBLIC events: the trick pile
        # and the capture piles project identity to every observer and an
        # announcement is heard by every seat, so seat 0 sees exactly what
        # every other seat does. (`chose` is seat 0's own private decision and
        # is not read here; the offered sets come through the chooser hook.)
        if player != 0:
            return
        if event[0] == "announce":
            self._announced(Player(int(event[1])), str(event[2]))
        elif event[0] == "move":
            self._moved(event)

    def _announced(self, who: Player, said: str) -> None:
        level = _BID_LEVEL.get(said)
        assert level is not None, (
            f"unclassified announcement {said!r} from P{who}: this module's "
            f"vocabulary {sorted(_BID_LEVEL)} has fallen behind "
            f"french-tarot.cardlang"
        )
        hand = self._hand
        hand.bids.append((who, said))
        if level > hand.level:
            hand.taker, hand.level = who, level

    def _moved(self, event: tuple[Any, ...]) -> None:
        _, src, src_view, dst, _dst_view = event
        src, dst = str(src), str(dst)
        if src == "deck" and dst == "chien":
            # One deal into the chien per hand, and the only movement into that
            # zone: it is where a hand begins.
            self.hands.append(_Hand())
            self._pending.clear()
        elif src.startswith("hand[") and dst == "trick_pile":
            (card_str,) = _dst_view  # one card per play
            play = (Player(int(src[src.index("[") + 1 : -1])), _parse(str(card_str)))
            self._hand.plays.append(play)
            self._pending.append(play)
        elif src == "trick_pile" and dst.startswith("captured["):
            seat = Player(int(dst[len("captured[") : -1]))
            drained = [_parse(str(c)) for c in src_view]
            self._hand.captured.setdefault(seat, []).extend(drained)
            if all(c.suit == "excuse" for c in drained):
                return  # the Excuse's own split drain; the winner takes the rest
            self._hand.tricks.append((seat, tuple(c for _, c in self._pending)))
            self._pending.clear()
        elif src.startswith("captured[") and dst.startswith("captured["):
            # The Excuse's compensation: one low card from the Excuse player's
            # pile to the trick winner's.
            frm = Player(int(src[len("captured[") : -1]))
            to = Player(int(dst[len("captured[") : -1]))
            for c in (_parse(str(x)) for x in src_view):
                self._hand.captured[frm].remove(c)
                self._hand.captured.setdefault(to, []).append(c)

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
        if not candidates or not all(isinstance(c, Card) for c in candidates):
            return  # the auction: an announcement vocabulary, not cards
        pool = list(rs.zones.instance("hand", player).cards)
        prefix = [c for _, c in self._pending]
        if n == CHIEN:
            # The chien discard -- a six-card pick, so `n` alone tells it from a
            # play. Its filter is the game's own two-branch rule.
            expected, arm = _discard_pool(pool)
        else:
            assert n == 1, f"an unrecognized {n}-card decision for P{player}"
            expected, arm = _legal(prefix, pool)
            if prefix and any(c.suit == "excuse" for c in candidates):
                self.arms["excuse-offered-under-an-obligation"] += 1
            if prefix and _effective_led(prefix) is None:
                self.excuse_lead_witnesses.append(
                    _Witness(
                        tuple(sorted(str(c) for c in pool)),
                        tuple(sorted(str(c) for c in candidates)),
                        any(c.suit == "atouts" for c in pool),
                    )
                )
        assert arm in _CASCADE_ARMS | _DISCARD_ARMS, (
            f"`_legal` produced the unclassified path {arm!r} -- add it to "
            f"`_CASCADE_ARMS` and to the census, or the sweep counts a rule "
            f"path nothing asserts is reached"
        )
        self.arms[arm] += 1
        offer = sorted(str(c) for c in candidates)
        if offer != sorted(str(c) for c in expected):
            self.offer_failures.append(
                f"hand {len(self.hands) - 1} trick {len(self._hand.tricks)}: "
                f"P{player} was offered {offer}, but the rules recomputed over "
                f"its holding {sorted(str(c) for c in pool)} give "
                f"{sorted(str(c) for c in expected)} ({arm}; prefix "
                f"{[(p, str(c)) for p, c in self._pending]})"
            )


def _play(game: Any, seed: int) -> tuple[_Table, Any]:
    tbl = _Table()
    rs_box: list[Any] = []
    rng = random.Random(seed)
    pick = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if rs_box:
            tbl.offered(rs_box[0], player, candidates, n)
        return pick(player, candidates, n)

    result = play_game(
        game,
        rng,
        None,
        chooser,
        observer=tbl.observe,
        on_first_decision=lambda rs: rs_box.append(rs),
    )
    return tbl, result


def _hand_value(h: _Hand, arms: Counter[str]) -> int:
    """The per-opponent settlement amount for one played hand, recomputed from
    scratch per french-tarot.md step 5 over the table's own record. The taker
    collects three times this and each opponent pays it (zero-sum)."""
    assert h.taker is not None

    # Conservation: the 72 plays are 72 distinct cards of the pack, and the six
    # the table never saw are the chien (Garde sans / Garde contre) or the
    # taker's hidden discards (Petite / Garde) -- recovered as the complement,
    # never read from a concealed zone.
    played = Counter((c.rank, c.suit) for _, c in h.plays)
    outside = played - _full_deck()
    assert not outside, f"cards outside the pack were played: {sorted(outside)}"
    leftover = [
        Card(r, s) for (r, s), k in (_full_deck() - played).items() for _ in range(k)
    ]
    assert len(leftover) == CHIEN, f"{len(leftover)} cards unaccounted for"

    taker_doubled = sum(_doubled_points(c) for c in h.captured.get(h.taker, []))
    bouts = sum(1 for c in h.captured.get(h.taker, []) if _is_bout(c))
    if h.level <= 2:
        # The discards still count to the taker, and both discard filters
        # exclude every bout by construction, so they can never add one.
        assert not any(_is_bout(c) for c in leftover), (
            f"a bout reached the taker's discard: {[str(c) for c in leftover]}"
        )
        taker_doubled += sum(_doubled_points(c) for c in leftover)
        arms["chien-discarded"] += 1
    elif h.level == 3:
        taker_doubled += sum(_doubled_points(c) for c in leftover)
        bouts += sum(1 for c in leftover if _is_bout(c))
        arms["chien-to-taker-unseen"] += 1
    else:
        arms["chien-to-opponents"] += 1
    arms[f"bouts-{bouts}"] += 1

    last_winner, last_trick = h.tricks[-1]
    petit_in_last = any(c.suit == "atouts" and c.rank == "1" for c in last_trick)
    pb = 0
    if petit_in_last:
        for_taker = last_winner == h.taker
        arms["petit-au-bout-for" if for_taker else "petit-au-bout-against"] += 1
        pb = 10 if for_taker else -10

    pt = taker_doubled / 2 - _THRESHOLD[bouts]
    arms["taker-made" if pt >= 0 else "taker-missed"] += 1
    return round((25 + pt + pb) * _MULT[h.level])


def _check_seed(game: Any, seed: int) -> tuple[_Table, Counter[str]]:
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
    assert len(table.hands) == HANDS, (
        f"seed {seed}: the stream shows {len(table.hands)} hands, expected "
        f"{HANDS}"
    )
    lost = [i for i, h in enumerate(table.hands) if h.taker is None and h.plays]
    assert not lost, (
        f"seed {seed}: hand(s) {lost} of {len(table.hands)} were played but no "
        f"seat took in them -- the observation stream lost those announcements, "
        f"and every claim below would skip the hand as thrown in"
    )
    played = [h for h in table.hands if h.taker is not None]
    assert played, (
        f"seed {seed}: no hand reached a contract, so every count below would "
        f"read 0 == 0 and this block would prove nothing"
    )
    for i, h in enumerate(table.hands):
        owed = TRICKS_PER_HAND if h.taker is not None else 0
        assert len(h.tricks) == owed and len(h.plays) == SEATS * owed, (
            f"seed {seed} hand {i}: the auction owes {owed} tricks "
            f"({'taken' if h.taker is not None else 'thrown in'}), the stream "
            f"shows {len(h.tricks)} tricks / {len(h.plays)} plays"
        )
        assert len(h.bids) == SEATS, (
            f"seed {seed} hand {i}: {len(h.bids)} announcements, expected one "
            f"per seat"
        )
        if h.taker is None:
            assert all(name == "pass" for _, name in h.bids), (
                f"seed {seed} hand {i}: a thrown-in hand is four passes"
            )
            arms["hand-thrown-in"] += 1
        else:
            arms[f"contract-{h.level}"] += 1

    scores = {p: 0 for p in range(SEATS)}
    for i, h in enumerate(played):
        for t, (drained_to, cards) in enumerate(h.tricks):
            group = h.plays[SEATS * t : SEATS * (t + 1)]
            assert {p for p, _ in group} == set(range(SEATS)), (
                f"seed {seed} hand {i} trick {t}: a seat played twice"
            )
            assert tuple(c for _, c in group) == cards
            w = _winner(group)
            assert w == drained_to, (
                f"seed {seed} hand {i} trick {t}: recomputed winner P{w}, the "
                f"pile drained to P{drained_to}"
            )
            assert next(c for p, c in group if p == w).suit != "excuse", (
                f"seed {seed} hand {i} trick {t}: the Excuse won the trick"
            )
            if t + 1 < TRICKS_PER_HAND:
                assert h.plays[SEATS * (t + 1)][0] == w, (
                    f"seed {seed} hand {i} trick {t}: P{w} won but did not lead "
                    f"the next"
                )
            trumped = any(c.suit == "atouts" for _, c in group)
            arms["trick-won-on-atout" if trumped else "trick-won-on-led-suit"] += 1
            excuse = [p for p, c in group if c.suit == "excuse"]
            if excuse:
                arms["excuse-played"] += 1
                same_side = (excuse[0] == h.taker) == (w == h.taker)
                arms["excuse-stayed-with-the-winner" if same_side
                     else "excuse-split-from-the-trick"] += 1

        v = _hand_value(h, arms)
        for p in range(SEATS):
            scores[p] += 3 * v if p == h.taker else -v

    assert sum(scores.values()) == 0, f"seed {seed}: the settlement is not zero-sum"
    assert scores == result.scores, f"seed {seed}: {scores} != {result.scores}"
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])
    return table, arms


# --- the sweep, run once ---------------------------------------------------

# Every path through the cascade `_legal` can label. Hand-written, but it
# cannot fall behind: `_Table.offered` refuses a label outside this set, so a
# new path fails at the decision that produced it rather than sitting
# uncounted. The two `atout-lead` paths have no bare form -- a trump lead puts
# a trump in the pile, so MustOverTrump always appends one of its two labels.
_CASCADE_ARMS: frozenset[str] = frozenset(
    {
        "lead",
        "follow",
        "atout-lead-over-trump",
        "atout-lead-under-trump-forced",
        "void-must-trump",
        "void-must-trump-over-trump",
        "void-must-trump-under-trump-forced",
        "void-no-trump",
        "excuse-lead-must-trump",
        "excuse-lead-no-trump",
    }
)
_DISCARD_ARMS: frozenset[str] = frozenset({"discard-preferred", "discard-fallback"})

# Every CASCADE arm not riding a named seed must fire on at least this many
# DISTINCT seeds of the sweep. One witness would be satisfiable by a single
# lucky deal, which is what makes a seed count unfalsifiable; with three, the
# count is load-bearing and a cut reddens. Scoped to the cascade because that
# is what the sweep SIZE is for -- the settlement's branches are deal
# accidents, and the census below asks only that each occurs.
WITNESS_SEEDS = 3

# Eight seeds. Measured 2026-08-19: every cascade arm but `excuse-lead-no-trump`
# fires on at least six of the first eight, so eight is the smallest round
# figure with headroom over WITNESS_SEEDS for a change that shifts one arm off
# an early seed.
#
# red under: SEEDS = 2 -- `assert not thin` names every cascade arm now
# under WITNESS_SEEDS, `excuse-lead-must-trump` among them at one seed
# (executed 2026-08-19).
SEEDS = 8

# The cells the eight-seed sweep does not reach at all, and the seeds that do.
# Derived by execution over seeds 0-59 (2026-08-19) rather than assumed, and
# each carrying the count it contributes so a deal shift that moved the shape
# fails `test_the_rare_arm_seeds_still_carry_their_arm` naming the cell,
# instead of leaving the census green over an arm nothing reaches:
#
# * a seat following a LED EXCUSE while holding no atout at all
#   (`excuse-lead-no-trump`) -- the other half of issue #357's shape, where the
#   must-trump rule cannot bind and the seat is free. Four occurrences in the
#   2160 hands of seeds 0-59, the first at seed 11.
# * a THROWN-IN hand -- all four seats pass -- occurs at seeds 20, 35, 50 and
#   51 of the first sixty and NOWHERE in seeds 0-7, so before this the `owed =
#   0` arm of `_check_seed` and its "four passes" assertion ran zero times:
#   written, never executed. (The predecessor of this module counted an
#   all-zero score delta as a thrown-in hand, which a settled hand worth
#   nothing also produces -- so its `hand_thrown_in` arm was green over
#   hands that were played to the end.)
_RARE_ARM_SEEDS: dict[str, tuple[int, int]] = {
    "excuse-lead-no-trump": (11, 1),
    "hand-thrown-in": (20, 1),
}

_CENSUS_SEEDS: tuple[int, ...] = (
    *range(SEEDS),
    *sorted({seed for seed, _ in _RARE_ARM_SEEDS.values()}),
)

# Every cell the census requires. The cascade and discard arms guard a RULE;
# the rest are the settlement arithmetic's own branches, each of which some
# assertion in `_hand_value` or `_check_seed` would otherwise take vacuously.
#
# `discard-fallback` is deliberately NOT here: the taker would have to hold
# fewer than six plain non-Kings among 24 cards, which does not occur in the
# 2160 hands of seeds 0-59 (measured 2026-08-19). A cell whose only witness
# would be a deal nothing reaches must not read as covered; the branch is
# exercised as a unit instead (`test_the_discard_fallback_branch_is_a_unit`).
_CENSUS_CELLS: tuple[str, ...] = (
    *sorted(_CASCADE_ARMS),
    "discard-preferred",
    "excuse-offered-under-an-obligation",
    "hand-thrown-in",
    "contract-1",
    "contract-2",
    "contract-3",
    "contract-4",
    "chien-discarded",
    "chien-to-taker-unseen",
    "chien-to-opponents",
    "bouts-0",
    "bouts-1",
    "bouts-2",
    "bouts-3",
    "trick-won-on-atout",
    "trick-won-on-led-suit",
    "excuse-played",
    "excuse-stayed-with-the-winner",
    "excuse-split-from-the-trick",
    "petit-au-bout-for",
    "petit-au-bout-against",
    "taker-made",
    "taker-missed",
)


@cache
def _sweep() -> tuple[dict[int, Counter[str]], tuple[tuple[int, _Witness], ...]]:
    """Every census seed, replayed and recomputed once. Cached because four
    tests read the same sweep and a tarot match is 36 hands of 18 tricks; the
    assertions live in `_check_seed`, so a failing seed fails every reader
    rather than one."""
    game = check_source(TAROT)
    per_seed: dict[int, Counter[str]] = {}
    witnesses: list[tuple[int, _Witness]] = []
    for seed in _CENSUS_SEEDS:
        table, arms = _check_seed(game, seed)
        per_seed[seed] = arms
        witnesses.extend((seed, w) for w in table.excuse_lead_witnesses)
    return per_seed, tuple(witnesses)


def test_random_games_recompute_exactly() -> None:
    """The sweep itself: every seed's whole match recomputes to the driver's
    own scores (the assertions are `_check_seed`'s), and no cascade arm rests
    on a single deal."""
    per_seed, _ = _sweep()
    witnessed: dict[str, list[int]] = {}
    for seed in range(SEEDS):
        for arm, count in per_seed[seed].items():
            if count and arm in _CASCADE_ARMS:
                witnessed.setdefault(arm, []).append(seed)
    thin = {
        a: witnessed.get(a, [])
        for a in _CASCADE_ARMS - set(_RARE_ARM_SEEDS)
        if len(witnessed.get(a, [])) < WITNESS_SEEDS
    }
    assert not thin, (
        f"{thin} fire on fewer than {WITNESS_SEEDS} of the {SEEDS} sweep seeds "
        f"-- the seed count no longer carries the arms it was derived from; "
        f"raise SEEDS, or name a witness seed in `_RARE_ARM_SEEDS`"
    )


def test_the_rare_arm_seeds_still_carry_their_arm() -> None:
    """Each named witness seed still produces the arm it is named for.

    Without this the census would keep passing off the OTHER seeds while its
    rare cells quietly depended on nothing -- and the failure would read as
    "the arm never occurred" with no hint that a named seed had drifted. Here
    it reads as the seed's own."""
    per_seed, _ = _sweep()
    for cell, (seed, want) in _RARE_ARM_SEEDS.items():
        got = per_seed[seed][cell]
        assert got == want, (
            f"seed {seed} was named as the census witness for '{cell}' and now "
            f"produces {got}, not {want} -- re-derive the seed (see "
            f"`_RARE_ARM_SEEDS`), do not drop the cell"
        )


def test_every_cascade_arm_is_reached() -> None:
    """Every cell of `_CENSUS_CELLS` occurs over the census seeds.

    The cascade arms are the cells that guard a RULE rather than an occurrence:
    each names the obligations that BOUND the candidate set at some decision,
    so a cell at zero would mean that path was never exercised and a rule's
    deletion could go unnoticed here. The rest are the arithmetic's own
    branches."""
    per_seed, _ = _sweep()
    arms: Counter[str] = Counter()
    for counter in per_seed.values():
        arms += counter
    missing = [cell for cell in _CENSUS_CELLS if not arms[cell]]
    assert not missing, f"{missing} never occurred: {dict(sorted(arms.items()))}"


def test_the_excuse_lead_quirk_is_preserved() -> None:
    """The corpus's known divergence from Pagat, pinned as a fact of the
    candidate set rather than of the prose (issue #357).

    Pagat: after a led Excuse "the second player to the trick can play any
    card". The corpus: nothing satisfies the follow demand while only the
    Excuse is down, so `MustTrumpIfVoid` binds and a seat holding atouts is
    offered its atouts alone. #357 owns the correction; every migration carries
    the quirk across unchanged, and this is what reddens if one silently fixes
    it."""
    _, witnesses = _sweep()
    narrowed = [(seed, w) for seed, w in witnesses if w.holds_atout]
    assert narrowed, (
        f"no seat followed a led Excuse holding an atout over "
        f"{len(_CENSUS_SEEDS)} seeds -- the quirk this pins is unreachable "
        f"here, so re-derive the seeds rather than deleting the test"
    )
    for seed, w in narrowed:
        assert all(c.endswith("★") for c in w.offer), (
            f"seed {seed}: a seat following a led Excuse from holding "
            f"{w.holding} was offered {w.offer} -- the corpus quirk narrows it "
            f"to atouts alone (issue #357 owns the Pagat correction)"
        )
    free = [(seed, w) for seed, w in witnesses if not w.holds_atout]
    for seed, w in free:
        assert w.offer == tuple(sorted(w.holding)), (
            f"seed {seed}: a seat following a led Excuse with no atout was "
            f"offered {w.offer} out of {w.holding} -- with the must-trump rule "
            f"unable to bind, nothing narrows the hand"
        )


def test_the_discard_fallback_branch_is_a_unit() -> None:
    """`_discard_pool`'s fallback arm, which no deal in seeds 0-59 reaches
    (`_CENSUS_CELLS`' note), exercised directly.

    The branch exists in the game file (`else { move chosen 6 cards ... where
    not is_bout(card) }`), so the recomputation must carry it; a branch the
    sweep cannot reach and no unit drives is code nothing executes."""
    hand = [Card(str(n), "atouts") for n in range(2, 21)] + [
        Card("K", "clubs"), Card("K", "hearts"), Card("K", "spades"),
        Card("1", "atouts"), Card("Excuse", "excuse"),
    ]
    pool, arm = _discard_pool(hand)
    assert arm == "discard-fallback"
    assert all(not _is_bout(c) for c in pool)
    assert len(pool) == len(hand) - 2  # the petit and the Excuse are bouts
    plain = [Card(str(n), "hearts") for n in range(1, 11)]
    assert _discard_pool(plain + hand)[1] == "discard-preferred"


def test_seed0_characterization() -> None:
    """Byte-identity pin for one whole game: any change to the decision
    sequence (the auction ring, the chien discard, the trick cascade's
    candidate order) moves this vector. Measured hash-independent: every
    collection on the decision path is ordered (hand-order pools, seating
    rings)."""
    game = check_source(TAROT)
    table, result = _play(game, 0)
    assert result.scores == {0: 842, 1: 1142, 2: -1542, 3: -442}
    assert result.winner == 1
    assert len(table.hands) == HANDS
    assert table.hands[0].taker == 2 and table.hands[0].level == 4
