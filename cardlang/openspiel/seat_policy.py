"""[[seat-policy]]s: what answers for a seat at a decision node.

A Seat Policy is handed the deciding seat's [[seat-view]] and the legal action
ids, and answers one of those ids. That is the whole of its input, so a policy
cannot condition on a card its seat does not see: leak-freeness is a property
of its signature, as it is of a renderer's. A person at a terminal, a
rule-based opponent, a trained policy and a language model all answer through
it. A perfect-information opponent, which reads the World, is a different type
with its own name, never this one widened.

The ids are OpenSpiel action ids, which is why the type lives in the Interop
package: its input and its output are that boundary's currency.

`OPPONENTS` is the table of [[opponent]]s, the Seat Policies a person seats by
name. It is the one place an opponent is defined, and every listing of them is
rendered from it.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol

from cardlang.openspiel.infostate import SeatView, render_information_state


class SeatPolicy(Protocol):
    """Answers for one seat at a decision node.

    Three obligations a signature cannot carry: the answer is one of ``legal``,
    which is never empty and sorted ascending (a line refuses any other answer
    before it is played); the answer is a function of what the policy was built
    with and the view it is handed, so one seed and one history name one line of
    play, undo and resume included; and a policy raises only to end the line on
    its seat's behalf, never to decline a decision."""

    def __call__(self, view: SeatView, legal: Sequence[int], /) -> int: ...


class UniformSeatPolicy:
    """Every legal id alike.

    The draw is a digest of the seed and the view's information state, not a
    random stream, so the same seed answers the same view the same way however
    the line reached it — after an undo, on a resumed session, in another
    process. It is a seeded pure strategy; varying the seed varies it."""

    def __init__(self, seed: int) -> None:
        self.seed = seed

    def __call__(self, view: SeatView, legal: Sequence[int]) -> int:
        digest = hashlib.sha256(
            f"{self.seed}\n{render_information_state(view)}".encode()
        ).digest()
        return legal[int.from_bytes(digest[:8], "big") % len(legal)]


class FirstSeatPolicy:
    """The lowest legal id, which is the first pick a person's menu lists.

    A baseline that answers a position the same way every time, so a table
    whose every seat takes the first pick can repeat one exchange until the
    game's `max_length` refuses it (issue #698)."""

    def __call__(self, view: SeatView, legal: Sequence[int]) -> int:
        return legal[0]


@dataclass(frozen=True)
class Opponent:
    """A Seat Policy a person seats by name: `description` says in one line
    what it does, and `make` builds it from the session's seed."""

    name: str
    description: str
    make: Callable[[int], SeatPolicy]


OPPONENTS: dict[str, Opponent] = {
    opponent.name: opponent
    for opponent in (
        Opponent("first", "always takes the first pick on the menu", lambda seed: FirstSeatPolicy()),
        Opponent("random", "picks uniformly at random", UniformSeatPolicy),
    )
}
