"""Canasta's runtime support (pure stdlib primitives).

The whole hand — the draw-or-take turn loop, the announce-then-stage meld
window, the frozen pile, the initial-meld minimums, and the per-team hand
scoring — runs in the DSL (docs/games/canasta.cardlang). This module holds
what is not expressible there:

- `POINTS` — the Canasta card-point table (Joker 50, deuces and aces 20,
  K..8 = 10, 7..4 and threes 5). The deck's `card_value()` table is empty
  for canasta108 (a scoring fact of the game, not a deck property — the
  Gin/Cribbage precedent exactly).
- the **meld-attempt core** (`_Attempt` / `_close_legal` / `_completable`) —
  the joint legality of a meld under composition (>= 2 naturals, <= 3
  wilds, size >= 3), the frozen/unfrozen pile-take justification, the
  initial-meld minimum (15/50/90/120 by cumulative score), and the go-out
  safety condition (never end a meld attempt unable to legally end the
  turn). The DSL's per-card `where` filters cannot state these joint
  facts; the incremental-totality trick is Gin's `gin_arrange_ok` exactly:
  every offered stage/close keeps a legal completion reachable, so random
  play can never wedge mid-meld.
- ctx-adapters (`canasta_can_take_pile`, `canasta_stage_ok`, …) reading
  hands, the stage zones, the pile, the per-rank team meld zones, and the
  `pile_frozen` / `team_melded` / `meld_rank` / `taking_pile` / `score`
  state vars.

Why no joint selection (`where jointly`): canasta108 holds duplicate
identical cards (two copies of every standard card, four jokers), and the
OpenSpiel combo block canonicalizes joint subsets by frozenset — a
{K spades, K spades} pair would collapse into {K spades}, colliding two
different actions. The staged per-card encoding uses only card-block ids,
which duplicate copies share soundly (identical cards are interchangeable).
The combo-block limitation itself is walled loudly at
`ActionSpace.for_game` and recorded in roadmap.md.

Every adapter is a pure function of the game state it reads — no hidden
state, no RNG (decisions.md kernel doctrine: meaning never state).
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.runtime import reads
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

# Every zone/state var this module reads by name is declared in
# PRIMITIVE_READS (cardlang/runtime/reads.py) — the declared-reads coupling
# contract; the accessors below are the only sanctioned way to touch state.
_R = reads.row("cardlang/runtime/canasta.py", "canasta.cardlang")

# The Canasta card-point table. Red threes never carry card points (they are
# bonus objects, swept out of hands on sight); the "3" row is the BLACK
# threes' 5 points (cards-left-in-hand counts, and the go-out black-three
# meld).
POINTS: dict[str, int] = {
    "Joker": 50, "2": 20, "A": 20,
    "K": 10, "Q": 10, "J": 10, "10": 10, "9": 10, "8": 10,
    "7": 5, "6": 5, "5": 5, "4": 5, "3": 5,
}

WILD_RANKS = ("Joker", "2")
# The ranks a meld can be OF (the game's `ranking:` declares exactly these —
# wilds substitute into them, threes are never meldable except the go-out
# black-three group).
NATURAL_MELD_RANKS = ("A", "K", "Q", "J", "10", "9", "8", "7", "6", "5", "4")


def is_wild(c: Card) -> bool:
    return c.rank in WILD_RANKS


def is_red3(c: Card) -> bool:
    return c.rank == "3" and c.suit in ("hearts", "diamonds")


def is_black3(c: Card) -> bool:
    return c.rank == "3" and c.suit in ("clubs", "spades")


def card_points(c: Card) -> int:
    return POINTS[c.rank]


def initial_minimum(cumulative_score: int) -> int:
    """The initial-meld minimum count by the partnership's cumulative score:
    negative -> 15, 0..1495 -> 50, 1500..2995 -> 90, 3000+ -> 120 (Pagat,
    Classic Canasta)."""
    if cumulative_score < 0:
        return 15
    if cumulative_score < 1500:
        return 50
    if cumulative_score < 3000:
        return 90
    return 120


def canasta_bonus_for(cards: list[Card]) -> int:
    """One meld pile's canasta bonus: 500 for a natural canasta (7+ cards, no
    wilds), 300 for a mixed one, 0 below seven cards."""
    if len(cards) < 7:
        return 0
    return 300 if any(is_wild(c) for c in cards) else 500


def red3_bonus_for(count: int, team_melded: bool) -> int:
    """The red-three bonus: 100 each (800 for all four), positive when the
    side has melded, negative when it has not."""
    base = 800 if count == 4 else 100 * count
    return base if team_melded else -base


# --- state reads -------------------------------------------------------------


def _hand(ctx: Ctx, p: Player) -> list[Card]:
    return list(reads.instance(ctx.rs, _R, "hand", p).cards)


def _stage(ctx: Ctx, p: Player) -> list[Card]:
    return list(reads.instance(ctx.rs, _R, "stage", p).cards)


def _pile_top(ctx: Ctx) -> list[Card]:
    return list(reads.single(ctx.rs, _R, "pile_top").cards)


def _pile_rest(ctx: Ctx) -> list[Card]:
    return list(reads.single(ctx.rs, _R, "pile_rest").cards)


def _meld_zones(ctx: Ctx, team: int) -> list[tuple[str, list[Card]]]:
    """Every meld pile of `team`, (rank, cards) — the black-three go-out pile
    included under its "3" key. Each zone is read with its literal name (the
    declared-reads scan refuses a variable name at an accessor call)."""
    rs = ctx.rs
    return [
        ("A", list(reads.instance(rs, _R, "meldA", team).cards)),
        ("K", list(reads.instance(rs, _R, "meldK", team).cards)),
        ("Q", list(reads.instance(rs, _R, "meldQ", team).cards)),
        ("J", list(reads.instance(rs, _R, "meldJ", team).cards)),
        ("10", list(reads.instance(rs, _R, "meld10", team).cards)),
        ("9", list(reads.instance(rs, _R, "meld9", team).cards)),
        ("8", list(reads.instance(rs, _R, "meld8", team).cards)),
        ("7", list(reads.instance(rs, _R, "meld7", team).cards)),
        ("6", list(reads.instance(rs, _R, "meld6", team).cards)),
        ("5", list(reads.instance(rs, _R, "meld5", team).cards)),
        ("4", list(reads.instance(rs, _R, "meld4", team).cards)),
        ("3", list(reads.instance(rs, _R, "meld3b", team).cards)),
    ]


def _meld_of(ctx: Ctx, team: int, rank: str) -> list[Card]:
    for r, cards in _meld_zones(ctx, team):
        if r == rank:
            return cards
    raise RuntimeError(
        f"canasta: no meld pile for rank {rank!r} — the meldable ranks are "
        f"{list(NATURAL_MELD_RANKS)} plus the go-out black-three pile; the "
        f"`ranking:` declaration and the start/take guards are the walls "
        f"that keep this unreachable"
    )


def _team_has_canasta(ctx: Ctx, team: int) -> bool:
    return any(len(cards) >= 7 for _, cards in _meld_zones(ctx, team))


def _team_melded(ctx: Ctx, team: int) -> bool:
    return bool(reads.state(ctx.rs, _R, "team_melded")[team])


def _frozen_for(ctx: Ctx, team: int) -> bool:
    """Whether the pile is frozen against this side: a wild card (or a
    setup-turned wild/red three) froze it for everyone, and a side that has
    not yet melded is frozen against it regardless."""
    return bool(reads.state(ctx.rs, _R, "pile_frozen")) or not _team_melded(ctx, team)


def _team_score(ctx: Ctx, team: int) -> int:
    return int(reads.state(ctx.rs, _R, "score")[team])


def _top_card(ctx: Ctx) -> Card:
    top = _pile_top(ctx)
    if not top:
        raise RuntimeError(
            "canasta: the discard pile is empty — the take-pile guard "
            "(canasta_can_take_pile) and the deal's turn-up are the walls "
            "that keep top-of-pile reads reachable only on a non-empty pile"
        )
    return top[-1]


# --- the meld-attempt core ---------------------------------------------------


@dataclass(frozen=True)
class _Attempt:
    """One meld attempt, normalized: the target rank, what the team pile
    already holds, what is staged so far, and the hand pools a completion
    may still draw from. `taking` marks a pile take (the staged set contains
    the pile's top card, and closing flushes the rest of the pile into the
    hand)."""

    rank: str
    existing_n: int  # naturals already in the team's pile of this rank
    existing_w: int  # wilds already in that pile
    staged_n: int  # naturals of the rank staged so far (incl. the top card when taking)
    staged_w: int  # wilds staged so far
    staged_value: int  # card points staged so far
    hand_nat: int  # naturals of the rank still in hand
    wild_values: tuple[int, ...]  # values of wilds still in hand, descending
    hand_size: int  # cards still in hand
    taking: bool
    flush_gain: int  # non-red-three cards the pile flush would add to the hand
    frozen: bool  # the pile is frozen against this side (take justification)
    minimum: int | None  # the initial-meld minimum, None once the side has melded
    other_canasta: bool  # the side already has a canasta in some other pile


def _close_legal(at: _Attempt, a: int, b: int) -> bool:
    """Would closing this attempt after staging `a` more naturals and `b`
    more wilds (value-best wilds first) be legal? The one function that
    states ALL the joint conditions; every guard below derives from it."""
    n = at.existing_n + at.staged_n + a
    w = at.existing_w + at.staged_w + b
    # Composition: every meld holds at least two naturals and at most three
    # wilds, and at least three cards in all (existing cards count — an
    # extension of a standing meld only needs the combined pile legal).
    if w > 3 or n < 2 or n + w < 3:
        return False
    added = at.staged_n + at.staged_w + a + b
    if at.taking:
        # Justification for taking the pile. Frozen against this side: at
        # least two natural cards from the HAND beside the top card (the
        # staged naturals include the top card itself). Unfrozen: the top
        # card either joins a standing meld of its rank or melds with two
        # cards from hand.
        if at.frozen:
            if (at.staged_n - 1) + a < 2:
                return False
        else:
            if at.existing_n + at.existing_w == 0 and added < 3:
                return False
    if at.minimum is not None:
        value = at.staged_value + a * POINTS[at.rank] + sum(at.wild_values[:b])
        if value < at.minimum:
            return False
    # Go-out safety: after the close (and the pile flush, when taking) the
    # player must be able to legally end the turn — keep two cards (one to
    # discard, one to hold), or have/complete a canasta so going out is
    # legal.
    hand_after = at.hand_size - a - b + at.flush_gain
    canasta_after = at.other_canasta or (n + w) >= 7
    return hand_after >= 2 or canasta_after


def _completable(at: _Attempt) -> bool:
    """Whether ANY legal close is still reachable from this attempt. Brute
    force over the (naturals, wilds) counts still stageable — pools are at
    most 8 naturals and a handful of wilds, and wilds are taken best-value
    first, so counts fully determine the best reachable value."""
    return any(
        _close_legal(at, a, b)
        for a in range(at.hand_nat + 1)
        for b in range(len(at.wild_values) + 1)
    )


def _attempt(
    ctx: Ctx,
    p: Player,
    rank: str,
    staged: list[Card],
    hand: list[Card],
    taking: bool,
) -> _Attempt:
    team = ctx.rs.team_of[p]
    existing = _meld_of(ctx, team, rank)
    melded = _team_melded(ctx, team)
    flush = 0
    if taking:
        flush = sum(1 for c in _pile_rest(ctx) if not is_red3(c))
    other_canasta = any(
        len(cards) >= 7 for r, cards in _meld_zones(ctx, team) if r != rank
    )
    return _Attempt(
        rank=rank,
        existing_n=sum(1 for c in existing if not is_wild(c)),
        existing_w=sum(1 for c in existing if is_wild(c)),
        staged_n=sum(1 for c in staged if not is_wild(c)),
        staged_w=sum(1 for c in staged if is_wild(c)),
        staged_value=sum(card_points(c) for c in staged),
        hand_nat=sum(1 for c in hand if c.rank == rank),
        wild_values=tuple(
            sorted((card_points(c) for c in hand if is_wild(c)), reverse=True)
        ),
        hand_size=len(hand),
        taking=taking,
        flush_gain=flush,
        frozen=_frozen_for(ctx, team),
        minimum=None if melded else initial_minimum(_team_score(ctx, team)),
        other_canasta=other_canasta,
    )


def _live_attempt(ctx: Ctx, p: Player) -> _Attempt:
    """The attempt currently open for `p`: the staged cards against the
    `meld_rank` / `taking_pile` state the announce wrote."""
    rank = reads.state(ctx.rs, _R, "meld_rank")
    if rank is None:
        raise RuntimeError(
            "canasta: no meld attempt is open (meld_rank is none) — "
            "stage/close guards are only offered inside an open attempt; "
            "the offer placement in canasta.cardlang is the wall"
        )
    taking = bool(reads.state(ctx.rs, _R, "taking_pile"))
    return _attempt(ctx, p, str(rank), _stage(ctx, p), _hand(ctx, p), taking)


# --- ctx-adapters (DSL-visible; signatures in stdlib/signatures.py) ----------


def canasta_is_red3(ctx: Ctx, card: Card) -> bool:
    """Is this card a red three (bonus card, swept to the team's row)?"""
    return is_red3(card)


def canasta_is_black3(ctx: Ctx, card: Card) -> bool:
    """Is this card a black three (stop card; meldable only when going out)?"""
    return is_black3(card)


def canasta_top_starts_pile(ctx: Ctx) -> bool:
    """May the current turned card start the discard pile? A wild card or a
    red three is turned under (freezing the pile) and another card turned —
    the deal loop's condition."""
    c = _top_card(ctx)
    return not is_wild(c) and not is_red3(c)


def canasta_top_is_wild(ctx: Ctx) -> bool:
    """Did the discard just made freeze the pile (a wild card on top)?"""
    return is_wild(_top_card(ctx))


def canasta_pile_rank(ctx: Ctx) -> str:
    """The rank of the pile's top card — the meld a take must feed. Guarded
    by canasta_can_take_pile, so the top is a meldable natural rank here."""
    return _top_card(ctx).rank


def canasta_can_take_pile(ctx: Ctx, p: Player) -> bool:
    """May `p` take the discard pile? The top card must be a natural meldable
    rank (never a wild or any three), and a complete legal take must exist:
    top card + hand cards close a valid meld of the top rank, meeting the
    frozen-pile pair justification, the initial-meld minimum when the side
    has not melded (only the top card counts toward it — the rest of the
    pile flushes to hand after the close), and the go-out safety rule."""
    top = _pile_top(ctx)
    if not top:
        return False
    c = top[-1]
    if c.rank not in NATURAL_MELD_RANKS:
        return False
    at = _attempt(ctx, p, c.rank, [c], _hand(ctx, p), taking=True)
    return _completable(at)


def canasta_must_take_pile(ctx: Ctx, p: Player) -> bool:
    """The stock-exhaustion forced take: with no stock, a player MUST take
    the pile when it is not frozen against their side and its top card
    matches one of the side's standing melds (Pagat, Classic Canasta) —
    provided the take is legal at all (the go-out safety corner)."""
    if not canasta_can_take_pile(ctx, p):
        return False
    team = ctx.rs.team_of[p]
    if _frozen_for(ctx, team):
        return False
    return len(_meld_of(ctx, team, _top_card(ctx).rank)) > 0


def canasta_can_start(ctx: Ctx, p: Player, rank: str) -> bool:
    """May `p` announce a new meld of `rank` from hand? The side must not
    already hold a meld of that rank (one meld per rank per side), and a
    complete legal close must be reachable from the hand alone."""
    team = ctx.rs.team_of[p]
    if len(_meld_of(ctx, team, rank)) > 0:
        return False
    at = _attempt(ctx, p, rank, [], _hand(ctx, p), taking=False)
    return _completable(at)


def canasta_stage_ok(ctx: Ctx, p: Player, card: Card) -> bool:
    """May `card` join the open meld attempt? It must fit the attempt (a
    natural of the announced rank, or a wild), and staging it must keep a
    legal close reachable — the incremental-totality guard that makes every
    reachable staging state completable, random play included."""
    at = _live_attempt(ctx, p)
    if card.rank == at.rank:
        nxt = _replace_staged(at, dn=1, value=card_points(card))
    elif is_wild(card):
        if not at.wild_values:
            return False
        # Staging a SPECIFIC wild: recompute with that wild's value staged
        # and its entry removed from the hand pool (a joker and a deuce
        # differ by 30 points, which the initial minimum can hinge on).
        vals = list(at.wild_values)
        vals.remove(card_points(card))
        nxt = _replace_staged(at, dw=1, value=card_points(card), wild_values=tuple(vals))
    else:
        return False
    return _completable(nxt)


def _replace_staged(
    at: _Attempt,
    dn: int = 0,
    dw: int = 0,
    value: int = 0,
    wild_values: tuple[int, ...] | None = None,
) -> _Attempt:
    from dataclasses import replace

    return replace(
        at,
        staged_n=at.staged_n + dn,
        staged_w=at.staged_w + dw,
        staged_value=at.staged_value + value,
        hand_nat=at.hand_nat - dn,
        wild_values=at.wild_values if wild_values is None else wild_values,
        hand_size=at.hand_size - 1,
    )


def canasta_close_ok(ctx: Ctx, p: Player) -> bool:
    """May the open attempt close as it stands? (All the joint conditions of
    `_close_legal` with nothing further staged.)"""
    return _close_legal(_live_attempt(ctx, p), 0, 0)


def canasta_add_ok(ctx: Ctx, p: Player, rank: str, card: Card) -> bool:
    """May `card` be laid directly onto the side's standing meld of `rank`?
    A natural of the rank always fits; a wild fits while the pile holds
    fewer than three. Guarded by go-out safety: the add must leave two
    cards in hand, or the side with (or completing) a canasta."""
    team = ctx.rs.team_of[p]
    existing = _meld_of(ctx, team, rank)
    if not existing:
        return False  # no standing meld — start one (the initial-minimum path)
    if card.rank == rank:
        pass
    elif is_wild(card):
        if sum(1 for c in existing if is_wild(c)) >= 3:
            return False
    else:
        return False
    hand_after = len(_hand(ctx, p)) - 1
    canasta_after = _team_has_canasta(ctx, team) or len(existing) + 1 >= 7
    return hand_after >= 2 or canasta_after


def canasta_discard_ok(ctx: Ctx, p: Player, card: Card) -> bool:
    """May `p` end the turn by discarding `card`? Any card may be discarded;
    discarding the LAST card is going out, legal only once the side has a
    canasta."""
    if len(_hand(ctx, p)) >= 2:
        return True
    return _team_has_canasta(ctx, ctx.rs.team_of[p])


def canasta_black3_ok(ctx: Ctx, p: Player) -> bool:
    """May `p` meld their black threes? Only as part of going out: the side
    has a canasta, the hand is three or four black threes plus at most one
    other card (the final discard), and the group takes no wilds."""
    if not _team_has_canasta(ctx, ctx.rs.team_of[p]):
        return False
    hand = _hand(ctx, p)
    b3 = sum(1 for c in hand if is_black3(c))
    return b3 in (3, 4) and len(hand) in (b3, b3 + 1)


# --- scoring -----------------------------------------------------------------


def canasta_meld_points(ctx: Ctx, team: int) -> int:
    """The card points of everything the side melded (canastas included; red
    threes are bonus objects, never meld)."""
    return sum(
        card_points(c) for _, cards in _meld_zones(ctx, team) for c in cards
    )


def canasta_canasta_bonus(ctx: Ctx, team: int) -> int:
    """The canasta bonuses: 500 per natural canasta, 300 per mixed — each
    meld pile scored as an object, by its own composition."""
    return sum(canasta_bonus_for(cards) for _, cards in _meld_zones(ctx, team))


def canasta_red3_bonus(ctx: Ctx, team: int) -> int:
    """The red-three bonus: +100 each (+800 for all four) when the side has
    melded, else the same amounts negative."""
    count = len(reads.instance(ctx.rs, _R, "red3", team).cards)
    return red3_bonus_for(count, _team_melded(ctx, team))


def canasta_hand_points(ctx: Ctx, team: int) -> int:
    """The card points still held in both partners' hands at the end of the
    hand — subtracted from the side's score."""
    return sum(
        card_points(c)
        for p, t in ctx.rs.team_of.items()
        if t == team
        for c in _hand(ctx, p)
    )
