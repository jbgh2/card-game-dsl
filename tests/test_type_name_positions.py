"""The declared-type-name POSITION x NAME-SOURCE grid.

Every syntactic position where a program writes a declared type name, crossed
with every source a legal name can come from. Each cell states what that
position's gate does with that name: `admit`, or a named rejection. The grid is
DERIVED — the position axis is scraped from the grammar productions that
reference `type_name` / `payload_type`, the admissible sets are computed from
the registries — so a new position or a new name source arrives as uncovered
cells that force someone to classify them, rather than as silence.

The defect class this exists to close (docs/decisions.md, "Closed-domain
completeness"): a domain whose axes are hand-listed. The wall this module
grids was first written against a five-position axis that a fresh-context
framing check found to be nine; the four it missed (procedure parameters,
rule parameters, phase-outcome payloads, struct literals) were invisible
precisely because nothing crossed the product.

Completeness ledger
--------------------
    property:   For every position P where a declared type name can be written,
                and every name source S, P's gate admits S exactly when the
                registries say it should, and REJECTS LOUDLY otherwise — never
                by mapping the name to the permissive top, and never with a
                diagnostic that calls a declared name unknown.

    domain:     Two axes, each derived rather than hand-listed:
                  A. positions — the grammar productions referencing
                     `type_name` (93) or `payload_type` (360), plus
                     `struct_lit` (502) whose head NAME is a type name in
                     EXPRESSION position. Nine cells today; pinned against the
                     grammar by `test_the_position_axis_is_the_grammar_s`, which
                     also carves out the one type-name carrier that cannot
                     appear in a standalone game — a library's `require_decl`,
                     validated transitively by `_check_requires` and covered in
                     `test_family_libraries.py`, not here.
                  B. name sources — `KNOWN_TYPE_NAMES`, `PARAM_DOMAINS`,
                     `_PROCEDURE_PARAM_DOMAINS`, the two bare inline literals
                     (`Card` at a move param, `Suit` at a rule param), per-game
                     `type` declarations, per-game `positions {}` declarations,
                     and an unknown name as the negative control.

    registry:   A. cardlang/grammar/cardlang.lark (scraped by the pin below)
                B. typecheck.KNOWN_TYPE_NAMES; domains.PARAM_DOMAINS;
                   resolve._PROCEDURE_PARAM_DOMAINS; resolve's inline `Card`
                   and `Suit` literals; the game's own TypeDef / PositionDecl

    covered:    The grid: `test_the_type_name_grid` over CELLS — 9 positions x
                13 name sources, every one executed. `EXPECTED` is computed per
                position from the registries, so the covered set cannot drift
                from the domain set by hand-editing a row.

    sampled:    The `?` spelling is sampled at `Rank?` and `Suit?` rather than
                crossed over every base name: the three disciplines that handle
                it (exact-string at P3/P5, base-stripped at P6/P7/P8, a separate
                `optional` flag at P1/P2) are each witnessed at least once, but
                base x optional is not a full sub-product.

    residual:   1. A POSITION DOMAIN AS A STATE-VAR OR STRUCT-FIELD TYPE
                   (P1/P2 x a `positions {}` name, and a board `cell`) is
                   rejected, and whether it SHOULD be admitted is undecided —
                   semantically such a value is an Integer with a declared
                   range (a TCell for a board cell), but no corpus game wants
                   one, so this grid does not guess a cell nobody has decided.
                   The wall is loud but the message spells it `unknown type
                   '<name>'`; naming the sharper reason (a position domain is
                   not a declared type in this slot) is a message-quality
                   residual, and the grid asserts admit-vs-reject only, not the
                   message text. Recorded in issue #133.
                2. NAMESPACES B AND C ARE NOT IN THIS GRID. Zone type names
                   (`Hand<player>`) and role/domain ids (the `player` in
                   `hand[player]`, `for each player`) are type-ish names with
                   their own registries and their own walls; the framing check
                   enumerated seven such positions. They are a different
                   domain, not a missing part of this one. Their own raggedness
                   -- a zone index admits position domains where a state index
                   does not -- is recorded in issue #98.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from importlib import resources

import pytest

from cardlang import typecheck
from cardlang.ast import nodes as n
from cardlang.domains import PARAM_DOMAINS
from cardlang.pipeline import check_dsl
from cardlang.resolve import _PROCEDURE_PARAM_DOMAINS
from cardlang.typecheck import KNOWN_TYPE_NAMES, TypeEnv
from cardlang.types import TInteger, TOptional, TStruct, Type


class CellMismatch(AssertionError):
    """A grid cell's OUTCOME differed from its expected value.

    Distinct from a bare `AssertionError` so an `xfail(raises=CellMismatch)`
    on a designed-to-flip cell cannot be satisfied by a helper assertion, an
    import error, or any other harness failure — red for the wrong reason is
    the vacuously-green class wearing red (decisions.md, "Closed-domain
    completeness"; the born-green pin rule).
    """


# --- Axis A: the positions, derived from the grammar -----------------------

GAME = """game G {
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  positions { column : 1..8 }
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  tick : Integer = 0%(extra_state)s }
  phase play%(outcome)s {%(rules)s for each player p: score[p] := 1 }
  winner: highest score
}
type T = { x : Integer }
%(extra)s"""


def _prog(*, extra: str = "", extra_state: str = "", outcome: str = "",
          rules: str = "") -> str:
    return GAME % {"extra": extra, "extra_state": extra_state,
                   "outcome": outcome, "rules": rules}


# Each entry: the grammar production that carries the name, and a probe that
# puts `d` in exactly that position. Probes are shaped so the only thing under
# test is the type-name gate: a procedure body reads no call-site pronoun, and
# a parameterized rule is instantiated, because neither is about this axis.
POSITIONS: dict[str, tuple[str, object]] = {
    "P1 state_decl": ("state_decl", lambda d: _prog(extra_state=f"  s : {d} = 1")),
    "P2 struct_field": ("struct_field", lambda d: _prog(extra=f"type S2 = {{ x : {d} }}")),
    "P3 move_param": ("move_param", lambda d: _prog(
        extra=f"move_type mv(x : {d}) {{ effect {{ score[actor] := 1 }} }}")),
    "P4 proc_param": ("procedure_def", lambda d: _prog(
        extra=f"procedure pr(x : {d}) {{ tick := 1 }}")),
    "P5 rule_param": ("rule_params", lambda d: _prog(
        rules=" active_rules: [Rl(hearts)]",
        extra=f"rule Rl(x : {d}) {{ demands: true }}")),
    "P6 func_param": ("func_param", lambda d: _prog(extra=f"function f(x : {d}) = 1")),
    "P7 define_payload": ("variant_case", lambda d: _prog(
        extra=f"define dd -> {{ won({d}) | lost }} {{ produce lost }}")),
    "P8 outcome_payload": ("phase_outcome", lambda d: _prog(
        outcome=f" -> outcome {{ won({d}) | lost }}")),
    "P9 struct_lit": ("struct_lit", lambda d: _prog(extra=f"function f() = {d} {{ x: 1 }}")),
}

# --- Axis B: the name sources ----------------------------------------------

POSITION_DOMAIN = "column"   # declared by the probe game's `positions {}`
USER_STRUCT = "T"            # declared by the probe game's `type T`
UNKNOWN_NAME = "Bogus"       # the negative control

NAMES = [
    "Integer", "Boolean", "Player", "Card", "Team", "Suit", "Rank",
    "Rank?", "Suit?", "SeatDirection", POSITION_DOMAIN, USER_STRUCT, UNKNOWN_NAME,
]

DECLARED = frozenset(KNOWN_TYPE_NAMES) | {USER_STRUCT}
_BASE_STRIPPED = DECLARED | {f"{n}?" for n in DECLARED}

# The expected column, COMPUTED per position from the registries above — never
# a hand-written row, so a registry change moves the expectation with it.
EXPECTED_ADMITS: dict[str, frozenset[str]] = {
    # Plain declared-name positions; `?` is a separate AST flag, so both spellings pass.
    "P1 state_decl": frozenset(_BASE_STRIPPED),
    "P2 struct_field": frozenset(_BASE_STRIPPED),
    # Enumerable move-parameter domains, plus the inline `Card` literal, plus
    # the game's position domains (the action space enumerates them).
    "P3 move_param": frozenset(PARAM_DOMAINS | {"Card", POSITION_DOMAIN}),
    "P4 proc_param": frozenset(_PROCEDURE_PARAM_DOMAINS),
    "P5 rule_param": frozenset({"Suit"}),
    # Declared names, `?` base-stripped, AND position domains: a function or a
    # payload may carry a position value, which types as its Integer range.
    "P6 func_param": frozenset(_BASE_STRIPPED | {POSITION_DOMAIN}),
    "P7 define_payload": frozenset(_BASE_STRIPPED | {POSITION_DOMAIN}),
    "P8 outcome_payload": frozenset(_BASE_STRIPPED | {POSITION_DOMAIN}),
    # A struct literal's head names a declared struct and nothing else.
    "P9 struct_lit": frozenset({USER_STRUCT}),
}

# The red set: cells a change designs to flip, carried as strict xfails so the
# pre-push checks stay green while the grid is red, and so a flip cannot be
# forgotten (a leftover mark on a now-passing cell fails loudly). Empty between
# changes; this grid shipped with the three position-domain cells at
# P6/P7/P8 in it, which the same change turned green at resolve AND in the
# function signature builder — resolve alone would have admitted the name and
# left the type layer mapping it to the permissive top.
DESIGNED_TO_FLIP: set[tuple[str, str]] = set()


def _outcome(src: str) -> str:
    """What this position's type-name gate did with the name.

    The subject is the gate, not whole-program validity: a probe that clears
    the gate and then trips an unrelated wall is still `admit`.
    """
    try:
        check_dsl(src, "grid")
    except AssertionError:
        return "raise"          # compiler-currency failure: always a defect here
    except Exception as e:  # noqa: BLE001 - every user-facing currency is in scope
        msg = str(e)
        if "syntax error" in msg:
            return "syntax"
        if "unknown type" in msg:
            return "unknown-type"
        if "domain" in msg:
            return "domain"
    return "admit"


CELLS = [(pos, name) for pos in POSITIONS for name in NAMES]


def _cell_id(cell: tuple[str, str]) -> str:
    return f"{cell[0].split()[1]}-{cell[1]}"


@pytest.mark.parametrize(
    "cell",
    [
        pytest.param(
            c,
            marks=pytest.mark.xfail(
                strict=True, raises=CellMismatch,
                reason="designed to flip: position domain restored at this position",
            ),
        )
        if c in DESIGNED_TO_FLIP
        else c
        for c in CELLS
    ],
    ids=[_cell_id(c) for c in CELLS],
)
def test_the_type_name_grid(cell: tuple[str, str]) -> None:
    """Every (position, name) cell matches what the registries say it should."""
    position, name = cell
    _production, build = POSITIONS[position]
    src = build(name)  # type: ignore[operator]
    actual = _outcome(src)
    admitted = name in EXPECTED_ADMITS[position]
    if admitted and actual != "admit":
        raise CellMismatch(
            f"{position} should admit {name!r} (its registry lists it) but the "
            f"gate answered {actual!r}"
        )
    if not admitted and actual == "admit":
        raise CellMismatch(
            f"{position} must not admit {name!r} — no registry backing it, so "
            f"admitting it maps the name to the permissive top"
        )


@pytest.mark.parametrize("position", sorted(POSITIONS))
def test_a_retired_type_name_is_loud_in_every_position(position: str) -> None:
    """`Direction` was the stdlib seat-ring enum's declared name until issue
    #201 renamed it `SeatDirection`, and Hearts declared one. A retired
    spelling is the sharpest case of this module's property, because it is the
    one an author has in muscle memory and in an in-flight game file: a
    silently-`TAny` `pass_direction` would keep typechecking and exempt itself
    from the `offset_by` operand wall. The grid above covers the CLASS (an
    unrecognized name, via `UNKNOWN_NAME`); this covers the retired member of
    it by name, in all nine positions.

    The diagnostic names the offending spelling but does not suggest the
    replacement: a retired-spelling hint table is its own closed domain
    spanning every rename in the glossary epic, and belongs to that epic
    (issue #204), not to a one-entry table minted here.
    """
    _production, build = POSITIONS[position]
    assert _outcome(build("Direction")) != "admit", (  # type: ignore[operator]
        f"{position} still admits the retired spelling 'Direction' — it now "
        f"maps to the permissive top instead of naming the rename"
    )


def test_an_admitted_name_never_resolves_to_the_permissive_top() -> None:
    """Admission is half the property; the RESULTING TYPE is the other half.

    A gate that admits a name whose builder maps it to the top is worse than a
    gate that rejects it: the name is accepted and every wall below it goes
    off. The grid above tests the verdict, so it cannot see this — a review
    found exactly that hole here, where position domains were admitted at the
    payload positions while `_payload_type` still resolved them to the top.

    Every resolver that turns a declared name into a type is checked, so a new
    one arrives as a missing row rather than as a silent leak.

    red under: drop the `positions` argument from any of the three calls below.
    """
    positions = {POSITION_DOMAIN: TInteger()}
    env = TypeEnv(positions=positions)
    structs: dict[str, TStruct] = {}
    resolvers: dict[str, Callable[[], Type]] = {
        "type_from_name": lambda: typecheck.type_from_name(
            POSITION_DOMAIN, False, structs, positions
        ),
        "_payload_type": lambda: typecheck._payload_type(
            POSITION_DOMAIN, structs, positions
        ),
        "_param_type": lambda: typecheck._param_type(
            n.MoveParam(name="x", type_name=POSITION_DOMAIN, span=None), env
        ),
    }
    for label, resolve_it in resolvers.items():
        assert resolve_it() == TInteger(), (
            f"{label} maps an admitted position domain to "
            f"{resolve_it()!r} — resolve admits the name, so this is a "
            f"permissive-top leak, not a rejection"
        )
    # ...and the optional spelling keeps its optionality rather than flattening.
    optional = typecheck._param_type(
        n.MoveParam(name="x", type_name=f"{POSITION_DOMAIN}?", span=None), env
    )
    assert optional == TOptional(TInteger()), (
        f"an optional position domain flattened to {optional!r}, so a body "
        f"would treat a nullable parameter as definitely present"
    )


def test_the_position_axis_is_the_grammar_s() -> None:
    """The position axis is scraped, not hand-listed.

    A new production that carries a type name arrives as a missing row here,
    which is the whole point: a hand-listed axis is complete only by luck and
    goes stale silently when a parallel change extends the surface.

    red under: add a production referencing `type_name` to cardlang.lark
    without adding its row to POSITIONS.
    """
    grammar = resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()
    carriers = set()
    for line in grammar.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r"^([a-z_]+):", s)
        if (
            m
            and re.search(r"\b(type_name|payload_type)\b", s)
            and m.group(1) not in ("type_name", "payload_type")
        ):
            carriers.add(m.group(1))
    # `move_param` is one production reached from three hosts (move type,
    # procedure, rule), and each host gates it differently — so the axis counts
    # HOSTS, not productions, and the scrape's `move_param` expands to three.
    gridded = {production for production, _ in POSITIONS.values()}
    expanded = (gridded - {"move_type_def", "procedure_def", "rule_params"}) | {"move_param"}
    # `require_decl` (a library's `requires { x : type_name }`) is the one
    # type-name carrier outside this grid's domain, and structurally so: every
    # POSITIONS cell emits a STANDALONE game string, but a `require_decl` can
    # appear only inside `library { }`, loaded by name — so there is no game to
    # put it in, and mirroring the type on a game `state` var would test the P1
    # gate, not this one. Its type is validated transitively and loudly instead:
    # the including game must declare the same name, and `_check_requires`
    # rejects a require type that does not match the game's declaration — naming
    # the library and quoting the type, so a library-side typo (`Integar`) is
    # surfaced, not silently dropped. The residual is span PRECISION only (the
    # diagnostic lands on the game's `uses` line, not the library's `requires`),
    # recorded in issue #128; the coverage lives in test_family_libraries.py.
    library_only = {"require_decl"}
    missing = carriers - expanded - library_only
    assert not missing, (
        f"grammar productions carrying a type name with no grid row: {sorted(missing)}"
    )


def test_a_plain_assertion_does_not_satisfy_a_designed_to_flip_cell() -> None:
    """The xfail marks are tied to CellMismatch, not to AssertionError.

    Pytest's assertion rewriting turns every failed `assert` into an
    `AssertionError`, so a mark that accepted the base class would let a
    helper failure, a broken fixture, or an import error impersonate the
    designed red run.

    red under: change `CellMismatch` to alias `AssertionError` (`CellMismatch =
    AssertionError`) — the isinstance check below then holds and this fails.
    """
    # `raises=` matches by isinstance, so this is exactly the discrimination a
    # designed-to-flip mark relies on: a helper's plain assertion is NOT a
    # CellMismatch, so it cannot satisfy the mark and register as design-red.
    assert not isinstance(AssertionError("a helper failed"), CellMismatch)
    # ...while a real cell mismatch still satisfies the AssertionError contract
    # pytest expects of a failing test.
    assert isinstance(CellMismatch("cell"), AssertionError)
