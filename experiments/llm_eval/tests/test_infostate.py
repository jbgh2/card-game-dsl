"""The information-state parser and the provable-lie criterion.

`infostate.py` is a string parser held deliberately free of engine imports, so
the two facts it hard-codes — the rank list and four-copies-per-rank — are
reconciled against the engine here. A silent divergence would not raise; it
would mis-parse, and every metric downstream would read a plausible wrong
number.
"""

from __future__ import annotations

import pytest

from .. import infostate as istate

REAL = (
    "P1|deck=#0;flipped=[];pile=#0;played=#1;hand[0]=#12;"
    "hand[1]=[10♥,10♦,2♥,3♦,4♣,4♥,6♣,6♦,7♥,8♥,8♦,9♦,A♣];hand[2]=#13;hand[3]=#13"
    "|state:challenged=False;challenger=None;claim_count=1;claim_rank=A;claimant=0;"
    "responder=1;window_open=True;won={0:False,1:False,2:False,3:False}"
    "|obs:('announce', 0, 'play_one');('move', 'hand[0]', 1, 'played', 1)"
)


def test_rank_membership_matches_the_engine() -> None:
    """The hard-coded rank SET is the engine's. Reconciled, not assumed.

    Order is deliberately different — this module carries Cheat's claim cycle
    (aces first), while `values.RANKS` is aces-high. `test_game.py` pins the
    order against a live game's cycle; membership is what parsing needs.
    """
    from cardlang.runtime.values import RANKS as ENGINE_RANKS

    assert set(istate.RANKS) == set(ENGINE_RANKS)
    assert len(istate.RANKS) == len(ENGINE_RANKS) == 13


def test_copies_per_rank_matches_the_deck() -> None:
    """Four of each rank in standard52 — the arithmetic `provably_false` rests
    on. A deck change would make the criterion unsound rather than merely
    imprecise."""
    from cardlang.runtime.values import build_deck

    deck = list(build_deck("standard52"))
    counts: dict[str, int] = {}
    for card in deck:
        counts[card.rank] = counts.get(card.rank, 0) + 1
    assert set(counts.values()) == {istate.COPIES_PER_RANK}
    # No duplicate physical cards. This is what makes counting DISTINCT cards
    # (which the widened criterion must, to union its own hand with the flip
    # evidence soundly) equal to counting occurrences (which the narrow one
    # does) on every reachable hand. A deck with `copies > 1` — pinochle48 —
    # would break that equality, and Cheat is standard52 by declaration.
    assert len(set(deck)) == len(deck) == 52


def test_parses_a_real_information_state() -> None:
    info = istate.parse(REAL)
    assert info.player == 1
    assert info.zones["hand[0]"] == 12
    assert info.zones["flipped"] == []
    assert info.hand_size(1) == 13
    assert info.claim_rank == "A"
    assert info.claim_count == 1
    assert info.claimant == 0
    assert info.count_of_rank("A") == 1
    assert info.count_of_rank("10") == 2
    assert "announce" in info.obs


def test_rank_of_handles_the_two_character_rank() -> None:
    assert istate.rank_of("10♥") == "10"
    assert istate.rank_of("A♣") == "A"


def test_own_hand_must_be_identities() -> None:
    """Handing the parser another player's view is a caller bug, and says so."""
    swapped = REAL.replace("P1|", "P0|")
    with pytest.raises(ValueError, match="not the acting player"):
        _ = istate.parse(swapped).hand


@pytest.mark.parametrize(
    "text",
    [
        "no pipes at all",
        "P1|hand[1]=[A♠]|obs:x",  # no `state:` section
        "P1|hand[1]=[A♠]|state:a=b",  # no `obs:` section
        "P1|hand[1]=@@@|state:a=b|obs:",  # unrecognized zone view
    ],
)
def test_malformed_states_raise(text: str) -> None:
    """Loud, not a half-populated `Info` — a silent partial parse would zero
    every metric while the run reported success."""
    with pytest.raises(ValueError):
        istate.parse(text)


@pytest.mark.parametrize(
    ("hand", "claim_rank", "claim_count", "expected"),
    [
        # Sound direction: the observer can account for enough of the rank that
        # the claim cannot fit in what is left.
        (["A♠", "A♥", "A♦", "A♣"], "A", 1, True),
        (["A♠", "A♥", "A♦"], "A", 2, True),
        (["A♠", "A♥"], "A", 3, True),
        (["A♠"], "A", 4, True),
        # Exactly consistent: 4 copies total, nothing proved.
        (["A♠", "A♥", "A♦"], "A", 1, False),
        (["A♠", "A♥"], "A", 2, False),
        (["A♠"], "A", 3, False),
        ([], "A", 4, False),
        # A different rank in hand proves nothing about this claim.
        (["K♠", "K♥", "K♦", "K♣"], "A", 4, False),
    ],
)
def test_hand_only_criterion_is_the_conservative_arithmetic(
    hand: list[str], claim_rank: str, claim_count: int, expected: bool
) -> None:
    """The narrow criterion: pure arithmetic over one hand, exhaustible.

    With no flip evidence in the log the WIDENED criterion must agree exactly —
    widening may only add opportunities, never move the boundary of this case.
    """
    info = istate.Info(
        player=0,
        zones={"hand[0]": list(hand)},
        state={"claim_rank": claim_rank, "claim_count": str(claim_count), "claimant": "1"},
        obs="",
    )
    assert istate.provably_false_hand_only(info, claim_rank, claim_count) is expected
    assert istate.provably_false(info, claim_rank, claim_count) is expected


def test_criteria_never_fire_on_an_arithmetically_possible_claim() -> None:
    """Soundness, exhaustively over the rank x held x count product, for BOTH
    criteria with no flip evidence present.

    This is the closed, enumerable half of the guarantee. The widened
    criterion's open half — reasoning over an event log across a whole game —
    cannot be enumerated, and is checked against ground truth by the execution
    oracle in `test_infostate_widened.py`.
    """
    suits = "♠♥♦♣"  # distinct cards: a hand cannot hold the same card twice
    for rank in istate.RANKS:
        for held in range(istate.COPIES_PER_RANK + 1):
            for claim_count in range(1, 5):
                info = istate.Info(
                    player=0,
                    zones={"hand[0]": [f"{rank}{s}" for s in suits[:held]]},
                    state={"claimant": "1"},
                    obs="",
                )
                truthful_possible = held + claim_count <= istate.COPIES_PER_RANK
                assert istate.provably_false_hand_only(info, rank, claim_count) != truthful_possible
                assert istate.provably_false(info, rank, claim_count) != truthful_possible
