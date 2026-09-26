"""Tichu's game-local runtime primitives.

The hand runs fully on the kernel (tichu.cardlang): the calls and the push
are plain statements, each climbing [[trick]] is one `round climb` over the
combination engine's queries, and the finishing and scoring flow is statement
control flow over the round's terminal state (`state.lead_ended_trick`,
`state.shed_first` / `state.shed_second`). What stays game-local is the
combination engine itself (`tichu_combinations.py`, shared with nothing — Big
Two's differs) and the combo codec below, which gives every play the engine
can emit a stable OpenSpiel action id.

`tichu_dragon_won` reads the completed round's standing play from
`last_round_state` (the same terminal frame the body reads as `state.x`).
"""

from __future__ import annotations

from itertools import combinations

from cardlang.runtime import reads
from cardlang.runtime.errors import ShadowGuardError
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.tichu_combinations import (
    PHOENIX_LEAD_VALUE,
    Play,
    _combos,
    _legal_follows,
    phoenix_single,
)
from cardlang.runtime.values import SUITS, Card, build_deck

# The CLIMB queries' row: `primitives.climb_row` imports this binding at load
# and the round machinery binds it per trick. `tichu_dragon_won` does not use
# it — the game declares that Primitive, so its bundle comes from its own
# `reads` clause — and the row outlives that declaration because the block
# does not cover the climb namespace.
ROW = reads.row("cardlang/runtime/tichu.py", "tichu.cardlang")


# --- the climb queries ---


def tichu_lead_options(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card]
) -> list[Play]:
    """Every combination the leader may lead: the engine's combinations, then
    the two lead-only plays — the Phoenix as a single at 1.5, and the Dog as
    its own trick-ending kind. The bundles are unused (Tichu leads depend only
    on the hand); the climb round passes them uniformly with the follows
    query."""
    leads = _combos(hand)
    phoenix = phoenix_single(hand, PHOENIX_LEAD_VALUE)
    if phoenix is not None:
        leads.append(phoenix)
    for c in hand:
        if c.rank == "Dog":
            leads.append(Play("dog", 1, 0, (c,)))
    return leads


def tichu_follows(
    facts: EngineFacts, gr: reads.GameReads, hand: list[Card], current: Play
) -> list[Play]:
    """The combinations that legally beat the standing play (same kind and
    length, higher key; a bomb over anything it outranks; the Phoenix's single
    answer). The bundles are unused, passed uniformly with the lead query."""
    return _legal_follows(hand, current)


# --- round-state reads (pure) ---


def tichu_dragon_won(facts: EngineFacts, gr: reads.GameReads) -> bool:
    """Did the Dragon capture the trick just completed? Reads the standing
    play from the round's terminal state: the Dragon appears in a pile only as
    a played single, and only a bomb can beat it — so the check is that the
    final play is one card and it is the Dragon."""
    st = facts.last_round_state
    cur = None if st is None else st.get("current")
    return (
        cur is not None and len(cur.cards) == 1 and cur.cards[0].rank == "Dragon"
    )


# ---------------------------------------------------------------------------
# The combo codec: play <-> action-index, computed, never enumerated
# ---------------------------------------------------------------------------
#
# The OpenSpiel adapter needs one stable global action id per distinct play
# the engine can ever emit. Big Two enumerates its universe; Tichu's is too
# large (straights under free suit assignment dominate — the size is
# `TICHU_COMBO_CODEC.size`, derived below from the block sizes), so its ids
# are *computed*: a fixed block layout — dog, single, pair, triple, bomb
# (four of a rank, then straight flushes), full house, straight, pair
# sequence, each kind's natural plays before its Phoenix plays — with a
# mixed-radix ranking inside each block. Every id is a pure function of the
# play's identity, (card-set, wild), so ids are stable across determinized
# worlds. Each identity has exactly one block decomposition: the kinds'
# size and rank structures are disjoint, and a suited run of five or more
# ranks is a bomb and never a straight, so the natural-straight block
# excludes the monochrome suit assignments. The blocks are exactly the
# engine's universe: every play `_combos` and the lead site emit encodes, and
# every id decodes to a play some hand can form. Pinned by
# tests/test_openspiel_encoding.py and tests/test_tichu_combinations.py.

_VAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
        "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14}
_RANK_OF_VAL = {v: r for r, v in _VAL.items()}

_DECK = build_deck("tichu56")
_MAHJONG = next(c for c in _DECK if c.rank == "Mahjong")
_DOG = next(c for c in _DECK if c.rank == "Dog")
_PHOENIX = next(c for c in _DECK if c.rank == "Phoenix")
_DRAGON = next(c for c in _DECK if c.rank == "Dragon")

_PAIR2 = tuple(combinations(range(4), 2))
_PAIR2_IDX: dict[tuple[int, ...], int] = {p: i for i, p in enumerate(_PAIR2)}
_COMB3 = tuple(combinations(range(4), 3))
_COMB3_IDX: dict[tuple[int, ...], int] = {t: i for i, t in enumerate(_COMB3)}

_N_DOG = 1
_N_SINGLE = 55
_N_PAIR_NAT = 13 * 6
_N_PAIR = _N_PAIR_NAT + 13 * 4  # then the Phoenix with one card of a rank
_N_TRIPLE_NAT = 13 * 4
_N_TRIPLE = _N_TRIPLE_NAT + 13 * 6  # then the Phoenix with two cards of a rank
_N_BOMB4 = 13
# Straight-flush bombs: (length, lo) windows over the ranks 2..A, four suits.
_SF_WINDOWS: tuple[tuple[int, int], ...] = tuple(
    (length, lo) for length in range(5, 14) for lo in range(2, 16 - length)
)
_SF_IDX: dict[tuple[int, int], int] = {w: i for i, w in enumerate(_SF_WINDOWS)}
_N_BOMBSF = len(_SF_WINDOWS) * 4
_N_BOMB = _N_BOMB4 + _N_BOMBSF
# Full houses: naturals; the Phoenix completing the pair beside a natural
# triple (triple rank x triple suits x pair card among the 12 other ranks);
# the Phoenix completing the triple beside a natural pair (triple rank x its
# two natural suits x pair rank x pair suits).
_N_FH_NAT = 13 * 12 * 4 * 6
_N_FH_PHPAIR = 13 * 4 * 12 * 4
_N_FH_PHTRIPLE = 13 * 12 * 6 * 6
_N_FH = _N_FH_NAT + _N_FH_PHPAIR + _N_FH_PHTRIPLE


def _suited_count(length: int, lo: int) -> int:
    """How many ranks of a straight window carry a suit (the Mahjong, at
    lo == 1, carries none)."""
    return length - (1 if lo == 1 else 0)


# Natural straights in (length, lo) order; a window's size is 4 to the power
# of its suited ranks, less the four monochrome assignments where those would
# be a straight flush (lo >= 2: no Mahjong in the run).
_STRAIGHT_WINDOWS: list[tuple[int, int, int]] = []
for _length in range(5, 15):
    for _lo in range(1, 16 - _length):
        _sz = 4 ** _suited_count(_length, _lo) - (4 if _lo >= 2 else 0)
        _STRAIGHT_WINDOWS.append((_length, _lo, _sz))
_STRAIGHT_OFFSETS: dict[tuple[int, int], int] = {}
_N_STRAIGHT_NAT = 0
for _length, _lo, _sz in _STRAIGHT_WINDOWS:
    _STRAIGHT_OFFSETS[(_length, _lo)] = _N_STRAIGHT_NAT
    _N_STRAIGHT_NAT += _sz

# Phoenix straights in (length, lo, wild) order: the Phoenix stands for one
# rank `wild` of the window (never the Mahjong's one), and the other suited
# ranks take any suit.
_PSTRAIGHT_WINDOWS: list[tuple[int, int, int, int]] = []
for _length in range(5, 15):
    for _lo in range(1, 16 - _length):
        for _wild in range(max(_lo, 2), _lo + _length):
            _sz = 4 ** (_suited_count(_length, _lo) - 1)
            _PSTRAIGHT_WINDOWS.append((_length, _lo, _wild, _sz))
_PSTRAIGHT_OFFSETS: dict[tuple[int, int, int], int] = {}
_N_STRAIGHT_PH = 0
for _length, _lo, _wild, _sz in _PSTRAIGHT_WINDOWS:
    _PSTRAIGHT_OFFSETS[(_length, _lo, _wild)] = _N_STRAIGHT_PH
    _N_STRAIGHT_PH += _sz
_N_STRAIGHT = _N_STRAIGHT_NAT + _N_STRAIGHT_PH

# Pair sequences: 2-7 consecutive pair ranks (a 14-card hand holds 7 pairs),
# each rank one of the six suit pairs; then the Phoenix standing for one card
# of one rank `wild`, whose natural partner takes any of the four suits.
_PAIRSEQ_WINDOWS: list[tuple[int, int, int]] = []
for _length in range(2, 8):
    for _lo in range(2, 16 - _length):
        _PAIRSEQ_WINDOWS.append((_length, _lo, 6 ** _length))
_PAIRSEQ_OFFSETS: dict[tuple[int, int], int] = {}
_N_PAIRSEQ_NAT = 0
for _length, _lo, _sz in _PAIRSEQ_WINDOWS:
    _PAIRSEQ_OFFSETS[(_length, _lo)] = _N_PAIRSEQ_NAT
    _N_PAIRSEQ_NAT += _sz
_PPAIRSEQ_WINDOWS: list[tuple[int, int, int, int]] = []
for _length in range(2, 8):
    for _lo in range(2, 16 - _length):
        for _wild in range(_lo, _lo + _length):
            _PPAIRSEQ_WINDOWS.append((_length, _lo, _wild, 4 * 6 ** (_length - 1)))
_PPAIRSEQ_OFFSETS: dict[tuple[int, int, int], int] = {}
_N_PAIRSEQ_PH = 0
for _length, _lo, _wild, _sz in _PPAIRSEQ_WINDOWS:
    _PPAIRSEQ_OFFSETS[(_length, _lo, _wild)] = _N_PAIRSEQ_PH
    _N_PAIRSEQ_PH += _sz
_N_PAIRSEQ = _N_PAIRSEQ_NAT + _N_PAIRSEQ_PH

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


def _mono_rank(digit: int, k: int) -> int:
    """`digit`'s index among the base-4 k-digit vectors that are not
    monochrome (all digits equal)."""
    mono = (4**k - 1) // 3
    return digit - sum(1 for s in range(4) if s * mono < digit)


def _mono_unrank(index: int, k: int) -> int:
    """The inverse of `_mono_rank`: the index-th non-monochrome vector."""
    mono = (4**k - 1) // 3
    digit = index
    for s in range(4):
        if s * mono <= digit:
            digit += 1
    return digit


def _refuse(cards: frozenset[Card], wild: int | None) -> ValueError:
    return ValueError(
        f"not an encodable Tichu play: {sorted(map(str, cards))} wild={wild}"
    )


class TichuComboCodec:
    """The climbing form's play universe as arithmetic (see the block comment
    above). `encode` raises ValueError on an identity outside the universe — a
    corrupted history, never a live candidate."""

    size = (
        _N_DOG + _N_SINGLE + _N_PAIR + _N_TRIPLE + _N_BOMB + _N_FH
        + _N_STRAIGHT + _N_PAIRSEQ
    )

    def encode(self, cards: frozenset[Card], wild: int | None) -> int:
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
        vals = sorted(by_val)
        counts = {v: len(cs) for v, cs in by_val.items()}
        if wild is not None and (not phoenix or wild not in _RANK_OF_VAL):
            raise _refuse(cards, wild)

        if n == 1:
            if wild is not None:
                raise _refuse(cards, wild)
            c = next(iter(cards))
            if c.rank == "Dog":
                return _BASE_DOG
            return _BASE_SINGLE + _single_index(c)

        if n == 2 and not mahjong:
            if phoenix and len(normals) == 1 and wild == _VAL[normals[0].rank]:
                (c,) = normals
                return _BASE_PAIR + _N_PAIR_NAT + (_VAL[c.rank] - 2) * 4 + _sidx(c)
            if not phoenix and len(vals) == 1 and counts[vals[0]] == 2:
                v = vals[0]
                pair = (_sidx(normals[0]), _sidx(normals[1]))
                return _BASE_PAIR + (v - 2) * 6 + _PAIR2_IDX[pair]

        if n == 3 and not mahjong and len(vals) == 1:
            v, cs = vals[0], by_val[vals[0]]
            if phoenix and len(cs) == 2 and wild == v:
                pair = (_sidx(cs[0]), _sidx(cs[1]))
                return _BASE_TRIPLE + _N_TRIPLE_NAT + (v - 2) * 6 + _PAIR2_IDX[pair]
            if not phoenix and len(cs) == 3:
                suits3 = tuple(sorted(_sidx(c) for c in cs))
                return _BASE_TRIPLE + (v - 2) * 4 + _COMB3_IDX[suits3]

        if n == 4 and not phoenix and not mahjong and len(vals) == 1:
            return _BASE_BOMB + (vals[0] - 2)

        if n == 5 and not mahjong and len(vals) == 2:
            lo_v, hi_v = vals
            if not phoenix and {counts[lo_v], counts[hi_v]} == {3, 2}:
                tr, pr = (lo_v, hi_v) if counts[lo_v] == 3 else (hi_v, lo_v)
                tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
                psuits = tuple(sorted(_sidx(c) for c in by_val[pr]))
                idx = (
                    ((tr - 2) * 12 + _pr_rel(tr, pr)) * 24
                    + _COMB3_IDX[tsuits] * 6
                    + _PAIR2_IDX[psuits]
                )
                return _BASE_FH + idx
            if phoenix and {counts[lo_v], counts[hi_v]} == {3, 1}:
                tr, pr = (lo_v, hi_v) if counts[lo_v] == 3 else (hi_v, lo_v)
                if wild == pr:
                    tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
                    (pc,) = by_val[pr]
                    group = (tr - 2) * 4 + _COMB3_IDX[tsuits]
                    return _BASE_FH + _N_FH_NAT + group * 48 + _pr_rel(tr, pr) * 4 + _sidx(pc)
            if phoenix and counts[lo_v] == 2 and counts[hi_v] == 2 and wild in vals:
                tr = wild
                pr = hi_v if tr == lo_v else lo_v
                tsuits = tuple(sorted(_sidx(c) for c in by_val[tr]))
                psuits = tuple(sorted(_sidx(c) for c in by_val[pr]))
                idx = (
                    ((tr - 2) * 12 + _pr_rel(tr, pr)) * 36
                    + _PAIR2_IDX[tsuits] * 6
                    + _PAIR2_IDX[psuits]
                )
                return _BASE_FH + _N_FH_NAT + _N_FH_PHPAIR + idx

        one_each = all(counts[v] == 1 for v in vals)

        # Straight-flush bombs: one card per consecutive rank, all one suit.
        if (
            n >= 5
            and not phoenix
            and not mahjong
            and one_each
            and vals == list(range(vals[0], vals[0] + n))
            and len({c.suit for c in normals}) == 1
        ):
            window = _SF_IDX.get((n, vals[0]))
            if window is not None:
                return _BASE_BOMB + _N_BOMB4 + window * 4 + _sidx(normals[0])

        # Natural straights: one card per value, consecutive; the Mahjong at 1.
        all_vals = ([1] if mahjong else []) + vals
        if (
            not phoenix
            and n >= 5
            and len(all_vals) == n
            and one_each
            and all_vals == list(range(all_vals[0], all_vals[0] + n))
        ):
            digit = 0
            for v in vals:
                digit = digit * 4 + _sidx(by_val[v][0])
            lo = all_vals[0]
            if lo >= 2:
                digit = _mono_rank(digit, n)
            return _BASE_STRAIGHT + _STRAIGHT_OFFSETS[(n, lo)] + digit

        # Phoenix straights: the Phoenix stands for `wild`, absent from the
        # natural values.
        if (
            phoenix
            and wild is not None
            and n >= 5
            and one_each
            and wild not in counts
            and len(all_vals) == n - 1
        ):
            with_wild = sorted([*all_vals, wild])
            if with_wild == list(range(with_wild[0], with_wild[0] + n)):
                digit = 0
                for v in vals:
                    digit = digit * 4 + _sidx(by_val[v][0])
                return (
                    _BASE_STRAIGHT
                    + _N_STRAIGHT_NAT
                    + _PSTRAIGHT_OFFSETS[(n, with_wild[0], wild)]
                    + digit
                )

        # Pair sequences: 2-7 consecutive values, two cards each.
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

        # Phoenix pair sequences: one value holds a single natural, the
        # Phoenix its partner; every other value two cards.
        if (
            phoenix
            and not mahjong
            and wild is not None
            and 2 <= len(vals) <= 7
            and counts.get(wild) == 1
            and all(counts[v] == 2 for v in vals if v != wild)
            and vals == list(range(vals[0], vals[0] + len(vals)))
        ):
            digit = 0
            for v in vals:
                if v != wild:
                    pair = (_sidx(by_val[v][0]), _sidx(by_val[v][1]))
                    digit = digit * 6 + _PAIR2_IDX[pair]
            (single,) = by_val[wild]
            digit = digit * 4 + _sidx(single)
            return (
                _BASE_PAIRSEQ
                + _N_PAIRSEQ_NAT
                + _PPAIRSEQ_OFFSETS[(len(vals), vals[0], wild)]
                + digit
            )

        raise _refuse(cards, wild)

    def decode(self, index: int) -> tuple[frozenset[Card], int | None]:
        if 0 <= index < _BASE_SINGLE:
            return frozenset({_DOG}), None
        if index < _BASE_PAIR:
            return frozenset({_single_card(index - _BASE_SINGLE)}), None
        if index < _BASE_TRIPLE:
            i = index - _BASE_PAIR
            if i < _N_PAIR_NAT:
                v, pi = divmod(i, 6)
                s1, s2 = _PAIR2[pi]
                r = _RANK_OF_VAL[v + 2]
                return frozenset({Card(r, SUITS[s1]), Card(r, SUITS[s2])}), None
            v, s = divmod(i - _N_PAIR_NAT, 4)
            return frozenset({Card(_RANK_OF_VAL[v + 2], SUITS[s]), _PHOENIX}), v + 2
        if index < _BASE_BOMB:
            i = index - _BASE_TRIPLE
            if i < _N_TRIPLE_NAT:
                v, ti = divmod(i, 4)
                r = _RANK_OF_VAL[v + 2]
                return frozenset({Card(r, SUITS[s]) for s in _COMB3[ti]}), None
            v, pi = divmod(i - _N_TRIPLE_NAT, 6)
            s1, s2 = _PAIR2[pi]
            r = _RANK_OF_VAL[v + 2]
            return frozenset({Card(r, SUITS[s1]), Card(r, SUITS[s2]), _PHOENIX}), v + 2
        if index < _BASE_FH:
            i = index - _BASE_BOMB
            if i < _N_BOMB4:
                r = _RANK_OF_VAL[i + 2]
                return frozenset({Card(r, s) for s in SUITS}), None
            window, s = divmod(i - _N_BOMB4, 4)
            length, lo = _SF_WINDOWS[window]
            return frozenset({Card(_RANK_OF_VAL[v], SUITS[s]) for v in range(lo, lo + length)}), None
        if index < _BASE_STRAIGHT:
            i = index - _BASE_FH
            if i < _N_FH_NAT:
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
                ), None
            i -= _N_FH_NAT
            if i < _N_FH_PHPAIR:
                group, slot = divmod(i, 48)
                tr = group // 4 + 2
                triple = {Card(_RANK_OF_VAL[tr], SUITS[s]) for s in _COMB3[group % 4]}
                rel, ps = divmod(slot, 4)
                pr = _pr_from_rel(tr, rel)
                return frozenset(triple | {Card(_RANK_OF_VAL[pr], SUITS[ps]), _PHOENIX}), pr
            i -= _N_FH_PHPAIR
            psuits_i = i % 6
            i //= 6
            tsuits_i = i % 6
            i //= 6
            tr = i // 12 + 2
            pr = _pr_from_rel(tr, i % 12)
            t1, t2 = _PAIR2[tsuits_i]
            p1, p2 = _PAIR2[psuits_i]
            trr, prr = _RANK_OF_VAL[tr], _RANK_OF_VAL[pr]
            return frozenset(
                {Card(trr, SUITS[t1]), Card(trr, SUITS[t2]), _PHOENIX,
                 Card(prr, SUITS[p1]), Card(prr, SUITS[p2])}
            ), tr
        if index < _BASE_PAIRSEQ:
            i = index - _BASE_STRAIGHT
            if i < _N_STRAIGHT_NAT:
                for (length, lo, sz) in _STRAIGHT_WINDOWS:
                    off = _STRAIGHT_OFFSETS[(length, lo)]
                    if i < off + sz:
                        digit = i - off
                        suit_vals = [v for v in range(lo, lo + length) if v != 1]
                        if lo >= 2:
                            digit = _mono_unrank(digit, len(suit_vals))
                        cards = self._straight_cards(suit_vals, digit, lo == 1)
                        return frozenset(cards), None
                # Shadow Guard of the codec's own window tables: offsets and
                # sizes partition the segment, so an in-bounds index matched.
                raise AssertionError("unreachable straight index")
            i -= _N_STRAIGHT_NAT
            for (length, lo, wild, sz) in _PSTRAIGHT_WINDOWS:
                off = _PSTRAIGHT_OFFSETS[(length, lo, wild)]
                if i < off + sz:
                    digit = i - off
                    suit_vals = [v for v in range(lo, lo + length) if v not in (1, wild)]
                    cards = self._straight_cards(suit_vals, digit, lo == 1)
                    return frozenset(cards | {_PHOENIX}), wild
            raise AssertionError("unreachable phoenix straight index")
        if index < self.size:
            i = index - _BASE_PAIRSEQ
            if i < _N_PAIRSEQ_NAT:
                for (length, lo, sz) in _PAIRSEQ_WINDOWS:
                    off = _PAIRSEQ_OFFSETS[(length, lo)]
                    if i < off + sz:
                        digit = i - off
                        cards = self._pairseq_cards(list(range(lo, lo + length)), digit)
                        return frozenset(cards), None
                raise AssertionError("unreachable pairseq index")
            i -= _N_PAIRSEQ_NAT
            for (length, lo, wild, sz) in _PPAIRSEQ_WINDOWS:
                off = _PPAIRSEQ_OFFSETS[(length, lo, wild)]
                if i < off + sz:
                    digit = i - off
                    digit, s = divmod(digit, 4)
                    cards = self._pairseq_cards([v for v in range(lo, lo + length) if v != wild], digit)
                    cards.add(Card(_RANK_OF_VAL[wild], SUITS[s]))
                    cards.add(_PHOENIX)
                    return frozenset(cards), wild
            raise AssertionError("unreachable phoenix pairseq index")
        raise ShadowGuardError(
            "openspiel.encoding.ActionSpace.decode",
            f"combo index {index} out of range 0..{self.size - 1}",
        )

    @staticmethod
    def _straight_cards(suit_vals: list[int], digit: int, with_mahjong: bool) -> set[Card]:
        digits: list[int] = []
        for _ in suit_vals:
            digits.append(digit % 4)
            digit //= 4
        digits.reverse()
        cards = {_MAHJONG} if with_mahjong else set()
        for v, s in zip(suit_vals, digits):
            cards.add(Card(_RANK_OF_VAL[v], SUITS[s]))
        return cards

    @staticmethod
    def _pairseq_cards(vals: list[int], digit: int) -> set[Card]:
        pdigits: list[int] = []
        for _ in vals:
            pdigits.append(digit % 6)
            digit //= 6
        pdigits.reverse()
        cards: set[Card] = set()
        for v, pi in zip(vals, pdigits):
            s1, s2 = _PAIR2[pi]
            r = _RANK_OF_VAL[v]
            cards.add(Card(r, SUITS[s1]))
            cards.add(Card(r, SUITS[s2]))
        return cards

    def kind_of(self, index: int) -> str:
        for base, kind in (
            (_BASE_SINGLE, "dog"), (_BASE_PAIR, "single"), (_BASE_TRIPLE, "pair"),
            (_BASE_BOMB, "triple"), (_BASE_FH, "bomb"), (_BASE_STRAIGHT, "fullhouse"),
            (_BASE_PAIRSEQ, "straight"), (self.size, "pairseq"),
        ):
            if index < base:
                return kind
        raise ShadowGuardError(
            "openspiel.encoding.ActionSpace.decode",
            f"combo index {index} out of range 0..{self.size - 1}",
        )


TICHU_COMBO_CODEC = TichuComboCodec()
