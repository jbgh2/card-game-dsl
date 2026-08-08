"""The `round` construct's forms are distinct AST nodes, not one node sniffed by field.

property:   Each grammar form of `round` builds its OWN AST node, and that node
            carries only the fields its form can use. Two consequences, and the
            second is the one worth the machinery: an impossible combination (an
            auction's `offering` beside a trick's `play_zone`) is unrepresentable
            rather than merely unchecked, and no pass can select a form by
            sniffing a nullable field -- which is what made a form's arm silently
            reachable from another form's node.
domain:     round form x optional-clause setting, at three layers (the AST node
            the parse builder mints, the field set that node carries, the IR the
            emitter writes).
registry:   form    -- `round_axes.round_productions` (grammar productions
                       opening with the `round` keyword) reconciled against
                       `round_axes.round_nodes` (those productions' parse-builder
                       return annotations). The reconciliation IS the derivation:
                       before this change the two disagreed -- three productions,
                       one node -- and no artifact crossed them, so the
                       disagreement was a fact you had to already know rather
                       than a failure. Pinned by
                       `test_every_round_production_builds_its_own_node`.
            clause  -- `round_axes.clause_settings`, the full cross of each
                       production's `[...]` groups, with `order`'s values from
                       `n.ROUND_ORDER_MODES` rather than binary. Pinned by
                       `test_clause_axis_is_the_grammar_and_the_order_registry`.
covered:    `test_round_cell_builds_its_own_node`,
            `test_no_field_is_null_across_a_whole_form`, and
            `test_no_ir_key_is_null_across_a_whole_form` -- each the full
            11-cell cross. The null-across-a-whole-form pair is the issue's
            acceptance criterion made executable: it reads the cells of one
            form as a GROUP, which is what lets it distinguish a field that is
            optional within a form (`trump`) from one the form can never use
            (`combos_fn` on a trick) without either being hand-listed.
sampled:    Execution. `test_round_cell_executes` runs every cell EXCEPT those
            setting an `outcome` clause: an auction with one raises its tagged
            result for an enclosing `produces:` arm to catch, so a minimal game
            exercising it would have to be a different game rather than this one
            with a clause added, and the cell would stop being a cell. Their
            front-end coverage is total; it is their runtime that is sampled,
            by the corpus (bridge, french-tarot, pinochle). Written as the
            excluded setting, not the included list, so the exclusion cannot
            quietly widen -- see `_RAISES_TAGGED_OUTCOME`.
residual:   ONE, and it is a naming correspondence rather than a gap in reach.
            `round_axes._CLAUSE_VALUE_REGISTRIES` -- which optional clauses
            carry a closed value registry -- is authored, because the link from
            a grammar keyword (`order`) to the AST field it fills (`order_mode`)
            to the registry that bounds it (`ROUND_ORDER_MODES`) is stated by no
            artifact. A clause missing from that mapping is treated as binary,
            so a NEW clause with a closed value set would be covered
            absent/present and its values left uncrossed. R4 -- reachable only
            by an engine maintainer adding a clause, and loud the moment they
            look, since the mapping sits beside the axis it feeds. Ledger owns
            the record; no issue.

            Not residual, deliberately: the four cells no corpus game writes
            (`trump`+`early` together, and every explicit `order ring`). They
            are grid rows like any other -- the derivation surfaced them, and
            covering them cost a template substitution each. That is the whole
            argument for deriving a clause axis instead of listing the
            combinations the corpus happens to use.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from tests import round_axes as axes

# --- fixtures -----------------------------------------------------------------
#
# One template per production, with a substitution slot per optional clause, so
# a cell is the template plus its clause setting. Written this way rather than
# as eleven games because the cell list is DERIVED: a new optional clause makes
# `clause_settings` return rows whose substitution key no template has, and the
# `KeyError` is the fixture telling you it no longer covers its own axis.

_TRICK = """
game G {{
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile }}
  state {{ trump_suit : Suit = hearts  won[player] : Integer = 0 }}
  phase deal {{ deal 3 cards from deck to each hand }}
  phase play {{
    repeat until (all players where hand[player] is empty) {{
      round play_to_trick from 0 over all players source hand into trick_pile
            winner highest_of_led_suit{trump}{early}
      won[winner] += 1
      move all cards from trick_pile to deck
    }}
  }}
  winner: highest won
}}
"""

_AUCTION = """
game G {{
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck }}
  state {{ acted[player] : Boolean = false  bumps[player] : Integer = 0 }}
  phase run {{
    round offering [bump, stop] from 0 over players where not acted[player]{order}
          until (number of players where not acted[player]) is 0{outcome}
  }}
  winner: highest bumps
}}
move_type bump {{ effect {{ bumps[actor] := bumps[actor] + 1  acted[actor] := true }} }}
move_type stop {{ effect {{ acted[actor] := true }} }}
"""

_CLIMB = """
game G {{
  players: 3
  max_length: 1000
  direction: clockwise
  cards: standard52
  ranking: 2 A K Q J 10 9 8 7 6 5 4 3
  zones {{ deck : Deck  hand[player] : Hand<player>  trick_pile : TrickPile  discard : Discard }}
  state {{ leader : Player = 0  taken[player] : Integer = 0 }}
  phase deal {{ deal 3 cards from deck to each hand }}
  phase play {{
    repeat until (any player where hand[player] is empty) {{
      round climb play_combination from leader
            over players where hand[player] is not empty
            source hand into trick_pile
            combinations president_lead_options follows president_follows
            until (any player where hand[player] is empty)
      leader := winner
      taken[winner] += 1
      move all cards from trick_pile to discard
    }}
  }}
  winner: highest taken
}}
"""

_TEMPLATES = {"round_stmt": _TRICK, "auction_stmt": _AUCTION, "climb_stmt": _CLIMB}

# How each clause setting is spelled in source. Keyed by (clause, setting) so a
# setting with no spelling is a missing key rather than a silently skipped cell.
_SPELLINGS = {
    ("trump", "absent"): "",
    ("trump", "present"): " trump trump_suit",
    ("early", "absent"): "",
    ("early", "present"): " early on_play_off_led_suit",
    ("order", "absent"): "",
    ("order", "ring"): " order ring",
    ("order", "priority"): " order priority",
    ("outcome", "absent"): "",
    ("outcome", "present"): " outcome bridge_auction_outcome",
}

# The one clause setting that stops a cell from being executable: an auction
# with an `outcome` raises its tagged result for an enclosing `produces:` arm.
# Stated as the excluded setting rather than as the included set, because the
# included set is the thing that silently shrinks — a filter listing what runs
# drops a whole form the day a clause is added, and reports full coverage while
# doing it.
_RAISES_TAGGED_OUTCOME = ("outcome", "present")


def _cells() -> list[tuple[str, tuple[tuple[str, str], ...]]]:
    """Every (production, clause setting) pair -- the grid's parametrization."""
    return [
        (production, setting)
        for production in axes.round_productions()
        for setting in axes.clause_settings(production)
    ]


def _label(production: str, setting: tuple[tuple[str, str], ...]) -> str:
    clauses = ",".join(f"{clause}={value}" for clause, value in setting)
    return f"{production}[{clauses or 'no-optional-clauses'}]"


CELLS = [pytest.param(p, s, id=_label(p, s)) for p, s in _cells()]


def _source(production: str, setting: tuple[tuple[str, str], ...]) -> str:
    return _TEMPLATES[production].format(
        **{clause: _SPELLINGS[(clause, value)] for clause, value in setting}
    )


def _round_node(game: n.Game) -> Any:
    """The one round statement of a cell's game, whatever node class it is.

    Found by field shape rather than by node class: this module's whole subject
    is which class a form builds, so a finder that already knew would beg the
    question.
    """
    found = [
        item
        for phase in game.phases
        for item in _statements(phase.items)
        if dataclasses.is_dataclass(item)
        and {"leader", "participants"} <= {f.name for f in dataclasses.fields(item)}
        and not isinstance(item, n.Turns)
    ]
    assert len(found) == 1, f"expected one round statement, found {len(found)}"
    return found[0]


def _statements(items: Any) -> list[Any]:
    """Every statement of a phase, flattened through the nesting constructs the
    templates use (`repeat until`)."""
    out = []
    for item in items:
        out.append(item)
        body = getattr(item, "body", None)
        if isinstance(body, tuple):
            out.extend(_statements(body))
    return out


# --- axis-derivation pins -----------------------------------------------------


def test_every_round_production_builds_its_own_node() -> None:
    """The form axis reconciles two sources, and they must agree in count.

    This is the pin the whole module rests on. A grammar form with no node of
    its own means some pass distinguishes it by sniffing a field, which is the
    defect the split removes; a node with no production means a form nothing
    can write.
    """
    productions = axes.round_productions()
    nodes = axes.round_nodes()
    assert len(nodes) == len(productions), (
        f"{len(productions)} `round` productions {productions} build "
        f"{len(nodes)} distinct node(s) {[c.__name__ for c in nodes]} -- a form "
        f"sharing another's node can only be told apart by sniffing a field"
    )


def test_clause_axis_is_the_grammar_and_the_order_registry() -> None:
    """The clause axis comes from the productions' optional groups, with a
    closed-value clause crossed over its registry rather than absent/present.

    A new optional clause, or a third order mode, must appear as new rows
    without anyone editing this file. Guarding that the axis is DERIVED, not
    that it currently has eleven members -- pinning the count would just be
    this module asserting its own parametrization back to itself.

    red under: hand-list `optional_clauses` to return `()` for `auction_stmt`,
    or drop the `order` entry from `_CLAUSE_VALUE_REGISTRIES`.
    """
    settings = {p: axes.clause_settings(p) for p in axes.round_productions()}
    for production, cells in settings.items():
        expected = 1
        for clause in axes.optional_clauses(production):
            expected *= 1 + (len(axes.order_modes()) if clause == "order" else 1)
        assert len(cells) == expected, (
            f"`{production}` has {len(axes.optional_clauses(production))} optional "
            f"clause(s) but {len(cells)} cells, not {expected} -- the cross is "
            f"not the full product, so some combination is unreachable by the grid"
        )
    assert any(
        ("order", mode) in setting
        for mode in axes.order_modes()
        for setting in settings["auction_stmt"]
    ), "the order clause is being crossed absent/present, not over its registry"


# --- the grid -----------------------------------------------------------------


@pytest.mark.parametrize(("production", "setting"), CELLS)
def test_round_cell_builds_its_own_node(
    production: str, setting: tuple[tuple[str, str], ...]
) -> None:
    """Each cell's game parses to the node class ITS production declares.

    Born green, and stays green through the split — the count pin above is the
    one that fails before it. This cell guards a different hazard, and only
    after the nodes are distinct: a builder wired to the WRONG one of the three
    (an optional clause moved between forms, a copied method body). Until then
    there is one node and every cell trivially lands on it.

    red under: make `parse._Builder.climb_stmt` return an `AuctionRound` (after
    the split) or annotate it as returning one (before).
    """
    game = check_dsl(_source(production, setting), "cell.cardlang")
    expected = axes.round_node_by_production()[production]
    assert type(_round_node(game)) is expected, (
        f"{_label(production, setting)} built a "
        f"{type(_round_node(game)).__name__}, not a {expected.__name__}"
    )


@pytest.mark.parametrize("production", list(_TEMPLATES))
def test_no_field_is_null_across_a_whole_form(production: str) -> None:
    """No field of a form's node is `None` in every one of that form's cells.

    The acceptance criterion of the split, executable. Read as a GROUP over one
    form's cells, which is what separates a field that is optional WITHIN a form
    (`trump`, absent in two trick cells and present in two) from one the form can
    never use (`combos_fn` on any trick at all). Neither list is written down
    here; the cells decide.
    """
    nodes = [
        _round_node(check_dsl(_source(production, setting), "cell.cardlang"))
        for setting in axes.clause_settings(production)
    ]
    fields = [f.name for f in dataclasses.fields(nodes[0]) if f.name != "span"]
    dead = [f for f in fields if all(getattr(node, f) is None for node in nodes)]
    assert not dead, (
        f"{type(nodes[0]).__name__} carries {dead} which is `None` in every one "
        f"of `{production}`'s {len(nodes)} cells -- a field this form cannot use, "
        f"so an impossible combination is representable and some pass can sniff it"
    )


@pytest.mark.parametrize("production", list(_TEMPLATES))
def test_no_ir_key_is_null_across_a_whole_form(production: str) -> None:
    """The same property one layer down: a form's IR carries no always-null key.

    Separate from the field pin because the emitter writes its own key set, and
    a per-node emitter arm that kept the shared key list would serialise nulls
    from a form's node that no longer has the fields. The corpus goldens cover
    the trick and auction forms; NO golden game has a climb round, so this is
    the only place the climbing form's IR shape is pinned at all.
    """
    settings = axes.clause_settings(production)
    emitted = []
    for setting in settings:
        ir: Any = emit(check_dsl(_source(production, setting), "cell.cardlang"))
        emitted.append(_ir_round(ir))
    keys = [k for k in emitted[0] if k != "kind"]
    dead = [k for k in keys if all(entry.get(k) is None for entry in emitted)]
    assert not dead, (
        f"`{production}`'s IR carries {dead}, null in all {len(settings)} cells"
    )
    kinds = {entry["kind"] for entry in emitted}
    assert len(kinds) == 1, f"one form emitted several kinds: {kinds}"


def _ir_round(ir: Any) -> dict[str, Any]:
    """The one round entry of a cell's emitted IR, found by its leader/participants
    pair -- by shape, not by `kind`, since the kind string is under test."""
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if {"leader", "participants"} <= node.keys() and "binder" not in node:
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ir)
    assert len(found) == 1, f"expected one round in the IR, found {len(found)}"
    return found[0]


EXECUTABLE_CELLS = [
    pytest.param(p, s, id=_label(p, s))
    for p, s in _cells()
    if _RAISES_TAGGED_OUTCOME not in s
]


@pytest.mark.parametrize(("production", "setting"), EXECUTABLE_CELLS)
def test_round_cell_executes(
    production: str, setting: tuple[tuple[str, str], ...]
) -> None:
    """Every cell that closes without a tagged outcome plays to completion.

    The execution half of the reach property: a form whose runtime arm stopped
    matching would raise here rather than quietly select a neighbour's. Cells
    with an `outcome` clause are excluded for the reason in the ledger's
    `sampled` row -- they raise their result for a `produces:` arm this minimal
    game deliberately does not have.

    red under: in `mechanics.build_form`, return the trick form's bundle for
    every node.
    """
    game = check_dsl(_source(production, setting), "cell.cardlang")
    for seed in range(5):
        play_game(game, random.Random(seed))
