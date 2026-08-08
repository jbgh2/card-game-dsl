"""Axis derivation for the `mode` surface grid (`test_mode_surface.py`).

Kept beside the grid rather than inside it so the same derived axes can be
read by the rejection-probe module without either importing the other's
parametrization. Every function here reads a DEFINITION SITE — the grammar
text, an AST union — and returns the member list. Nothing here hand-lists a
domain: a production that grows a new alternative shows up as a new grid row
that nobody wrote, which is the whole point (decisions.md, "Closed-domain
completeness").

Contract
--------
Assumes: the grammar file parses as text (no Lark import — see `_alternatives`).
Establishes: every public axis function returns a NON-EMPTY tuple, or raises.
Illegal after this module: parametrizing a grid over an axis that came back
empty. An empty axis yields zero cells and a passing grid — the vacuously-green
class (decisions.md, "Closed-domain completeness"), which is why the emptiness
check lives here at the producer rather than in each consumer.
"""

from __future__ import annotations

import re
from pathlib import Path

GRAMMAR = Path(__file__).resolve().parent.parent / "cardlang" / "grammar" / "cardlang.lark"


class AxisDerivationError(AssertionError):
    """An axis came back empty or its defining production vanished.

    `AssertionError` so a grid cell awaiting an unlanded production reddens
    under the same exception a wrong expected outcome does, keeping
    `xfail(raises=...)` marks constrained to one failure shape.
    """


def _alternatives(nonterminal: str) -> tuple[str, ...]:
    """The alternative names of a `?rule: a | b | c` production, from the grammar text.

    Reads the grammar rather than Lark's parsed table because the grid must be
    derivable against the MERGE BASE too (the review replays HEAD-derived cells
    there), and a production that does not exist yet cannot be imported.

    Raises rather than returning `()`: a silent empty tuple is how a scrape
    whose regex drifted past its production goes on reporting full coverage
    over nothing.
    """
    text = GRAMMAR.read_text()
    match = re.search(rf"^\??{nonterminal}:(.*?)(?=^\S)", text, re.DOTALL | re.MULTILINE)
    if match is None:
        raise AxisDerivationError(
            f"no `{nonterminal}` production in {GRAMMAR.name} — the axis has no "
            f"defining site, so any grid over it covers nothing"
        )
    body = re.sub(r"//[^\n]*", "", match.group(1))  # strip trailing comments
    out: list[str] = []
    for chunk in body.replace("|", "\n").splitlines():
        chunk = chunk.strip()
        if not chunk:
            continue
        head = chunk.split()[0]
        if re.fullmatch(r"[a-z_][a-z0-9_]*", head):
            out.append(head)
    if not out:
        raise AxisDerivationError(
            f"`{nonterminal}` matched but yielded no alternatives — the scrape's "
            f"shape assumption no longer holds for it"
        )
    return tuple(dict.fromkeys(out))


def phase_item_alternatives() -> tuple[str, ...]:
    """Every item a `phase { }` body admits — the grammar's `?phase_item`."""
    return _alternatives("phase_item")


def mode_item_alternatives() -> tuple[str, ...]:
    """Every item a `mode { }` body admits — the grammar's `?mode_item`."""
    return _alternatives("mode_item")


def statement_alternatives() -> tuple[str, ...]:
    """Every `?statement` alternative — the sub-axis under `phase_item`'s
    `statement`, sampled rather than crossed by the grid (see its ledger)."""
    return _alternatives("statement")


def item_containers() -> tuple[str, ...]:
    """Every brace-or-sequence container whose contents come from an `_item`
    registry: the `X` of any `X_item*` or `X_item+` in the grammar.

    Both repetition forms, because `start: top_item+` is an item registry
    exactly as `game: … game_item* …` is — scraping only `*` silently drops
    the top level, which is one of the positions a new phase-level construct
    must be decided against.
    """
    text = re.sub(r"//[^\n]*", "", GRAMMAR.read_text())
    found = re.findall(r"(\w+)_item[*+]", text)
    if not found:
        raise AxisDerivationError("no `X_item*`/`X_item+` containers found in the grammar")
    return tuple(dict.fromkeys(found))


def mode_roles() -> tuple[tuple[bool, bool], ...]:
    """The per-mode role axis: the full 2x2 of (declares at least one
    transition) x (is named by at least one sibling's transition).

    Crossed in code so neither diagonal can be dropped by hand. The two
    rejects are the shapes that run silently wrong before this change: `both`
    is a chain or self-loop (mode 2 of a 3-chain is active before it is ever
    entered), `neither` is an orphan whose `active_rules` are dead.

    This axis is per MODE. It cannot express a property of the mode SET —
    see `mode_set_shapes`, which is a separate axis for exactly that reason.
    """
    return tuple((source, target) for source in (True, False) for target in (True, False))


def mode_set_shapes() -> tuple[str, ...]:
    """The per-phase mode-SET axis: how the modes of one phase body relate.

    Distinct from `mode_roles` because "how many modes are active when the
    phase is entered" is a property of the set, not of any member — a grid
    over the per-mode 2x2 alone passes every cell of a two-source-mode game
    while saying nothing about the two of them together. Hand-listed with its
    reason: this axis has no defining site in code to derive from, because it
    is a property of a graph the grammar imposes no shape on. Recorded as a
    residual in the grid's ledger rather than passed off as derived.
    """
    return (
        "single_pair",  # one source, one target: hearts and spades
        "independent_pairs",  # N source/target pairs: all sources live at entry
        "shared_terminal",  # two sources naming one target
        "fan_out",  # one source, several targets
        "chain",  # a mode that is both source and target
        "self_loop",  # a mode targeting itself
        "orphan",  # a mode that is neither
    )
