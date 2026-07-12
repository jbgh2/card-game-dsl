"""Tichu's game-local runtime primitives.

The hand runs fully on the kernel (tichu.cardlang): the Tichu/Grand-Tichu
calls and the push are plain statements (a `for each player` of one chosen
3-card movement, then a draw-free giver-major distribution), each climbing
trick is one `round climb` over the combination engine's queries, and the
finishing/scoring flow is statement control flow over the round's terminal
state (`state.lead_ended_trick`, `state.shed_first` / `state.shed_second`).
What stays game-local: the combination engine itself (`combinations.py`,
shared with nothing — Big Two's differs), the two non-chooser RNG sites the
monolith drew (the call-rate gates and the Dragon's trick going to a random
opponent — reproduced draw-for-draw at the same sites), partnership lookups,
and the card-point table.

The state-reading primitives (`tichu_double_victory`, `tichu_first_out`) read
the finishing order from phase state via `ctx.rs.get` — the Stud/Cribbage/Skat
precedent for game-local primitives over live state. `tichu_dragon_won` reads
the completed round's standing play from `last_round_state` (the same terminal
frame the body reads as `state.x`).
"""

from __future__ import annotations

from cardlang.runtime.combinations import Play, _combos, _legal_follows, _points
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player


# --- the climb queries (the monolith's candidate lists, verbatim) ---


def tichu_lead_options(hand: list[Card], ctx: Ctx) -> list[Play]:
    """Every combination the leader may lead: the engine's combos, then the
    three specials as lead singles in hand order (Dragon highest at 15, the
    Phoenix at 1.5, the Dog as its own trick-ending kind). `ctx` is unused —
    Tichu leads depend only on the hand — but the climb round passes it
    uniformly with the follows query."""
    leads = _combos(hand)
    for c in hand:
        if c.rank == "Dragon":
            leads.append(Play("single", 1, 15, (c,)))
        elif c.rank == "Phoenix":
            leads.append(Play("single", 1, 1.5, (c,)))
        elif c.rank == "Dog":
            leads.append(Play("dog", 1, 0, (c,)))
    return leads


def tichu_follows(hand: list[Card], current: Play, ctx: Ctx) -> list[Play]:
    """The combinations that legally beat the standing play (same kind and
    length, higher key; any bomb; the Dragon/Phoenix single answers). `ctx` is
    unused, passed uniformly with the lead query."""
    return _legal_follows(hand, current)


# --- the two non-chooser RNG sites (the monolith's, draw-for-draw) ---


# --- zone / seating / state reads (pure) ---


def tichu_mahjong_holder(ctx: Ctx) -> Player:
    """Who leads the first trick: the Mahjong holder (post-push hands; the
    full deal guarantees one exists)."""
    hands = ctx.rs.zones.families["hand"]
    return next(
        p for p in ctx.rs.seating.players
        if any(c.rank == "Mahjong" for c in hands[p].cards)
    )


def tichu_players_holding(ctx: Ctx) -> int:
    """How many players still hold cards (the hand ends at <= 1)."""
    hands = ctx.rs.zones.families["hand"]
    return sum(1 for p in ctx.rs.seating.players if hands[p].cards)


def tichu_double_victory(ctx: Ctx) -> bool:
    """Both recorded finishers are teammates (ends the hand early, +200)."""
    first, second = ctx.rs.get("out_first"), ctx.rs.get("out_second")
    return (
        first is not None
        and second is not None
        and ctx.rs.team_of[first] == ctx.rs.team_of[second]
    )


def tichu_partner(ctx: Ctx, p: Player) -> Player:
    """The teammate (partners sit across)."""
    return next(
        q for q in ctx.rs.seating.players
        if q != p and ctx.rs.team_of[q] == ctx.rs.team_of[p]
    )


def tichu_next_holder(ctx: Ctx, p: Player) -> Player:
    """`p` if they still hold cards, else the next holder counterclockwise —
    the monolith's post-trick leader advance. Returns `p` unchanged when
    everyone is out (the hand is over; the value is never read)."""
    hands = ctx.rs.zones.families["hand"]
    players = list(ctx.rs.seating.players)
    if not any(hands[q].cards for q in players):
        return p
    q = p
    while not hands[q].cards:
        q = (q - 1) % len(players)
    return q


def tichu_dragon_won(ctx: Ctx) -> bool:
    """Did the Dragon capture the trick just completed? Reads the standing
    play from the round's terminal state: the Dragon appears in a pile only as
    a played single, and only a bomb can beat it — so the check is exactly the
    monolith's (the final play is one card and it is the Dragon)."""
    st = ctx.rs.last_round_state
    cur = None if st is None else st.get("current")
    return (
        cur is not None and len(cur.cards) == 1 and cur.cards[0].rank == "Dragon"
    )


def tichu_opponent_team(ctx: Ctx, p: Player) -> int:
    """The team `p` does not belong to (two-team game)."""
    return next(t for t in ctx.rs.teams if t != ctx.rs.team_of[p])


def tichu_first_out(ctx: Ctx) -> Player:
    """The first player to shed out, defaulting to player 0 when nobody is
    recorded (the monolith's fallback; unreachable in a completed hand)."""
    first = ctx.rs.get("out_first")
    return 0 if first is None else int(first)


def tichu_card_points(ctx: Ctx, c: Card) -> int:
    """The card-point table (K and 10 score 10, 5 scores 5, Dragon +25,
    Phoenix -25; 100 points per hand)."""
    return _points(c)


def tichu_hand_summary(ctx: Ctx) -> int:
    """Emit the hand's `tichu_hand` trace — the double-victory flag and the
    card points sitting in the two captured piles after routing — and return
    the card points. The playout harness asserts every non-double-victory hand
    distributes exactly 100 (tests/test_playout_tichu.py)."""
    captured = ctx.rs.zones.families["captured"]
    pts = sum(_points(c) for t in ctx.rs.teams for c in captured[t].cards)
    ctx.trace(
        "tichu_hand",
        {"double_victory": tichu_double_victory(ctx), "card_points": pts},
    )
    return pts


# ---------------------------------------------------------------------------
# The combo codec: card-set <-> action-index, computed, never enumerated
# ---------------------------------------------------------------------------
#
# The OpenSpiel adapter needs one stable global action id per distinct play the
# engine can ever emit. Big Two enumerates its 19,898-play universe; Tichu's is
# 211,204,694 (straights of length 5-14 under free suit assignment are 208.8M
# of it), so its ids are *computed*: a fixed block layout — dog, single, pair,
# triple, bomb, fullhouse, straight, pairseq — with a mixed-radix ranking
# inside each block. Every id is a pure function of the card-set (stable across
# determinized worlds), each card-set has exactly one block decomposition
# (sizes and rank structures are disjoint), and the blocks are a superset of
# everything `_combos` + the lead-site specials can produce — including the
# engine's Mahjong quirk (`by_rank` treats the Mahjong as a normal rank-1 card,
# so a Phoenix+Mahjong pair and Mahjong-filled phoenix fullhouses are
# emittable). Pinned by tests/test_openspiel_encoding.py.

from cardlang.runtime.values import SUITS, build_deck  # noqa: E402

_VAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
        "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
_RANK_OF_VAL = {v: r for r, v in _VAL.items()}

_DECK = build_deck("tichu56")
_MAHJONG = next(c for c in _DECK if c.rank == "Mahjong")
_DOG = next(c for c in _DECK if c.rank == "Dog")
_PHOENIX = next(c for c in _DECK if c.rank == "Phoenix")
_DRAGON = next(c for c in _DECK if c.rank == "Dragon")

_PAIR2 = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
_PAIR2_IDX: dict[tuple[int, ...], int] = {p: i for i, p in enumerate(_PAIR2)}
_COMB3 = ((0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3))
_COMB3_IDX: dict[tuple[int, ...], int] = {t: i for i, t in enumerate(_COMB3)}

_N_DOG = 1
_N_SINGLE = 55
# naturals, then phoenix pairs: {Phoenix, Mahjong} first, then 13 ranks x 4 suits
_N_PAIR = 13 * 6 + (1 + 13 * 4)
_N_TRIPLE = 13 * 4 + 13 * 6
_N_BOMB = 13
# naturals, then phoenix fullhouses: per (triple rank, triple suits) the pair
# filler is the Mahjong (slot 0) or one of 12 other ranks x 4 suits
_N_FH = 13 * 12 * 4 * 6 + 13 * 4 * (1 + 12 * 4)

# Straight windows in (length, lo) order; each window's size is the product of
# its per-rank suit choices (the Mahjong slot, value 1, has one).
_STRAIGHT_WINDOWS: list[tuple[int, int, int]] = []
for _length in range(5, 15):
    for _lo in range(1, 16 - _length):
        _sz = 1
        for _v in range(_lo, _lo + _length):
            _sz *= 1 if _v == 1 else 4
        _STRAIGHT_WINDOWS.append((_length, _lo, _sz))
_STRAIGHT_OFFSETS: dict[tuple[int, int], int] = {}
_N_STRAIGHT = 0
for _length, _lo, _sz in _STRAIGHT_WINDOWS:
    _STRAIGHT_OFFSETS[(_length, _lo)] = _N_STRAIGHT
    _N_STRAIGHT += _sz

# Pairseq windows: 2-7 consecutive pair ranks (a 14-card hand holds 7 pairs).
_PAIRSEQ_WINDOWS: list[tuple[int, int, int]] = []
for _length in range(2, 8):
    for _lo in range(2, 16 - _length):
        _PAIRSEQ_WINDOWS.append((_length, _lo, 6 ** _length))
_PAIRSEQ_OFFSETS: dict[tuple[int, int], int] = {}
_N_PAIRSEQ = 0
for _length, _lo, _sz in _PAIRSEQ_WINDOWS:
    _PAIRSEQ_OFFSETS[(_length, _lo)] = _N_PAIRSEQ
    _N_PAIRSEQ += _sz

_BASE_DOG = 0
_BASE_SINGLE = _BASE_DOG + _N_DOG
_BASE_PAIR = _BASE_SINGLE + _N_SINGLE
_BASE_TRIPLE = _BASE_PAIR + _N_PAIR
_BASE_BOMB = _BASE_TRIPLE + _N_TRIPLE
_BASE_FH = _BASE_BOMB + _N_BOMB
_BASE_STRAIGHT = _BASE_FH + _N_FH
_BASE_PAIRSEQ = _BASE_STRAIGHT + _N_STRAIGHT


def _sidx(c: Card) -> int:
    return SUITS.index(c.suit)


def _single_index(c: Card) -> int:
    if c.rank == "Mahjong":
        return 0
    if c.rank == "Dragon":
        return 53
    if c.rank == "Phoenix":
        return 54
    return 1 + (_VAL[c.rank] - 2) * 4 + _sidx(c)


def _single_card(i: int) -> Card:
    if i == 0:
        return _MAHJONG
    if i == 53:
        return _DRAGON
    if i == 54:
        return _PHOENIX
    v, s = divmod(i - 1, 4)
    return Card(_RANK_OF_VAL[v + 2], SUITS[s])


def _pr_rel(tr: int, pr: int) -> int:
    """The pair rank's index among the 12 ranks that are not the triple's."""
    return (pr - 2) if pr < tr else (pr - 3)


def _pr_from_rel(tr: int, rel: int) -> int:
    v = rel + 2
    return v if v < tr else v + 1


class TichuComboCodec:
    """The climbing form's play universe as arithmetic (see the block comment
    above). `encode_cards` raises ValueError on a card-set outside the
    universe — a corrupted history, never a live candidate."""

    size = (
        _N_DOG + _N_SINGLE + _N_PAIR + _N_TRIPLE + _N_BOMB + _N_FH
        + _N_STRAIGHT + _N_PAIRSEQ
    )

    def encode_cards(self, cards: frozenset[Card]) -> int:
        n = len(cards)
        phoenix = _PHOENIX in cards
        mahjong = _MAHJONG in cards
        normals = sorted(
            (c for c in cards if c.rank in _VAL),
            key=lambda c: (_VAL[c.rank], _sidx(c)),
        )
        by_val: dict[int, list[Card]] = {}
        for c in normals:
            by_val.setdefault(_VAL[c.rank], []).append(c)

        if n == 1:
            c = next(iter(cards))
            if c.rank == "Dog":
                return _BASE_DOG
            return _BASE_SINGLE + _single_index(c)

        if n == 2:
            if phoenix:
                if mahjong:  # the engine pairs the Phoenix with the Mahjong
                    return _BASE_PAIR + 78
                if len(normals) == 1:
                    (c,) = normals
                    return _BASE_PAIR + 79 + (_VAL[c.rank] - 2) * 4 + _sidx(c)
            elif len(normals) == 2 and _VAL[normals[0].rank] == _VAL[normals[1].rank]:
                v = _VAL[normals[0].rank]
                pair = (_sidx(normals[0]), _sidx(normals[1]))
                return _BASE_PAIR + (v - 2) * 6 + _PAIR2_IDX[pair]

        if n == 3:
            if phoenix and len(by_val) == 1:
                v, cs = next(iter(by_val.items()))
                if len(cs) == 2:
                    pair = (_sidx(cs[0]), _sidx(cs[1]))
                    return _BASE_TRIPLE + 52 + (v - 2) * 6 + _PAIR2_IDX[pair]
            elif not phoenix and len(by_val) == 1:
                v, cs = next(iter(by_val.items()))
                if len(cs) == 3:
                    suits3 = tuple(sorted(_sidx(c) for c in cs))
                    return _BASE_TRIPLE + (v - 2) * 4 + _COMB3_IDX[suits3]

        vals = sorted(by_val)
        counts = {v: len(cs) for v, cs in by_val.items()}

        if n == 4 and not phoenix and not mahjong and len(vals) == 1:
            return _BASE_BOMB + (vals[0] - 2)

        if n == 5 and phoenix and mahjong and len(vals) == 1 and counts[vals[0]] == 3:
            tr = vals[0]  # {tr x3, Mahjong, Phoenix}: the Mahjong fills the pair
            tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
            return _BASE_FH + 3744 + ((tr - 2) * 4 + _COMB3_IDX[tsuits]) * 49
        if n == 5 and phoenix and not mahjong and len(vals) == 2:
            trs = [v for v in vals if counts[v] == 3]
            prs = [v for v in vals if counts[v] == 1]
            if trs and prs:
                tr, pr = trs[0], prs[0]
                tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
                (pc,) = by_val[pr]
                slot = 1 + _pr_rel(tr, pr) * 4 + _sidx(pc)
                return _BASE_FH + 3744 + ((tr - 2) * 4 + _COMB3_IDX[tsuits]) * 49 + slot
        if n == 5 and not phoenix and not mahjong and len(vals) == 2:
            trs = [v for v in vals if counts[v] == 3]
            prs = [v for v in vals if counts[v] == 2]
            if trs and prs:
                tr, pr = trs[0], prs[0]
                tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
                psuits = tuple(sorted(_sidx(c) for c in by_val[pr]))
                idx = (
                    ((tr - 2) * 12 + _pr_rel(tr, pr)) * 24
                    + _COMB3_IDX[tsuits] * 6
                    + _PAIR2_IDX[psuits]
                )
                return _BASE_FH + idx

        # straights: one card per value, consecutive; the Mahjong anchors at 1
        all_vals = ([1] if mahjong else []) + vals
        if (
            not phoenix
            and n >= 5
            and len(all_vals) == n
            and all(counts[v] == 1 for v in vals)
            and all_vals == list(range(all_vals[0], all_vals[0] + n))
        ):
            digit = 0
            for v in all_vals:
                if v == 1:
                    continue
                digit = digit * 4 + _sidx(by_val[v][0])
            return _BASE_STRAIGHT + _STRAIGHT_OFFSETS[(n, all_vals[0])] + digit

        # pairseq: 2-7 consecutive values, two cards each
        if (
            not phoenix
            and not mahjong
            and 2 <= len(vals) <= 7
            and all(counts[v] == 2 for v in vals)
            and vals == list(range(vals[0], vals[0] + len(vals)))
        ):
            digit = 0
            for v in vals:
                pair = (_sidx(by_val[v][0]), _sidx(by_val[v][1]))
                digit = digit * 6 + _PAIR2_IDX[pair]
            return _BASE_PAIRSEQ + _PAIRSEQ_OFFSETS[(len(vals), vals[0])] + digit

        raise ValueError(
            f"not an encodable Tichu play card-set: {sorted(map(str, cards))}"
        )

    def decode(self, index: int) -> frozenset[Card]:
        if 0 <= index < _BASE_SINGLE:
            return frozenset({_DOG})
        if index < _BASE_PAIR:
            return frozenset({_single_card(index - _BASE_SINGLE)})
        if index < _BASE_TRIPLE:
            i = index - _BASE_PAIR
            if i < 78:
                v, pi = divmod(i, 6)
                s1, s2 = _PAIR2[pi]
                r = _RANK_OF_VAL[v + 2]
                return frozenset({Card(r, SUITS[s1]), Card(r, SUITS[s2])})
            i -= 78
            if i == 0:
                return frozenset({_MAHJONG, _PHOENIX})
            v, s = divmod(i - 1, 4)
            return frozenset({Card(_RANK_OF_VAL[v + 2], SUITS[s]), _PHOENIX})
        if index < _BASE_BOMB:
            i = index - _BASE_TRIPLE
            if i < 52:
                v, ti = divmod(i, 4)
                r = _RANK_OF_VAL[v + 2]
                return frozenset({Card(r, SUITS[s]) for s in _COMB3[ti]})
            i -= 52
            v, pi = divmod(i, 6)
            s1, s2 = _PAIR2[pi]
            r = _RANK_OF_VAL[v + 2]
            return frozenset({Card(r, SUITS[s1]), Card(r, SUITS[s2]), _PHOENIX})
        if index < _BASE_FH:
            r = _RANK_OF_VAL[index - _BASE_BOMB + 2]
            return frozenset({Card(r, s) for s in SUITS})
        if index < _BASE_STRAIGHT:
            i = index - _BASE_FH
            if i < 3744:
                pair_i = i % 6
                i //= 6
                trip_i = i % 4
                i //= 4
                tr = i // 12 + 2
                pr = _pr_from_rel(tr, i % 12)
                trr, prr = _RANK_OF_VAL[tr], _RANK_OF_VAL[pr]
                s1, s2 = _PAIR2[pair_i]
                return frozenset(
                    {Card(trr, SUITS[s]) for s in _COMB3[trip_i]}
                    | {Card(prr, SUITS[s1]), Card(prr, SUITS[s2])}
                )
            i -= 3744
            group, slot = divmod(i, 49)
            tr = group // 4 + 2
            triple = {Card(_RANK_OF_VAL[tr], SUITS[s]) for s in _COMB3[group % 4]}
            if slot == 0:
                return frozenset(triple | {_MAHJONG, _PHOENIX})
            rel, ps = divmod(slot - 1, 4)
            prr = _RANK_OF_VAL[_pr_from_rel(tr, rel)]
            return frozenset(triple | {Card(prr, SUITS[ps]), _PHOENIX})
        if index < _BASE_PAIRSEQ:
            i = index - _BASE_STRAIGHT
            for (length, lo, sz) in _STRAIGHT_WINDOWS:
                off = _STRAIGHT_OFFSETS[(length, lo)]
                if i < off + sz:
                    digit = i - off
                    suit_vals = [v for v in range(lo, lo + length) if v != 1]
                    digits: list[int] = []
                    for _ in suit_vals:
                        digits.append(digit % 4)
                        digit //= 4
                    digits.reverse()
                    cards = {_MAHJONG} if lo == 1 else set()
                    for v, s in zip(suit_vals, digits):
                        cards.add(Card(_RANK_OF_VAL[v], SUITS[s]))
                    return frozenset(cards)
            raise AssertionError("unreachable straight index")
        if index < self.size:
            i = index - _BASE_PAIRSEQ
            for (length, lo, sz) in _PAIRSEQ_WINDOWS:
                off = _PAIRSEQ_OFFSETS[(length, lo)]
                if i < off + sz:
                    digit = i - off
                    pdigits: list[int] = []
                    for _ in range(length):
                        pdigits.append(digit % 6)
                        digit //= 6
                    pdigits.reverse()
                    cards = set()
                    for v, pi in zip(range(lo, lo + length), pdigits):
                        s1, s2 = _PAIR2[pi]
                        r = _RANK_OF_VAL[v]
                        cards.add(Card(r, SUITS[s1]))
                        cards.add(Card(r, SUITS[s2]))
                    return frozenset(cards)
            raise AssertionError("unreachable pairseq index")
        raise ValueError(f"combo index {index} out of range 0..{self.size - 1}")

    def kind_of(self, index: int) -> str:
        for base, kind in (
            (_BASE_SINGLE, "dog"), (_BASE_PAIR, "single"), (_BASE_TRIPLE, "pair"),
            (_BASE_BOMB, "triple"), (_BASE_FH, "bomb"), (_BASE_STRAIGHT, "fullhouse"),
            (_BASE_PAIRSEQ, "straight"), (self.size, "pairseq"),
        ):
            if index < base:
                return kind
        raise ValueError(f"combo index {index} out of range 0..{self.size - 1}")


TICHU_COMBO_CODEC = TichuComboCodec()
