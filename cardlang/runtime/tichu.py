"""The Tichu hand mechanic (four-player partnership climbing game; concrete).

The corpus's first climbing game and first with non-(rank,suit) cards. Built as
one concrete mechanic: the pushing phase, the climbing trick (play a combination
that matches the led type/length and beats it, or a bomb, or pass; three passes
end the trick), the four special cards (Mahjong leads and is lowest; the Dog
hands the lead to partner; the Phoenix is a wild / contextual single worth -25;
the Dragon is the highest single, worth 25, and its trick goes to an opponent),
finishing order with the double-victory shortcut, and card-point + Tichu-call
scoring. First partnership to 1000 wins.

Card points total 100 every hand (K and 10 score 10, 5 scores 5, Dragon +25,
Phoenix -25) — the falsifiable conservation invariant.

Scope reductions (random play; logged in IMPLEMENTATION_LOG.md): the Mahjong
wish, the Phoenix as a wildcard inside straights / consecutive-pairs,
straight-flush bombs, and out-of-turn bombs are omitted. Tichu / Grand Tichu are
called at a low random rate so card points (always +100/hand) drive the game to
1000.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cardlang.ast import nodes as n
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx
from cardlang.runtime.values import Card, Player

_RANKVAL = {"2": 2, "3": 3, "4": 4, "5": 5, "6": 6, "7": 7, "8": 8, "9": 9,
            "10": 10, "J": 11, "Q": 12, "K": 13, "A": 14, "Mahjong": 1, "Dragon": 15}


def _rv(c: Card) -> float | None:
    return _RANKVAL.get(c.rank)  # None for Phoenix / Dog


def _points(c: Card) -> int:
    if c.rank == "Dragon":
        return 25
    if c.rank == "Phoenix":
        return -25
    if c.rank in ("K", "10"):
        return 10
    if c.rank == "5":
        return 5
    return 0


@dataclass(frozen=True)
class Play:
    kind: str       # single|pair|triple|fullhouse|straight|pairseq|bomb|dog
    length: int
    key: float      # comparison key within (kind, length); bombs compare across
    cards: tuple[Card, ...]

    @property
    def is_bomb(self) -> bool:
        return self.kind == "bomb"


def _combos(hand: list[Card]) -> list[Play]:
    """Combinations a hand can form. Phoenix is used as a wildcard in pairs,
    triples, and full houses (not straights/pairseqs/bombs); plain singles cover
    every card. Straight-flush bombs are omitted (four-of-a-kind bombs only)."""
    out: list[Play] = []
    phoenix = next((c for c in hand if c.rank == "Phoenix"), None)
    normal = [c for c in hand if c.rank not in ("Dog", "Dragon", "Phoenix")]

    for c in hand:  # singles (Dog handled as a lead only, Phoenix/Dragon added at call sites)
        if c.rank != "Dog":
            v = _rv(c)
            if v is not None:
                out.append(Play("single", 1, v, (c,)))

    by_rank: dict[float, list[Card]] = {}
    for c in normal:
        by_rank.setdefault(_rv(c), []).append(c)  # type: ignore[arg-type]

    for r, cs in by_rank.items():
        if len(cs) >= 2:
            out.append(Play("pair", 2, r, tuple(cs[:2])))
        if len(cs) >= 3:
            out.append(Play("triple", 3, r, tuple(cs[:3])))
        if len(cs) >= 4:
            out.append(Play("bomb", 4, r, tuple(cs[:4])))
        if phoenix is not None:
            if len(cs) >= 1:
                out.append(Play("pair", 2, r, (cs[0], phoenix)))
            if len(cs) >= 2:
                out.append(Play("triple", 3, r, (cs[0], cs[1], phoenix)))

    # full houses: a triple rank + a different pair rank (Phoenix can fill either)
    triples = [r for r, cs in by_rank.items() if len(cs) >= 3]
    pairs = [r for r, cs in by_rank.items() if len(cs) >= 2]
    for tr in triples:
        for pr in pairs:
            if pr != tr:
                cards = tuple(by_rank[tr][:3] + by_rank[pr][:2])
                out.append(Play("fullhouse", 5, tr, cards))
    if phoenix is not None:  # Phoenix completes a pair atop a natural triple
        for tr in triples:
            for pr, cs in by_rank.items():
                if pr != tr and len(cs) >= 1:
                    cards = tuple(by_rank[tr][:3] + [cs[0], phoenix])
                    out.append(Play("fullhouse", 5, tr, cards))

    # straights (>= 5 consecutive ranks, one card each)
    ranks_present = sorted(by_rank)
    for i in range(len(ranks_present)):
        run = [ranks_present[i]]
        while run[-1] + 1 in by_rank:
            run.append(run[-1] + 1)
        if len(run) >= 5:
            for length in range(5, len(run) + 1):
                for s in range(0, len(run) - length + 1):
                    seg = run[s:s + length]
                    cards = tuple(by_rank[r][0] for r in seg)
                    out.append(Play("straight", length, seg[-1], cards))

    # consecutive pairs (>= 2 consecutive ranks each with a pair)
    pair_ranks = sorted(r for r, cs in by_rank.items() if len(cs) >= 2)
    for i in range(len(pair_ranks)):
        run = [pair_ranks[i]]
        while run[-1] + 1 in by_rank and len(by_rank[run[-1] + 1]) >= 2:
            run.append(run[-1] + 1)
        if len(run) >= 2:
            for length in range(2, len(run) + 1):
                for s in range(0, len(run) - length + 1):
                    seg = run[s:s + length]
                    cards = tuple(c for r in seg for c in by_rank[r][:2])
                    out.append(Play("pairseq", length, seg[-1], cards))
    return out


def _legal_follows(hand: list[Card], current: Play) -> list[Play]:
    if current.kind == "dog":
        return []
    phoenix = next((c for c in hand if c.rank == "Phoenix"), None)
    dragon = next((c for c in hand if c.rank == "Dragon"), None)
    follows: list[Play] = []
    for p in _combos(hand):
        if p.is_bomb:
            follows.append(p)  # a bomb beats any non-bomb
        elif p.kind == current.kind and p.length == current.length and p.key > current.key:
            follows.append(p)
    if current.kind == "single":
        if dragon is not None:
            follows.append(Play("single", 1, 15, (dragon,)))
        if phoenix is not None and current.key < 15:  # Phoenix can't top the Dragon
            follows.append(Play("single", 1, current.key + 0.5, (phoenix,)))
    return follows


def run_tichu_hand(stmt: n.Instantiate, ctx: Ctx) -> Player:
    rs = ctx.rs
    rng = rs.rng
    choose = ctx.chooser
    args = {a.name: a.value for a in stmt.args}
    starting: Player = evaluate(args["starting"], ctx)  # type: ignore[arg-type]
    players = list(rs.seating.players)
    npl = len(players)
    hands = rs.zones.families["hand"]
    captured = rs.zones.families["captured"]
    discard = rs.zones.single("discard")
    team_of = rs.team_of

    def ccw(p: Player) -> Player:
        return (p - 1) % npl

    def partner(p: Player) -> Player:
        return next(q for q in players if q != p and team_of[q] == team_of[p])

    # Tichu / Grand Tichu calls (low random rate so card points drive the game).
    called = {p: 0 for p in players}  # 0 none, 100 tichu, 200 grand
    for p in players:
        if rng.random() < 0.04:
            called[p] = 200
        elif rng.random() < 0.08:
            called[p] = 100

    # Pushing: each player gives one card to each other player (simultaneously).
    gifts: dict[Player, list[Card]] = {p: [] for p in players}
    for p in players:
        picks = choose(p, list(hands[p].cards), npl - 1)
        for c in picks:
            hands[p].remove(c)
        recipients = [q for q in players if q != p]
        for q, c in zip(recipients, picks):
            gifts[q].append(c)
    for q in players:
        hands[q].add_all(gifts[q])

    # Mahjong holder leads the first trick.
    leader = next((p for p in players if any(c.rank == "Mahjong" for c in hands[p].cards)), starting)
    out_order: list[Player] = []

    def record_out(p: Player) -> None:
        if not hands[p].cards and p not in out_order:
            out_order.append(p)

    def still_in() -> list[Player]:
        return [p for p in players if hands[p].cards]

    guard = 0
    while len(still_in()) > 1:
        guard += 1
        if guard > 5000:
            raise RuntimeError(
                "tichu hand exceeded 5000 tricks without resolving (non-termination?)"
            )
        if len(out_order) >= 2 and team_of[out_order[0]] == team_of[out_order[1]]:
            break  # double victory — stop early
        leader = _play_trick(  # type: ignore[no-untyped-call]
            leader, hands, captured, discard, players, ccw, partner,
            team_of, choose, rng, called, record_out, still_in,
        )
        if leader is None:  # everyone out
            break
        while hands[leader].cards == [] and still_in():
            leader = ccw(leader)

    double_victory = _score_hand(
        rs, hands, captured, players, team_of, out_order, called, partner
    )
    card_pts = sum(_points(c) for t in rs.teams for c in captured[t].cards)
    ctx.trace("tichu_hand", {"double_victory": double_victory, "card_points": card_pts})
    return out_order[0] if out_order else leader if leader is not None else starting


def _play_trick(  # type: ignore[no-untyped-def]
    leader, hands, captured, discard, players, ccw, partner,
    team_of, choose, rng, called, record_out, still_in,
):
    """Play one climbing trick; route its cards; return the next leader (or None
    if everyone is out)."""
    current: Play | None = None
    last_player: Player | None = None
    pending: set[Player] = set()
    pile: list[Card] = []
    dragon_won = False
    turn = leader
    guard = 0
    while True:
        guard += 1
        if guard > 5000:
            raise RuntimeError(
                "tichu trick exceeded 5000 plays without resolving (non-termination?)"
            )
        if current is not None and not pending:
            break  # everyone else passed — trick over
        if not hands[turn].cards or (current is not None and turn not in pending):
            turn = ccw(turn)
            continue
        if current is None:  # the leader must lead
            leads = _combos(hands[turn].cards)
            for c in hands[turn].cards:  # Dragon / Phoenix / Dog as a lead single
                if c.rank == "Dragon":
                    leads.append(Play("single", 1, 15, (c,)))
                elif c.rank == "Phoenix":
                    leads.append(Play("single", 1, 1.5, (c,)))
                elif c.rank == "Dog":
                    leads.append(Play("dog", 1, 0, (c,)))
            play = choose(turn, leads, 1)[0]
            for c in play.cards:
                hands[turn].remove(c)
            if play.kind == "dog":  # lead passes to partner, no capture
                discard.add_all(play.cards)
                return partner(turn)
            pile.extend(play.cards)
            current, last_player = play, turn
            pending = {p for p in players if p != turn and hands[p].cards}
            record_out(turn)
            turn = ccw(turn)
        else:  # follow or pass
            opts: list[Any] = [*_legal_follows(hands[turn].cards, current), "pass"]
            choice = choose(turn, opts, 1)[0]
            if choice == "pass":
                pending.discard(turn)
                turn = ccw(turn)
            else:
                for c in choice.cards:
                    hands[turn].remove(c)
                pile.extend(choice.cards)
                current, last_player = choice, turn
                pending = {p for p in players if p != turn and hands[p].cards}
                record_out(turn)
                turn = ccw(turn)

    assert last_player is not None
    dragon_won = current is not None and len(current.cards) == 1 and current.cards[0].rank == "Dragon"
    if dragon_won:  # the Dragon's trick is given to an opponent
        opponents = [p for p in players if team_of[p] != team_of[last_player]]
        recipient = rng.choice(opponents)
        captured[team_of[recipient]].add_all(pile)
    else:
        captured[team_of[last_player]].add_all(pile)

    if hands[last_player].cards:
        return last_player
    nxt = ccw(last_player)
    while not hands[nxt].cards and still_in():
        nxt = ccw(nxt)
    return nxt if still_in() else None


def _score_hand(rs, hands, captured, players, team_of, out_order, called, partner) -> bool:  # type: ignore[no-untyped-def]
    score = rs.get("score")
    teams = rs.teams
    delta = {t: 0 for t in teams}

    double_victory = (
        len(out_order) >= 2 and team_of[out_order[0]] == team_of[out_order[1]]
    )
    if double_victory:
        delta[team_of[out_order[0]]] += 200
    else:
        # The lone remaining player: their hand → the opponents, their captured
        # tricks → the first player out.
        remaining = [p for p in players if hands[p].cards]
        first_out = out_order[0] if out_order else players[0]
        if remaining:
            last = remaining[0]
            opp_team = next(t for t in teams if t != team_of[last])
            captured[opp_team].add_all(hands[last].take_all())
            captured[team_of[first_out]].add_all(captured[team_of[last]].take_all())
        for t in teams:
            delta[t] += sum(_points(c) for c in captured[t].cards)

    for p in players:  # Tichu / Grand Tichu calls
        if called[p]:
            if out_order and p == out_order[0]:
                delta[team_of[p]] += called[p]
            else:
                delta[team_of[p]] -= called[p]

    for t in teams:
        score[t] += delta[t]
    return double_victory
