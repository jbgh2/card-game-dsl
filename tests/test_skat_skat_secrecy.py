"""The skat stays hidden until the play is over, from every seat that never picks it up.

Rules (Pagat, Skat, "The Possible Contracts"): the declarer may "pick up the
two skat cards, add them to your hand without showing them to the other
players, and discard any two cards face down"; a declarer who does not look
at the skat plays a hand game, and "in this case no one must look at the skat
cards until after the play". Pagat, "Matadors": "in a Hand game declarer does
not know what is in the skat when choosing the game".

The check is two worlds that differ only in one skat card: world B exchanges
a skat card with one card of a seat's hand at the first decision, and
replays world A's line through the first hand. At every decision of that
hand which world B still replays, the seat asked must be the same seat in
both worlds, and a seat that holds neither exchanged card and has not
picked the skat up must see the same information state — so no
announcement, state variable, exposure or order of asking tells it what
lies in the skat. The lines alternate a hand game and a skat game by seed,
so both of the source's clauses are exercised: in a hand game the declarer
is held too, in a skat game only the two defenders.

red under: `skat : FaceDownPile` written as a face-up zone type, or the
matador count (which reads the skat) written into a state variable before
the play — either reaches a defender's information state.

What a green here does not prove: nothing after the first hand's last card,
where the skat is scored and so legitimately revealed; nothing for the seat
holding the exchanged hand card (it holds a different card in each world);
nothing past the decision at which world B stops replaying (a pick of the
exchanged card), which the count of compared decisions guards against
covering nothing.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path
from typing import Any

from cardlang.openspiel.infostate import render_information_state
from cardlang.openspiel.replay import DecisionNode, HistoryMismatch, RecordedPick, load, run
from cardlang.runtime.state import RuntimeState
from cardlang.runtime.values import Card

SKAT = Path(__file__).parent.parent / "docs" / "games" / "skat.cardlang"
SEEDS = range(6)


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


def _first_hand(path: str, seed: int, hand_game: bool) -> list[int]:
    """World A's line through the first hand: every decision takes the first
    legal action, except the skat choice, which is `hand_game`'s, and the
    contract, which is never open — an exposed hand would show the exchanged
    hand card itself, which is not the skat. Returns the history up to the
    second hand's first decision, which is not taken."""
    _, space = load(path)
    skat_choice = space.encode(("declare_hand" if hand_game else "pick_up_skat", None))
    closed = {space.encode((name, None)) for name in ("declare_null_ouvert", "announce_ouvert")}
    history: list[int] = []
    node = run(path, seed, ())
    assert isinstance(node, DecisionNode)
    while node.rs.get("hands_played") == 0:
        legal = [a for a in node.legal if a not in closed]
        history.append(skat_choice if skat_choice in legal else legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode)
        node = nxt
    return history[:-1]


def test_the_skat_is_hidden_from_every_seat_that_does_not_pick_it_up() -> None:
    path = str(SKAT)
    _, space = load(path)
    pick_up = space.encode(("pick_up_skat", None))
    compared = {True: 0, False: 0}
    for seed in SEEDS:
        hand_game = seed % 2 == 0
        history = _first_hand(path, seed, hand_game)
        picks_a: list[RecordedPick] = []
        dealt: dict[str, list[Card]] = {}

        def snapshot(rs: RuntimeState) -> None:
            dealt["skat"] = list(rs.zones.singles["skat"].cards)
            for p in range(3):
                dealt[f"hand[{p}]"] = list(rs.zones.instance("hand", p).cards)

        run(path, seed, tuple(history), snapshot, picks_a)
        declarer = next((p.decider for p in picks_a if pick_up in p.legal), None)
        for holder in range(3):
            y = dealt[f"hand[{holder}]"][-1]
            picks_b: list[RecordedPick] = []
            try:
                run(path, seed, tuple(history), _exchange(dealt["skat"][0], y), picks_b)
            except HistoryMismatch:
                pass  # the line played the exchanged card: compare the prefix
            assert picks_b, f"seed {seed}: world B replays no decision at all"
            assert [p.decider for p in picks_a[: len(picks_b)]] == [p.decider for p in picks_b], (
                f"seed {seed}: who is asked depends on what lies in the skat (exchanged with seat {holder})"
            )
            for a, b in zip(picks_a, picks_b):
                if a.decider == holder or (a.decider == declarer and not hand_game):
                    continue
                assert render_information_state(a.view) == render_information_state(b.view), (
                    f"seed {seed}: seat {a.decider} sees what lies in the skat "
                    f"({'hand' if hand_game else 'skat'} game, exchanged with seat {holder})"
                )
                compared[hand_game] += 1
    assert compared[True] > 0 and compared[False] > 0, compared
