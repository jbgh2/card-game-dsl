"""French Tarot's runtime support (pure stdlib primitives).

The whole hand — the four-level bid (the auction form of the kernel `round`),
the chien handling by bid level, the eighteen atout-trump tricks with the
Excuse's special routing and the must-follow/must-trump/must-over-trump
obligations (the `ExcuseIsExempt`/`MustFollowSuit`/`MustTrumpIfVoid`/
`MustOverTrump` rule cascade), and the bouts-conditional threshold scoring all
run in the DSL (docs/games/french-tarot.cardlang). This module holds only what
is not expressible there:

- `tarot_card_points` / `tarot_trump_height` — per-card pure queries (the
  doubled card-point value; the trump rank strength for the over-trump
  comparison).
- `tarot_led_suit` — the effective led suit over the live `trick_pile` (the
  first non-Excuse card's suit, or "excuse" if only the Excuse has been played
  so far) — distinct from the kernel's own `state.led_suit` (the literal first
  card played, "excuse" included), which gates the rules' `applies_when`.
- `tarot_trick_winner` — the trick round's `outcome` function: highest atout
  if any was played, else highest of the effective led suit; the Excuse never
  wins.
- `tarot_excuse_player` — which player (if any) played the Excuse in the trick
  that just completed, read off the round's exposed terminal state.
- `tarot_per_opp` — the zero-sum per-opponent settlement amount: the
  bouts-conditional threshold, the taker's doubled card points (the chien's
  too, at Garde sans le chien — the chien is never moved there, so it counts
  where it sits), the petit-au-bout adjustment, and the bid multiplier
  (verbatim monolith arithmetic: a float division then Python's banker's
  rounding).

Card points are kept in *doubled* integer units (the printed half-points
doubled; the 78 cards sum to 182).
"""

from __future__ import annotations

from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# Bid levels, ascending, with their scoring multipliers.
_LEVELS = ("petite", "garde", "garde_sans", "garde_contre")
_MULT = {"petite": 1, "garde": 2, "garde_sans": 4, "garde_contre": 6}
# Non-trump in-suit strength: K > Q > Cavalier > J > 10 > ... > 1.
_SUIT_STR = {"K": 14, "Q": 13, "C": 12, "J": 11}


def tarot_card_points(c: Card) -> int:
    """Doubled card-point value (printed value × 2, so all integers)."""
    if c.suit == "excuse":
        return 9
    if c.suit == "atouts":
        return 9 if c.rank in ("1", "21") else 1
    return {"K": 9, "Q": 7, "C": 5, "J": 3}.get(c.rank, 1)


def _is_bout(c: Card) -> bool:
    """A bout (oudler): the Excuse, the 1 of atouts (petit), or the 21. The
    DSL's own `is_bout` function (french-tarot.cardlang) computes the same
    predicate independently for the discard filter, mirroring this."""
    return c.suit == "excuse" or (c.suit == "atouts" and c.rank in ("1", "21"))


def _suit_strength(c: Card) -> int:
    return _SUIT_STR.get(c.rank, 0) or int(c.rank)


def _led_suit(cards: list[Card]) -> str:
    """The suit to follow: the first non-Excuse card's suit."""
    for c in cards:
        if c.suit != "excuse":
            return c.suit
    return "excuse"  # only the Excuse played so far


def tarot_led_suit(ctx: Ctx) -> str:
    """The effective led suit for the live trick, read off the `trick_pile`
    zone (the follow-suit demand's own view — distinct from the kernel's
    `state.led_suit`, the literal first card's suit, which gates a rule's
    `applies_when` instead)."""
    return _led_suit(ctx.rs.zones.single("trick_pile").cards)


def tarot_trump_height(c: Card) -> int:
    """Trump strength for the over-trump comparison: an atout's rank as an
    int (1..21); 0 for a non-atout (never subject to, or able to satisfy, an
    over-trump demand)."""
    return int(c.rank) if c.suit == "atouts" else 0


def tarot_trick_winner(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: dict[str, int],
) -> Player:
    """The trick outcome: highest atout if any was played; else highest of the
    effective led suit (the first non-Excuse card's suit — recomputed here,
    never the raw `led_suit` arg, which the kernel sets from the literal
    first-played card and can be "excuse"). The Excuse itself never wins.
    Ignores `led_suit`/`trump`/`rank_index` (the OutcomeFn interface)."""
    atouts = [(p, c) for p, c in played if c.suit == "atouts"]
    if atouts:
        return max(atouts, key=lambda pc: int(pc[1].rank))[0]
    led = _led_suit([c for _, c in played])
    of_led = [(p, c) for p, c in played if c.suit == led]
    return max(of_led, key=lambda pc: _suit_strength(pc[1]))[0]


def tarot_excuse_player(ctx: Ctx) -> Player | None:
    """The player who played the Excuse in the trick that just completed, or
    None if nobody did. Reads the round's exposed terminal state exactly as
    the `state` pronoun does (`mech_state[-1]` while a round is still active,
    else `last_round_state`) — the DSL calls this right after `round
    play_to_trick` returns, when the round is no longer active."""
    state = ctx.rs.mech_state[-1] if ctx.rs.mech_state else ctx.rs.last_round_state
    if state is None:
        # Same contract as the `state` pronoun: whether a round has run is
        # live game flow, so a premature call is the description's error, in
        # the runtime's currency.
        raise RuntimeError(
            "tarot_excuse_player() called with no active or just-completed "
            "round"
        )
    played: list[tuple[Player, Card]] = state["played"]
    return next((p for p, c in played if c.suit == "excuse"), None)


def tarot_per_opp(ctx: Ctx, pb: int) -> int:
    """The zero-sum per-opponent settlement amount for the hand just played:
    the bouts-conditional threshold ({3: 36, 2: 41, 1: 51, 0: 56} doubled
    points), the taker's doubled card points (`captured[taker]`, plus the
    chien's at Garde sans le chien — never moved, counted where it sits), the
    petit-au-bout adjustment `pb`, and the bid multiplier. Verbatim monolith
    arithmetic (a float division then Python's banker's rounding).

    Counts `discard[taker]` (the taker's hidden chien discards, at Petite/
    Garde) as taker cards too — the fidelity stage's discard reroute moved
    those six cards out of `captured[taker]` into their own hidden zone, so
    without this they would silently drop out of the taker's total. Their
    bouts contribution is always zero and is not added: both discard filters
    (`is_pref_discard`, `not is_bout`) exclude every bout by construction, so
    a discarded card can never BE one."""
    rs = ctx.rs
    taker: Player = rs.get("taker")
    level = _LEVELS[rs.get("bid_level") - 1]  # bid_level is 1..4 (0 = no bid)
    captured = rs.zones.families["captured"]
    chien = rs.zones.single("chien")
    discard = rs.zones.families["discard"]

    taker_doubled = sum(tarot_card_points(c) for c in captured[taker].cards)
    taker_doubled += sum(tarot_card_points(c) for c in discard[taker].cards)
    bouts = sum(1 for c in captured[taker].cards if _is_bout(c))
    if level == "garde_sans":
        taker_doubled += sum(tarot_card_points(c) for c in chien.cards)
        bouts += sum(1 for c in chien.cards if _is_bout(c))
    threshold = {3: 36, 2: 41, 1: 51, 0: 56}[bouts]

    pt = taker_doubled / 2 - threshold
    return round((25 + pt + pb) * _MULT[level])
