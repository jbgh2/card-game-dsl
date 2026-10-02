"""Who leads stays hidden through the post-push small tichu window.

Rules (Fata Morgana FAQ, on small tichu): "Dann wird geschupft. Wiederum
dürfen alle über eine Tichuansage (nach dem Schupfen) nachdenken. (Aber ohne
Information über das Ausspiel) / Dann wird ausgespielt. Wiederum kann man
Tichu ansagen. (Im Wissen um Anspiel und allfälligem Wunsch.)" — after the
push every player may consider a call without information about the lead;
the next window comes once the lead and any wish are known.

The check is two worlds that differ only in where the Mahjong lies: world B
exchanges the Mahjong with one card of another hand before any of it is
dealt, and replays world A's line. At every small tichu decision between the
push and the first lead, a seat holding neither exchanged card must be the
same seat in both worlds and must see the same information state — so no
announcement, state variable or order of asking tells it who holds the
Mahjong.

red under: write tichu.cardlang's `leader := player_holding(...)` before the
post-push poll, or let the Hosted Poll run before the hand's first lead —
the leader then reaches the deciding seat's view or the order of asking.

What a green here does not prove: nothing about decisions after the first
lead, where who led is public; nothing for a seat that pushed or received
either exchanged card (such a line drops the pair, and the count of compared
decisions guards against every pair dropping).
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from cardlang.openspiel.infostate import render_information_state
from cardlang.openspiel.replay import DecisionNode, HistoryMismatch, RecordedPick, load, run
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card

TICHU = Path(__file__).parent.parent / "docs" / "games" / "tichu.cardlang"
SEEDS = range(6)
MAHJONG = Card("Mahjong", "special")


def _ids(space: Any, *names: str) -> set[int]:
    out = set()
    for name in names:
        try:
            out.add(space.encode(name))
        except (KeyError, ValueError):
            out.add(space.encode((name, None)))
    return out


def _walk_to_first_lead(path: str, seed: int, declines: set[int]) -> tuple[list[int], int, DecisionNode]:
    """Decline every call window and push the first legal card; return the
    history to the first climbing lead, the history length at which the push
    completes, and the lead's decision node."""
    history: list[int] = []
    pushed = 0
    push_done_at = -1
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    while True:
        quiet = [a for a in r.legal if a in declines]
        if quiet:
            history.append(quiet[0])
        elif pushed < 12:
            history.append(r.legal[0])
            pushed += 1
            if pushed == 12:
                push_done_at = len(history)
        else:
            return history, push_done_at, r
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode)
        r = nxt


def _exchange(x: Card, y: Card) -> Any:
    """Exchange two cards wherever they lie at the first decision, each taking
    the other's position and arrival record."""

    def swap(rs: RuntimeState) -> None:
        zones = [*rs.zones.singles.values(), *(z for f in rs.zones.families.values() for z in f.values())]
        zx = next(z for z in zones if x in z.cards)
        zy = next(z for z in zones if y in z.cards)
        ix, iy = zx.cards.index(x), zy.cards.index(y)
        zx.cards[ix], zy.cards[iy] = y, x
        for zone, before, after in ((zx, x, y), (zy, y, x)):
            i = next(k for k, a in enumerate(zone.arrivals) if a.card == before)
            zone.arrivals[i] = dataclasses.replace(zone.arrivals[i], card=after)

    return swap


def test_the_post_push_window_does_not_reveal_who_leads() -> None:
    path = str(TICHU)
    _, space = load(path)
    declines = _ids(space, "decline_grand", "no_call")
    small = _ids(space, "call_tichu", "no_call")
    compared = 0
    for seed in SEEDS:
        history, push_done_at, lead = _walk_to_first_lead(path, seed, declines)
        holder = lead.player
        picks_a: list[RecordedPick] = []
        run(path, seed, tuple(history), None, picks_a)
        window = [p for p in picks_a[push_done_at:] if set(p.legal) <= small]
        for other in (q for q in range(4) if q != holder):
            for x in list(lead.rs.zones.instance("hand", other).cards):
                picks_b: list[RecordedPick] = []
                try:
                    run(path, seed, tuple(history), _exchange(MAHJONG, x), picks_b)
                except HistoryMismatch:
                    continue  # a pushed card moved: the line does not replay
                window_b = [p for p in picks_b[push_done_at:] if set(p.legal) <= small]
                assert [p.decider for p in window] == [p.decider for p in window_b], (
                    f"seed {seed}: the post-push small tichu window asks in an order "
                    f"that depends on who holds the Mahjong ({holder} vs {other})"
                )
                for a, b in zip(window, window_b):
                    if a.decider in (holder, other):
                        continue
                    assert render_information_state(a.view) == render_information_state(b.view), (
                        f"seed {seed}: seat {a.decider} sees who holds the Mahjong "
                        f"before the first lead ({holder} vs {other})"
                    )
                    compared += 1
                break
    assert compared > 0
