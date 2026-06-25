"""The French Tarot hand mechanic (four-player, FFT rules; concrete).

Built as one concrete mechanic: the four-level ascending bid (Petite < Garde <
Garde sans < Garde contre), the chien handling dispatched by bid level, eighteen
tricks under atout trumps with the must-trump / must-over-trump obligations and
the Excuse's special routing, and the bouts-conditional threshold scoring with
the bid multiplier and petit-au-bout. The random chooser bids, discards, and
plays uniformly. Card points are kept in *doubled* integer units (the printed
half-points doubled; the 78 cards sum to 182).

Out of scope (matching french-tarot.md, plus pragmatic random-play cuts):
poignée declaration (a strategic pre-play reveal a random player can't sensibly
make), the Excuse half-point IOU deferral, and 3-/5-player variants.
"""

from __future__ import annotations

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# Bid levels, ascending, with their scoring multipliers.
_LEVELS = ("petite", "garde", "garde_sans", "garde_contre")
_MULT = {"petite": 1, "garde": 2, "garde_sans": 4, "garde_contre": 6}
# Non-trump in-suit strength: K > Q > Cavalier > J > 10 > ... > 1.
_SUIT_STR = {"K": 14, "Q": 13, "C": 12, "J": 11}


def _value(c: Card) -> int:
    """Doubled card-point value (printed value × 2, so all integers)."""
    if c.suit == "excuse":
        return 9
    if c.suit == "atouts":
        return 9 if c.rank in ("1", "21") else 1
    return {"K": 9, "Q": 7, "C": 5, "J": 3}.get(c.rank, 1)


def _is_bout(c: Card) -> bool:
    return c.suit == "excuse" or (c.suit == "atouts" and c.rank in ("1", "21"))


def _suit_strength(c: Card) -> int:
    return _SUIT_STR.get(c.rank, 0) or int(c.rank)


def _led_suit(trick: list[tuple[Player, Card]]) -> str:
    """The suit to follow: the first non-Excuse card's suit."""
    for _, c in trick:
        if c.suit != "excuse":
            return c.suit
    return "excuse"  # only the Excuse so far


def _trick_winner(trick: list[tuple[Player, Card]]) -> Player:
    atouts = [(p, c) for p, c in trick if c.suit == "atouts"]
    if atouts:
        return max(atouts, key=lambda pc: int(pc[1].rank))[0]
    led = _led_suit(trick)
    of_led = [(p, c) for p, c in trick if c.suit == led]
    return max(of_led, key=lambda pc: _suit_strength(pc[1]))[0]


def _legal(hand: list[Card], trick: list[tuple[Player, Card]]) -> list[Card]:
    """Follow suit; if void, trump and over-trump if able; the Excuse may always
    be played."""
    if not trick:
        return list(hand)
    excuse = [c for c in hand if c.suit == "excuse"]
    body = [c for c in hand if c.suit != "excuse"]
    led = _led_suit(trick)
    trumps_in_trick = [c for _, c in trick if c.suit == "atouts"]
    highest_trump = max((int(c.rank) for c in trumps_in_trick), default=0)

    if led == "atouts":
        mine = [c for c in body if c.suit == "atouts"]
        if mine:
            over = [c for c in mine if int(c.rank) > highest_trump]
            base = over or mine
        else:
            base = body
    else:
        same = [c for c in body if c.suit == led]
        if same:
            base = same
        else:
            mine = [c for c in body if c.suit == "atouts"]
            if mine:
                over = [c for c in mine if int(c.rank) > highest_trump]
                base = over or mine
            else:
                base = body
    return base + excuse


def run_tarot_rest(stmt: n.Instantiate, ctx: Ctx) -> Player:
    """The Tarot hand after the auction: chien handling (by bid level), the
    eighteen atout-trump tricks, and the bouts/multiplier/petit scoring. The
    four-level bid runs on the kernel `round` (`french-tarot.cardlang`,
    `tarot_auction_outcome`); this mechanic reads the taker and level it settled
    on from hand state, and `opener` (the first-trick leader) from its arg."""
    rs = ctx.rs
    args = {a.name: a.value for a in stmt.args}
    start: Player = evaluate(args["opener"], ctx)  # type: ignore[arg-type]
    choose = ctx.chooser
    n_players = rs.seating.count
    hands = rs.zones.families["hand"]
    captured = rs.zones.families["captured"]
    chien = rs.zones.single("chien")

    taker: Player = rs.get("taker")
    level = _LEVELS[rs.get("bid_level") - 1]  # bid_level is 1..4 (0 = no bid)

    # --- chien handling by bid level ---
    if level in ("petite", "garde"):
        hands[taker].add_all(chien.take_all())
        keepable = [c for c in hands[taker].cards if not _is_bout(c)]
        pref = [c for c in keepable if c.suit not in ("atouts", "excuse") and c.rank != "K"]
        pool = pref if len(pref) >= 6 else keepable
        for c in choose(taker, pool, 6):  # discard six; they count to the taker
            hands[taker].remove(c)
            captured[taker].add(c)

    def same_team(a: Player, b: Player) -> bool:
        return (a == taker) == (b == taker)

    # --- eighteen tricks ---
    leader = start
    last_winner = leader
    petit_in_last = False
    for t in range(18):
        order = [(leader - i) % n_players for i in range(n_players)]
        trick: list[tuple[Player, Card]] = []
        for q in order:
            legal = _legal(hands[q].cards, trick)
            card = choose(q, legal, 1)[0]
            hands[q].remove(card)
            trick.append((q, card))
            ctx.trace("play", (q, card))
        winner = _trick_winner(trick)
        ctx.trace("trick_end", {"trump": "atouts"})
        ctx.trace("trick", (winner, [c for _, c in trick]))

        excuse = [(p, c) for p, c in trick if c.suit == "excuse"]
        if excuse and not same_team(excuse[0][0], winner):
            ep = excuse[0][0]
            for _, c in trick:
                (captured[ep] if c.suit == "excuse" else captured[winner]).add(c)
            comp = next(
                (c for c in captured[ep].cards if _value(c) == 1 and c.suit != "excuse"),
                None,
            )
            if comp is not None:  # repay the trick winner a low card for the Excuse
                captured[ep].remove(comp)
                captured[winner].add(comp)
        else:
            for _, c in trick:
                captured[winner].add(c)

        if t == 17:
            petit_in_last = any(c.suit == "atouts" and c.rank == "1" for _, c in trick)
        last_winner = winner
        leader = winner

    # --- scoring ---
    opponents = [p for p in rs.seating.players if p != taker]
    taker_doubled = sum(_value(c) for c in captured[taker].cards)
    if level == "garde_sans":
        taker_doubled += sum(_value(c) for c in chien.cards)
    bouts = sum(1 for c in captured[taker].cards if _is_bout(c))
    if level == "garde_sans":
        bouts += sum(1 for c in chien.cards if _is_bout(c))
    threshold = {3: 36, 2: 41, 1: 51, 0: 56}[bouts]

    pb = 0
    if petit_in_last:
        pb = 10 if same_team(last_winner, taker) else -10
    pt = taker_doubled / 2 - threshold
    per_opp = round((25 + pt + pb) * _MULT[level])

    score = rs.get("score")
    score[taker] += 3 * per_opp
    for opp in opponents:
        score[opp] -= per_opp

    opp_doubled = sum(_value(c) for opp in opponents for c in captured[opp].cards)
    if level == "garde_contre":
        opp_doubled += sum(_value(c) for c in chien.cards)
    ctx.trace(
        "tarot_hand",
        {"taker_doubled": taker_doubled, "opp_doubled": opp_doubled, "bouts": bouts},
    )
    return taker
