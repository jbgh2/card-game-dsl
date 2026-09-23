"""A rule that reads concealed cards is refused (decisions.md "Honest Play is
assumed, so a rule reading concealed cards is mis-modelled").

Every designer expression whose value reaches a decision is judged against the
declared visibility of every zone it reads. Where no seat is deciding (a
phase's `when` gate or `repeat until` condition, a mode's `transition_to`
trigger) every seat must be able to see what the read needs; where a seat is
deciding (a move type's `when:`, a rule's clauses, a `choose`'s range, a
chosen movement's amount, source, `where` and destination) the deciding seat
must.

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property:        a zone read at a position in `HIDDEN_READ_POSITIONS`'s two
                 judged kinds checks clean exactly when the zone's declared
                 type reveals what the read needs to every seat (no seat
                 deciding) or to the deciding seat; otherwise `check_dsl`
                 refuses it, located, naming the zone and the fix.
domain:          the verdict grid crosses every judged position (the table's
                 rows, the phase qualifier split into its two kinds) with
                 every read need, every library zone type and, where a seat
                 decides, the index's relation to that seat (the seat's own
                 instance or another's; an unowned zone has one relation).
                 Its expected column reads each type's projection from
                 `docs/library.md`'s `composition:` rows and the lattice from
                 decisions.md, never from `ZONE_PROJECTIONS`. The relation
                 grid crosses every way the deciding seat is proven with a
                 concealed hand read; the route grid crosses every route a
                 read can take with both verdicts; the implicit-pool grid
                 crosses every `DECISION_POOLS` row whose cards come from a
                 declared zone with every zone type a seat's `hand` can be
                 declared as; the destination cells name a zone of every
                 library type as a chosen movement's destination; the
                 indirection grid crosses every name the
                 reader follows by value with the seat that consumes it; the
                 corpus cells hold the
                 State Variable rule to the corpus games whose chosen
                 movements it admits. A position outside the
                 two judged kinds is not judged: the control positions (an
                 `if`, a round's `leader`/`participants`/`until`, the seat of
                 an `as` or an `offer`) are issue #755, and a Primitive's
                 result stored into state is issue #471. A chosen pick from a
                 pool its chooser cannot see is refused until a pick by
                 position exists (issue #756); a pile's order is judged
                 visible where the pile is face up to every seat, and a
                 shuffle of such a pile publishes nothing (issue #757).
registry:        positions: `cardlang.resolve.HIDDEN_READ_POSITIONS`, pinned
                 against the `cardlang/ast/nodes.py` dataclass fields whose
                 type admits an `Expr`; needs:
                 `cardlang.stdlib.zones.READ_NEEDS`; zone types:
                 `cardlang.stdlib.zones.LIBRARY_ZONE_TYPES`, projections from
                 `docs/library.md`; the Builtin partition:
                 `cardlang.builtins.functions.BUILTIN_ARGUMENT_READS`,
                 `BUILTIN_READS_NOTHING`, `BUILTIN_IMPLICIT_READS`; the
                 phase qualifier's two kinds: `cardlang.ast.nodes.PhaseQualifier`;
                 the decision points: `cardlang.resolve.DECISION_POOLS`, pinned
                 against `cardlang.runtime.delegation.DECISION_POINTS` and
                 `FORM_CONSTRUCTS`.
                 An Arrival Record pile argument:
                 tests/test_arrival_record.py (its Owner Guard,
                 `_check_arrival_record_pile_args`, judges it in every position).
                 The rendered messages: tests/rejections/hidden_read_gate.cardlang,
                 tests/rejections/hidden_read_transition.cardlang,
                 tests/rejections/hidden_read_rule.cardlang,
                 tests/rejections/hidden_read_blind_draw.cardlang,
                 tests/rejections/implicit_pool_hidden_from_owner.cardlang,
                 tests/rejections/hidden_read_outcome_payload.cardlang. The swap
                 proof's own witnesses, and the ones refused before it runs:
                 tests/openspiel_ready/test_blind_decisions.py. The verdicts'
                 invariance under hoisting into a `let`:
                 tests/test_hidden_reads_let_invariance.py; under wrapping in
                 `as`: tests/test_hidden_reads_as_invariance.py. A chosen
                 movement's deciding and evaluating seats:
                 `cardlang.resolve.CHOSEN_MOVEMENT_SEATS`, pinned against a run.
does not prove:  that a seat's knowledge beyond its projections is credited:
                 the check judges the declared projection, never the observed
                 history, so a seat that passed a card or saw one revealed is
                 still refused a read of it. That a Primitive reads its
                 declared zones at no more than identity: a `reads` clause
                 names a zone and no need, and the check judges it at identity.
                 That a delegated decision's pool is visible to its decider:
                 `play_source_for` is accepted statically, and the runtime
                 Owner Guard `delegation.check_decider_sees` refuses it per
                 delegated decision.
"""

from __future__ import annotations

import dataclasses
import inspect
import re
import typing
from collections.abc import Callable
from pathlib import Path

import pytest

from cardlang import resolve as R
from cardlang.ast import nodes as n
from cardlang.builtins import functions as F
from cardlang.diagnostics import DiagnosticError
from cardlang.parse import parse_library
from cardlang.pipeline import check_dsl, check_source
from cardlang.stdlib import zones as Z

_REPO = Path(__file__).resolve().parent.parent


class _Accepted(AssertionError):
    """A refusal cell's game checked clean."""


# ---------------------------------------------------------------------------
# The expected column's sources: docs/library.md and decisions.md, never the
# code under test.
# ---------------------------------------------------------------------------


def _lattice() -> tuple[str, ...]:
    """decisions.md's lattice line, least informative first."""
    text = (_REPO / "docs" / "decisions.md").read_text()
    match = re.search(r"^identity > [a-z_ >]+$", text, re.MULTILINE)
    assert match is not None, "decisions.md no longer states the lattice line"
    return tuple(reversed(match.group(0).split(" > ")))


_LATTICE = _lattice()

# The operator's ruling (docs/plans/2026-09-23-hidden-read-wall.md,
# "What the wall judges by"): each need maps to the least level that reveals
# it, and membership is judged at identity. Order is not a level.
_NEED_LEVEL = {"existence": "existence_only", "count": "count_only", "identity": "identity"}

_ROW = re.compile(
    r"^type (?P<name>\w+)(?:<(?P<param>[^>]*)>)?\s*=\s*Zone<[^{]*\{\s*composition:\s*(?P<comp>[^,}]+(?:,[^,}]+)?)"
)


def _library_md() -> dict[str, tuple[str, str, str]]:
    """type -> (owner projection, others projection, index kind), read from
    docs/library.md's `composition:` rows. Index kind: `player`, `team`,
    `position`, or `none` for an unindexed type."""
    rows: dict[str, tuple[str, str, str]] = {}
    for line in (_REPO / "docs" / "library.md").read_text().splitlines():
        m = _ROW.match(line.strip())
        if m is None:
            continue
        owner = others = ""
        for clause in m.group("comp").split(","):
            if " to " not in clause:
                continue  # `ordered: yes`, `capacity: 1`
            level, _, who = clause.strip().partition(" to ")
            who = who.strip()
            if who == "all":
                owner = others = level
            elif who == "others":
                others = level
            else:
                owner = level
        param = (m.group("param") or "").lower()
        kind = (
            "none" if not param
            else "position" if "position" in param
            else "team" if "team" in param
            else "player"
        )
        rows[m.group("name")] = (owner, others, kind)
    return rows


_TYPES = _library_md()


def _sees(level: str, need: str, zone_type: str) -> bool:
    if need == "order":
        # The operator's order ruling: face up to every seat.
        owner, others, _ = _TYPES[zone_type]
        return owner == others == "identity"
    return _LATTICE.index(level) >= _LATTICE.index(_NEED_LEVEL[need])


# ---------------------------------------------------------------------------
# Pins on the tables.
# ---------------------------------------------------------------------------


def test_projection_levels_are_the_decisions_lattice() -> None:
    """`PROJECTION_LEVELS` is decisions.md's lattice, in its order.

    red under: swap `count_only` and `existence_only` in `PROJECTION_LEVELS`."""
    assert Z.PROJECTION_LEVELS == _LATTICE


def test_every_declared_projection_is_a_level() -> None:
    """Every `ZONE_PROJECTIONS` value is a member of the lattice, so `reveals`
    can compare it.

    red under: declare `Muck` as `ZoneVisibility("hidden", "hidden")`."""
    stray = {
        (name, level)
        for name, vis in Z.ZONE_PROJECTIONS.items()
        for level in (vis.owner, vis.others)
        if level not in Z.PROJECTION_LEVELS
    }
    assert not stray


def test_library_md_and_the_projection_table_agree() -> None:
    """The two definition sites of a type's projection -- the kernel table
    and library.md's `composition:` rows -- state the same projection for
    every library zone type, so the grid's expected column (read from
    library.md) and the check (read from the table) judge the same types.

    red under: declare `Hand`'s others column `identity` in `ZONE_PROJECTIONS`."""
    for name in Z.LIBRARY_ZONE_TYPES:
        assert name in _TYPES, f"docs/library.md has no `composition:` row for {name}"
        owner, others, _ = _TYPES[name]
        vis = Z.ZONE_PROJECTIONS[name]
        assert (vis.owner, vis.others) == (owner, others), name


def test_reveals_answers_every_need_for_every_type() -> None:
    """`reveals` is total over the read needs and the library zone types, and
    refuses a need outside `READ_NEEDS`.

    red under: drop `count` from `_NEED_LEVEL` in `cardlang/stdlib/zones.py`."""
    for name in Z.LIBRARY_ZONE_TYPES:
        for need in Z.READ_NEEDS:
            for owner in (True, False):
                Z.reveals(name, need, owner)
    with pytest.raises(KeyError):
        Z.reveals("Hand", "peek", True)


def test_the_builtin_zone_read_partition_is_total() -> None:
    """Every Builtin is classified by how it reads zones: through its
    arguments, not at all, or implicitly. The three sets partition
    `BUILTIN_CALL_FUNCS`, and every Arrival Record call reads its arguments.

    red under: delete `team_of` from `BUILTIN_READS_NOTHING`."""
    args = set(F.BUILTIN_ARGUMENT_READS)
    nothing = set(F.BUILTIN_READS_NOTHING)
    implicit = set(F.BUILTIN_IMPLICIT_READS)
    assert not (args & nothing) and not (args & implicit) and not (nothing & implicit)
    assert args | nothing | implicit == set(F.BUILTIN_CALL_FUNCS), (
        f"unclassified: {sorted(set(F.BUILTIN_CALL_FUNCS) - args - nothing - implicit)}; "
        f"stale: {sorted((args | nothing | implicit) - set(F.BUILTIN_CALL_FUNCS))}"
    )
    assert set(F.ARRIVAL_RECORD_CALLS) <= args
    assert set(F.BUILTIN_ARGUMENT_READS.values()) <= set(Z.READ_NEEDS)
    assert {need for _, need in F.BUILTIN_IMPLICIT_READS.values()} <= set(Z.READ_NEEDS)


_EXPR_KINDS = set(typing.get_args(n.Expr))


def _admits_expr(hint: object) -> bool:
    if hint in _EXPR_KINDS:
        return True
    return any(_admits_expr(arg) for arg in typing.get_args(hint))


def _expression_positions() -> set[tuple[type, str]]:
    """Every expression-bearing field of every AST dataclass, less the fields
    of the expression nodes themselves (part of the position their expression
    sits in), `Choose` excepted."""
    out: set[tuple[type, str]] = set()
    for _, cls in inspect.getmembers(n, inspect.isclass):
        if not dataclasses.is_dataclass(cls) or cls.__module__ != n.__name__:
            continue
        if cls in _EXPR_KINDS and cls is not n.Choose:
            continue
        hints = typing.get_type_hints(cls, vars(n))
        for f in dataclasses.fields(cls):
            if _admits_expr(hints[f.name]):
                out.add((cls, f.name))
    return out


def test_every_expression_position_is_bucketed() -> None:
    """The position table is total over the AST: a new expression-bearing
    field fails here until it is classified, and a row naming no field fails
    as stale.

    red under: delete the `(n.IfStmt, "cond")` row of `HIDDEN_READ_POSITIONS`."""
    derived = _expression_positions()
    table = set(R.HIDDEN_READ_POSITIONS)
    assert derived == table, (
        f"unbucketed: {sorted((c.__name__, f) for c, f in derived - table)}; "
        f"stale: {sorted((c.__name__, f) for c, f in table - derived)}"
    )
    for kind, why in R.HIDDEN_READ_POSITIONS.values():
        assert kind in R.READ_POSITION_KINDS and why


# ---------------------------------------------------------------------------
# The game every cell is built from.
# ---------------------------------------------------------------------------

_BASE = """
game Probe {{
  players: 3
  cards: standard52
  max_length: 200
  ranking: aces high
  {teams}
  positions {{ column : 1..3 }}
  zones {{
    deck : Deck
    hand[player] : Hand<player>
    pile : Discard
    won[player] : PlayerPile<player>
    {zone}
  }}
  {primitives}
  state {{ score[player] : Integer = 0  leader : Player = 0  flag : Boolean = false }}
  phase setup {{ shuffle deck  deal 5 cards from deck to each hand }}
  {body}
  winner: highest score
}}
{defs}
"""

_TEAMS = "teams: [[0, 2], [1]]"
_TRICK = (
    "round play_to_trick from 0 over all players source hand into pile "
    "winner highest_trump_or_led_suit"
)
_OFFER_TAKE = "phase play { offer to 0 one of [take] }"


def _game(
    body: str, defs: str = "", zone: str = "", teams: bool = False, primitives: str = ""
) -> str:
    return _BASE.format(
        body=body,
        defs=defs,
        zone=zone,
        teams=_TEAMS if teams else "",
        primitives=primitives,
    )


def _full_text(err: DiagnosticError) -> str:
    return "\n".join([str(err), *getattr(err, "__notes__", [])])


def _check(source: str, refuse: str | None) -> None:
    """Accept the game, or refuse it with a located diagnostic carrying
    `refuse`. A refusal cell whose game checks clean raises `_Accepted`."""
    if refuse is None:
        check_dsl(source, "reads.cardlang")
        return
    try:
        check_dsl(source, "reads.cardlang")
    except DiagnosticError as err:
        text = _full_text(err)
        assert err.diagnostic.span is not None, "a refusal must be located"
        assert refuse in text, text
        return
    raise _Accepted(f"accepted; expected a refusal naming {refuse!r}")


def _cell(
    cell_id: str,
    *values: object,
    refuse: str | None,
    xfail: str | None = None,
    raises: type[Exception] = _Accepted,
) -> object:
    """One grid cell. `xfail` names the reason a refusal cell is a strict
    expected failure, constrained to `raises`: by default the one failure a
    missing check produces, the game checking clean."""
    marks = (
        [pytest.mark.xfail(strict=True, raises=raises, reason=xfail)]
        if xfail is not None
        else []
    )
    return pytest.param(*values, refuse, id=cell_id, marks=marks)


# The fragments each verdict's message carries.
_EVERY_SEAT = "every seat can check"
_DECIDER = "must be able to check it"
_BLIND = "pick by position"


# ---------------------------------------------------------------------------
# The verdict grid: position x need x zone type x relation.
# ---------------------------------------------------------------------------

# How a read of zone reference `z` at each need spells, as a Boolean and as
# an Integer. Membership is the identity read; `top_of` the order read.
_BOOL: dict[str, Callable[[str], str]] = {
    "existence": lambda z: f"{z} is not empty",
    "count": lambda z: f"(number of cards in {z}) > 1",
    "identity": lambda z: f"(2 of clubs) in {z}",
    "order": lambda z: f"suit_of(top_of({z})) is hearts",
}
_INT: dict[str, Callable[[str], str]] = {
    "existence": lambda z: f"if {z} is empty then 1 else 2",
    "count": lambda z: f"number of cards in {z}",
    "identity": lambda z: f"number of cards in {z} where card.suit is hearts",
    "order": lambda z: f"rank_value(top_of({z}))",
}
_GATE_BODY = "{ for each player p: move chosen 1 card from hand[p] to pile }"


def _rule(clauses: str) -> tuple[str, str]:
    return (
        "phase play { active_rules: [Probed] " + _TRICK + " }",
        "rule Probed { constrains: play_to_trick " + clauses + " }",
    )


def _take(when: str = "", effect: str = "move chosen 1 card from hand to pile") -> tuple[str, str]:
    guard = f"when: {when} " if when else ""
    return _OFFER_TAKE, "move_type take { " + guard + "effect { " + effect + " } }"


# (position label, table row) -> (needs it can carry, builder of (body, defs)
# from the need and the zone reference). The labels split the phase
# qualifier into its two kinds (`PhaseQualifier.kind`).
_Builder = Callable[[str, str], tuple[str, str]]
_POSITIONS: dict[str, tuple[tuple[type, str], tuple[str, ...], _Builder]] = {
    "phase-when": (
        (n.PhaseQualifier, "expr"),
        Z.READ_NEEDS,
        lambda need, z: (f"phase play when {_BOOL[need](z)} {_GATE_BODY}", ""),
    ),
    "phase-repeat-until": (
        (n.PhaseQualifier, "expr"),
        Z.READ_NEEDS,
        lambda need, z: (f"phase play repeat until {_BOOL[need](z)} {_GATE_BODY}", ""),
    ),
    "transition": (
        (n.MoveEvent, "where"),
        Z.READ_NEEDS,
        lambda need, z: (
            "phase play { mode open { transition_to: closed when play_to_trick where "
            f"{_BOOL[need](z)} }} mode closed {{ }} {_TRICK} }}",
            "",
        ),
    ),
    "move-when": (
        (n.MoveTypeDef, "when"),
        Z.READ_NEEDS,
        lambda need, z: _take(when=_BOOL[need](z)),
    ),
    "applies-when": (
        (n.AppliesWhen, "pred"),
        Z.READ_NEEDS,
        lambda need, z: _rule(
            f"applies_when: {_BOOL[need](z)} demands: cards in hand where card.suit is hearts "
            "if_impossible: hand"
        ),
    ),
    "demands": (
        (n.Demands, "expr"),
        Z.READ_NEEDS,
        lambda need, z: _rule(f"demands: cards in hand where {_BOOL[need](z)} if_impossible: hand"),
    ),
    "if-impossible": (
        (n.RuleDef, "if_impossible"),
        Z.READ_NEEDS,
        lambda need, z: _rule(
            "demands: cards in hand where card.suit is hearts "
            f"if_impossible: cards in hand where {_BOOL[need](z)}"
        ),
    ),
    "exempts": (
        (n.RuleDef, "exempts"),
        Z.READ_NEEDS,
        lambda need, z: _rule(
            "demands: cards in hand where card.suit is hearts if_impossible: hand "
            f"exempts: cards in hand where {_BOOL[need](z)}"
        ),
    ),
    "choose-lo": (
        (n.Choose, "lo"),
        Z.READ_NEEDS,
        lambda need, z: _take(effect=f"score[actor] := choose integer in ({_INT[need](z)}) .. 13"),
    ),
    "choose-hi": (
        (n.Choose, "hi"),
        Z.READ_NEEDS,
        lambda need, z: _take(
            effect=f"score[actor] := choose integer in 0 .. ({_INT[need](z)}) up to 13"
        ),
    ),
    "choose-excluding": (
        (n.Choose, "excluding"),
        Z.READ_NEEDS,
        lambda need, z: _take(
            effect=f"score[actor] := choose integer in 0 .. 13 excluding ({_INT[need](z)})"
        ),
    ),
    "chosen-amount": (
        (n.Transfer, "amount"),
        Z.READ_NEEDS,
        lambda need, z: _take(effect=f"move chosen ({_INT[need](z)}) cards from hand to pile"),
    ),
    # The pool IS the menu: a chosen source is read at identity and nothing else.
    "chosen-source": (
        (n.Transfer, "source"),
        ("identity",),
        lambda need, z: _take(effect=f"move chosen 1 card from {z} to pile"),
    ),
    "chosen-where": (
        (n.Transfer, "where"),
        Z.READ_NEEDS,
        lambda need, z: _take(effect=f"move chosen 1 card from hand where {_BOOL[need](z)} to pile"),
    ),
    "chosen-destination": (
        (n.Transfer, "dest"),
        Z.READ_NEEDS,
        lambda need, z: _take(
            effect=f"move chosen 1 card from hand to won[if {_BOOL[need](z)} then actor else actor]"
        ),
    ),
}


def test_the_grid_positions_are_the_judged_rows() -> None:
    """The grid's positions are exactly the table's judged rows: a row moved
    into or out of the two judged kinds changes the grid, or fails here.

    red under: move `(n.RuleDef, "exempts")` to `READ_POSITION_OUTSIDE`."""
    judged = {
        key
        for key, (kind, _) in R.HIDDEN_READ_POSITIONS.items()
        if kind in (R.READ_POSITION_NO_SEAT, R.READ_POSITION_SEAT, R.READ_POSITION_CHOSEN)
    }
    assert {row for row, _, _ in _POSITIONS.values()} == judged


def _zone_decl(zone_type: str) -> tuple[str, bool]:
    """The probe zone's declaration, and whether it needs `teams:`."""
    kind = _TYPES[zone_type][2]
    if kind == "none":
        return f"probe : {zone_type}", False
    if kind == "position":
        return f"probe[column] : {zone_type}<column>", False
    return f"probe[{kind}] : {zone_type}<{kind}>", kind == "team"


def _zone_ref(zone_type: str, relation: str) -> str:
    kind = _TYPES[zone_type][2]
    if kind in ("none",):
        return "probe"
    if kind == "position":
        return "probe[1]"
    seat = {"own": "actor", "other": "actor offset_by left", "any": "1"}[relation]
    return f"probe[team_of({seat})]" if kind == "team" else f"probe[{seat}]"


def _expected_accept(no_seat: bool, need: str, zone_type: str, relation: str) -> bool:
    owner, others, kind = _TYPES[zone_type]
    owned = kind in ("player", "team")
    if no_seat:
        return _sees(others, need, zone_type) and (not owned or _sees(owner, need, zone_type))
    if relation == "own":
        return _sees(owner, need, zone_type)
    return _sees(others, need, zone_type)


def _verdict_cells() -> list[object]:
    cells: list[object] = []
    for label, (row, needs, _) in _POSITIONS.items():
        no_seat = R.HIDDEN_READ_POSITIONS[row][0] == R.READ_POSITION_NO_SEAT
        for need in needs:
            for zone_type in sorted(Z.LIBRARY_ZONE_TYPES):
                owned = _TYPES[zone_type][2] in ("player", "team")
                relations = ("any",) if no_seat else ("own", "other") if owned else ("any",)
                for relation in relations:
                    accept = _expected_accept(no_seat, need, zone_type, relation)
                    refuse = (
                        None if accept
                        else _EVERY_SEAT if no_seat
                        else _BLIND if label == "chosen-source"
                        else _DECIDER
                    )
                    cells.append(
                        _cell(
                            f"{label}-{need}-{zone_type}-{relation}",
                            label,
                            need,
                            zone_type,
                            relation,
                            refuse=refuse,
                        )
                    )
    return cells


_VERDICT_CELLS = _verdict_cells()


@pytest.mark.parametrize("label,need,zone_type,relation,refuse", _VERDICT_CELLS)
def test_a_read_is_judged_by_its_positions_verdict(
    label: str, need: str, zone_type: str, relation: str, refuse: str | None
) -> None:
    """Each judged position, each need, each library zone type and each
    relation of the read's index to the deciding seat, direct route."""
    _, _, build = _POSITIONS[label]
    body, defs = build(need, _zone_ref(zone_type, relation))
    decl, teams = _zone_decl(zone_type)
    _check(_game(body, defs, zone=decl, teams=teams), refuse)


def test_the_verdict_grid_commands_both_outcomes() -> None:
    """If every verdict cell expected the same outcome the grid would prove
    nothing, and a broken expected column could make that true silently.

    red under: make `_sees` return True."""
    outcomes = {cell.values[-1] is None for cell in _VERDICT_CELLS}  # type: ignore[attr-defined]
    assert outcomes == {True, False}


# A chosen movement's destination zone is named, not read: the seat is told
# where the card lands, and learns nothing of the cards already there. Every
# library zone type, as another seat's instance where the type is owned.
def _destination_cells() -> list[object]:
    cells = []
    for zone_type in sorted(Z.LIBRARY_ZONE_TYPES):
        decl, teams = _zone_decl(zone_type)
        ref = _zone_ref(zone_type, "other")
        cells.append(
            _cell(
                f"destination-{zone_type}",
                *_take(effect=f"move chosen 1 card from hand to {ref}"),
                decl, teams, refuse=None,
            )
        )
    return cells


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _destination_cells())
def test_a_destination_zone_is_named_not_read(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """The destination zone of a chosen movement, of every library type,
    whoever owns it, is accepted: only its index is read."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# The relation grid: every way the deciding seat is proven, over a concealed
# hand (`Hand`: identity to its owner, a count to the others).
# ---------------------------------------------------------------------------

_BUMP = "move_type bump { effect { leader := 1 } }"

# cell -> (body, defs, zone, teams, the refusal's fragment or None). Each
# outcome is the ruling's (docs/plans/2026-09-23-hidden-read-wall.md,
# "What the wall judges by").
_RELATIONS: dict[str, tuple[str, str, str, bool, str | None]] = {
    # Bare-family sugar is the acting seat's own instance by construction.
    "bare-family": (*_take(effect="move chosen 1 card from hand to pile"), "", False, None),
    # The `actor` pronoun and the binders `_ActorAliases` derives.
    "actor-pronoun": (*_take(effect="move chosen 1 card from hand[actor] to pile"), "", False, None),
    "for-each-binder": (
        "phase play { for each player p: move chosen 1 card from hand[p] to pile }",
        "", "", False, None,
    ),
    "turns-binder": (
        "phase play { turns t from 0 over all players until flag "
        "{ move chosen 1 card from hand[t] to pile  flag := true } }",
        "", "", False, None,
    ),
    "each-simultaneously": (
        "phase play { each player simultaneously: move chosen 1 card from hand[player] to won[player] }",
        "", "", False, None,
    ),
    "as-binder": (
        "phase play { for each player p: as p { move chosen 1 card from hand[p] to pile } }",
        "", "", False, None,
    ),
    "let-alias": (
        *_take(effect="let me = actor  move chosen 1 card from hand[me] to pile"),
        "", False, None,
    ),
    "procedure-argument": (
        _OFFER_TAKE,
        "move_type take { effect { run grab(actor) } }\n"
        "procedure grab(x : Player) { move chosen 1 card from hand[x] to pile }",
        "", False, None,
    ),
    # `team_of` of the deciding seat, for a team-indexed zone.
    "team-of-decider": (
        *_take(effect="move chosen 1 card from secret[team_of(actor)] to pile"),
        "secret[team] : Hand<team>", True, None,
    ),
    "team-of-another": (
        *_take(effect="move chosen 1 card from secret[team_of(actor offset_by left)] to pile"),
        "secret[team] : Hand<team>", True, _BLIND,
    ),
    # A State Variable naming the decider in `as X`, provided no path from the
    # `as` entry to the read writes X.
    "as-state-variable": (
        "phase play { as leader { move chosen 1 card from hand[leader] to pile } }",
        "", "", False, None,
    ),
    "as-state-variable-written-before": (
        "phase play { as leader { leader := 1  move chosen 1 card from hand[leader] to pile } }",
        "", "", False, _BLIND,
    ),
    "as-state-variable-written-after": (
        "phase play { as leader { move chosen 1 card from hand[leader] to pile  leader := 1 } }",
        "", "", False, None,
    ),
    "as-state-variable-written-in-sibling-branch": (
        "phase play { as leader { if flag { leader := 1 } "
        "else { move chosen 1 card from hand[leader] to pile } } }",
        "", "", False, None,
    ),
    "as-state-variable-written-on-the-branch": (
        "phase play { as leader { if flag { leader := 1  "
        "move chosen 1 card from hand[leader] to pile } } }",
        "", "", False, _BLIND,
    ),
    "as-state-variable-written-later-in-a-loop": (
        "phase play { as leader { repeat until flag { "
        "move chosen 1 card from hand[leader] to pile  leader := 1  flag := true } } }",
        "", "", False, _BLIND,
    ),
    "as-state-variable-written-by-an-offered-move": (
        "phase play { as leader { offer to leader one of [bump]  "
        "move chosen 1 card from hand[leader] to pile } }",
        _BUMP, "", False, _BLIND,
    ),
    # Another seat, and an index computed from the decider.
    "another-seat": (*_take(effect="move chosen 1 card from hand[1] to pile"), "", False, _BLIND),
    "computed-seat": (
        *_take(effect="move chosen 1 card from hand[actor offset_by left] to pile"),
        "", False, _BLIND,
    ),
    "winner-pronoun": (*_take(when="(2 of clubs) in hand[winner]"), "", False, _DECIDER),
    # A chosen movement `to each` decides at each receiving seat; its source
    # is evaluated once, in the outer context.
    "to-each-public-pool": (
        "phase play { as leader { move chosen 1 card from pile to each won } }",
        "", "", False, None,
    ),
    "to-each-concealed-pool": (
        "phase play { for each player p: move chosen 1 card from hand[p] to each won }",
        "", "", False, _BLIND,
    ),
    "to-each-bare-family": (
        "phase play { for each player p: move chosen 1 card from hand to each won }",
        "", "", False, _BLIND,
    ),
    # A literal seat `as` binds, read at the same literal.
    "as-literal-seat": (
        "phase play { as 0 { move chosen 1 card from hand[0] to pile } }",
        "", "", False, None,
    ),
    "as-literal-seat-another": (
        "phase play { as 0 { move chosen 1 card from hand[1] to pile } }",
        "", "", False, _BLIND,
    ),
    # A delegated decision: a Shadow cell whose Owner is the runtime's
    # `delegation.check_decider_sees`.
    "delegated-pool": (
        "phase play { " + _TRICK + " }",
        "function chooser_for(p : Player) = if p is 1 then 0 else p\n"
        "function play_source_for(p : Player) = if p is 1 then shown[p] else hand[p]",
        "shown[player] : PublicHand<player>", False, None,
    ),
    # A delegated decision's rule clause read at the attributed seat: the
    # decider is `chooser_for(actor)`, not `actor`.
    "delegated-rule-reads-the-attributed-hand": (
        "phase play { active_rules: [Probed] " + _TRICK + " }",
        "function chooser_for(p : Player) = if p is 1 then 0 else p\n"
        "function play_source_for(p : Player) = if p is 1 then shown[p] else hand[p]\n"
        "rule Probed { constrains: play_to_trick applies_when: (2 of clubs) in hand[actor] "
        "demands: cards in hand where card.suit is hearts if_impossible: hand }",
        "shown[player] : PublicHand<player>", False, _DECIDER,
    ),
}

# cell -> why it is a strict expected failure.
_RELATION_XFAILS: dict[str, str] = {
    "delegated-rule-reads-the-attributed-hand": (
        "a rule clause under Delegated Play is judged against the attributed "
        "seat, not its decider (issue #758)"
    ),
}


def _relation_cells() -> list[object]:
    return [
        _cell(
            cell_id, body, defs, zone, teams, refuse=refuse, xfail=_RELATION_XFAILS.get(cell_id)
        )
        for cell_id, (body, defs, zone, teams, refuse) in _RELATIONS.items()
    ]


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _relation_cells())
def test_the_deciding_seat_is_proven_statically(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """A concealed hand read at a chosen movement's source (or a `when:`) is
    accepted exactly where the index is statically the deciding seat."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# The route grid: every route a read can take, under both verdicts, over a
# concealed hand read at identity and over a face-up pile.
# ---------------------------------------------------------------------------

_GIN = "primitives { gin_deadwood(p : Player) : Integer reads hand[p] }"
_GIN_FAMILY = "primitives { gin_deadwood(p : Player) : Integer reads hand }"
_PEEK = "function peek(p : Player) = (2 of clubs) in hand[p]"
_PEEK_PILE = "function peek_pile(p : Player) = (2 of clubs) in won[p]"

# cell -> (body, defs, primitives, library, accepted, fragment when refused).
_ROUTES: dict[str, tuple[str, str, str, str, bool, str]] = {
    # Direct.
    "gate-direct-concealed": (
        f"phase play when (2 of clubs) in hand[1] {_GATE_BODY}", "", "", "", False, _EVERY_SEAT,
    ),
    "gate-direct-public": (
        f"phase play when (2 of clubs) in won[1] {_GATE_BODY}", "", "", "", True, "",
    ),
    "gate-direct-count": (
        f"phase play when (number of cards in hand[1]) > 2 {_GATE_BODY}", "", "", "", True, "",
    ),
    # Through a `let` the qualifier sees (a phase body's `let` scopes over its
    # nested phases' qualifiers).
    "gate-let": (
        "phase outer { let held = (2 of clubs) in hand[1]  "
        f"phase inner when held {_GATE_BODY} }}",
        "", "", "", False, _EVERY_SEAT,
    ),
    "gate-let-public": (
        "phase outer { let held = (2 of clubs) in won[1]  "
        f"phase inner when held {_GATE_BODY} }}",
        "", "", "", True, "",
    ),
    # Through a designer function, and a library's.
    "gate-function": (f"phase play when peek(1) {_GATE_BODY}", _PEEK, "", "", False, _EVERY_SEAT),
    "gate-function-public": (
        f"phase play when peek_pile(1) {_GATE_BODY}", _PEEK_PILE, "", "", True, "",
    ),
    "gate-library-function": (
        f"phase play when lib_peek(1, 2 of clubs) {_GATE_BODY}", "", "", "lib", False, _EVERY_SEAT,
    ),
    # Through a Primitive's declared `reads`.
    "gate-primitive": (
        f"phase play when gin_deadwood(1) > 3 {_GATE_BODY}", "", _GIN, "", False, _EVERY_SEAT,
    ),
    # Through the Builtin partition's rows.
    "gate-builtin-implicit": (
        f"phase play when player_holding(2 of clubs) is 1 {_GATE_BODY}",
        "", "", "", False, _EVERY_SEAT,
    ),
    "gate-builtin-argument-top": (
        f"phase play when suit_of(top_of(won[1])) is hearts {_GATE_BODY}", "", "", "", True, "",
    ),
    "gate-builtin-argument-bottom": (
        f"phase play when suit_of(bottom_of(deck)) is hearts {_GATE_BODY}",
        "", "", "", False, _EVERY_SEAT,
    ),
    "gate-builtin-argument-suit-of-zone": (
        f"phase play when suit_of(deck) is hearts {_GATE_BODY}", "", "", "", False, _EVERY_SEAT,
    ),
    "gate-builtin-reads-nothing": (
        f"phase play when rank_value(2 of clubs) > 3 {_GATE_BODY}", "", "", "", True, "",
    ),
    # Bare-family sugar where no seat decides: the acting seat's instance,
    # and no seat is the acting one.
    "gate-bare-family": (
        f"phase play when (2 of clubs) in hand {_GATE_BODY}", "", "", "", False, _EVERY_SEAT,
    ),
    # The pronouns: the played card is public.
    "transition-played-card": (
        "phase play { mode open { transition_to: closed when play_to_trick where "
        "action.card.suit is hearts } mode closed { } " + _TRICK + " }",
        "", "", "", True, "",
    ),
    # A rule template argument is a suit literal, so it reads nothing: the
    # template guard refuses any other argument before this check runs.
    "rule-argument": (
        "phase play { active_rules: [Probed(suit_of(top_of(deck)))] " + _TRICK + " }",
        "rule Probed(s : Suit) { constrains: play_to_trick applies_when: s is hearts "
        "demands: cards in hand where card.suit is hearts if_impossible: hand }",
        "", "", False, "must be a suit literal",
    ),
    # Seat-deciding routes.
    "when-function-own": (
        _OFFER_TAKE, _PEEK + "\n" + _take(when="peek(actor)")[1], "", "", True, "",
    ),
    "when-function-other": (
        _OFFER_TAKE,
        _PEEK + "\n" + _take(when="peek(actor offset_by left)")[1],
        "", "", False, _DECIDER,
    ),
    "when-library-function-other": (
        *_take(when="lib_peek(actor offset_by left, 2 of clubs)"), "", "lib", False, _DECIDER,
    ),
    "when-primitive-own": (*_take(when="gin_deadwood(actor) > 3"), _GIN, "", True, ""),
    "when-primitive-other": (
        *_take(when="gin_deadwood(actor offset_by left) > 3"), _GIN, "", False, _DECIDER,
    ),
    "when-primitive-whole-family": (
        *_take(when="gin_deadwood(actor) > 3"), _GIN_FAMILY, "", False, _DECIDER,
    ),
    "when-builtin-implicit": (
        *_take(when="player_holding(2 of clubs) is actor"), "", "", False, _DECIDER,
    ),
    "when-let-in-effect": (
        *_take(effect="let held = (2 of clubs) in hand[actor offset_by left]  "
               "move chosen 1 card from hand where held to pile"),
        "", "", False, _DECIDER,
    ),
    "when-let-own": (
        *_take(effect="let held = (2 of clubs) in hand[actor]  "
               "move chosen 1 card from hand where held to pile"),
        "", "", True, "",
    ),
    "source-procedure-other": (
        _OFFER_TAKE,
        "move_type take { effect { run grab(actor offset_by left) } }\n"
        "procedure grab(x : Player) { move chosen 1 card from hand[x] to pile }",
        "", "", False, _BLIND,
    ),
    "source-let": (
        *_take(effect="let h = hand[1]  move chosen 1 card from h to pile"),
        "", "", False, _BLIND,
    ),
    "amount-produce-payload": (
        "phase deal -> outcome { hint(Integer) } "
        "{ produce hint(number of cards in hand[1] where card.suit is hearts) } "
        "phase play { deal produces: hint(k) "
        "{ for each player p: move chosen (k) cards from hand[p] to pile } }",
        "", "", "", False, _DECIDER,
    ),
    "choose-nested-in-an-assignment": (
        *_take(effect="score[actor] := choose integer in 0 .. (number of cards in hand[1] "
               "where card.suit is hearts) up to 13"),
        "", "", False, _DECIDER,
    ),
}

_LIBRARY = """
library lib {
  requires { hand[player] : Hand<player> }
  function lib_peek(p : Player, c : Card) = c in hand[p]
}
"""


def _route_cells() -> list[object]:
    return [
        _cell(cell_id, body, defs, prims, lib, refuse=None if ok else fragment)
        for cell_id, (body, defs, prims, lib, ok, fragment) in _ROUTES.items()
    ]


@pytest.mark.parametrize("body,defs,primitives,library,refuse", _route_cells())
def test_every_route_a_read_takes_is_followed(
    body: str,
    defs: str,
    primitives: str,
    library: str,
    refuse: str | None,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A read reached through a `let`, a designer or library function, a
    Primitive's `reads`, a Builtin, a procedure, a rule argument or a phase
    outcome is judged as if written in place."""
    uses = ""
    if library:
        lib = parse_library(_LIBRARY, "lib.cardlang")
        monkeypatch.setattr("cardlang.resolve.library_names", lambda: frozenset({"lib"}))
        monkeypatch.setattr("cardlang.resolve.load_library", lambda name: lib)
        uses = "uses lib\n"
    source = _game(body, defs, primitives=primitives).replace(
        "game Probe {", "game Probe {\n  " + uses, 1
    )
    _check(source, refuse)


# ---------------------------------------------------------------------------
# Misuse probes (surface-totality audit, Step 2): the most plausible wrong
# sentences a designer writes, each refused loud with the fix named.
# ---------------------------------------------------------------------------

_PROBES: dict[str, tuple[str, str, str, str]] = {
    # No seat deciding.
    "showdown-gate-on-a-hand": (
        "phase showdown when any card in hand[0] where card.suit is spades "
        + _GATE_BODY,
        "", "", "announce",
    ),
    "hand-loop-on-the-muck": (
        "phase play repeat until (number of cards in muck) > 3 " + _GATE_BODY,
        "", "muck : Muck", "no seat",
    ),
    "transition-on-a-hand": (
        "phase play { mode closed_mode { transition_to: opened when play_to_trick where "
        "any card in hand[0] where card.suit is spades } mode opened { } " + _TRICK + " }",
        "", "", "`action.card`",
    ),
    "gate-through-a-function": (
        "phase play when holds_ace(1) " + _GATE_BODY,
        "function holds_ace(p : Player) = any card in hand[p] where card.rank is A",
        "", "holds_ace",
    ),
    "gate-on-the-stock-top": (
        "phase play when suit_of(top_of(deck)) is hearts " + _GATE_BODY,
        "", "", "order",
    ),
    # A seat deciding.
    "old-maid-blind-draw": (
        "phase play { as 0 { move chosen 1 card from hand[1] to hand[0] } }",
        "", "", "issue #756",
    ),
    "ask-only-what-they-hold": (
        _OFFER_TAKE.replace("take", "ask"),
        "move_type ask(target : Player, r : Rank) { when: target is not actor and "
        "(any card in hand[target] where card.rank is r) effect { } }",
        "", "hand[target]",
    ),
    "rule-on-the-next-hand": (
        "phase play { active_rules: [Probed] " + _TRICK + " }",
        "rule Probed { constrains: play_to_trick applies_when: "
        "(number of cards in hand[actor offset_by left] where card.suit is hearts) > 0 "
        "demands: cards in hand where card.suit is hearts if_impossible: hand }",
        "", "Probed",
    ),
    "amount-from-the-muck": (
        *_take(effect="move chosen (number of cards in muck) cards from hand to pile"),
        "muck : Muck", "`muck`",
    ),
    "bid-bounded-by-another-hand": (
        *_take(effect="score[actor] := choose integer in 0 .. (number of cards in "
               "hand[actor offset_by left] where card.rank is A) up to 13"),
        "", "choose",
    ),
    "as-leader-reassigned-first": (
        "phase play { as leader { leader := 2  move chosen 1 card from hand[leader] to pile } }",
        "", "", "is written",
    ),
}


def _probe_cells() -> list[object]:
    return [
        _cell(probe_id, body, defs, zone, fragment, refuse=fragment)
        for probe_id, (body, defs, zone, fragment) in _PROBES.items()
    ]


@pytest.mark.parametrize("body,defs,zone,fragment,refuse", _probe_cells())
def test_a_plausible_wrong_sentence_is_refused(
    body: str, defs: str, zone: str, fragment: str, refuse: str | None
) -> None:
    """Each misuse probe is refused in the checker's channel -- a located
    diagnostic -- naming what the designer should write instead."""
    _check(_game(body, defs, zone=zone), refuse)


# ---------------------------------------------------------------------------
# The implicit pools: a decision whose cards the kernel takes from a declared
# zone, with no designer expression to read. The zone's type must show its
# owner, the deciding seat, the cards in its own instance.
# ---------------------------------------------------------------------------

# The one chooser call site that fans out over the round forms.
_ROUND_SITE = "mechanics.run_decision_round"


def test_every_decision_point_names_its_pool() -> None:
    """Every chooser call site, the round site taken form by form, says where
    the cards it offers come from, so a new decision point is classified
    before a pool nothing checks can land.

    red under: delete the `ClimbRound` row of `DECISION_POOLS`."""
    from cardlang.runtime.delegation import DECISION_POINTS, FORM_CONSTRUCTS

    assert _ROUND_SITE in DECISION_POINTS
    derived = (set(DECISION_POINTS) - {_ROUND_SITE}) | set(FORM_CONSTRUCTS)
    assert set(R.DECISION_POOLS) == derived, (
        f"unclassified: {sorted(derived - set(R.DECISION_POOLS))}; "
        f"stale: {sorted(set(R.DECISION_POOLS) - derived)}"
    )
    assert set(R.DECISION_POOLS.values()) <= R.POOL_KINDS


_CLIMB = (
    "legal_moves: [play_combination] "
    "round climb play_combination from 0 over all players source hand into pile "
    "combinations bigtwo_lead_options follows bigtwo_follows until flag"
)
_PICK = "move_type pick(c : Card) { effect { } }"

# The pools the kernel builds from a declared zone, by `DECISION_POOLS` row,
# each probed through the game's `hand`. member -> (its row, body, defs).
_IMPLICIT_POOLS: dict[str, tuple[str, str, str]] = {
    "trick-source": ("TrickRound", "phase play { " + _TRICK + " }", ""),
    "climb-source": ("ClimbRound", "phase play { " + _CLIMB + " }", ""),
    "card-parameter-offered": ("execute._offer", _OFFER_TAKE.replace("take", "pick"), _PICK),
    "card-parameter-in-an-auction": (
        "AuctionRound",
        "phase play { round offering [pick] from 0 over all players until flag }",
        _PICK,
    ),
}

_OWN_POOL = "does not show its owner the cards in it"


def test_the_implicit_pools_are_the_declared_zone_rows() -> None:
    """The implicit-pool members are exactly the decision points whose pool is
    a declared zone.

    red under: move the `AuctionRound` row of `DECISION_POOLS` to `POOL_NONE`."""
    implicit = {
        row
        for row, kind in R.DECISION_POOLS.items()
        if kind in (R.POOL_FROM_ROUND_SOURCE, R.POOL_FROM_CARD_PARAMETERS)
    }
    assert {row for row, _, _ in _IMPLICIT_POOLS.values()} == implicit


def _implicit_pool_cells() -> list[object]:
    cells = []
    for member, (_, body, defs) in _IMPLICIT_POOLS.items():
        for zone_type in sorted(Z.LIBRARY_ZONE_TYPES):
            if not Z.LIBRARY_ZONE_TYPES[zone_type]:
                continue  # a per-seat pool is a zone family
            accept = _TYPES[zone_type][0] == "identity"
            cells.append(
                _cell(
                    f"{member}-{zone_type}", member, zone_type,
                    refuse=None if accept else _OWN_POOL,
                )
            )
    return cells


@pytest.mark.parametrize("member,zone_type,refuse", _implicit_pool_cells())
def test_an_implicit_pool_shows_its_decider_the_cards(
    member: str, zone_type: str, refuse: str | None
) -> None:
    """Each implicit pool, over every zone type a seat's `hand` can be
    declared as: accepted exactly where the type shows its owner the cards."""
    _, body, defs = _IMPLICIT_POOLS[member]
    source = _game(body, defs).replace(
        "hand[player] : Hand<player>", f"hand[player] : {zone_type}<player>"
    )
    _check(source, refuse)


# ---------------------------------------------------------------------------
# The indirections: every name the reader follows by value -- a `let`, an
# indexed `let`, a function's or a procedure's parameter, a phase outcome's
# payload -- judged at the seat that consumes it and whatever the order its
# producer is declared in, and an index proof reached through a `let`.
# ---------------------------------------------------------------------------

_HEARTS_OF = "number of cards in {z} where card.suit is hearts"
_HINT = "phase deal -> outcome { hint(Integer) } "

# cell -> (body, defs, zone, teams, the refusal's fragment or None).
_INDIRECTIONS: dict[str, tuple[str, str, str, bool, str | None]] = {
    # A value computed under one acting seat and consumed at another's
    # decision proves nothing the producing seat could see.
    "outcome-payload-consumed-by-another-seat": (
        _HINT + "{ as 1 { produce hint(" + _HEARTS_OF.format(z="hand[1]") + ") } } "
        "phase play { deal produces: hint(k) "
        "{ for each player p: move chosen (k) cards from hand[p] to pile } }",
        "", "", False, _DECIDER,
    ),
    "outcome-payload-public": (
        _HINT + "{ produce hint(" + _HEARTS_OF.format(z="pile") + ") } "
        "phase play { deal produces: hint(k) "
        "{ for each player p: move chosen (k) cards from hand[p] to pile } }",
        "", "", False, None,
    ),
    "let-consumed-in-a-nested-seat": (
        "phase play { for each player p: as p { let k = " + _HEARTS_OF.format(z="hand[p]")
        + "  as 0 { move chosen (k) cards from hand[0] to pile } } }",
        "", "", False, _DECIDER,
    ),
    "let-consumed-by-the-same-seat": (
        "phase play { for each player p: as p { let k = " + _HEARTS_OF.format(z="hand[p]")
        + "  move chosen (k) cards from hand[p] to pile } }",
        "", "", False, None,
    ),
    "let-consumed-by-the-same-seat-moving-a-public-pile": (
        "phase play { for each player p: as p { let k = " + _HEARTS_OF.format(z="hand[p]")
        + "  move chosen (k) cards from pile to won[p] } }",
        "", "", False, None,
    ),
    "indexed-let-consumed-in-a-nested-seat": (
        "phase play { for each player p: as p { let k[q] = " + _HEARTS_OF.format(z="hand[q]")
        + "  as 0 { move chosen (k[p]) cards from hand[0] to pile } } }",
        "", "", False, _DECIDER,
    ),
    "procedure-argument-consumed-in-a-nested-seat": (
        "phase play { for each player p: as p { run give(" + _HEARTS_OF.format(z="hand[p]") + ") } }",
        "procedure give(k : Integer) { as 0 { move chosen (k) cards from hand[0] to pile } }",
        "", False, _DECIDER,
    ),
    "function-argument-read-at-the-call": (
        "phase play { for each player p: as p { move chosen (cnt(p)) cards from hand[p] to pile } }",
        "function cnt(q : Player) = " + _HEARTS_OF.format(z="hand[q]"),
        "", False, None,
    ),
    # A consumer whose producer is declared after it: an `after_each` runs
    # after the body, so it may consume a child outcome declared later.
    "after-each-consumes-a-later-outcome": (
        "phase loop repeat until flag { after_each { prod produces: hint(k) "
        "{ for each player p: move chosen (k) cards from hand[p] to pile } } "
        "phase prod -> outcome { hint(Integer) } { produce hint("
        + _HEARTS_OF.format(z="hand[1]") + ") } flag := true }",
        "", "", False, _DECIDER,
    ),
    "after-each-consumes-a-later-public-outcome": (
        "phase loop repeat until flag { after_each { prod produces: hint(k) "
        "{ for each player p: move chosen (k) cards from hand[p] to pile } } "
        "phase prod -> outcome { hint(Integer) } { produce hint("
        + _HEARTS_OF.format(z="pile") + ") } flag := true }",
        "", "", False, None,
    ),
    # A destination's index is read even where its zone is only named, and
    # through a `let` as written in place.
    "destination-index-reads-concealed-cards": (
        *_take(effect="move chosen 1 card from hand to won[player_holding(2 of clubs)]"),
        "", False, _DECIDER,
    ),
    "destination-through-a-let-index-reads-concealed-cards": (
        *_take(effect="let dst = won[player_holding(2 of clubs)]  "
               "move chosen 1 card from hand to dst"),
        "", False, _DECIDER,
    ),
    "destination-through-a-let-names-another-hand": (
        *_take(effect="let dst = hand[actor offset_by left]  move chosen 1 card from hand to dst"),
        "", False, None,
    ),
    # An index proof reached through a `let`.
    "let-names-the-deciders-team": (
        *_take(effect="let t = team_of(actor)  move chosen 1 card from secret[t] to pile"),
        "secret[team] : Hand<team>", True, None,
    ),
    "let-names-another-team": (
        *_take(effect="let t = team_of(actor offset_by left)  "
               "move chosen 1 card from secret[t] to pile"),
        "secret[team] : Hand<team>", True, _BLIND,
    ),
    "let-names-the-literal-seat": (
        "phase play { as 0 { let s = 0  move chosen 1 card from hand[s] to pile } }",
        "", "", False, None,
    ),
    "let-names-the-state-variable-seat": (
        "phase play { as leader { let who = leader  move chosen 1 card from hand[who] to pile } }",
        "", "", False, None,
    ),
    "let-names-the-binder-seat": (
        "phase play { for each player p: as p { let who = p  "
        "move chosen 1 card from hand[who] to pile } }",
        "", "", False, None,
    ),
}

def _indirection_cells() -> list[object]:
    return [
        _cell(cell_id, body, defs, zone, teams, refuse=refuse)
        for cell_id, (body, defs, zone, teams, refuse) in _INDIRECTIONS.items()
    ]


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _indirection_cells())
def test_a_value_is_judged_where_it_is_consumed(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """Each name the reader follows by value, crossed with whether its value
    reaches a decision of the seat that computed it, and each index proof
    reached through a `let`."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# Who evaluates each sub-position of a chosen movement, and whose decision its
# value reaches. A chosen movement `to each` is decided at every receiving
# seat, but the acting seat evaluates its amount, source and `where`, and so
# makes any `choose` nested in them.
# ---------------------------------------------------------------------------


def test_a_chosen_movements_seats_are_the_runtimes(monkeypatch: pytest.MonkeyPatch) -> None:
    """`CHOSEN_MOVEMENT_SEATS` is what the runtime does: a run records the
    acting seat at every evaluation of each sub-position and the decider at
    every pick, single and `to each`. A `to each` destination is a family name
    the runtime never evaluates, so its row has no evaluation to record.

    red under: map `("amount", True)` to `(SEAT_EACH_RECEIVER, SEAT_EACH_RECEIVER)`."""
    import random

    from cardlang.runtime import execute
    from cardlang.runtime.driver import play_game

    for each in (False, True):
        dest = "each won" if each else "won[0]"
        source = _game(
            "phase play { as 0 { move chosen (1 + 0) cards from pile "
            f"where rank_value(card) >= 0 to {dest} }} }}"
        ).replace(
            "deal 5 cards from deck to each hand", "deal 5 cards from deck to each hand  "
            "deal 10 cards from deck to pile"
        )
        game = check_dsl(source, "seats.cardlang")
        block = game.phases[1].items[0]
        assert isinstance(block, n.AsBlock)
        transfer = block.body[0]
        assert isinstance(transfer, n.Transfer)
        fields = {"amount": transfer.amount, "source": transfer.source, "where": transfer.where}
        evaluated: dict[str, set[object]] = {name: set() for name in fields}
        deciders: set[object] = set()
        real_evaluate = getattr(execute, "evaluate")
        real_decide = getattr(execute, "decide")

        def recording_evaluate(expr: object, ctx: object) -> object:
            for name, node in fields.items():
                if expr is node:
                    evaluated[name].add(ctx.current_player)  # type: ignore[attr-defined]
            return real_evaluate(expr, ctx)

        def recording_decide(ctx: object, player: object, *rest: object) -> object:
            deciders.add(player)
            return real_decide(ctx, player, *rest)

        with monkeypatch.context() as patched:
            patched.setattr(execute, "evaluate", recording_evaluate)
            patched.setattr(execute, "decide", recording_decide)
            play_game(game, random.Random(0))
        seat_of = {R.SEAT_ACTING: {0}, R.SEAT_EACH_RECEIVER: {0, 1, 2}}
        for name, seats in evaluated.items():
            decider, evaluator = R.CHOSEN_MOVEMENT_SEATS[(name, each)]
            assert seats == seat_of[evaluator], (name, each, seats)
            assert deciders == seat_of[decider], (name, each, deciders)
        assert set(R.CHOSEN_MOVEMENT_SEATS) == {
            (name, e) for name in ("amount", "source", "where", "dest") for e in (False, True)
        }


_EVAL_CHOOSE = "(choose integer in 0 .. (" + "number of cards in {z} where card.suit is hearts) up to 13)"

# cell -> (body, the refusal's fragment or None).
_EVALUATORS: dict[str, tuple[str, str | None]] = {
    "to-each-amount-choose-reads-the-evaluators-hand": (
        "phase play { as 0 { move chosen " + _EVAL_CHOOSE.format(z="hand[0]")
        + " cards from pile to each won } }",
        None,
    ),
    "to-each-amount-choose-reads-another-hand": (
        "phase play { as 0 { move chosen " + _EVAL_CHOOSE.format(z="hand[1]")
        + " cards from pile to each won } }",
        _DECIDER,
    ),
    "to-each-amount-reads-the-evaluators-hand": (
        "phase play { as 0 { move chosen (number of cards in hand[0] where card.suit is hearts) "
        "cards from pile to each won } }",
        _DECIDER,
    ),
    "to-each-where-choose-reads-the-evaluators-hand": (
        "phase play { as 0 { move chosen 1 card from pile where rank_value(card) < "
        + _EVAL_CHOOSE.format(z="hand[0]") + " to each won } }",
        None,
    ),
    "to-each-where-reads-the-evaluators-hand": (
        "phase play { as 0 { move chosen 1 card from pile where (2 of clubs) in hand[0] "
        "to each won } }",
        _DECIDER,
    ),
    "single-amount-choose-reads-the-evaluators-hand": (
        "phase play { as 0 { move chosen " + _EVAL_CHOOSE.format(z="hand[0]")
        + " cards from pile to won[0] } }",
        None,
    ),
}

def _evaluator_cells() -> list[object]:
    return [
        _cell(cell_id, body, "", "", False, refuse=refuse)
        for cell_id, (body, refuse) in _EVALUATORS.items()
    ]


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _evaluator_cells())
def test_a_choose_is_judged_at_the_seat_that_makes_it(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """A `choose` nested in a sub-position of a chosen movement is the
    evaluating seat's decision; the sub-position's value is every receiving
    seat's where the movement is `to each`."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# Delegated Play: a rule's clauses are asked at the trick round's card
# decision, the one decision a game's `chooser_for` routes, so in a game
# defining it they are decided by `chooser_for(actor)`, not by `actor`, the
# seat whose card is played. Bare `hand` and a trick round's bare source
# family read the routed pool.
# ---------------------------------------------------------------------------

_CHOOSER = "function chooser_for(p : Player) = if p is 1 then 0 else p\n"
_ROUTE = "function play_source_for(p : Player) = if p is 1 then shown[p] else hand[p]\n"
_SHOWN = "shown[player] : PublicHand<player>  vault[player] : Hand<player>"
_CLAUSES: dict[str, str] = {
    "applies_when": "applies_when: {read} demands: cards in hand where card.suit is hearts "
    "if_impossible: hand",
    "demands": "demands: cards in hand where {read} if_impossible: hand",
    "if_impossible": "demands: cards in hand where card.suit is hearts "
    "if_impossible: cards in hand where {read}",
    "exempts": "demands: cards in hand where card.suit is hearts if_impossible: hand "
    "exempts: cards in hand where {read}",
}
# read -> (the Boolean read, accepted where `chooser_for(actor)` decides)
_DELEGATED_READS: dict[str, tuple[str, bool]] = {
    "the-routed-pool": ("hand is not empty and (2 of clubs) in hand", True),
    "the-attributed-hand": ("(2 of clubs) in hand[actor]", False),
    "the-deciders-hand": ("(2 of clubs) in hand[chooser_for(actor)]", True),
    "a-public-zone": ("(2 of clubs) in won[actor]", True),
    "another-bare-family": ("(2 of clubs) in vault", False),
}
# game -> (the Delegated Play helpers it defines, whether they route the decider)
_DELEGATIONS: dict[str, tuple[str, bool]] = {
    "delegated": (_CHOOSER + _ROUTE, True),
    "decider-routed-only": (_CHOOSER, True),
    "pool-routed-only": (_ROUTE, False),
    "undelegated": ("", False),
}


def _delegated_cells() -> list[object]:
    cells = []
    for game, (helpers, routes_decider) in _DELEGATIONS.items():
        for clause, template in _CLAUSES.items():
            for read_id, (read, accepted_delegated) in _DELEGATED_READS.items():
                if routes_decider:
                    accepted = accepted_delegated
                else:
                    # `actor` decides: its own hand and vault are its own.
                    accepted = read_id != "the-deciders-hand" or game == "pool-routed-only"
                if read_id == "the-deciders-hand" and not helpers.startswith(_CHOOSER):
                    continue  # names a helper the game does not define
                body = "phase play { active_rules: [Probed] " + _TRICK + " }"
                defs = helpers + "rule Probed { constrains: play_to_trick " + template.format(
                    read=read
                ) + " }"
                red = routes_decider and read_id in (
                    "the-attributed-hand", "another-bare-family", "the-deciders-hand"
                )
                cells.append(
                    _cell(
                        f"{game}-{clause}-{read_id}", body, defs, _SHOWN, False,
                        refuse=None if accepted else _DECIDER,
                        xfail="a rule clause is judged against the attributed seat" if red else None,
                        raises=DiagnosticError if accepted else _Accepted,
                    )
                )
    return cells


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _delegated_cells())
def test_a_delegated_rule_is_judged_at_its_decider(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """Each rule clause, each read, in a game whose `chooser_for` routes the
    decision, whose `play_source_for` alone routes the pool, and in neither."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# A cycle the reader follows: every name graph it walks may be cyclic before
# the guard that refuses the cycle has raised, since resolve raises its bag
# once, at the end. Each is refused by its own Owner Guard, never by a crash.
# ---------------------------------------------------------------------------

# cell -> (body, defs, the refusal's fragment).
_CYCLES: dict[str, tuple[str, str, str]] = {
    "procedure-runs-itself": (
        "phase play { for each player p: run again(p) }",
        "procedure again(x : Player) { run again(x) }",
        "again",
    ),
    "procedures-run-each-other": (
        "phase play { for each player p: run ping(p) }",
        "procedure ping(x : Player) { run pong(x) }\n"
        "procedure pong(x : Player) { run ping(x) }",
        "ping",
    ),
    "function-calls-itself": (
        _OFFER_TAKE.replace("take", "loop_move"),
        "function deep(x : Integer) = deep(x)\n"
        "move_type loop_move { when: deep(1) > 0 effect { } }",
        "recursive",
    ),
}

def _cycle_cells() -> list[object]:
    return [
        _cell(cell_id, body, defs, "", False, refuse=fragment)
        for cell_id, (body, defs, fragment) in _CYCLES.items()
    ]


@pytest.mark.parametrize("body,defs,zone,teams,refuse", _cycle_cells())
def test_a_cycle_is_refused_by_its_owner_not_followed(
    body: str, defs: str, zone: str, teams: bool, refuse: str | None
) -> None:
    """A recursive procedure or function reaches the checker's diagnostic
    channel, located, however the reader meets it."""
    _check(_game(body, defs, zone=zone, teams=teams), refuse)


# ---------------------------------------------------------------------------
# The corpus: the State Variable rule is what admits these games' chosen
# movements.
# ---------------------------------------------------------------------------

_STATE_VARIABLE_SEATS: dict[str, frozenset[str]] = {
    "cribbage": frozenset({"active"}),
    "doppelkopf": frozenset({"leader"}),
    "five-hundred": frozenset({"declarer", "leader"}),
    "french-tarot": frozenset({"taker"}),
    "president": frozenset({"president"}),
    "scopa": frozenset({"active"}),
    "skat": frozenset({"leader"}),
}


@pytest.mark.parametrize("game", sorted(_STATE_VARIABLE_SEATS))
def test_a_corpus_seat_named_by_a_state_variable_is_proven_by_it(game: str) -> None:
    """Each game's `as <State Variable>` block picks from that seat's own hand,
    and the check accepts the read because no path from the `as` writes the
    variable -- Cribbage's through a write in a sibling branch.

    red under: delete the `state_var` arm of `_HiddenReads._names_acting_seat`."""
    checked = check_source(_REPO / "docs" / "games" / f"{game}.cardlang")
    proven = {
        v.reason.split("`")[1]
        for v in R.hidden_read_verdicts(checked)
        if v.accepted and v.reason.startswith("the State Variable")
    }
    assert proven == _STATE_VARIABLE_SEATS[game]
