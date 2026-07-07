"""Schnapsen (2 players) — OpenSpiel readiness.

Depth 6: greedy `legal[0]` always leads the lowest card id, and at seed 5
the even depths pause on player 0 — the first decider, as the harness's
2-player branch requires (p == d0). Depth 6 is three completed tricks (real
leads, follows, and talon draws happened) while the talon still holds 3
hidden cards to pair the swap against; by depth 10 it is empty.

`stock_zone="talon"`: Schnapsen empties its deck into the `talon` before the
first decision (the stock it draws from), so its hidden pool lives there —
the deck itself is empty at every pause.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run
from cardlang.runtime.values import Card

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_schnapsen",
        "schnapsen.cardlang",
        depth=6,
        stock_zone="talon",
    )


def test_lead_actions_derive_hidden_observations() -> None:
    """Schnapsen's information structure, positively confirmed (the
    Tarot/Cribbage precedent: the harness's swap-based leak-closure proof
    never confirms an event's *shape*): the talon is a count to everyone, the
    turned trump indicator identity to everyone, the free lead actions
    (exchange the trump jack, declare a marriage) public announcements whose
    card movements reveal exactly what the table sees, and a marriage never
    reveals the king.

    Seed 10, confirmed by direct probe: at the very first pause player 0 (the
    leader) may declare the hearts marriage, exchange the trump jack, or close
    the talon — one seed drives the whole scenario. The exchange does not lead
    (the ring re-offers the leader); the marriage leads its queen and ends the
    leader round.
    """
    path = str(GAMES_DIR / "schnapsen.cardlang")
    game, space = load(path)
    seed = 10

    r = run(path, seed, ())
    assert isinstance(r, Pause)
    leader, opp = r.player, 1 - r.player
    exchange_aid = space.encode(("exchange_trump_jack", None))
    marriage_aid = space.encode(("declare_marriage", "hearts"))
    assert exchange_aid in r.legal and marriage_aid in r.legal

    # The deal: each player sees their own five cards, the other's as counts,
    # and the turned trump indicator at identity (it is face up on the table).
    for p, log in r.obs_logs.items():
        own = [e for e in log if e[0] == "move" and e[3] == f"hand[{p}]"]
        assert own and all(isinstance(e[4], tuple) for e in own)
        other = [e for e in log if e[0] == "move" and e[3] == f"hand[{1 - p}]"]
        assert other and all(isinstance(e[4], int) for e in other)
        indicator = next(e for e in log if e[0] == "move" and e[3] == "trump_indicator")
        assert isinstance(indicator[4], tuple) and len(indicator[4]) == 1
        # The stock: nine cards into the talon, a count to everyone.
        talon = next(e for e in log if e[0] == "move" and e[3] == "talon")
        assert talon[4] == 9

    turned = r.rs.zones.single("trump_indicator").cards[0]

    # Exchange the trump jack — a free action: the round re-offers the leader.
    r = run(path, seed, (exchange_aid,))
    assert isinstance(r, Pause)
    assert r.player == leader, "the exchange must not end the leader's turn"
    assert exchange_aid not in r.legal, "the jack is in the indicator now"
    assert marriage_aid in r.legal, "the marriage is untouched by the exchange"
    for p, log in r.obs_logs.items():
        assert ("announce", leader, "exchange_trump_jack") in log
        # The turned card leaves the indicator at identity (everyone knows
        # which card the leader took)...
        out = next(e for e in log if e[0] == "move" and e[1] == "trump_indicator")
        assert out[2] == (str(turned),)
        # ...and the jack arrives face up at identity (the deal's turn-up is
        # also a dst=trump_indicator event, hence the src filter).
        into = next(
            e
            for e in log
            if e[0] == "move" and e[1] == f"hand[{leader}]" and e[3] == "trump_indicator"
        )
        assert isinstance(into[4], tuple) and into[4][0].startswith("J")

    # Declare the hearts marriage: a public announcement; the queen leads at
    # identity; the king is never revealed.
    r = run(path, seed, (exchange_aid, marriage_aid))
    assert isinstance(r, Pause)
    assert r.player == opp, "the marriage leads its queen, ending the leader round"

    for p, log in r.obs_logs.items():
        assert ("announce", leader, "declare_marriage(hearts)") in log
        queen = next(e for e in log if e[0] == "move" and e[3] == "trick_pile")
        assert queen[4] == (str(Card("Q", "hearts")),)
    assert not any(
        str(Card("K", "hearts")) in str(e) for e in r.obs_logs[opp]
    ), "the marriage revealed the king; only the suit is public"

    # The follower answers (greedy lowest card id), the trick resolves, and
    # the winner and loser each draw from the talon: a count to the other
    # player, identity to the drawer.
    r2 = run(path, seed, (exchange_aid, marriage_aid, r.legal[0]))
    assert isinstance(r2, Pause)
    for drawer in (0, 1):
        other_log = r2.obs_logs[1 - drawer]
        draw_seen = next(
            e
            for e in other_log
            if e[0] == "move" and e[1] == "talon" and e[3] == f"hand[{drawer}]"
        )
        assert draw_seen[2] == 1 and draw_seen[4] == 1, (
            f"P{1 - drawer} saw more than a count of P{drawer}'s talon draw"
        )
        own_draw = next(
            e
            for e in r2.obs_logs[drawer]
            if e[0] == "move" and e[1] == "talon" and e[3] == f"hand[{drawer}]"
        )
        assert isinstance(own_draw[4], tuple) and len(own_draw[4]) == 1

    # Belt-and-braces: the opponent's rendered info state shows the leader's
    # hand and the talon as bare counts, never identity.
    info_opp = information_state(opp, r2.rs, r2.obs_logs[opp])
    n_leader = len(r2.rs.zones.instance("hand", leader).cards)
    n_talon = len(r2.rs.zones.single("talon").cards)
    assert f"hand[{leader}]=#{n_leader}" in info_opp
    assert f"talon=#{n_talon}" in info_opp
