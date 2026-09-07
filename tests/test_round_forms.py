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
            emitter writes). One direction of the order-mode reconciliation
            sits outside, and it bounds what this module covers rather than
            leaving a hole in the grid: an `AuctionRound` carrying a mode the
            form cannot walk is resolve's to refuse and is unreachable from
            source text, so the check that would close it belongs with the
            traversal that would make it reachable -- issue #425 carries it
            for whoever writes that traversal.
registry:   form    -- `round_axes.round_productions` (grammar productions
                       opening with the `round` keyword) reconciled against
                       `round_axes.round_nodes` (those productions' parse-builder
                       return annotations). The reconciliation IS the derivation:
                       nothing else crosses the productions against the nodes,
                       so a production whose builder returns another form's node
                       fails here rather than being a fact you have to already
                       know. The crossing:
                       `test_every_round_production_builds_its_own_node`.
            clause  -- `round_axes.clause_settings`, the full cross of each
                       production's `[...]` groups, with `order`'s values from
                       `n.ROUND_ORDER_MODES` rather than binary. The crossing:
                       `test_clause_axis_is_the_grammar_and_the_order_registry`.
            movetype -- `round_axes.move_type_forms`, the round nodes carrying
                       a `move_type` field, crossed against
                       `stdlib.moves.LIBRARY_MOVE_TYPES`. Which forms are in
                       the axis is derived from their fields, and the name each
                       one runs is read from the constant the resolver's guard
                       reads (`RULE_ENFORCED_MOVE_TYPE`,
                       `CLIMB_DECISION_MOVE_TYPE`) -- so only the pairing of
                       node to constant is authored, and a form with the field
                       and no pairing raises rather than dropping out.
            The `ROUND_ORDER_MODES` widening guard on `AuctionForm`:
            tests/test_registry_guard_witnesses.py::test_widening_round_order_modes_fails_the_auction_form.
            The `state.` fields each form publishes:
            cardlang/stdlib/round_state.py.
does not prove:  four things.

            (1) That the `order` clause SELECTS anything. It admits one value
            and that value is the default: `order ring` and no clause at all
            reach the same traversal, and nothing below resolve reads
            `order_mode`. The grid's `order` rows prove the clause parses,
            resolves, emits and runs -- not that it chooses a traversal. The
            clause is kept as the docking point a second traversal arrives at
            (decisions.md, "The auction form of `round`", under Order).

            (2) That a cell setting an `outcome` clause EXECUTES. Such a cell
            raises its tagged result for an enclosing `produces:` arm to
            catch, which this minimal game deliberately does not have, so
            `test_round_cell_executes` excludes them -- written as the
            excluded setting (`_RAISES_TAGGED_OUTCOME`) rather than the
            included list, so the exclusion cannot quietly widen. Their front
            end is crossed here; their runtime rests on the corpus games that
            write one -- tests/openspiel_ready/test_bridge.py,
            tests/openspiel_ready/test_french_tarot.py,
            tests/openspiel_ready/test_pinochle.py, and those games' per-seed
            goldens in tests/test_migration_characterization.py.

            (3) That a clause with a closed value set is crossed over that
            set. The two AUTHORED mappings in `round_axes` are naming
            correspondences no artifact states -- which registry bounds a
            clause's values (`_CLAUSE_VALUE_REGISTRIES`), and which node pairs
            with which move-type constant (`_RUNNABLE_MOVE_TYPE`) -- and they
            degrade differently: a form missing from the second RAISES, while
            a clause missing from the first is merely treated as binary and
            its values go uncrossed.

            (4) Anything about what `AuctionForm` publishes to `state.`.
            stdlib/round_state.py enumerates the forms as data, and its own
            pin is asymmetric: the surface-rejection half spans every form,
            but the auction form publishes nothing, so the half that would
            observe its writes runs over an empty set.
"""

from __future__ import annotations

import dataclasses
import random
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.stdlib.moves import LIBRARY_MOVE_TYPES
from tests import round_axes as axes

# --- fixtures -----------------------------------------------------------------
#
# One template per production, with a substitution slot per optional clause, so
# a cell is the template plus its clause setting. Written this way rather than
# as eleven games because the cell list is DERIVED: a new optional clause makes
# `clause_settings` return rows whose substitution key no template has, and the
# `KeyError` is the fixture telling you it no longer covers its own axis.
#
# The trick template names `highest_trump_or_led_suit`, the winner whose body
# READS the round's `trump` clause: on `highest_of_led_suit` the clause is
# accepted-but-ignored and resolve refuses it (`TRUMP_READING_WINNERS`,
# tests/test_trump_slot_class.py), so the `trump=present` cells need a
# reading winner to be legal cells at all.

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
            winner highest_trump_or_led_suit{trump}{early}
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
    """The one round entry of a cell's emitted IR.

    Found by the leader/participants shape AND a `kind` ending in `_round`.
    Which of the three kinds it is remains under test; that it is a round at
    all is the stable half, and it is what keeps this finder honest. Matching
    on shape alone would need a hand-listed exclusion for every other
    construct carrying the same pair (`turns` today), and the day a fourth
    appeared this finder would silently return the wrong entry while the AST
    finder next door failed loud.
    """
    found: list[dict[str, Any]] = []

    def walk(node: Any) -> None:
        if isinstance(node, dict):
            if {"leader", "participants"} <= node.keys() and str(
                node.get("kind", "")
            ).endswith("_round"):
                found.append(node)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(ir)
    assert len(found) == 1, f"expected one round in the IR, found {len(found)}"
    return found[0]


def test_the_three_forms_emit_three_distinct_ir_kinds() -> None:
    """One kind per form, and no two forms sharing one.

    `test_no_ir_key_is_null_across_a_whole_form` pins one kind per form; that
    alone would be satisfied by all three emitting `"round"`, which is exactly
    the state this change left.

    red under: give `ir._stmt`'s climb arm the auction arm's kind string.
    """
    kinds = set()
    for production in _TEMPLATES:
        setting = axes.clause_settings(production)[0]
        ir: Any = emit(check_dsl(_source(production, setting), "cell.cardlang"))
        kinds.add(_ir_round(ir)["kind"])
    assert len(kinds) == len(_TEMPLATES), f"forms share an IR kind: {sorted(kinds)}"


EXECUTABLE_CELLS = [
    pytest.param(p, s, id=_label(p, s))
    for p, s in _cells()
    if _RAISES_TAGGED_OUTCOME not in s
]


@pytest.mark.parametrize(("node", "runnable"), axes.move_type_forms())
def test_only_the_runnable_move_type_is_accepted(node: type, runnable: str) -> None:
    """A form naming a move type its decision site cannot run is rejected.

    The misuse probe, and it found a real hole: the trick form has carried this
    guard since the surface was written, and the climbing form never had one.
    `round climb submit_bid` was accepted and then played out as an ordinary
    climb -- big-two scored identically with the move type replaced. Seven of
    the eight `LIBRARY_MOVE_TYPES` spellings meant nothing there.

    The rejection must NAME the form: the two messages are otherwise a
    copy-paste apart, and one saying "trick" on a climb round would send the
    author to the wrong clause while still passing a bare `raises` check.
    """
    production = next(
        p for p, cls in axes.round_node_by_production().items() if cls is node
    )
    setting = axes.clause_settings(production)[0]
    form_word = node.__name__.removesuffix("Round").lower()
    source = _source(production, setting)
    assert f" {runnable}" in source, "the template does not name the runnable move type"

    check_dsl(source, "cell.cardlang")  # the runnable name is accepted

    wrong = sorted(LIBRARY_MOVE_TYPES - {runnable})
    assert wrong, "no other move type exists to probe with"
    for name in wrong:
        probe = source.replace(f" {runnable}", f" {name}")
        with pytest.raises(DiagnosticError) as excinfo:
            check_dsl(probe, "cell.cardlang")
        message = str(excinfo.value)
        assert name in message, f"{form_word}: the diagnostic does not quote {name!r}"
        assert form_word in message, (
            f"a {form_word} round naming '{name}' was rejected, but the message "
            f"does not say which form: {message.splitlines()[0]}"
        )


@pytest.mark.parametrize(("production", "setting"), EXECUTABLE_CELLS)
def test_round_cell_executes(
    production: str, setting: tuple[tuple[str, str], ...]
) -> None:
    """Every cell that closes without a tagged outcome plays to completion.

    The execution half of the reach property: a form whose runtime arm stopped
    matching would raise here rather than quietly select a neighbour's. Cells
    with an `outcome` clause are excluded for the reason in the ledger's
    `does not prove:` row -- they raise their result for a `produces:` arm this
    minimal game deliberately does not have.

    red under: in `mechanics.build_form`, return the trick form's bundle for
    every node.
    """
    game = check_dsl(_source(production, setting), "cell.cardlang")
    for seed in range(5):
        play_game(game, random.Random(seed))
