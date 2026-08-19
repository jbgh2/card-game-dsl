"""500's game-local runtime [[primitive]]s: the bid ladder.

The hand runs fully on the kernel (five-hundred.cardlang): the ascending
auction is the drop-out ring [[form]] of `round` (the Pinochle shape), the kitty
pickup and discard are plain [[transfer]]s, the joker nomination an `offer`, and
the ten tricks single-actor filtered movements (the Skat/Doppelkopf shape). The
contract's order is the game's declared [[trick-order]] — the joker and both
bowers as members of the trump suit, the no-trump family's un-nominated joker
as that contract's one trump — so follow legality and the winner are the
language's, and what stays game-local is the 27-rung bid ladder with the
misère insertions. Every function here is a pure function of its arguments:
nothing in this module reads the live world.

Contract ordinals: every bid is a rung on one strictly-ordered ladder,
encoded as an integer so the standing bid is one public [[state-variable]].
Suit/no-trump bids take 10*((level-6)*5 + strain) with strain ♠1 ♣2 ♦3 ♥4
NT5 (so 6♠=10 … 10NT=250); misère sits at 105 (above every seven bid, below
every eight bid) and open misère at 235 (above 10♦, below 10♥). Point values
are a separate table — misère (250) is worth MORE than 8♠ (240) but ranks
BELOW it; the ordinal and the value never share a scale.
"""

from __future__ import annotations

from cardlang.runtime.errors import OwnerGuardError

# Bidding order of the strains within a level: ♠ < ♣ < ♦ < ♥ < no-trump
# (None). The deck-derived Suit domain also contains "joker" (the joker's own
# suit); it is NOT a biddable or nominable strain — `five_hundred_next_bid`
# returns 0 for it and the game file's guards mask it, so the action exists
# in the fixed action space but is never legal.
_STRAIN_ORD: dict[str | None, int] = {"spades": 1, "clubs": 2, "diamonds": 3, "hearts": 4, None: 5}

_MISERE_ORD = 105
_OPEN_MISERE_ORD = 235
_SUIT_BID_ORDS = tuple(10 * n for n in range(1, 26))  # 6♠=10 .. 10NT=250


def _is_suit_bid_ord(rank: int) -> bool:
    return rank in _SUIT_BID_ORDS


def five_hundred_next_bid(standing: int, strain: str | None) -> int:
    """The ordinal of the cheapest bid in `strain` that beats the standing
    bid ordinal, or 0 when none exists (levels stop at ten) — also 0 for the
    joker pseudo-strain, which is never biddable. The auction's guard reads
    0 as "this strain cannot outbid", exactly like skat_next_bid's exhausted
    ladder."""
    so = _STRAIN_ORD.get(strain)
    if so is None:
        return 0  # the deck-derived "joker" suit: never a biddable strain
    nexts = [10 * ((lvl - 6) * 5 + so) for lvl in range(6, 11)]
    higher = [o for o in nexts if o > standing]
    return higher[0] if higher else 0


def five_hundred_bid_value(rank: int) -> int:
    """The score value of a contract ordinal: the Pagat table (6♠=40, +20 per
    strain, +100 per level, 10NT=520), misère 250, open misère 500. Any other
    integer is no contract — the ladder above is the whole domain, so a stray
    value is the description's error, so this raise is its [[owner-guard]]."""
    if rank == _MISERE_ORD:
        return 250
    if rank == _OPEN_MISERE_ORD:
        return 500
    if not _is_suit_bid_ord(rank):
        raise OwnerGuardError(
            f"five_hundred_bid_value: {rank} is not a contract ordinal "
            f"(suit bids 10..250 by tens, misère 105, open misère 235)"
        )
    n = rank // 10 - 1
    level, strain = 6 + n // 5, n % 5 + 1
    return 40 + 20 * (strain - 1) + 100 * (level - 6)


def five_hundred_bid_level(rank: int) -> int:
    """The trick target (6..10) of a suit or no-trump contract ordinal.
    Misère ordinals have no trick target (the game scores them on
    `declarer_tricks is 0`, never through this) and anything off the ladder
    is no contract — both are the description's error, loud."""
    if not _is_suit_bid_ord(rank):
        raise OwnerGuardError(
            f"five_hundred_bid_level: {rank} is not a suit/no-trump contract "
            f"ordinal (misère contracts have no trick target)"
        )
    return 6 + (rank // 10 - 1) // 5
