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
`_verify` pins the observed counts against that BEFORE any recomputation
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
   facts throughout. The ONE public exception is the forced discard's atouts:
   they pass through `shown_atouts : Discard` (identity to every seat) on
   their way into the hidden discard, so the table DOES see them --
   `_Table._moved` records the arrivals, and `_hand_value` holds each shown
   card against the conservation complement. A Garde sans / Garde contre
   hand moves no discard, so `shown` stays empty there -- `_hand_value`
   asserts that before reading the level, and the assert's red needs a
   two-edit plant (its comment records the executed pair; every single
   edit is caught elsewhere first).
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
* the forced branch's force-move dropped (one chosen-six pick over `not
  is_bout`, Kings offered) -- `_discard_pool`'s "the discard pick was offered
  while 3 plain non-Kings were still in hand" assert, via the stacked
  witness (executed 2026-08-30, against the game text this module's rule
  rewrite preceded).
* `shown_atouts` demoted to `FaceDownPile` (count-only) -- `_Table._moved`'s
  "the zone must project identity to every seat" assert, before any
  stacked-test comparison runs (executed 2026-08-30).
* a duplicated card in `_pack()` (a second 5 of diamonds in place of the 6)
  -- `_RiggedFirstShuffle.shuffle`'s "not a permutation of the engine's own
  deck" assert; without it the stacked witness stays green over a pack the
  game does not declare, its conservation check derived from the same list
  (executed 2026-08-30).
* the `taken` arm pinning `bid_level := 1` while the stacked script bids
  `bid_garde_sans` -- `_hand_value`'s "were shown on a level-3 contract"
  assert; a two-edit plant, each single edit caught elsewhere first
  (executed 2026-08-30).
"""

from __future__ import annotations

import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import cache
from pathlib import Path
from typing import Any

import pytest

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


def _pack() -> list[Card]:
    """The 78-card tarot pack, written out rather than read from the engine's
    deck registry: conservation is what this module checks, so its expectation
    may not come from the thing under test."""
    cards = [Card(r, s) for s in _PLAIN_SUITS for r in _PLAIN_RANKS]
    cards += [Card(str(n), "atouts") for n in range(1, 22)]
    cards.append(Card("Excuse", "excuse"))
    return cards


def _full_deck() -> Counter[tuple[str, str]]:
    return Counter((c.rank, c.suit) for c in _pack())


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


def _discard_pool(hand: list[Card]) -> tuple[list[Card], int, str]:
    """The pool the taker's discard pick draws from, the pick's size, and which
    branch chose it -- recomputed over the acting seat's LIVE hand at the
    decision (french-tarot.md, "Chien").

    Preferred: six chosen from the plain non-Kings. Forced (fewer than six
    exist): every plain non-King has already been force-moved into the discard
    before the pick, so the live hand holds none, and the pick tops the discard
    up to six from the non-bout atouts -- Kings and bouts are never
    discardable, and an atout is discardable only for want of anything else.
    Both arms size the pick by the same arithmetic -- it returns the live
    hand to the 18 a seat plays tricks from -- so a merge or deal defect
    that hands the taker anything but 24 cards fails at the pick, sized and
    named, rather than two layers later as a trick-count discrepancy."""
    pref = [c for c in hand if _is_pref_discard(c)]
    if len(pref) >= CHIEN:
        return pref, len(hand) - 18, "discard-preferred"
    assert not pref, (
        f"the discard pick was offered while {len(pref)} plain non-Kings were "
        f"still in hand -- the forced branch moves ALL of them first"
    )
    atouts = [c for c in hand if c.suit == "atouts" and not _is_bout(c)]
    return atouts, len(hand) - 18, "discard-forced"


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
    # The forced discard's atouts, read off their public arrival in
    # `shown_atouts` -- empty on any hand whose taker discards six plain
    # non-Kings.
    shown: list[Card] = field(default_factory=list)


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
        _, src, src_view, dst, dst_view = event
        src, dst = str(src), str(dst)
        if src == "deck" and dst == "chien":
            # One deal into the chien per hand, and the only movement into that
            # zone: it is where a hand begins.
            self.hands.append(_Hand())
            self._pending.clear()
        elif src.startswith("hand[") and dst == "trick_pile":
            (card_str,) = dst_view  # one card per play
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
        elif dst == "shown_atouts":
            # The forced discard's atouts, shown to the whole table on their way
            # into the hidden discard: `shown_atouts : Discard` projects
            # identity to every observer, so seat 0 reads the arrivals exactly
            # as every other seat does. (The onward tuck into `discard[taker]`
            # needs no branch: its destination is hidden and its cards are
            # these.)
            assert isinstance(dst_view, tuple), (
                f"shown_atouts arrived as {dst_view!r} in observer 0's public "
                f"stream -- the zone must project identity to every seat, or "
                f"the forced discard's reveal does not exist"
            )
            self._hand.shown.extend(_parse(str(c)) for c in dst_view)

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
        if len(pool) > 18:
            # The discard pick: only there does the acting seat hold more than a
            # trick hand's 18 cards (24 on the preferred branch, 24 minus the
            # force-moved plain non-Kings on the forced one -- at least 19
            # either way). `n` no longer discriminates: the forced pick is
            # sized 6 minus the force-moved count, which reaches 1.
            expected, want_n, arm = _discard_pool(pool)
            assert n == want_n, (
                f"hand {len(self.hands) - 1}: P{player}'s discard pick is sized "
                f"{n}, but the rules over its {len(pool)}-card holding size "
                f"it {want_n} ({arm})"
            )
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


def _play(
    game: Any,
    rng: random.Random,
    script: Callable[[Player, list[Any], int], list[Any] | None] | None = None,
    tap: Callable[[Player, tuple[Any, ...]], None] | None = None,
) -> tuple[_Table, Any]:
    """One full match against the table's record. `script` may claim any
    decision (return None to leave it to the random pick); `tap` sees every
    observer's raw event stream where `_Table` keeps only seat 0's."""
    tbl = _Table()
    rs_box: list[Any] = []
    pick = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        if rs_box:
            tbl.offered(rs_box[0], player, candidates, n)
        if script is not None:
            scripted = script(player, candidates, n)
            if scripted is not None:
                return scripted
        return pick(player, candidates, n)

    def observe(player: Player, event: tuple[Any, ...]) -> None:
        if tap is not None:
            tap(player, event)
        tbl.observe(player, event)

    result = play_game(
        game,
        rng,
        None,
        chooser,
        observer=observe,
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
    # A no-discard contract can show nothing. red under a TWO-edit plant only
    # (executed 2026-08-30): the `taken` arm pinning `bid_level := 1` while
    # the stacked script bids garde_sans -- each single edit fires elsewhere
    # first (the seed-0 score comparison, or the rare-arm census). It stays
    # because it is the one reader of that state: without it a shown card on
    # a level-3/4 hand would skip the whole block below in silence.
    assert not h.shown or h.level <= 2, (
        f"atouts {[str(c) for c in h.shown]} were shown on a level-{h.level} "
        f"contract, which moves no discard at all"
    )
    if h.level <= 2:
        # The discards still count to the taker, and both discard filters
        # exclude every bout by construction, so they can never add one.
        assert not any(_is_bout(c) for c in leftover), (
            f"a bout reached the taker's discard: {[str(c) for c in leftover]}"
        )
        # The shown atouts are discard cards the whole table saw: each is a
        # non-bout atout and sits among the six the conservation complement
        # recovers. A preferred-branch hand shows nothing. Shadow Guards: the
        # offer comparison (`_discard_pool` through `offered`) owns the
        # filter claim and the pick-size assert owns membership -- every
        # single-edit plant fires there first (measured 2026-08-30); these
        # restate the claims at the settlement, where a defect past those
        # walls would land.
        remainder = Counter((c.rank, c.suit) for c in leftover)
        for c in h.shown:
            assert c.suit == "atouts" and not _is_bout(c), (
                f"{c} was shown into the discard, but only a non-bout atout is "
                f"ever forced there"
            )
            assert remainder[(c.rank, c.suit)] > 0, (
                f"{c} was shown into the discard yet is not among the six cards "
                f"the table never saw played"
            )
            remainder[(c.rank, c.suit)] -= 1
        if h.shown:
            arms["forced-atouts-shown"] += 1
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
    table, result = _play(game, random.Random(seed))
    return table, _verify(table, result, f"seed {seed}")


def _verify(table: _Table, result: Any, label: str) -> Counter[str]:
    """Every claim this module makes about one match, over the table's own
    record -- shared by the seed sweep and the stacked-deal witness."""
    arms = Counter(table.arms)

    # The legality rules, judged on the CANDIDATE SETS the acting seats were
    # offered rather than on the cards that came out of them.
    assert not table.offer_failures, (
        f"{label}: " + "\n  ".join(table.offer_failures[:4])
    )

    # Non-vacuity, DERIVED from the auction and asserted BEFORE any
    # recomputation below: an observation stream that went empty fails here
    # instead of leaving every loop iterating nothing.
    #
    # A hand with PLAYS but no taker is checked first, because it is the shape
    # partial loss takes: lose one hand's announcements and the hand looks
    # thrown in, and every claim below silently skips it.
    assert len(table.hands) == HANDS, (
        f"{label}: the stream shows {len(table.hands)} hands, expected "
        f"{HANDS}"
    )
    lost = [i for i, h in enumerate(table.hands) if h.taker is None and h.plays]
    assert not lost, (
        f"{label}: hand(s) {lost} of {len(table.hands)} were played but no "
        f"seat took in them -- the observation stream lost those announcements, "
        f"and every claim below would skip the hand as thrown in"
    )
    played = [h for h in table.hands if h.taker is not None]
    assert played, (
        f"{label}: no hand reached a contract, so every count below would "
        f"read 0 == 0 and this block would prove nothing"
    )
    for i, h in enumerate(table.hands):
        owed = TRICKS_PER_HAND if h.taker is not None else 0
        assert len(h.tricks) == owed and len(h.plays) == SEATS * owed, (
            f"{label} hand {i}: the auction owes {owed} tricks "
            f"({'taken' if h.taker is not None else 'thrown in'}), the stream "
            f"shows {len(h.tricks)} tricks / {len(h.plays)} plays"
        )
        assert len(h.bids) == SEATS, (
            f"{label} hand {i}: {len(h.bids)} announcements, expected one "
            f"per seat"
        )
        if h.taker is None:
            assert all(name == "pass" for _, name in h.bids), (
                f"{label} hand {i}: a thrown-in hand is four passes"
            )
            arms["hand-thrown-in"] += 1
        else:
            arms[f"contract-{h.level}"] += 1

    scores = {p: 0 for p in range(SEATS)}
    for i, h in enumerate(played):
        for t, (drained_to, cards) in enumerate(h.tricks):
            group = h.plays[SEATS * t : SEATS * (t + 1)]
            assert {p for p, _ in group} == set(range(SEATS)), (
                f"{label} hand {i} trick {t}: a seat played twice"
            )
            assert tuple(c for _, c in group) == cards
            w = _winner(group)
            assert w == drained_to, (
                f"{label} hand {i} trick {t}: recomputed winner P{w}, the "
                f"pile drained to P{drained_to}"
            )
            assert next(c for p, c in group if p == w).suit != "excuse", (
                f"{label} hand {i} trick {t}: the Excuse won the trick"
            )
            if t + 1 < TRICKS_PER_HAND:
                assert h.plays[SEATS * (t + 1)][0] == w, (
                    f"{label} hand {i} trick {t}: P{w} won but did not lead "
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

    assert sum(scores.values()) == 0, f"{label}: the settlement is not zero-sum"
    assert scores == result.scores, f"{label}: {scores} != {result.scores}"
    assert result.winner == max(result.scores, key=lambda p: result.scores[p])
    return arms


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
_DISCARD_ARMS: frozenset[str] = frozenset({"discard-preferred", "discard-forced"})

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
#   0` arm of `_verify` and its "four passes" assertion ran zero times:
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
# assertion in `_hand_value` or `_verify` would otherwise take vacuously.
#
# `discard-forced` and `forced-atouts-shown` are deliberately NOT here: the
# taker would have to hold fewer than six plain non-Kings among 24 cards.
# Only a Petite/Garde contract puts 24 cards in a hand at all, so the
# population is discard decisions, not hands: seeds 0-59 produce 109 of
# them across their 2160 hands, every one preferred (measured 2026-08-30).
# A cell whose only witness would be a deal nothing reaches must not read
# as covered; the branch rides a stacked first shuffle instead
# (`test_the_forced_discard_shows_its_atouts_to_the_table`), which drives
# the ENGINE through it and holds both cells non-zero there.
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
    assertions live in `_verify`, so a failing seed fails every reader
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
    own scores (the assertions are `_verify`'s), and no cascade arm rests
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


def test_the_discard_pool_arithmetic_spans_its_range() -> None:
    """`_discard_pool` fed the LIVE-hand shapes no playout produces: the
    sweep's discard decisions are all the one preferred vector (24 cards,
    size 6) and the stacked witness adds a single forced one (21 cards,
    size 3), so the branch boundary and the size derivation are pinned here
    across their range rather than at two points.

    The vectors are live hands as `offered` reads them: a preferred hand
    still holds its plain non-Kings, a forced hand holds NONE (the branch
    force-moves them before the pick) -- so the boundary pair is six
    preferred in a 24-card hand against five force-moved out of a 19-card
    one."""
    kings = [Card("K", s) for s in ("clubs", "diamonds", "hearts", "spades")]
    atouts = [Card(str(v), "atouts") for v in range(2, 21)]  # the 19 non-bout
    bouts = [Card("1", "atouts"), Card("21", "atouts"), Card("Excuse", "excuse")]
    plains = [Card(str(v), "hearts") for v in range(2, 11)]

    # Preferred boundary: exactly six plain non-Kings among 24.
    pool, n, arm = _discard_pool(plains[:6] + kings + bouts + atouts[:11])
    assert arm == "discard-preferred" and n == 6
    assert sorted(map(str, pool)) == sorted(map(str, plains[:6]))

    # The preferred size DERIVES from the hand rather than being the
    # constant 6: a merge defect handing the taker 25 cards asks for 7.
    assert _discard_pool(plains[:7] + kings + bouts + atouts[:11])[1] == 7

    # Forced extremes: five force-moved leaves 19 cards owing one atout;
    # zero preferred leaves all 24 owing six. The pool is the non-bout
    # atouts alone -- never a King, never a bout.
    pool, n, arm = _discard_pool(kings + bouts + atouts[:12])
    assert arm == "discard-forced" and n == 1
    assert sorted(map(str, pool)) == sorted(map(str, atouts[:12]))
    pool, n, arm = _discard_pool(kings + bouts + atouts[:17])
    assert arm == "discard-forced" and n == 6
    assert sorted(map(str, pool)) == sorted(map(str, atouts[:17]))

    # The forced arm refuses a live hand still holding a plain non-King --
    # the Owner Guard on "the branch moves ALL of them first".
    with pytest.raises(AssertionError, match="still in hand"):
        _discard_pool(kings + bouts + atouts[:11] + [Card("2", "clubs")])


class _RiggedFirstShuffle(random.Random):
    """A Random whose FIRST shuffle deals a chosen order and every later draw
    is honest. `shuffle deck` is the deal's only rng consumer and the deal
    then slices deterministically (18 off the top per seat, the last 6 to the
    chien), so overriding one call stacks exactly one deal without touching
    the engine's own shuffle/deal statements."""

    def __init__(self, seed: int, first_order: list[Card]) -> None:
        super().__init__(seed)
        self._first: list[Card] | None = list(first_order)

    def shuffle(self, x: Any) -> None:
        if self._first is not None:
            # The stack must be a permutation of the deck the ENGINE dealt
            # this rig, or the witness would drive the forced branch over a
            # pack the game does not declare -- and its conservation check,
            # derived from the same `_pack()` as the stack, could never
            # notice the substitution.
            assert Counter(x) == Counter(self._first), (
                "the stacked order is not a permutation of the engine's own "
                "deck -- `_pack()` and the game's `cards:` registry disagree"
            )
            x[:] = self._first
            self._first = None
        else:
            super().shuffle(x)


def test_the_forced_discard_shows_its_atouts_to_the_table() -> None:
    """The forced discard, end to end through the ENGINE: a taker holding fewer
    than six plain non-Kings puts every one of them in the discard, tops it up
    with chosen non-bout atouts -- never a King, never a bout -- and those
    atouts are SHOWN, arriving in `shown_atouts` with identity to all four
    seats before they join the hidden discard.

    The deal rides a stacked first shuffle rather than a seed search: the
    taker needs at least 19 of its 24 cards from the 26 atouts-Kings-Excuse,
    which no deal in seeds 0-59 produces and no feasible search would (the
    go-fish opening-quad precedent searched a ~0.1%-per-deal event; this one
    is astronomically past that). Hand 0 is the stacked hand at Petite; every
    later auction passes, so the other 35 hands are thrown in and the match
    stays one played hand.

    Seat 0's 18 dealt cards are the atouts 2..19 and the chien is 20, 21,
    K-2-3-4 of clubs, so the merged 24 hold exactly three plain non-Kings:
    the forced pick is 3 from the 19 non-bout atouts (`_discard_pool` sizes
    and pools it; a wrong offer lands in `table.offer_failures` and a wrong
    size fails `offered`'s own assert). The petit and the Excuse sit with the
    defenders, keeping the stacked side simple: the 21 is the hand's one
    bout, and it may never be discarded."""
    game = check_source(TAROT)
    seat0 = [Card(str(v), "atouts") for v in range(2, 20)]
    chien = [Card("20", "atouts"), Card("21", "atouts"), Card("K", "clubs"),
             Card("2", "clubs"), Card("3", "clubs"), Card("4", "clubs")]
    rest = [c for c in _pack() if c not in seat0 + chien]
    stacked = seat0 + rest + chien
    assert len(stacked) == 78

    auction_calls = [0]

    def script(player: Player, candidates: list[Any], n: int) -> list[Any] | None:
        if candidates and isinstance(candidates[0], Card):
            return None  # card decisions stay with the random pick
        auction_calls[0] += 1
        names = [str(c[0]) for c in candidates]
        if auction_calls[0] <= SEATS and player == 0:
            return [candidates[names.index("bid_petite")]]
        return [candidates[names.index("pass")]]

    hops: list[tuple[Player, tuple[Any, ...]]] = []

    def tap(player: Player, event: tuple[Any, ...]) -> None:
        if event[0] == "move" and "shown_atouts" in (str(event[1]), str(event[3])):
            hops.append((player, event))

    table, result = _play(
        game, _RiggedFirstShuffle(0, stacked), script=script, tap=tap
    )
    arms = _verify(table, result, "stacked discard")

    # The stacked hand went as scripted, and the branch actually fired -- the
    # census note names this test as the forced arm's only witness.
    h0 = table.hands[0]
    assert h0.taker == 0 and h0.level == 1
    assert arms["discard-forced"] == 1, arms
    assert arms["forced-atouts-shown"] == 1
    assert len(h0.shown) == 3 and all(
        c.suit == "atouts" and not _is_bout(c) for c in h0.shown
    ), h0.shown

    # The reveal derives to EVERY seat, not just observer 0's stream: each of
    # the four observers sees the same three identities arrive in
    # `shown_atouts` (count-only out of the taker's hidden hand), and the
    # onward tuck shows the same identities leaving while the hidden discard
    # takes them as a bare count.
    shown = tuple(sorted(str(c) for c in h0.shown))
    arrivals = {p: e for p, e in hops if str(e[3]) == "shown_atouts"}
    tucks = {p: e for p, e in hops if str(e[1]) == "shown_atouts"}
    assert set(arrivals) == set(tucks) == set(range(SEATS))
    for p in range(SEATS):
        arr, tuck = arrivals[p], tucks[p]
        assert tuple(sorted(str(c) for c in arr[4])) == shown, f"P{p}: {arr}"
        assert tuple(sorted(str(c) for c in tuck[2])) == shown, f"P{p}: {tuck}"
        if p != 0:
            assert arr[2] == 3, f"P{p} saw inside the taker's hand: {arr}"
            assert tuck[4] == 3, f"P{p} saw inside the discard: {tuck}"


def test_seed0_characterization() -> None:
    """Byte-identity pin for one whole game: any change to the decision
    sequence (the auction ring, the chien discard, the trick cascade's
    candidate order) moves this vector. Measured hash-independent: every
    collection on the decision path is ordered (hand-order pools, seating
    rings)."""
    game = check_source(TAROT)
    table, result = _play(game, random.Random(0))
    assert result.scores == {0: 842, 1: 1142, 2: -1542, 3: -442}
    assert result.winner == 1
    assert len(table.hands) == HANDS
    assert table.hands[0].taker == 2 and table.hands[0].level == 4
