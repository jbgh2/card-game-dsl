"""The [[kernel-definition-contract]] registry: the card facts the kernel reads
by name and only the game answers.

A Kernel Definition Contract is a signature the kernel states and a game
answers by writing `function <name>` with that signature — the shape a family
library's `requires` row has, with the kernel as the party requiring
(decisions.md "Trick Order", "Scoring has no constructs of its own"). The four
rows are the trick facts the winner, the follow test and the legality filter
read (`is_trump`, `follow_class`, `card_strength`) and the card points the
scoring text and the end-of-game census read (`card_points`). A game answers a
row by the name alone: no marker, the signature check doing the work a marker
would.

The `card_points { }` table is a spelling of an answer: the parse builder
lowers it to the `FunctionDef` a designer would write by hand, stamped with its
source spelling so a refusal names what was written (`n.LoweredSpelling`). No
pass below the parser sees a block.

Two rows carry a default the driver applies once, at load, when the game has
a Trick Order and leaves the row unanswered: `follow_class` (the printed suit)
and `card_strength` (`rank_value`). `is_trump` and `card_points` carry none, so
their absence is stated — `function is_trump(c : Card) = false` for a game with
no trumps.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a parsed `Game` whose `functions` hold every answer, lowered or
              hand-written.
Establishes:  ONE statement of each contract's name, parameter and result,
              and of which rows default; ONE reference order for the Trick
              Order rows (`TRICK_ORDER_CONTRACTS`); and ONE presence question,
              `answer`, from which `has_trick_order` derives.
Now illegal:  a contract signature stated anywhere but its row here; a
              consumer deciding whether a game answers a contract by scanning
              `game.functions` itself; a contract name in any native registry
              (`BUILTIN_CALL_FUNCS`, `CALL_SIGS`, `VALUE_NAMES`,
              `PRIMITIVE_CALL_FUNCS`), pinned disjoint by
              tests/test_kernel_definition_contracts.py.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from cardlang.ast import nodes as n
from cardlang.types import TBoolean, TCard, TEnum, TInteger, TOptional, Type


@dataclass(frozen=True)
class KernelDefinitionContract:
    """One row: the name a game's `function` answers, the one parameter the
    kernel passes (a card, spelled `card` in the designer's words), the result
    it reads, and whether the driver supplies a default when a Trick Order
    game leaves the row unanswered."""

    name: str
    param: str
    param_type: Type
    result: Type
    result_spelling: str
    defaulted: bool

    @property
    def spelled(self) -> str:
        """The row as a designer reads it: `is_trump(card : Card) : Boolean`."""
        return f"{self.name}({self.param} : Card) : {self.result_spelling}"


KERNEL_DEFINITION_CONTRACTS: tuple[KernelDefinitionContract, ...] = (
    KernelDefinitionContract(
        "is_trump", "card", TCard(), TBoolean(), "Boolean", defaulted=False
    ),
    KernelDefinitionContract(
        "follow_class", "card", TCard(), TOptional(TEnum("Suit")), "Suit?", defaulted=True
    ),
    KernelDefinitionContract(
        "card_strength", "card", TCard(), TInteger(), "Integer", defaulted=True
    ),
    KernelDefinitionContract(
        "card_points", "card", TCard(), TInteger(), "Integer", defaulted=False
    ),
)

CONTRACTS: dict[str, KernelDefinitionContract] = {
    c.name: c for c in KERNEL_DEFINITION_CONTRACTS
}
KERNEL_CONTRACT_NAMES: frozenset[str] = frozenset(CONTRACTS)

# The Trick Order's three rows in the language's reference order: an answer
# may call the answers BEFORE it and no others, whatever order the game writes
# them in. `card_points` is outside the order: any answer may call it, and it
# may call any of the three, the recursion guard refusing a cycle.
TRICK_ORDER_CONTRACTS: tuple[str, ...] = ("is_trump", "follow_class", "card_strength")

# The contract that makes a Trick Order present: a game with a Trick Order
# answers it, and the other two rows default.
TRICK_ORDER_KEY_CONTRACT = "is_trump"


def answer(game: n.Game, name: str) -> n.FunctionDef | None:
    """The game's own definition answering contract `name`, lowered or
    hand-written, or None. A library's definition never answers (resolve
    refuses one); a game answering a row twice is refused as a duplicate, so
    the first is the answer."""
    assert name in CONTRACTS, f"{name!r} is not a Kernel Definition Contract"
    return next(
        (f for f in game.functions if f.name == name and f.origin is None), None
    )


def answers(game: n.Game) -> Iterable[n.FunctionDef]:
    """Every answer the game writes, in the registry's order."""
    for row in KERNEL_DEFINITION_CONTRACTS:
        found = answer(game, row.name)
        if found is not None:
            yield found


def has_trick_order(game: n.Game) -> bool:
    """Whether the game declares a [[trick-order]]: it answers `is_trump`."""
    return answer(game, TRICK_ORDER_KEY_CONTRACT) is not None


def trick_order_answers(game: n.Game) -> tuple[n.FunctionDef, ...]:
    """The game's answers to the Trick Order rows, in the reference order;
    empty without a Trick Order."""
    if not has_trick_order(game):
        return ()
    return tuple(
        f for name in TRICK_ORDER_CONTRACTS if (f := answer(game, name)) is not None
    )
