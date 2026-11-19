"""A card lands in a zone during play through one door, and that door is what
tells each seat (`execute.deposit`).

Every transfer a seat can learn of is delivered from the site that writes the
destination, so a new verb that lands a card is observed by routing through
the door rather than by remembering a second call beside it. These pins hold
the door's callers to the text of `cardlang/`: they are scrapes, because a
`Zone` is a public class and Python has no module-private method, so which code
writes a zone is a fact about the call graph that no type holds.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        under `cardlang/`, a zone gains a card only through
                 `Zone.add_all`, called by `execute.deposit` and by the
                 driver's deck seeding alone; a `MovementEvent` is constructed
                 only in `observe.movement`, called by `execute.deposit`
                 alone; no
                 code outside `Zone` writes a zone's cards or Arrival Record
                 directly.
domain:          every `.py` file under `cardlang/`, every call and every
                 assignment target in it.
registry:        `Zone`'s mutators (cardlang/runtime/state.py); the sanctioned
                 callers below, each named with why it is sanctioned.
held by:         Derived and Pinned (these scrapes). Why not higher: a `Zone`
                 is a public class, so a write site is a fact about the text,
                 and the deck seeding is a write the door must not observe.
does not prove:  that the door delivers the right events -- the per-observer
                 proofs under tests/openspiel_ready/ and the spelling capture
                 in tests/test_observation_spelling.py hold that; that a
                 caller deposits a multi-card step as one call rather than one
                 card at a time, which would spell the log differently and is
                 held by that capture; anything outside `cardlang/` -- the
                 proof harness writes zones directly by design, to build and
                 restore the worlds it probes.
red under:       each test names its own reddening mutation.
"""

from __future__ import annotations

import ast
from pathlib import Path

CARDLANG = Path(__file__).parent.parent / "cardlang"

# Seeding the deck lands the whole pack before the first statement runs: no
# card is transferred from anywhere, so no seat is told anything.
_DECK_SEEDING = "driver.play_game"

_CARD_MUTATORS = frozenset({"append", "extend", "insert", "pop", "clear", "remove"})


def _sites(match: type[ast.AST], pred: object) -> set[str]:
    """Every node of type `match` satisfying `pred` under `cardlang/`, as
    "module.enclosing_function"."""
    assert callable(pred)
    sites: set[str] = set()
    for path in sorted(CARDLANG.rglob("*.py")):
        tree = ast.parse(path.read_text())
        spans = [
            (node.lineno, node.end_lineno or node.lineno, node.name)
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        for node in ast.walk(tree):
            if isinstance(node, match) and pred(node):
                lineno = getattr(node, "lineno")
                enclosing = [name for lo, hi, name in spans if lo <= lineno <= hi]
                sites.add(f"{path.stem}.{enclosing[-1] if enclosing else '<module>'}")
    return sites


def _calls_attr(attr: str) -> set[str]:
    return _sites(
        ast.Call,
        lambda c: isinstance(c.func, ast.Attribute) and c.func.attr == attr,
    )


def test_a_zone_gains_a_card_only_through_the_door() -> None:
    """red under: land a card in a zone from a second site -- for instance the
    trick form appending its play with `add_all` beside `deposit` -- and the
    scrape gains that site."""
    assert _calls_attr("add_all") == {"execute.deposit", _DECK_SEEDING}, (
        "a card lands in a zone during play through `execute.deposit`, which "
        "is what tells each seat of the transfer; a second write site lands "
        "cards no seat is told of"
    )


def test_a_movement_is_delivered_only_by_the_door() -> None:
    """red under: call `observe.movement` from a second site, or construct a
    `MovementEvent` outside it -- the scrape gains that site."""
    assert _calls_attr("movement") == {"execute.deposit"}, (
        "a movement is delivered from the site that writes the destination "
        "(`execute.deposit`), so it cannot be delivered for a write that did "
        "not happen or missed for one that did"
    )
    def builds_a_move(c: ast.Call) -> bool:
        return (isinstance(c.func, ast.Name) and c.func.id == "MovementEvent") or (
            isinstance(c.func, ast.Attribute) and c.func.attr == "MovementEvent"
        )

    assert _sites(ast.Call, builds_a_move) == {"observe.movement"}, (
        "a `move` event is made in one place, `observe.movement`"
    )


def test_no_code_outside_zone_writes_its_cards_or_record() -> None:
    """red under: append to a zone's `cards` (or its `arrivals`) from outside
    `Zone`, or assign either -- the scrape gains that site. A shuffle permutes
    `cards` in place through the generator and lands no card, so it is not a
    write here."""

    def writes(node: ast.AST) -> bool:
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            receiver = node.func.value
            return (
                node.func.attr in _CARD_MUTATORS
                and isinstance(receiver, ast.Attribute)
                and receiver.attr in {"cards", "arrivals"}
            )
        if isinstance(node, (ast.Assign, ast.AugAssign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                base = target.value if isinstance(target, ast.Subscript) else target
                if isinstance(base, ast.Attribute) and base.attr in {"cards", "arrivals"}:
                    return True
        return False

    assert _sites(ast.AST, writes) <= {
        "state.__init__",
        "state.add_all",
        "state.remove",
        "state.take_all",
    }, "a zone's cards and Arrival Record are written by `Zone`'s own mutators alone"
