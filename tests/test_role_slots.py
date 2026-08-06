"""Every role slot admits exactly the domains its position allows.

A *role slot* is a field a construct holds as a bare string naming a
quantifiable domain -- `for each <role>`, `hand[<index>]`, `Hand<owner>`.
The domain registry (`cardlang/domains.py`) closes the ROLE half of what may
sit there; a game's `positions { }` block and a `board:` clause open the
other half. Neither half is visible in the field's annotation, which is
`str`, so every wall over these slots is written by hand at the consuming
pass -- and a slot whose wall was never written accepts whatever it is given.

That is the shape this grid measures. It is the sibling of the role TYPE
(`domains.Role`), which governs how a role is CONSULTED once classified;
this one governs what a role slot ACCEPTS in the first place. Neither
implies the other: a slot can be walled and then consulted by ad-hoc logic,
or consulted correctly and never walled at all -- and the second is what the
`RequireDecl.index` row was, accepting any name a library cared to write
while every consumer downstream handled roles impeccably.

Completeness ledger (decisions.md "Closed-domain completeness")
--------------------------------------------------------------
property:   every role slot either accepts a domain name and honours it, or
            rejects it at a pass that names the slot -- never accepts it and
            ignores it. Quantifier's four spellings are closed by the GRAMMAR
            (a fifth noun builds a `DomainQuery`, a different node), which is
            a rung-1 fact and is asserted as such rather than assumed.
domain:     role slot x value class. Both axes derived:
            - the SLOT axis from `resolve._REFERENCE_SLOTS`, taking every slot
              whose namespace names a role or an index domain, plus the
              zone-type owner argument (`zone_type_arg`), which resolve checks
              against the same role sets under its own namespace name. Derived
              rather than listed so a role slot added to the registry arrives
              here as a missing template and fails loud
              (`test_every_registry_role_slot_has_a_template`).
            - the VALUE axis as the four registry rows (from `domains.DOMAINS`,
              so a fifth row widens the grid without editing it) plus the four
              classes the registry does not close: a declared integer position
              domain, a board-minted named position domain (`cell`), the
              board-minted direction domain (`dir`), and an unknown name.
registry:   `cardlang.domains.DOMAINS` (role ids); `resolve._REFERENCE_SLOTS`
            (the slot axis); `cardlang.board_domains.BOARD_DOMAIN` /
            `DIRECTION_DOMAIN` (the two minted names).
covered:    the full cross product, executed by
            `test_a_role_slot_admits_exactly_its_declared_domains` -- one row
            per (slot, value), each commanded ACCEPT, REJECT or INEXPRESSIBLE.
            `cell` and `dir` cells run on a BOARD base and the rest on a card
            base, because a value class that does not exist in the game under
            test would make its own row vacuous -- the cell would then prove
            "an undeclared name is refused", which is the `unknown` row.
sampled:    none -- every cell is executed.
residual:   ONE. The grid commands ACCEPT/REJECT/INEXPRESSIBLE, not WHICH wall
            reports: at the zone-owner slot the template holds index and owner
            equal (what a designer writes), so for a non-indexable value the
            INDEX wall reports first and the owner wall is not the one
            measured. The owner wall is separately executed against a fixed
            `player` index by
            `tests/test_zone_index_roles.py::test_a_zone_type_may_not_be_owned_
            by_a_value_domain`. R4 -- auditor-only, and it guards no
            information-set guarantee: both spellings refuse, so no game is
            accepted-and-ignored either way. Recorded here per decisions.md
            "Reachability ranks the work"; no issue.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from cardlang.ast import nodes as n
from cardlang.board_domains import BOARD_DOMAIN, DIRECTION_DOMAIN
from cardlang.diagnostics import DiagnosticError
from cardlang.domains import DOMAINS
from cardlang.parse import parse_library, parse_text
from cardlang.pipeline import check_dsl

import cardlang.resolve as _resolve_mod

# --- the SLOT axis, derived from the reference-slot registry -----------------
#
# `getattr` rather than a direct import: mypy strict's `--no-implicit-reexport`
# refuses the private name (the same workaround tests/test_permissive_top.py
# and tests/test_role_registry.py use).
_REFERENCE_SLOTS: dict[tuple[type, str], str] = getattr(
    _resolve_mod, "_REFERENCE_SLOTS"
)

# The namespaces whose values are drawn from the domain registry (plus a
# game's declared position domains). `zone_type_arg` is listed because
# `_resolve_zone` validates it against `_KNOWN_ROLES | positions` -- the same
# sets as `index_domain` -- even though the registry gives it its own
# namespace name for the separate agreement rule it also carries.
#
# `binder` slots are deliberately NOT here: `LetStmt.index` is a lexical
# BINDER, not a domain name (`let x[i] = …` builds a per-player map whatever
# `i` is called), and the registry classifies it that way. Its role-noun
# confusion is a different wall, covered by
# `tests/test_zone_index_roles.py::test_an_indexed_let_may_not_borrow_a_value_
# domain_noun`.
_ROLE_NAMESPACES = frozenset({"role", "index_domain", "zone_type_arg"})


def _role_slots() -> frozenset[str]:
    """The slot axis, read from whatever registry it is handed.

    Labelled `Class.field` so a template table can key on it without importing
    the node classes into the parametrization ids."""
    return frozenset(
        f"{cls.__name__}.{field}"
        for (cls, field), ns in _REFERENCE_SLOTS.items()
        if ns in _ROLE_NAMESPACES
    )


# --- the VALUE axis ---------------------------------------------------------

_REGISTRY_ROLES: tuple[str, ...] = tuple(sorted(d.id.value for d in DOMAINS))
_DECLARED_POSITION = "column"  # `positions { column : 1..3 }`
_UNKNOWN = "croupier"  # no registry row, no declaration

# The two classes the board mints, and the one a game declares, kept as named
# constants so a rename in `board_domains` reaches this grid.
_VALUES: tuple[str, ...] = _REGISTRY_ROLES + (
    _DECLARED_POSITION,
    BOARD_DOMAIN,
    DIRECTION_DOMAIN,
    _UNKNOWN,
)

# Values that only EXIST in a board game. A cell for one of these run against
# the card base would silently degrade into the `unknown` cell.
_BOARD_VALUES = frozenset({BOARD_DOMAIN, DIRECTION_DOMAIN})

ACCEPT = "accept"
REJECT = "reject"
# The grammar cannot build this node with this value at all -- a stronger
# outcome than REJECT, and asserted as such (no `Quantifier` carrying the
# value survives the parse).
INEXPRESSIBLE = "inexpressible"


# --- the two bases ----------------------------------------------------------


def _card_game(*, zones: str = "", state: str = "", stmt: str = "") -> str:
    return f"""game G {{
  players: 4
  teams: [[0, 2], [1, 3]]
  max_length: 100
  direction: clockwise
  cards: standard52
  positions {{ {_DECLARED_POSITION} : 1..3 }}
  zones {{
    deck : Deck
    hand[player] : Hand<player>
    pile[player] : PlayerPile<player>
    {zones}
  }}
  state {{ n[player] : Integer = 0  {state} }}
  phase p {{
    deal 1 cards from deck to each hand
    {stmt}
  }}
  winner: highest n
}}"""


def _board_game(*, zones: str = "", state: str = "", stmt: str = "") -> str:
    return f"""game B {{
  players: 2
  direction: clockwise
  max_length: 30
  board: grid(3, 3)
  pieces: xo_marks
  zones {{
    box : Deck
    square[{BOARD_DOMAIN}] : Cell<{BOARD_DOMAIN}>
    reserve[player] : PlayerPile<player>
    {zones}
  }}
  state {{ n[player] : Integer = 0  done : Boolean = false  {state} }}
  phase setup {{
    move all pieces from box where piece.side is x to reserve[0]
    move all pieces from box to reserve[1]
    {stmt}
  }}
  phase play {{
    turns t from 0 over all players until done {{
      offer to t one of [stop]
    }}
  }}
  winner: highest n
}}
move_type stop {{ effect {{ done := true }} }}
"""


# A base builder: keyword-only `zones`/`state`/`stmt`, returning game source.
_Base = Callable[..., str]


def _base_for(value: str) -> _Base:
    return _board_game if value in _BOARD_VALUES else _card_game


# --- one template per slot --------------------------------------------------
#
# Each runs the full pipeline and raises `DiagnosticError` on refusal. Every
# template is legal for at least one value, so a cell varies ONLY the role.
# Bodies never mention the role's own binder: `each team simultaneously:
# … hand[player] …` refuses for the unbound `player`, which would score the
# role wall's cell on a different wall entirely.


def _run_for_each(value: str, _mp: pytest.MonkeyPatch) -> None:
    base = _base_for(value)
    check_dsl(base(stmt=f"for each {value} b: n[0] := 1"), "probe.cardlang")


def _run_quantifier(value: str, _mp: pytest.MonkeyPatch) -> None:
    base = _base_for(value)
    check_dsl(
        base(stmt=f"if any {value} where n[0] > 0 {{ n[0] := 1 }}"), "probe.cardlang"
    )


def _run_each_simultaneous(value: str, _mp: pytest.MonkeyPatch) -> None:
    base = _base_for(value)
    item, src, dst = (
        ("pieces", "reserve[0]", "square[a1]")
        if value in _BOARD_VALUES
        else ("cards", "hand[0]", "pile[0]")
    )
    check_dsl(
        base(stmt=f"each {value} simultaneously: transfer chosen 1 {item} from {src} to {dst}"),
        "probe.cardlang",
    )


def _run_zone_index(value: str, _mp: pytest.MonkeyPatch) -> None:
    base = _base_for(value)
    check_dsl(base(zones=f"p2[{value}] : Discard"), "probe.cardlang")


def _run_state_index(value: str, _mp: pytest.MonkeyPatch) -> None:
    base = _base_for(value)
    check_dsl(base(state=f"x[{value}] : Integer = 0"), "probe.cardlang")


def _run_type_arg(value: str, _mp: pytest.MonkeyPatch) -> None:
    # Index and owner held EQUAL -- what a designer writes, and what the
    # agreement wall demands. See the ledger's residual row.
    base = _base_for(value)
    check_dsl(base(zones=f"h2[{value}] : PlayerPile<{value}>"), "probe.cardlang")


def _run_require_index(value: str, monkeypatch: pytest.MonkeyPatch) -> None:
    """The library side of the contract: `requires { q[<value>] : Integer }`.

    The GAME always declares the LEGAL `q[player]`, never a copy of the value
    under test. That asymmetry is the whole point of this row: with the game
    declaring the same bad index, its own state-index wall refuses first and
    the cell goes green having proved nothing about the library's slot. The
    grid must not let one wall stand in for another it is measuring."""
    library = parse_library(
        f"""library probe_lib {{
  requires {{ q[{value}] : Integer }}
  procedure bump() {{ q[0] := 1 }}
}}""",
        "probe_lib.cardlang",
    )
    monkeypatch.setattr(
        "cardlang.resolve.library_names", lambda: frozenset({"probe_lib"})
    )
    monkeypatch.setattr("cardlang.resolve.load_library", lambda name: library)
    base = _base_for(value)
    source = base(state="q[player] : Integer = 0", stmt="run bump()")
    source = source.replace("  zones {", "  uses probe_lib\n  zones {", 1)
    # The game text is otherwise IDENTICAL across this row -- only the library
    # varies -- and `pipeline._check` memoizes on the parsed tree while
    # `resolve` reads the library registry from module globals (issue #186).
    # Without a tag, every cell whose predecessor was ACCEPTED returns that
    # verdict and the row goes green having run once. The tag is the game's
    # NAME, not a comment: comments do not survive into the AST, so a comment
    # separates two cells only when the two values differ in LENGTH (the memo
    # key includes span offsets) -- which silently left `column` colliding with
    # `player`, the one accepting cell, in exactly the direction that hides a
    # defect. The other rows vary their own source text and are unaffected.
    source = source.replace("game G {", f"game G_{value} {{", 1)
    source = source.replace("game B {", f"game B_{value} {{", 1)
    check_dsl(source, "probe.cardlang")


_TEMPLATES: dict[str, Callable[[str, pytest.MonkeyPatch], None]] = {
    "ForEach.role": _run_for_each,
    "Quantifier.role": _run_quantifier,
    "EachSimultaneous.role": _run_each_simultaneous,
    "ZoneDecl.index": _run_zone_index,
    "StateDecl.index": _run_state_index,
    "TypeArg.name": _run_type_arg,
    "RequireDecl.index": _run_require_index,
}


# --- the expected column, authored as decisions ------------------------------
#
# `player`/`team` are the seat rows; `suit`/`rank` the card-axis rows. The
# splits are not uniform across the grid and each is a decision:
#
#  - `for each` iterates every registry row plus a board's NAMED-member
#    position domain; an integer `positions { }` domain stays walled (#111).
#  - a quantifier's four spellings are GRAMMAR productions, so a fifth noun
#    builds a `DomainQuery` -- inexpressible as a `Quantifier`.
#  - `each … simultaneously` is seat-only, and only the seat that IS an actor.
#  - a zone/state index must be a domain an observer has a key of their own in
#    (`zone_key_of`); zones additionally admit position domains, state does not.
_EXPECTED: dict[tuple[str, str], str | tuple[str, str]] = {
    # slot                    player  team    suit    rank    column  cell    dir     unknown
    **dict.fromkeys([("ForEach.role", v) for v in ("player", "team", "suit", "rank")], ACCEPT),
    ("ForEach.role", _DECLARED_POSITION): REJECT,
    ("ForEach.role", BOARD_DOMAIN): ACCEPT,
    ("ForEach.role", DIRECTION_DOMAIN): REJECT,
    ("ForEach.role", _UNKNOWN): REJECT,

    **dict.fromkeys([("Quantifier.role", v) for v in ("player", "team", "suit", "rank")], ACCEPT),
    ("Quantifier.role", _DECLARED_POSITION): INEXPRESSIBLE,
    ("Quantifier.role", BOARD_DOMAIN): INEXPRESSIBLE,
    ("Quantifier.role", DIRECTION_DOMAIN): INEXPRESSIBLE,
    ("Quantifier.role", _UNKNOWN): INEXPRESSIBLE,

    ("EachSimultaneous.role", "player"): ACCEPT,
    **dict.fromkeys(
        [("EachSimultaneous.role", v)
         for v in ("team", "suit", "rank", _DECLARED_POSITION, BOARD_DOMAIN,
                   DIRECTION_DOMAIN, _UNKNOWN)],
        REJECT,
    ),

    ("ZoneDecl.index", "player"): ACCEPT,
    ("ZoneDecl.index", "team"): ACCEPT,
    ("ZoneDecl.index", "suit"): REJECT,
    ("ZoneDecl.index", "rank"): REJECT,
    ("ZoneDecl.index", _DECLARED_POSITION): ACCEPT,
    ("ZoneDecl.index", BOARD_DOMAIN): ACCEPT,
    ("ZoneDecl.index", DIRECTION_DOMAIN): REJECT,
    ("ZoneDecl.index", _UNKNOWN): REJECT,

    ("StateDecl.index", "player"): ACCEPT,
    ("StateDecl.index", "team"): ACCEPT,
    **dict.fromkeys(
        [("StateDecl.index", v)
         for v in ("suit", "rank", _DECLARED_POSITION, BOARD_DOMAIN,
                   DIRECTION_DOMAIN, _UNKNOWN)],
        REJECT,
    ),

    ("TypeArg.name", "player"): ACCEPT,
    ("TypeArg.name", "team"): ACCEPT,
    ("TypeArg.name", "suit"): REJECT,
    ("TypeArg.name", "rank"): REJECT,
    ("TypeArg.name", _DECLARED_POSITION): ACCEPT,
    ("TypeArg.name", BOARD_DOMAIN): ACCEPT,
    ("TypeArg.name", DIRECTION_DOMAIN): REJECT,
    ("TypeArg.name", _UNKNOWN): REJECT,

    # The require slot is the game's contract read from the library side. It
    # must admit exactly what a state declaration admits -- the requirement
    # names a state variable the game declares, so a name the game could never
    # declare cannot be a legal requirement either.
    #
    # This row alone commands the MESSAGE, not just the verdict, because the
    # verdict cannot discriminate here: the game declares `q[player]`, so every
    # non-`player` value mismatches and refuses no matter whether the library's
    # index was ever checked. What separates "checked" from "not checked" is
    # which sentence comes back.
    ("RequireDecl.index", "player"): ACCEPT,
    # A role/role mismatch must name BOTH roles. Today both sides render from
    # the truthiness of `.index`, so this prints "per-player, but … per-player"
    # (issue #144).
    ("RequireDecl.index", "team"): (REJECT, "per-team"),
    # A value domain, a position domain and an unknown name are all things a
    # state declaration may not be indexed by, so a requirement may not name
    # one either -- and must say so, rather than reporting a shape mismatch
    # against a role that does not exist.
    **dict.fromkeys(
        [("RequireDecl.index", v)
         for v in ("suit", "rank", _DECLARED_POSITION, BOARD_DOMAIN,
                   DIRECTION_DOMAIN, _UNKNOWN)],
        (REJECT, "not an indexable role"),
    ),
}


# --- the grid ---------------------------------------------------------------


def test_every_registry_role_slot_has_a_template() -> None:
    """The slot axis is DERIVED, so a role slot added to the reference-slot
    registry arrives here as a missing template rather than as silence.

    red under: add a `(n.SomeNode, "role"): "role"` row to
    `resolve._REFERENCE_SLOTS` without adding a template."""
    assert set(_TEMPLATES) == _role_slots()


def test_the_expected_column_covers_the_whole_cross_product() -> None:
    """Every cell is a decision. A value class or a slot added without an
    authored outcome fails here rather than quietly shrinking the grid.

    red under: delete any row from `_EXPECTED`."""
    assert set(_EXPECTED) == {(slot, v) for slot in _TEMPLATES for v in _VALUES}


@pytest.mark.parametrize("value", _VALUES)
@pytest.mark.parametrize("slot", sorted(_TEMPLATES))
def test_a_role_slot_admits_exactly_its_declared_domains(
    slot: str, value: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    expected = _EXPECTED[(slot, value)]
    template = _TEMPLATES[slot]

    if expected is INEXPRESSIBLE:
        # Stronger than "refused": the grammar cannot build the node at all.
        # Asserted over the parse tree, so a future production that DID admit
        # the noun would fail here even if resolve went on to refuse it.
        source = _base_for(value)(
            stmt=f"if any {value} where n[0] > 0 {{ n[0] := 1 }}"
        )
        try:
            tree = parse_text(source, "probe.cardlang")
        except DiagnosticError:
            return  # refused at parse: also inexpressible
        assert not [
            node
            for node in _walk(tree)
            if isinstance(node, n.Quantifier) and node.role == value
        ], f"{value} built a Quantifier -- the grammar's four spellings are no longer closed"
        return

    if expected is ACCEPT:
        template(value, monkeypatch)
        return
    # A commanded rejection, optionally with the sentence it must come back
    # with -- see the `RequireDecl.index` row on why the verdict alone is not
    # always enough to tell a checked slot from an unchecked one.
    required = expected[1] if isinstance(expected, tuple) else None
    with pytest.raises(DiagnosticError) as exc:
        template(value, monkeypatch)
    if required is not None:
        assert required in str(exc.value), (
            f"{slot} x {value}: refused, but not for the reason commanded — "
            f"expected {required!r} in:\n    {exc.value}"
        )
    if slot == "RequireDecl.index" and value != "team":
        # CURRENCY, not just verdict. Every OTHER requires failure lands on
        # the game's `uses` line (pinned in tests/test_family_libraries.py),
        # so this row deviates from a pinned convention and must say so out
        # loud: a malformed index is wrong in the library's own text and no
        # game can answer it. The `team` cell is excluded because it is a
        # genuine CONTRACT mismatch, which keeps the game's currency.
        assert "probe_lib.cardlang:" in str(exc.value), (
            f"{slot} x {value}: refused in the wrong file — a malformed "
            f"requirement index is the library's defect:\n    {exc.value}"
        )


def _walk(node: object) -> list[object]:
    """Every AST node under `node`, this module's own walker so the grid does
    not depend on a resolve-internal helper."""
    out: list[object] = []
    stack: list[object] = [node]
    while stack:
        cur = stack.pop()
        if isinstance(cur, (list, tuple)):
            stack.extend(cur)
            continue
        if not hasattr(cur, "__dataclass_fields__"):
            continue
        out.append(cur)
        for field in getattr(cur, "__dataclass_fields__"):
            stack.append(getattr(cur, field))
    return out
