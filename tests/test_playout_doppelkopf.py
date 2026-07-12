"""Random-playout harness for Doppelkopf.

Doppelkopf's falsifiable surface is unusually rich because the whole hand is
recomputable from the play traces plus the announcement decisions: the deal
partitions the double pack (hands reconstruct from what each player played),
follow legality and the trick winner are pure functions of the fixed normal-
game trump structure, the ♣Q partition derives from who played the queens,
and the hand value is a closed formula over card points, tricks, extras
(Fox / Charlie / Doppelkopf) and the announcement ladder. This test replays
every seed and recomputes ALL of it independently — an implementation of the
Pagat rules written against the trace log, not the runtime — and asserts the
driver's final scores match the recomputed per-hand settlements exactly.
"""

from __future__ import annotations

import json
import os
import random
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any

from cardlang.pipeline import check_source
from cardlang.runtime.chooser import random_chooser
from cardlang.runtime.driver import play_game
from cardlang.runtime.values import Card, Player

DOKO = Path(__file__).parent.parent / "docs" / "games" / "doppelkopf.cardlang"
GOLDEN = Path(__file__).parent / "golden" / "doppelkopf_scores.json"
REPO = Path(__file__).parent.parent

HANDS = 4
TRICKS_PER_HAND = 12

_VALUES = {"A": 11, "10": 10, "K": 4, "Q": 3, "J": 2, "9": 0}
_SUIT_ORDER = {"clubs": 4, "spades": 3, "hearts": 2, "diamonds": 1}
_PLAIN_RANK = {"A": 4, "10": 3, "K": 2, "9": 1}
_ANNOUNCE_NAMES = frozenset(
    {
        "announce_re",
        "announce_kontra",
        "announce_re_no90",
        "announce_re_no60",
        "announce_re_no30",
        "announce_re_schwarz",
        "announce_kontra_no90",
        "announce_kontra_no60",
        "announce_kontra_no30",
        "announce_kontra_schwarz",
    }
)


def _is_trump(c: Card) -> bool:
    if c.suit == "hearts" and c.rank == "10":
        return True
    return c.rank in ("Q", "J") or c.suit == "diamonds"


def _strength(c: Card) -> int:
    """Trick strength: trumps above every plain card; plain cards rank within
    their suit only (cross-suit comparison never decides a trick)."""
    if c.suit == "hearts" and c.rank == "10":
        return 1300
    if c.rank == "Q":
        return 1200 + _SUIT_ORDER[c.suit]
    if c.rank == "J":
        return 1100 + _SUIT_ORDER[c.suit]
    if c.suit == "diamonds":
        return 1000 + _PLAIN_RANK[c.rank]
    return _PLAIN_RANK[c.rank]


def _trick_winner(played: list[tuple[Player, Card]]) -> Player:
    """First-of-equals: strictly-greater comparison in play order, counting
    only trumps or led-suit plain cards."""
    led = played[0][1]
    led_trump = _is_trump(led)
    best_p, best_c = played[0]
    for p, c in played[1:]:
        if _is_trump(c):
            if not _is_trump(best_c) or _strength(c) > _strength(best_c):
                best_p, best_c = p, c
        elif not _is_trump(best_c) and not led_trump and c.suit == led.suit:
            if _strength(c) > _strength(best_c):
                best_p, best_c = p, c
    return best_p


def _full_pack() -> Counter[tuple[str, str]]:
    return Counter(
        {(r, s): 2 for r in _VALUES for s in ("clubs", "spades", "hearts", "diamonds")}
    )


def _hand_value(
    tricks: list[tuple[Player, list[Card]]],
    plays: list[tuple[Player, Card]],
    announcements: list[str],
) -> tuple[dict[Player, int], str]:
    """The hand's settlement (and its outcome branch), recomputed from
    scratch per the Pagat base text."""
    players = sorted({p for p, _ in plays})
    re_team = {p for p, c in plays if c.rank == "Q" and c.suit == "clubs"}
    assert 1 <= len(re_team) <= 2
    is_re = {p: p in re_team for p in players}

    pts = {True: 0, False: 0}
    trick_count = {True: 0, False: 0}
    extras = {True: 0, False: 0}
    for i, (winner, cards) in enumerate(tricks):
        seat_cards = plays[4 * i : 4 * i + 4]
        pts[is_re[winner]] += sum(_VALUES[c.rank] for c in cards)
        trick_count[is_re[winner]] += 1
        if all(c.rank in ("A", "10") for c in cards):
            extras[is_re[winner]] += 1
        for p, c in seat_cards:
            if c.rank == "A" and c.suit == "diamonds" and is_re[winner] != is_re[p]:
                extras[is_re[winner]] += 1
            if i == TRICKS_PER_HAND - 1 and c.rank == "J" and c.suit == "clubs":
                if p == winner:
                    extras[is_re[p]] += 1
                elif is_re[p] != is_re[winner]:
                    extras[is_re[winner]] += 1
    assert pts[True] + pts[False] == 240

    re_said = "announce_re" in announcements
    kontra_said = "announce_kontra" in announcements
    re_level = sum(1 for a in announcements if a.startswith("announce_re_"))
    kontra_level = sum(1 for a in announcements if a.startswith("announce_kontra_"))

    re_base = 120 if (kontra_said and not re_said) else 121
    kontra_base = 121 if (kontra_said and not re_said) else 120
    level_target = {1: 151, 2: 181, 3: 211}

    def ann_ok(level: int, own_pts: int, opp_tricks: int) -> bool:
        if level == 0:
            return True
        if level == 4:
            return opp_tricks == 0
        return own_pts >= level_target[level]

    re_ann_ok = ann_ok(re_level, pts[True], trick_count[False])
    kontra_ann_ok = ann_ok(kontra_level, pts[False], trick_count[True])
    re_wins = re_ann_ok and (pts[True] >= re_base if kontra_ann_ok else True)
    kontra_wins = kontra_ann_ok and (pts[False] >= kontra_base if re_ann_ok else True)
    assert not (re_wins and kontra_wins)

    if re_wins or kontra_wins:
        l_pts = pts[False] if re_wins else pts[True]
        l_tricks = trick_count[False] if re_wins else trick_count[True]
        w_level = re_level if re_wins else kontra_level
        l_level = kontra_level if re_wins else re_level
        v = (
            1
            + (1 if kontra_wins else 0)
            + (2 if re_said else 0)
            + (2 if kontra_said else 0)
            + sum(1 for t in (90, 60, 30) if l_pts < t)
            + (1 if l_tricks == 0 else 0)
            + w_level
            + 2 * l_level
        )
        d = v if re_wins else -v
    else:
        # Both-failed settlement. The schwarz terms are defined for totality
        # but unreachable here: a side taking zero tricks means the other
        # achieved every level it announced, which makes it the winner, not
        # a no_winner participant.
        d = (
            sum(1 for t in (90, 60, 30) if pts[False] < t)
            + (1 if trick_count[False] == 0 else 0)
            + 2 * kontra_level
            - sum(1 for t in (90, 60, 30) if pts[True] < t)
            - (1 if trick_count[True] == 0 else 0)
            - 2 * re_level
        )
    d += extras[True] - extras[False]

    branch = "re_wins" if re_wins else ("kontra_wins" if kontra_wins else "no_winner")
    mult = 3 if len(re_team) == 1 else 1
    return {p: (d * mult if is_re[p] else -d) for p in players}, branch


def _run_and_verify(
    game: Any, seed: int, drop: frozenset[str] = frozenset()
) -> Counter[str]:
    """Play one seeded game (suppressing the announcement moves named in
    `drop`, the announcement-policy axis) and verify every recomputable fact.
    Returns the per-hand outcome-branch census for coverage assertions."""
    plays: list[tuple[Player, Card]] = []
    tricks: list[tuple[Player, list[Card]]] = []
    announcements: list[tuple[int, str]] = []
    branches: Counter[str] = Counter()

    def tracer(event: str, data: Any) -> None:
        if event == "play":
            plays.append((data[0], data[1]))
        elif event == "trick":
            tricks.append((data[0], list(data[1])))

    rng = random.Random(seed)
    base = random_chooser(rng)

    def chooser(player: Player, candidates: list[Any], n: int) -> list[Any]:
        live = [
            c
            for c in candidates
            if not (isinstance(c, tuple) and c and c[0] in drop)
        ] or candidates
        picked = base(player, live, n)
        for item in picked:
            if isinstance(item, tuple) and item and item[0] in _ANNOUNCE_NAMES:
                announcements.append((len(tricks), str(item[0])))
        return picked

    result = play_game(game, rng, tracer, chooser)

    assert len(tricks) == HANDS * TRICKS_PER_HAND, f"seed {seed}"
    assert len(plays) == 4 * len(tricks), f"seed {seed}"
    assert sum(result.scores.values()) == 0, f"seed {seed}: {result.scores}"

    totals: dict[Player, int] = {p: 0 for p in result.scores}
    first_leader = plays[0][0]
    for h in range(HANDS):
        h_plays = plays[48 * h : 48 * (h + 1)]
        h_tricks = tricks[12 * h : 12 * (h + 1)]

        # The deal reconstructs from the plays: 12 cards each, and the
        # union is exactly the double pack (conservation).
        dealt: dict[Player, list[Card]] = {}
        for p, c in h_plays:
            dealt.setdefault(p, []).append(c)
        assert all(len(cs) == 12 for cs in dealt.values()), f"seed {seed} hand {h}"
        pack = Counter((c.rank, c.suit) for _, c in h_plays)
        assert pack == _full_pack(), f"seed {seed} hand {h}"

        # Dealer rotation: each hand's opening leader advances one seat in
        # a constant direction (the numeric sign of "left" is the
        # runtime's, so only consistency is asserted).
        if h >= 1:
            rotation = (plays[48][0] - first_leader) % 4
            assert rotation in (1, 3), f"seed {seed}: rotation {rotation}"
            assert h_plays[0][0] == (first_leader + rotation * h) % 4, (
                f"seed {seed} hand {h}"
            )

        remaining = {p: Counter((c.rank, c.suit) for c in cs) for p, cs in dealt.items()}
        for t, (winner, cards) in enumerate(h_tricks):
            seat_cards = h_plays[4 * t : 4 * t + 4]
            assert [c for _, c in seat_cards] == cards, f"seed {seed} hand {h} trick {t}"
            # Routing: the winner leads the next trick.
            if t + 1 < TRICKS_PER_HAND:
                assert h_plays[4 * (t + 1)][0] == winner, f"seed {seed} hand {h} trick {t}"
            # The winner recomputes (first-of-equals over the trump class).
            assert _trick_winner(seat_cards) == winner, f"seed {seed} hand {h} trick {t}"
            # Follow legality: a holder of the led class must play in it.
            led = seat_cards[0][1]
            led_trump = _is_trump(led)
            for idx, (p, c) in enumerate(seat_cards):
                if idx > 0:
                    holds_class = any(
                        k > 0
                        and _is_trump(Card(r, s)) == led_trump
                        and (led_trump or s == led.suit)
                        for (r, s), k in remaining[p].items()
                    )
                    followed = (
                        _is_trump(c)
                        if led_trump
                        else (not _is_trump(c) and c.suit == led.suit)
                    )
                    if holds_class:
                        assert followed, (
                            f"seed {seed} hand {h} trick {t}: {p} broke follow"
                        )
                remaining[p][(c.rank, c.suit)] -= 1
                assert remaining[p][(c.rank, c.suit)] >= 0, (
                    f"seed {seed} hand {h} trick {t}"
                )

        h_ann = [a for hh, a in announcements if hh // TRICKS_PER_HAND == h]
        deltas, branch = _hand_value(h_tricks, h_plays, h_ann)
        branches[branch] += 1
        for p, delta in deltas.items():
            totals[p] += delta

    assert totals == result.scores, f"seed {seed}: {totals} != {result.scores}"
    assert result.winner in [
        p for p, s in result.scores.items() if s == max(result.scores.values())
    ], f"seed {seed}"
    return branches


_LADDER = frozenset(a for a in _ANNOUNCE_NAMES if "_no" in a or a.endswith("schwarz"))


def test_20_random_games_recompute_exactly() -> None:
    """Unrestricted random play. Random announcing cascades both ladders in
    nearly every hand, so this run exercises the no-winner settlement (both
    sides failing their announcements) — the branch real play rarely sees."""
    game = check_source(DOKO)
    branches: Counter[str] = Counter()
    for seed in range(20):
        branches += _run_and_verify(game, seed)
    assert branches["no_winner"] > 0, branches


def test_15_games_without_announcements_have_a_winner_every_hand() -> None:
    """Announcements suppressed: every hand settles by the plain base targets
    (Re 121 / Kontra 120), so both ordinary winner branches are exercised."""
    game = check_source(DOKO)
    branches: Counter[str] = Counter()
    for seed in range(15):
        branches += _run_and_verify(game, seed, drop=_ANNOUNCE_NAMES)
    assert branches["re_wins"] > 0 and branches["kontra_wins"] > 0, branches
    assert branches["no_winner"] == 0, branches


# Exact-score golden: rules.legal_cards iterates a set, so chooser candidate
# order — and therefore per-seed results — is hash-dependent; the capture
# runs in a PYTHONHASHSEED=0 subprocess (the repo's exact-score convention).
_CAPTURE = """
import json, random
from pathlib import Path
from cardlang.pipeline import check_source
from cardlang.runtime.driver import play_game

game = check_source(Path("docs/games/doppelkopf.cardlang"))
out = {}
for seed in range(40):
    r = play_game(game, random.Random(seed))
    out[str(seed)] = {
        "scores": {str(p): s for p, s in sorted(r.scores.items())},
        "winner": r.winner,
    }
print(json.dumps(out))
"""


def test_per_seed_scores_match_golden() -> None:
    env = dict(os.environ, PYTHONHASHSEED="0")
    proc = subprocess.run(
        [sys.executable, "-c", _CAPTURE],
        cwd=REPO,
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    captured = json.loads(proc.stdout)
    expected = json.loads(GOLDEN.read_text())
    assert captured == expected


def test_15_games_where_only_re_announces() -> None:
    """Kontra's announcements suppressed: the Re side ladders and usually
    fails, so the failed-announcement transfer (Kontra winning below 120,
    collecting the level and announced points) is exercised."""
    game = check_source(DOKO)
    branches: Counter[str] = Counter()
    for seed in range(15):
        branches += _run_and_verify(
            game,
            seed,
            drop=frozenset({a for a in _ANNOUNCE_NAMES if "kontra" in a}),
        )
    assert branches["kontra_wins"] > 0, branches
