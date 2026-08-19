"""Skat's game-local runtime [[primitive]]s.

The hand runs fully on the kernel (skat.cardlang): the Reizen call-and-response
is the auction [[form]] of `round` over a role-guarded two-participant ring, the
contract declaration a pair of `offer`s plus a one-draw suit round, the ten
tricks three single-actor filtered [[transfer]]s per trick, and the scoring plain
statements. Follow legality and trick resolution are the game's declared
[[trick-order]], so what stays game-local is only what the expression language
cannot say: the 62-value bid ladder, matador counting, and the overbid
arithmetic (a ceiling).

`skat_matadors` reads the declared contract from state (`is_grand` / `is_null`
/ `trump_suit`) — the Stud/Cribbage precedent for game-local primitives over
live state.
"""

from __future__ import annotations

from cardlang.runtime import reads
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.narrowing import EngineFacts
from cardlang.runtime.values import Player

ROW = reads.row("cardlang/runtime/skat.py", "skat.cardlang")

# The legal Reizen bid sequence (reachable game values).
_BID_SEQUENCE = (
    18, 20, 22, 23, 24, 27, 30, 33, 35, 36, 40, 44, 45, 46, 48, 50,
    54, 55, 59, 60, 63, 66, 70, 72, 77, 80, 81, 84, 88, 90, 96, 99,
    100, 108, 110, 117, 120, 121, 126, 130, 132, 135, 140, 143, 144,
    150, 153, 156, 160, 162, 165, 168, 170, 176, 180, 187, 192, 198,
    204, 216, 240, 264,
)


def _contract(gr: reads.GameReads) -> tuple[str, str | None]:
    """The declared contract, read from state (the declaration move effects set
    it before any consumer runs)."""
    if gr.state["is_null"]:
        return "null", None
    if gr.state["is_grand"]:
        return "grand", None
    return "suit", gr.state["trump_suit"]


def _trump_order(game_type: str, trump_suit: str | None) -> list[tuple[str, str]]:
    jacks = [("J", "clubs"), ("J", "spades"), ("J", "hearts"), ("J", "diamonds")]
    if game_type == "grand":
        return jacks
    if trump_suit is None:
        # The contract is live game state (Null names no trump suit, and the
        # docstrings of the consumers say the game guards for it), so being
        # called without one is the description's error, in the runtime's
        # channel.
        raise OwnerGuardError(
            f"skat trump order consulted for a {game_type!r} contract with no "
            f"trump suit declared"
        )
    return jacks + [(r, trump_suit) for r in ("A", "10", "K", "Q", "9", "8", "7")]


# --- the native call surface -------------------------------------------------


def skat_next_bid(value: int) -> int:
    """The next Reizen ladder value above `value`, or 0 when the ladder is
    exhausted (the auction's `until` reads 0 as "the speaker cannot raise",
    ending the exchange with no draw, exactly like the reference)."""
    nexts = [x for x in _BID_SEQUENCE if x > value]
    return nexts[0] if nexts else 0


def skat_matadors(facts: EngineFacts, gr: reads.GameReads, p: Player) -> int:
    """The matador count for `p`'s hand plus the skat under the declared
    trump structure: the length of the unbroken with/without run from the
    club Jack down the trump order. Undefined for Null (the game guards)."""
    game_type, trump_suit = _contract(gr)
    cards = list(gr.families["hand"][p]) + list(gr.singles["skat"])
    order = _trump_order(game_type, trump_suit)
    held = [any(c.rank == r and c.suit == s for c in cards) for (r, s) in order]
    want = held[0]  # "with" if holding the top trump (CJ), else "without"
    n = 0
    for h in held:
        if h == want:
            n += 1
        else:
            break
    return n
