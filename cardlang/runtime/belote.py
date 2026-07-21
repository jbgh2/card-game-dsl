"""Belote's runtime support (pure stdlib primitives).

The whole hand — the two-round take/name trump-making over the turned card,
the eight tricks under the follow/trump/over-trump obligation cascade (the
`MustFollowSuit`/`MustHeadTrumpLead`/`MustTrumpIfVoidVsOpponents`/
`MustOverTrumpVsOpponents`/`NoUnderTrumpVsPartner` rules), the declaration
poll with its comparison and showing, the Belote-Rebelote window, and the
contract scoring all run in the DSL (docs/games/belote.cardlang). This module
holds only what is not expressible there:

- `belote_trump_height` — a rank's strength within the trump suit
  (J > 9 > A > 10 > K > Q > 8 > 7), the over-trump comparison's currency.
  A pure rank map: the caller's demand filters on `card.suit is trump_suit`,
  so this needs no suit knowledge (the Tarot `tarot_trump_height` shape).
  Suit-contextual orders are explicitly outside the `ranking:` declaration's
  scope (decisions.md, "The `ranking:` declaration"), so the trump reorder
  lives here while the plain-suit order stays `ranking: ace-ten`.
- `belote_trick_winner` — the trick round's `outcome` function: highest trump
  under the trump order if any trump was played, else highest of the led suit
  under the game's ace-ten `rank_index`.
- `belote_opp_winning` — is the player currently winning the live, partial
  trick an OPPONENT of the acting player? The partnership-relative gate on
  the trump/over-trump obligations ("if an opponent is currently winning the
  trick, he must trump if he can … if his partner is currently winning he is
  free"). Read off the live round accumulator exactly as the `state` pronoun
  is, plus the acting player the rules engine bound (the engine facts' `actor`).
- `belote_royal_player` — who (if anyone) played a trump King or Queen in the
  trick that just completed, while the Belote-Rebelote window is still open.
  A PUBLIC fact (trick plays are identity to all): the DSL uses it only to
  aim the window's offer; whether that player actually holds the partner
  card is the `say_belote` move's own private guard.
- `belote_decl_*` — the declaration family over the BEST combination of a
  live hand under the declared trump: its points, class, height, trump
  flag, the announcement guard (`belote_best_is` — a declaration must state
  the best combination exactly), and the per-card enumeration
  (`size`/`slot`) the showing reveals walk. The combination model is
  game-local like Pinochle's `pinochle_meld_value`
  (docs/kernel-migration.md, Workstream 3).

The announcement's public CONTENT rides the declaration move's name and
Rank parameter (`declare_tierce(K)`, `declare_carre(J)`, …), never a state
write: a player's information set derives from their observation log plus
zone projections, and a decision's announce event carries exactly the move
name and parameter — so what was announced must be spelled there (the
Doppelkopf announcement-vocabulary precedent; belote.md, "Declarations").

The canonical best combination (documented in belote.md, "Declarations"):
over the decomposition that takes carrés first (J/9/A/10/K/Q only — 8s and
7s score nothing and are not declarable), then per suit the maximal
descending runs of the REMAINING cards in the natural A K Q J 10 9 8 7
order, each run at its greatest declarable length (5+ → quinte on the top
five, 4 → quarte, 3 → tierce), the strongest by (class, height, trump).
Announcing is scoped to that one best combination per player (belote.md,
"Scope and departures").
"""

from __future__ import annotations

from typing import Mapping

from cardlang.runtime import reads
from cardlang.runtime.sidecar import EngineFacts
from cardlang.runtime.values import SUITS, Card, Player

ROW = reads.row("cardlang/runtime/belote.py", "belote.cardlang")

# Trump-suit strength, strongest 8: J > 9 > A > 10 > K > Q > 8 > 7. Nonzero
# for every trump rank so the demand's `or 0` empty-pile default sits below
# the whole scale.
_TRUMP_HEIGHT = {"J": 8, "9": 7, "A": 6, "10": 5, "K": 4, "Q": 3, "8": 2, "7": 1}

# Natural (sequence) order A K Q J 10 9 8 7 — the declaration order, distinct
# from BOTH play orders (ace-ten in plain suits, the trump reorder above).
_NATURAL = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}

# Carré strength and points: J > 9 > A > 10 > K > Q; 8s and 7s not declarable.
_CARRE_HEIGHT = {"J": 6, "9": 5, "A": 4, "10": 3, "K": 2, "Q": 1}
_CARRE_POINTS = {"J": 200, "9": 150, "A": 100, "10": 100, "K": 100, "Q": 100}

_SEQ_POINTS = {3: 20, 4: 50, 5: 100}
_SEQ_CLASS = {3: 1, 4: 2, 5: 3}  # tierce / quarte / quinte
_CARRE_CLASS = 4  # "a square is higher than a 5 card sequence"


def belote_trump_height(c: Card) -> int:
    """A rank's strength within the trump suit (1..8). Pure rank map — the
    demand that consumes it filters on `card.suit is trump_suit` itself. A
    rank outside the 32-card pack (a game calling this over another deck)
    is a game-description error, reported here at the cause rather than as
    a bare KeyError mid-playout."""
    height = _TRUMP_HEIGHT.get(c.rank)
    if height is None:
        raise RuntimeError(
            f"belote_trump_height: rank {c.rank!r} is not a skat32 rank — "
            f"the Belote primitives serve the 32-card A..7 pack only"
        )
    return height


def belote_trick_winner(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: dict[str, int],
) -> Player:
    """The trick outcome: the highest trump under the J-9 trump order if any
    trump was played, else the highest card of the led suit under the game's
    ace-ten `rank_index`."""
    trumps = [(p, c) for p, c in played if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: _TRUMP_HEIGHT[pc[1].rank])[0]
    of_led = [(p, c) for p, c in played if c.suit == led_suit]
    return max(of_led, key=lambda pc: rank_index[pc[1].rank])[0]


def _round_state(facts: EngineFacts, caller: str) -> Mapping[str, object]:
    """The live round accumulator, or the just-completed round's terminal
    state — exactly the `state` pronoun's view (`mech_state[-1]` while a round
    runs, else `last_round_state`). Whether a round is live is game flow, so a
    premature call is the description's error, in the runtime's currency."""
    state = facts.round_state
    if state is None:
        raise RuntimeError(f"{caller}() called with no active or just-completed round")
    return state


def belote_opp_winning(facts: EngineFacts, gr: reads.GameReads) -> bool:
    """Is the current winner of the live, partial trick an opponent of the
    acting player? False while nothing has been played. The rules engine binds
    the candidate actor before evaluating `applies_when`, so the facts'
    `actor` is the player whose legality is being computed."""
    state = _round_state(facts, "belote_opp_winning")
    played: list[tuple[Player, Card]] = state["played"]  # type: ignore[assignment]
    if not played:
        return False
    actor = facts.actor
    if actor is None:
        raise RuntimeError(
            "belote_opp_winning() evaluated with no acting player — it belongs "
            "in a rule's applies_when, where legal_cards binds the actor"
        )
    trump: str | None = state["trump"]  # type: ignore[assignment]
    led: str = played[0][1].suit
    winner = belote_trick_winner(played, led, trump, dict(facts.rank_index))
    return facts.team_of[winner] != facts.team_of[actor]


def belote_royal_player(
    facts: EngineFacts, gr: reads.GameReads
) -> Player | None:
    """The player who played a trump King or Queen in the trick that just
    completed (the first of them in play order), or None. A pure read of
    public facts — the trick's plays and the declared trump — used by the DSL
    to aim the Belote-Rebelote window's offer; the announcing move's own
    guard checks the private partner-card holding."""
    state = _round_state(facts, "belote_royal_player")
    played: list[tuple[Player, Card]] = state["played"]  # type: ignore[assignment]
    trump: str | None = state["trump"]  # type: ignore[assignment]
    return next(
        (p for p, c in played if c.suit == trump and c.rank in ("K", "Q")), None
    )


# --- the declaration family -------------------------------------------------

# A combination: (class, height, trump_flag, points, cards strongest-first).
_Combo = tuple[int, int, bool, int, list[Card]]


def decomposition(cards: list[Card], trump: str | None) -> list[_Combo]:
    """The canonical decomposition of a hand under the declared trump — see
    the module docstring. Deterministic: carré cards in the deck's suit
    order, suits scanned in deck order, runs top-down."""
    combos: list[_Combo] = []
    used: set[Card] = set()

    by_rank: dict[str, list[Card]] = {}
    for c in cards:
        by_rank.setdefault(c.rank, []).append(c)
    for rank, height in _CARRE_HEIGHT.items():
        of_rank = by_rank.get(rank, [])
        if len({c.suit for c in of_rank}) == 4:
            members = sorted(of_rank, key=lambda c: SUITS.index(c.suit))
            combos.append((_CARRE_CLASS, height, False, _CARRE_POINTS[rank], members))
            used.update(members)

    for suit in SUITS:
        of_suit = sorted(
            (c for c in cards if c.suit == suit and c not in used),
            key=lambda c: _NATURAL[c.rank],
            reverse=True,
        )
        run: list[Card] = []
        for c in of_suit:
            if run and _NATURAL[run[-1].rank] - _NATURAL[c.rank] != 1:
                combos.extend(_run_combo(run, suit == trump))
                run = []
            run.append(c)
        combos.extend(_run_combo(run, suit == trump))

    return sorted(combos, key=lambda k: (k[0], k[1], k[2]), reverse=True)


def _run_combo(run: list[Card], is_trump: bool) -> list[_Combo]:
    """A maximal descending run's declaration: its greatest declarable length
    (top five as a quinte, four as a quarte, three as a tierce); shorter runs
    (and a 6/7-run's sub-quinte leftover) declare nothing."""
    if len(run) < 3:
        return []
    length = min(len(run), 5)
    members = run[:length]
    return [
        (
            _SEQ_CLASS[length],
            _NATURAL[members[0].rank],
            is_trump,
            _SEQ_POINTS[length],
            members,
        )
    ]


def _best_combo(facts: EngineFacts, gr: reads.GameReads, p: Player) -> _Combo | None:
    hand = gr.families["hand"][p]
    trump = gr.state["trump_suit"]
    combos = decomposition(list(hand), trump)
    return combos[0] if combos else None


# The declaration vocabulary's (class, trump_flag) per move name — the guard
# checks a declaration states the best combination exactly, and the height
# parameter arrives as a Rank name, mapped through the order the class uses.
_HEIGHT_OF_CLASS = {1: _NATURAL, 2: _NATURAL, 3: _NATURAL, 4: _CARRE_HEIGHT}


def belote_best_is(facts: EngineFacts, gr: reads.GameReads, p: Player, cls: int, rank: str, trump_flag: bool) -> bool:
    """Does `p`'s best combination have exactly this class, top rank, and
    trump flag? The declaration moves' guard: a player may announce their
    best combination or stay silent, never a weaker or absent one. A class
    outside 1..4 is the game description's error (the class argument is a
    literal in the declaration move's guard), reported at the cause; a rank
    with no height in the class's order (a carré of 8s or 7s) is simply
    never the best combination — the guard masks it false."""
    heights = _HEIGHT_OF_CLASS.get(cls)
    if heights is None:
        raise RuntimeError(
            f"belote_best_is: class {cls!r} is not a declaration class "
            f"(1 tierce, 2 quarte, 3 quinte, 4 carré)"
        )
    best = _best_combo(facts, gr, p)
    if best is None:
        return False
    height = heights.get(rank)
    return best[0] == cls and best[1] == height and best[2] == trump_flag


def belote_decl_points(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """The best combination's points (0 with none) — what a declaration
    scores for the entitled side."""
    best = _best_combo(facts, gr, p)
    return best[3] if best is not None else 0


def belote_decl_class(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """The best combination's class (4 carré > 3 quinte > 2 quarte >
    1 tierce; 0 with no combination)."""
    best = _best_combo(facts, gr, p)
    return best[0] if best is not None else 0


def belote_decl_height(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """The best combination's height: the top card's natural-order strength
    for a sequence, the carré rank's strength for a carré; 0 with none."""
    best = _best_combo(facts, gr, p)
    return best[1] if best is not None else 0


def belote_decl_trump(facts: EngineFacts, gr: reads.GameReads, p: Player) -> bool:
    """Is the best combination a sequence in the trump suit? (False for a
    carré — carré heights are unique, so the tie-break never needs it.)"""
    best = _best_combo(facts, gr, p)
    return best[2] if best is not None else False


def belote_decl_size(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """How many cards `p`'s best combination comprises — the showing bound."""
    best = _best_combo(facts, gr, p)
    return len(best[4]) if best is not None else 0


def belote_decl_slot(facts: EngineFacts, gr: reads.GameReads, p: Player, k: int, c: Card) -> bool:
    """Is `c` the `k`-th card of `p`'s best combination (strongest first)?
    The showing walks k = 0..size-1, revealing one card per step."""
    best = _best_combo(facts, gr, p)
    if best is None:
        return False
    return 0 <= k < len(best[4]) and best[4][k] == c
