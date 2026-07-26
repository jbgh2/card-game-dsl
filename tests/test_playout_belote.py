"""Random-playout harness for Belote.

Belote's falsifiable surface is broad because a whole hand recomputes from
the play traces plus the recorded decisions: the deal reconstructs from what
each player played (conservation over the 32-card pack), follow legality is
a pure function of the trick prefix, the declared trump, and the acting
player's partnership (the five-obligation cascade — the corpus's richest),
the trick winner is a pure function of the plays under the J-9 trump order,
declarations recompute from the reconstructed hand at the poll, and the
settlement is a closed formula over card points, the dix de der, capot,
entitled declarations, and Belote-Rebelote. This test replays every seed and
recomputes ALL of it independently — an implementation of the Pagat rules
(as scoped in docs/games/belote.md) written against the trace log, not the
runtime — and asserts the driver's final scores match exactly.
"""

from __future__ import annotations

import random
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import SUITS, Card, Player

BELOTE = Path(__file__).parent.parent / "docs" / "games" / "belote.cardlang"

_TRUMP_HEIGHT = {"J": 8, "9": 7, "A": 6, "10": 5, "K": 4, "Q": 3, "8": 2, "7": 1}
_PLAIN_HEIGHT = {"A": 8, "10": 7, "K": 6, "Q": 5, "J": 4, "9": 3, "8": 2, "7": 1}
_NATURAL = {"A": 8, "K": 7, "Q": 6, "J": 5, "10": 4, "9": 3, "8": 2, "7": 1}
_TRUMP_PTS = {"J": 20, "9": 14, "A": 11, "10": 10, "K": 4, "Q": 3, "8": 0, "7": 0}
_PLAIN_PTS = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0, "8": 0, "7": 0}
_CARRE_HEIGHT = {"J": 6, "9": 5, "A": 4, "10": 3, "K": 2, "Q": 1}
_CARRE_POINTS = {"J": 200, "9": 150, "A": 100, "10": 100, "K": 100, "Q": 100}

_BID_NAMES = frozenset({"take", "take_suit", "pass"})
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

TEAM_OF = {0: 0, 2: 0, 1: 1, 3: 1}

# One log entry: ("play", p, card) | ("trick", winner, cards) |
# ("trump", suit) | ("decision", p, name, param)
Event = tuple[Any, ...]


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
) -> list[Card]:
    """The legal set under the Pagat obligations (belote.md, "Play") —
    written directly from the rulebook, independent of the runtime cascade."""
    if not prefix:
        return list(hand)
    led = prefix[0][1].suit
    best_trump = max(
        (_TRUMP_HEIGHT[c.rank] for _, c in prefix if c.suit == trump), default=0
    )
    higher = [c for c in hand if c.suit == trump and _TRUMP_HEIGHT[c.rank] > best_trump]
    trumps = [c for c in hand if c.suit == trump]

    if led == trump:
        # Beat the best trump if able ("whoever holds the trick"), else any
        # trump, else anything.
        return higher or trumps or list(hand)

    of_led = [c for c in hand if c.suit == led]
    if of_led:
        return of_led  # follow suit; plain suits carry no head obligation
    opp_winning = TEAM_OF[_winner(prefix, trump)] != TEAM_OF[actor]
    trick_trumped = best_trump > 0
    if opp_winning:
        if trick_trumped:
            return higher or trumps or list(hand)  # over-trump, else under-trump
        return trumps or list(hand)  # must trump if able
    if trick_trumped:
        # Partner winning with a trump: discard or over-trump, never
        # under-trump — unless under-trumps are all that is left.
        allowed = [c for c in hand if c.suit != trump] + higher
        return allowed or list(hand)
    return list(hand)


def _decompose(cards: list[Card], trump: str) -> list[tuple[int, int, bool, int]]:
    """(class, height, trump_flag, points) per combination — the canonical
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


class _Hand:
    """One dealt hand's recorded events."""

    def __init__(self) -> None:
        self.bids: list[tuple[Player, str, Any]] = []
        self.plays: list[tuple[Player, Card]] = []
        self.tricks: list[tuple[Player, list[Card]]] = []
        self.polls: list[tuple[Player, str, Any]] = []
        self.belote: list[tuple[Player, str]] = []
        self.trump: str | None = None

    @property
    def thrown(self) -> bool:
        return not self.plays


def _split_hands(log: list[Event]) -> list[_Hand]:
    hands: list[_Hand] = []
    cur: _Hand | None = None
    for e in log:
        kind = e[0]
        if kind == "decision" and e[2] in _BID_NAMES:
            if cur is None or cur.tricks or (cur.bids and cur.thrown and len(cur.bids) == 8):
                cur = _Hand()
                hands.append(cur)
            cur.bids.append((e[1], e[2], e[3]))
        else:
            assert cur is not None, f"{kind} event before any bid"
            if kind == "play":
                cur.plays.append((e[1], e[2]))
            elif kind == "trick":
                cur.tricks.append((e[1], list(e[2])))
            elif kind == "trump":
                cur.trump = e[1]
            elif kind == "decision" and e[2] in _POLL_NAMES:
                cur.polls.append((e[1], e[2], e[3]))
            elif kind == "decision" and e[2] in _BELOTE_NAMES:
                cur.belote.append((e[1], e[2]))
    return hands


def _hand_value(h: _Hand) -> tuple[dict[int, int], str]:
    """The hand's settlement per team (and its outcome branch), recomputed
    from scratch per the Pagat rules as scoped in belote.md."""
    assert h.trump is not None
    trump = h.trump
    takes = [(p, name, param) for p, name, param in h.bids if name != "pass"]
    assert len(takes) == 1, f"expected exactly one take, got {takes}"
    taker, _take_name, _take_param = takes[0]
    taking = TEAM_OF[taker]

    # The deal reconstructs from the plays; conservation over the pack.
    dealt: dict[Player, list[Card]] = {}
    for p, c in h.plays:
        dealt.setdefault(p, []).append(c)
    assert sorted(len(cs) for cs in dealt.values()) == [8, 8, 8, 8]
    pack = Counter((c.rank, c.suit) for _, c in h.plays)
    assert pack == Counter(
        {(r, s): 1 for r in _TRUMP_HEIGHT for s in SUITS}
    ), "the 32 plays are not the full pack"

    # Trick replay: winners, routing, and per-play legality.
    remaining = {p: list(cs) for p, cs in dealt.items()}
    pts = {0: 0, 1: 0}
    tricks_won = {0: 0, 1: 0}
    for t, (winner, cards) in enumerate(h.tricks):
        seat_cards = h.plays[4 * t : 4 * t + 4]
        assert [c for _, c in seat_cards] == cards
        prefix: list[tuple[Player, Card]] = []
        for p, c in seat_cards:
            assert c in _legal(prefix, remaining[p], p, trump), (
                f"trick {t}: {p} played {c} against the obligations "
                f"(prefix {prefix}, hand {remaining[p]})"
            )
            remaining[p].remove(c)
            prefix.append((p, c))
        assert _winner(seat_cards, trump) == winner, f"trick {t} winner"
        if t + 1 < 8:
            assert h.plays[4 * (t + 1)][0] == winner, "winner leads the next trick"
        pts[TEAM_OF[winner]] += sum(_points(c, trump) for c in cards)
        tricks_won[TEAM_OF[winner]] += 1
    last_team = TEAM_OF[h.tricks[-1][0]]

    # Declarations: recompute each player's best combination from the hand at
    # the poll (dealt minus the trick-1 card), check the ANNOUNCED content —
    # kind and trump status in the move name, the top card as the Rank
    # parameter — states it exactly, walk the announcements in poll order
    # (strict > keeps the earlier announcer), and apply the entitlement.
    trick1_card = {p: c for p, c in h.plays[:4]}
    assert [p for p, _, _ in h.polls] == [p for p, _ in h.plays[:4]], (
        "the poll runs in the first trick's play order"
    )
    ann_pts = {0: 0, 1: 0}
    best_key = 0
    best_team: int | None = None
    for p, name, param in h.polls:
        if name == "no_declaration":
            continue
        at_poll = [c for c in dealt[p] if c != trick1_card[p]]
        combos = _decompose(at_poll, trump)
        assert combos, f"{p} declared with no combination"
        cls, height, trumped, pts_best = max(combos)
        want_cls, want_trump = _DECLARE[name]
        heights = _CARRE_HEIGHT if want_cls == 4 else _NATURAL
        assert (cls, trumped) == (want_cls, want_trump) and heights[param] == height, (
            f"{p} announced {name}({param}) but the best combination is "
            f"(class {cls}, height {height}, trump {trumped})"
        )
        ann_pts[TEAM_OF[p]] += pts_best
        key = cls * 100 + height * 2 + (1 if trumped else 0)
        if key > best_key:
            best_key, best_team = key, TEAM_OF[p]
    meld = {0: 0, 1: 0}
    if best_team is not None and tricks_won[best_team] > 0:
        meld[best_team] = ann_pts[best_team]

    # Belote-Rebelote: at most one window; saying it banks 20 in every branch.
    assert len(h.belote) <= 1, "the Belote-Rebelote window fired twice"
    bel = {0: 0, 1: 0}
    for p, name in h.belote:
        if name == "say_belote":
            bel[TEAM_OF[p]] = 20

    total = {t: pts[t] + meld[t] + bel[t] for t in (0, 1)}
    if tricks_won[taking] == 8:
        total[taking] += 100
    else:
        total[last_team] += 10
    defending = 1 - taking
    if total[taking] >= total[defending]:
        branch = "capot" if tricks_won[taking] == 8 else "made"
        return {taking: total[taking], defending: total[defending]}, branch
    return (
        {
            taking: bel[taking],
            defending: 162 + ann_pts[0] + ann_pts[1] + bel[defending],
        },
        "dedans",
    )


def _run_and_verify(game: Any, seed: int) -> Counter[str]:
    """Play one seeded game recording plays, tricks, trump, and every
    vocabulary decision; recompute every hand from scratch and check the
    driver's final scores. Returns the per-hand outcome-branch census."""
    log: list[Event] = []

    def tracer(event: str, data: Any) -> None:
        if event == "play":
            log.append(("play", data[0], data[1]))
        elif event == "trick":
            log.append(("trick", data[0], data[1]))
        elif event == "trick_end":
            log.append(("trump", data["trump"]))

    rng = random.Random(seed)
    base = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        picked = base(player, candidates, n)
        for item in picked:
            if isinstance(item, tuple) and item and isinstance(item[0], str):
                log.append(("decision", player, item[0], item[1]))
        return picked

    result = play_game(game, rng, tracer, chooser)
    assert sum(result.scores.values()) >= 1000
    assert max(result.scores.values()) >= 1000

    branches: Counter[str] = Counter()
    totals = {0: 0, 1: 0}
    for h in _split_hands(log):
        if h.thrown:
            assert len(h.bids) == 8 and all(name == "pass" for _, name, _ in h.bids)
            branches["thrown"] += 1
            continue
        # A second-round take names a suit other than the turn-up's; the
        # turn-up suit itself is not observable from the traces, so assert
        # only the vocabulary shape.
        for _, name, param in h.bids:
            assert (param is not None) == (name == "take_suit")
        deltas, branch = _hand_value(h)
        branches[branch] += 1
        branches["declared"] += sum(1 for _, nm, _ in h.polls if nm != "no_declaration")
        branches["belote_said"] += sum(1 for _, nm in h.belote if nm == "say_belote")
        branches["named_suit"] += sum(1 for _, nm, _ in h.bids if nm == "take_suit")
        for t, d in deltas.items():
            totals[t] += d
    assert totals == result.scores, f"seed {seed}: {totals} != {result.scores}"
    assert result.winner in [
        t for t, s in result.scores.items() if s == max(result.scores.values())
    ]
    return branches


def test_20_random_games_recompute_exactly() -> None:
    game = check_source(BELOTE)
    branches: Counter[str] = Counter()
    for seed in range(20):
        branches += _run_and_verify(game, seed)
    # Both ordinary settlement branches occur; random play makes contracts
    # and goes dedans routinely. (Capot and thrown-in hands are too rare for
    # a 20-seed census and are exercised by their own arithmetic above when
    # they do occur.) The vocabulary census keeps the recompute honest: the
    # declaration, Belote-Rebelote, and name-a-suit paths were all taken, so
    # their arithmetic was actually checked, not vacuously green.
    assert branches["made"] > 0 and branches["dedans"] > 0, branches
    assert branches["declared"] > 0, branches
    assert branches["belote_said"] > 0, branches
    assert branches["named_suit"] > 0, branches


def test_seed0_characterization() -> None:
    # Byte-identity pin for one whole game: any change to the decision
    # sequence (bidding rings, the trick cascade's candidate order, the
    # declaration poll, the Belote-Rebelote window) moves this vector.
    # Measured hash-independent (identical under PYTHONHASHSEED 0-12):
    # every collection on the decision path is ordered (hand-order pools,
    # seating rings, sorted-name gathers).
    game = check_source(BELOTE)
    result = play_game(game, random.Random(0))
    assert result.scores == {0: 1106, 1: 998}
    assert result.winner == 0
