"""GOPS — OpenSpiel readiness.

Harness configuration rationale:

- `depth=12` (the default) lands the pause on P0's round-7 bid: with two
  decisions per round, an even depth keeps the 2-player swap branch's
  `p == d0` requirement (both are P0, the round's first bidder).
- `stock_zone="prize_deck"`: the un-dealt stock hidden from both players.
  A swapped-in card lands at the *end* of the pile and the swapped-out card
  was still present at the pause, so the replayed prefix's prize reveals are
  untouched.
- `swap_axis="rank"`: the deal is public knowledge (P0 holds clubs, P1
  spades, the prize pile diamonds), so a *suit*-preserving cross-zone pair
  never exists; rank-preserving pairs do. Every hidden card in GOPS is
  logically pinned by the rules (the structural-infoset-proofs caveat class:
  physically unobserved, but publicly implied — here by the fixed suit
  partition), so the swap certifies the *rendering* property: the
  information state and the offered actions derive only from projections and
  events, never from hidden zone contents.
- `conformance_steps=None`: a 13-round game is short enough for the full
  `pyspiel.random_sim_test`.
- `adapter_terminal_steps=40`: the greedy line runs exactly 26 decisions
  (both players bid their lowest card every round — every round ties and
  every prize is discarded, so the greedy terminal returns are [0, 0]).
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import Pause, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs, action_strings

PATH = str(GAMES_DIR / "gops.cardlang")


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_gops",
        "gops.cardlang",
        stock_zone="prize_deck",
        swap_axis="rank",
        adapter_terminal_steps=40,
    )


def test_sealed_bid_derivation_before_and_after_the_reveal() -> None:
    """The positive derivation shape of the sealed bid, end to end.

    (1) Sealed: P1 decides its round-1 bid knowing *nothing* of P0's committed
    card — two histories differing only in P0's hidden commit give P1
    byte-identical observation logs, information states, and legal actions
    (the commit is genuinely simultaneous even though the kernel serializes
    the two decisions). (2) The bid zone's projection: the committed card
    renders as identity to its owner and as a bare count to the opponent.
    The `each player simultaneously:` block applies both movements only after
    both players have chosen, so no *pause* has an occupied bid zone; the
    projection is asserted by placing the committed card in the zone at the
    paused world and re-rendering (the soundness-matrix technique:
    mutate -> render -> restore). (3) Public resolution: after the round, both
    reveal events sit in BOTH players' logs and both bid cards render
    publicly in the discard."""
    _, space = load(PATH)
    r0 = run(PATH, 5, ())
    assert isinstance(r0, Pause)
    assert r0.player == 0 and len(r0.legal) == 13

    # (1) Two worlds differing only in P0's sealed commit.
    a, a_alt = r0.legal[0], r0.legal[7]
    r1 = run(PATH, 5, (a,))
    r1_alt = run(PATH, 5, (a_alt,))
    assert isinstance(r1, Pause) and isinstance(r1_alt, Pause)
    assert r1.player == 1 and r1_alt.player == 1
    assert r1.obs_logs[1] == r1_alt.obs_logs[1], (
        "P0's sealed commit left a trace in P1's observation log"
    )
    assert information_state(1, r1.rs, r1.obs_logs[1]) == information_state(
        1, r1_alt.rs, r1_alt.obs_logs[1]
    ), "P1's information state depends on P0's sealed commit"
    assert r1.legal == r1_alt.legal, (
        "P1's legal actions depend on P0's sealed commit"
    )
    # ...and read the same. Backstop; the wall is `test_action_strings.py`.
    assert action_strings(space, r1.legal) == action_strings(space, r1_alt.legal), (
        "P1's rendered action text depends on P0's sealed commit"
    )

    # (2) The bid-zone projection, at the paused world. The kernel holds the
    # committed card in the chooser snapshot until both players have chosen;
    # place it in the zone to render the projection both players would get.
    card = space.decode(a)
    r1.rs.zones.instance("hand", 0).remove(card)
    r1.rs.zones.instance("bid", 0).add(card)
    p0_view = information_state(0, r1.rs, r1.obs_logs[0])
    p1_view = information_state(1, r1.rs, r1.obs_logs[1])
    assert f"bid[0]=[{card}]" in p0_view, "the owner must see their own bid card"
    assert "bid[0]=#1" in p1_view, "the opponent must see only a count"
    assert "hand[0]=#12" in p1_view, "the opponent sees the hand only as a count"

    # (3) Complete the round (P1's lowest spade ties P0's lowest club) and
    # check the public resolution.
    b = r1.legal[0]
    bid1 = space.decode(b)
    r2 = run(PATH, 5, (a, b))
    assert isinstance(r2, Pause)
    assert r2.player == 0, "round 2 must open on P0's bid"
    for q in (0, 1):
        log = r2.obs_logs[q]
        assert ("reveal", "bid[0]", str(card)) in log, f"P{q} missed the bid[0] reveal"
        assert ("reveal", "bid[1]", str(bid1)) in log, f"P{q} missed the bid[1] reveal"
        info = information_state(q, r2.rs, r2.obs_logs[q])
        discard_line = next(
            part for part in info.split("|")[1].split(";") if part.startswith("discard=")
        )
        assert str(card) in discard_line and str(bid1) in discard_line, (
            f"P{q} does not see both spent bids publicly in the discard"
        )
