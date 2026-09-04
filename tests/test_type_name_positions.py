"""The declared-type-name POSITION x NAME-SOURCE grid.

Every syntactic position where a program writes a declared type name, crossed
with every source a legal name can come from. Each cell states what that
position's gate does with that name: `admit`, or a named rejection. The grid is
DERIVED — the position axis is scraped from the grammar productions that
reference a type-carrying nonterminal, the admissible sets are computed from
the registries — so a new position or a new name source arrives as uncovered
cells that force someone to classify them, rather than as silence.

The defect class this exists to close (docs/decisions.md, "Closed-domain
completeness"): a domain whose axes are hand-listed. The guard this module
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
                  A. positions — the grammar productions referencing any of
                     the three type-carrying nonterminals (`_TYPE_CARRIERS`:
                     `type_name`, `payload_type`, `primitive_type`), plus
                     `struct_lit` whose head NAME is a type name in EXPRESSION
                     position. `POSITIONS` is the row set and
                     `_grammar_carriers()` the scrape; a row that reaches its
                     type name through another production is translated to
                     that HOST by `_carrier_host`, a breadth-first walk over
                     the grammar's own right-hand sides, so no host mapping is
                     authored and none can hold a value the grammar does not
                     back. The two are held equal in BOTH directions
                     (`test_the_position_axis_is_the_grammar_s`,
                     `test_every_gridded_production_is_still_a_grammar_carrier`),
                     and the walk itself is a per-row cell
                     (`test_every_grid_row_reaches_its_type_name_through_the_grammar`)
                     because a row the walk answers nothing for would drop out
                     of both directions at once. This carves out the one
                     type-name carrier that
                     cannot appear in a standalone game — a library's
                     `require_decl`, validated transitively by
                     `_check_requires` and covered in
                     `test_family_libraries.py`, not here.
                     Every derivation above reads `_bodies_of`, which takes a
                     rule's body to be its definition line plus each following
                     line that opens with `|`. Two shapes could hide a
                     reference from it, and they are held differently: a
                     modifier on the rule's own name is READ, pinned by
                     `test_the_rule_scrape_reads_a_prefixed_rule`; an
                     alternative wrapping onto a line that opens with neither
                     `|` nor a name is ASSUMED absent, stated rather than
                     pinned, with the query that holds it in `_bodies_of`'s
                     own docstring.
                  B. name sources — `KNOWN_TYPE_NAMES`, `PARAM_DOMAINS`,
                     `_PROCEDURE_PARAM_DOMAINS`, the two bare inline literals
                     (`Card` at a move param, `Suit` at a rule param), per-game
                     `type` declarations, per-game `positions {}` declarations,
                     the block's one parameterized value spelling
                     (`COLLECTION_NAME`), and an unknown name as the negative
                     control.

    registry:   A. cardlang/grammar/cardlang.lark (scraped by the pin below)
                B. typecheck.KNOWN_TYPE_NAMES; domains.PARAM_DOMAINS;
                   resolve._PROCEDURE_PARAM_DOMAINS; resolve's inline `Card`
                   and `Suit` literals; the game's own TypeDef / PositionDecl

    covered:    The grid: `test_the_type_name_grid` over CELLS — `POSITIONS` x
                `NAMES`, every one executed. `EXPECTED_ADMITS` is computed per
                position from the registries, so the covered set cannot drift
                from the domain set by hand-editing a row. `_outcome` reads the
                verdict through an ALLOW-LIST over the message space
                (`_GATE_REFUSALS`, `_PAST_THE_GATE`) and raises on a diagnostic
                neither names, so a refusal in an unlisted voice cannot pass
                for an admit. The collection column carries a second
                assertion the rest of the grid does not:
                `test_the_collection_column_reaches_the_message_its_position_owns`
                pins WHICH refusal each position gives, derived from the type
                nonterminal that position writes through, because "not
                admitted" is satisfied by a lexer error as readily as by the
                ruled twin.

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
                   The guard is loud but the message spells it `unknown type
                   '<name>'`; naming the sharper reason (a position domain is
                   not a declared type in this slot) is a message-quality
                   residual, and the grid asserts admit-vs-reject only, not the
                   message text. Recorded in issue #133.
                2. THE BARE CONSTRUCTOR WORD IS NOT A COLUMN. `Collection`
                   with no argument is refused everywhere, and the SENTENCE
                   splits: a `primitives { }` entry says it takes an element
                   type and names the ruled spelling, while every position
                   here says `unknown type 'Collection'` — the "unknown"
                   currency spent on a word the language has a meaning for
                   and the checker itself prints. The BRACKETED spelling has
                   no such split any more (the teaching twin reaches every
                   type position, and the zone slot names which bracket it
                   is), so this is the remainder of that class rather than
                   part of it, and closing it is a change across the five
                   sites that phrase "unknown type" plus the move-parameter
                   domain gate — its own grid, not a column here. R2: a
                   designer who writes `s : Collection` at a state row meets
                   it. It carries NO tracker issue: the only record is the
                   review round's report, and this sentence.
                3. NAMESPACES B AND C ARE NOT IN THIS GRID. Zone type names
                   (`Hand<player>`) and role/domain ids (the `player` in
                   `hand[player]`, `for each player`) are type-ish names with
                   their own registries and their own guards; the framing check
                   enumerated seven such positions. They are a different
                   domain, not a missing part of this one. Their own raggedness
                   -- a zone index admits position domains where a state index
                   does not -- is recorded in issue #98.
"""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Callable
from importlib import resources

import pytest

from cardlang import typecheck
from cardlang.ast import nodes as n
from cardlang.domains import PARAM_DOMAINS
from cardlang.pipeline import check_dsl
from cardlang.primitives_block import DECLARABLE_BUILTIN_TYPE_NAMES
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
  positions { column : 1..8 }%(extra_clause)s
  zones { deck : Deck  hand[player] : Hand<player> }
  state { score[player] : Integer = 0  tick : Integer = 0%(extra_state)s }
  phase play%(outcome)s {%(rules)s for each player p: score[p] := 1 }
  winner: highest score
}
type T = { x : Integer }
%(extra)s"""


def _prog(*, extra: str = "", extra_state: str = "", outcome: str = "",
          rules: str = "", extra_clause: str = "") -> str:
    return GAME % {"extra": extra, "extra_state": extra_state,
                   "outcome": outcome, "rules": rules,
                   "extra_clause": extra_clause}


# Each entry: the grammar production that carries the name, and a probe that
# puts `d` in exactly that position. Probes are shaped so the only thing under
# test is the type-name gate: a procedure body reads no call-site pronoun, and
# a parameterized rule is instantiated, because neither is about this axis.
POSITIONS: dict[str, tuple[str, object]] = {
    "P1 state_decl": ("state_decl", lambda d: _prog(extra_state=f"  s : {d} = 1")),
    "P2 struct_field": ("struct_field", lambda d: _prog(extra=f"type S2 = {{ x : {d} }}")),
    "P3 move_param": ("move_type_def", lambda d: _prog(
        extra=f"move_type mv(x : {d}) {{ effect {{ score[actor] := 1 }} }}")),
    "P4 proc_param": ("procedure_def", lambda d: _prog(
        extra=f"procedure pr(x : {d}) {{ tick := 1 }}")),
    "P5 rule_param": ("rule_params", lambda d: _prog(
        rules=" active_rules: [Rl(hearts)]",
        extra=f"rule Rl(x : {d}) {{ demands: true }}")),
    "P6 func_param": ("function_def", lambda d: _prog(extra=f"function f(x : {d}) = 1")),
    "P7 define_payload": ("outcome_case", lambda d: _prog(
        extra=f"define dd -> {{ won({d}) | lost }} {{ produce lost }}")),
    "P8 outcome_payload": ("phase_outcome", lambda d: _prog(
        outcome=f" -> outcome {{ won({d}) | lost }}")),
    "P9 struct_lit": ("struct_lit", lambda d: _prog(extra=f"function f() = {d} {{ x: 1 }}")),
    # The `primitives { }` entry's two type slots. Both name an IMPLEMENTED
    # Primitive, so the only thing under test is the type-name gate: an
    # unimplemented name would trip its own guard first and the cell would be
    # measuring that instead.
    "P10 primitive_param": ("primitive_param", lambda d: _prog(
        extra_clause=f"\n  primitives {{ pinochle_meld_value(x : {d}) : Integer }}")),
    "P11 primitive_return": ("primitive_decl", lambda d: _prog(
        extra_clause=f"\n  primitives {{ pinochle_meld_value(p : Player) : {d} }}")),
}

# --- Axis B: the name sources ----------------------------------------------

POSITION_DOMAIN = "column"   # declared by the probe game's `positions {}`
USER_STRUCT = "T"            # declared by the probe game's `type T`
UNKNOWN_NAME = "Bogus"       # the negative control

COLLECTION_NAME = "Collection<Card>"  # the one parameterized value spelling
# The collection's optional spelling. Admitted nowhere — a collection is never
# optional — but it is a sentence a designer writes, so it is a column of its
# own rather than a shape left to the lexer.
COLLECTION_OPTIONAL = "Collection<Card>?"

NAMES = [
    "Integer", "Boolean", "Player", "Card", "Team", "Suit", "Rank",
    "Rank?", "Suit?", "SeatDirection", POSITION_DOMAIN, USER_STRUCT, UNKNOWN_NAME,
    COLLECTION_NAME, COLLECTION_OPTIONAL,
]

DECLARED = frozenset(KNOWN_TYPE_NAMES) | {USER_STRUCT}
_BASE_STRIPPED = DECLARED | {f"{n}?" for n in DECLARED}
# What a `primitives { }` entry may spell, from the block's own registry
# crossed with the probe game's position domain — never a hand-listed copy.
_PRIMITIVE_BASE = DECLARABLE_BUILTIN_TYPE_NAMES | {POSITION_DOMAIN}
_PRIMITIVE_SPELLABLE = frozenset(
    _PRIMITIVE_BASE | {f"{n}?" for n in _PRIMITIVE_BASE}
)

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
    # A `primitives` entry spells the built-in declared-type names, the game's
    # position domains, and the one parameterized value spelling — and NOT a
    # declared struct: a Primitive receives values across the narrowing
    # boundary, and no witness carries a `StructValue` over it (issue #547).
    # Both slots take the same set: the return slot admits `Collection<Card>`
    # at this gate and the both-ways shape check refuses every concrete entry,
    # which is the `cell` precedent and is not this gate's answer.
    "P10 primitive_param": _PRIMITIVE_SPELLABLE | {COLLECTION_NAME},
    "P11 primitive_return": _PRIMITIVE_SPELLABLE | {COLLECTION_NAME},
}

# The red set: cells a change designs to flip, carried as strict xfails so the
# pre-push checks stay green while the grid is red, and so a flip cannot be
# forgotten (a leftover mark on a now-passing cell fails loudly). Empty between
# changes; this grid shipped with the three position-domain cells at
# P6/P7/P8 in it, which the same change turned green at resolve AND in the
# function signature builder — resolve alone would have admitted the name and
# left the type layer mapping it to the permissive top.
DESIGNED_TO_FLIP: set[tuple[str, str]] = set()


# The gate's own refusals, ORDERED: the first match names the outcome. An
# allow-list over an open message space, because the alternative reads silence
# as an admit — and a refusal in a voice nobody listed is exactly the reading
# that must not pass for one.
_GATE_REFUSALS: tuple[tuple[str, str], ...] = (
    # BEFORE the generic rows: the entry-slot twin's sentence carries no
    # needle any of them would match, and a row added after `syntax` would be
    # unreachable for the spellings the grammar refuses in its own voice.
    ("a collection is never optional", "collection-optional"),
    ("syntax error", "syntax"),
    ("unknown type", "unknown-type"),
    ("domain", "domain"),
    ("may not spell", "unspellable"),
    ("is spellable in a `primitives { }` entry only", "collection-elsewhere"),
)

# Refusals from BELOW the gate: the name was admitted and a later guard spoke.
# Each is named, so a new one arrives as an unclassified message rather than as
# a silent admit — the shape check in particular, whose sentence a deny-list
# read as an admit by the accident of the fallthrough.
_PAST_THE_GATE: tuple[str, ...] = (
    "is not the signature its implementation takes",
    "is never run",
    "constrains no move type",
    "but its default has type",
    "is out of range",
)


class UnclassifiedOutcome(AssertionError):
    """A probe's diagnostic matched no row of either table above."""


def _outcome(src: str) -> str:
    """What this position's type-name gate did with the name.

    The subject is the gate, not whole-program validity: a probe that clears
    the gate and then trips an unrelated guard is still `admit`.
    """
    try:
        check_dsl(src, "grid")
    except UnclassifiedOutcome:
        raise
    except AssertionError:
        return "raise"          # compiler-channel failure: always a defect here
    except Exception as e:  # noqa: BLE001 - every user-facing channel is in scope
        msg = "\n".join([str(e), *(list(getattr(e, "__notes__", None) or []))])
        for needle, label in _GATE_REFUSALS:
            if needle in msg:
                return label
        if any(needle in msg for needle in _PAST_THE_GATE):
            return "admit"
        raise UnclassifiedOutcome(
            f"no row of `_GATE_REFUSALS` or `_PAST_THE_GATE` names this "
            f"diagnostic, so the grid cannot tell a refusal from an admit: "
            f"{msg}"
        ) from e
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


# The collection column's expected MESSAGE, per position. The grid above
# asserts admit-vs-not, which a refusal in the wrong voice satisfies; this
# says WHICH refusal. Derived from the type nonterminal the position's host
# writes its type name through, because that is what decides: the teaching
# twin rides `type_name` and `payload_type`, the entry family answers in its
# own voice, and a position with no type nonterminal at all has no twin to
# reach.
_TWIN_BY_CARRIER: dict[str | None, dict[str, str]] = {
    "type_name": {
        COLLECTION_NAME: "collection-elsewhere",
        COLLECTION_OPTIONAL: "collection-elsewhere",
    },
    "payload_type": {
        COLLECTION_NAME: "collection-elsewhere",
        COLLECTION_OPTIONAL: "collection-elsewhere",
    },
    "primitive_type": {
        COLLECTION_NAME: "admit",
        COLLECTION_OPTIONAL: "collection-optional",
    },
    # A struct literal's head is `STRUCT_TYPE_NAME` in EXPRESSION position, so
    # no type production is in play and no twin can be reached — the lexer's
    # own voice is the whole answer available there, and saying so is what
    # keeps this column from asserting a message the grammar cannot produce.
    None: {COLLECTION_NAME: "syntax", COLLECTION_OPTIONAL: "syntax"},
}


def _position_carrier(position: str) -> str | None:
    """Which type nonterminal `position` writes its type name through."""
    production, _ = POSITIONS[position]
    host = _carrier_host(production)
    if host is None:
        return None
    body = _grammar_bodies()[host]
    written = [c for c in _TYPE_CARRIERS if re.search(rf"\b{c}\b", body)]
    assert len(written) == 1, (
        f"{position}'s host '{host}' writes {written or 'no'} type "
        f"nonterminal(s); the expected-message column needs exactly one"
    )
    return written[0]


_TWIN_CELLS = [
    (position, spelling)
    for position in POSITIONS
    for spelling in (COLLECTION_NAME, COLLECTION_OPTIONAL)
]


@pytest.mark.parametrize(
    "position,spelling",
    _TWIN_CELLS,
    ids=[f"{p.split()[1]}-{s}" for p, s in _TWIN_CELLS],
)
def test_the_collection_column_reaches_the_message_its_position_owns(
    position: str, spelling: str
) -> None:
    """Every collection cell is pinned to its TEACHING TWIN, not merely to
    "not admitted".

    A grid that asserts admission alone cannot tell the ruled refusal from any
    other loud one, so a position whose twin stopped landing — because a
    parallel change moved a production off the shared carrier, say — would
    keep passing while its designer met the lexer. The expected label is
    derived from the grammar, so a position that changes carriers changes its
    expectation with it rather than being re-authored by hand.

    red under: delete the `collection_type_reject` alternative from
    `payload_type` in cardlang.lark — the four `parameter` hosts and the
    outcome payloads then answer `syntax` against a `collection-elsewhere`
    expectation.
    """
    _production, build = POSITIONS[position]
    expected = _TWIN_BY_CARRIER[_position_carrier(position)][spelling]
    actual = _outcome(build(spelling))  # type: ignore[operator]
    assert actual == expected, (
        f"{position} answered {actual!r} for {spelling!r}; the position writes "
        f"its type through {_position_carrier(position)!r}, whose ruled "
        f"answer is {expected!r}"
    )


@pytest.mark.parametrize("position", sorted(POSITIONS))
def test_a_retired_type_name_is_loud_in_every_position(position: str) -> None:
    """`Direction` was the SeatDirection enum's declared name until issue
    #201 renamed it `SeatDirection`, and Hearts declared one. A retired
    spelling is the sharpest case of this module's property, because it is the
    one an author has in muscle memory and in an in-flight game file: a
    silently-`TAny` `pass_direction` would keep typechecking and exempt itself
    from the `offset_by` operand guard. The grid above covers the CLASS (an
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
    gate that rejects it: the name is accepted and every guard below it goes
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
            n.Parameter(name="x", type_name=POSITION_DOMAIN, span=None), env
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
        n.Parameter(name="x", type_name=f"{POSITION_DOMAIN}?", span=None), env
    )
    assert optional == TOptional(TInteger()), (
        f"an optional position domain flattened to {optional!r}, so a body "
        f"would treat a nullable parameter as definitely present"
    )


# The grammar's type-carrying nonterminals. A production referencing ANY of
# them writes a declared type name, so the scrape reads all three: an entry-only
# family added beside the two shared ones would otherwise take P10 and P11 out
# of the carrier set with nothing going red.
_TYPE_CARRIERS: tuple[str, ...] = ("type_name", "payload_type", "primitive_type")


# Grid rows whose type name is written in EXPRESSION position, with its own
# terminal rather than through a type nonterminal — so the grammar scrape
# cannot see them, and the reverse direction says so rather than by omission.
_EXPRESSION_POSITIONS: frozenset[str] = frozenset({"struct_lit"})


def _grammar_text() -> str:
    """The grammar file's source."""
    return resources.files("cardlang.grammar").joinpath("cardlang.lark").read_text()


def _bodies_of(grammar: str) -> dict[str, str]:
    r"""Every rule name in `grammar` mapped to its whole right-hand side.

    A rule may continue over several lines — an alternative written on its own
    line with a leading `|` — so a body accumulates until the next definition.
    Reading the first line alone would make a carrier referenced from a later
    alternative invisible, which is the shape of blindness this module exists
    to close one axis up. A continuation opening with neither `|` nor a name
    would be dropped just as silently; that the grammar has none is an
    ASSUMPTION, and it holds while

        grep -vE '^[[:space:]]*(//|\||%|$)' cardlang/grammar/cardlang.lark |
          grep -vE '^[[:space:]]*[?!]{0,2}_?[A-Za-z][A-Za-z0-9_]*(\.-?[0-9]+)?[[:space:]]*:'

    prints nothing — every line of the file being a comment, a directive, a
    definition, or an alternative that opens with `|`.

    A rule's MODIFIER is skipped and its bare name kept, because that is the
    name every reference spells: lark's `RULE_MODIFIERS` are `!`, `?` and
    their two orders, and a table keyed by `?statement` would answer nothing
    for the `statement` a body writes.

    Takes the text rather than reading the file, so a cell can plant a shape
    the real grammar does not carry without writing to it.
    """
    bodies: dict[str, str] = {}
    current: str | None = None
    for line in grammar.splitlines():
        s = line.strip()
        if not s or s.startswith("//"):
            continue
        m = re.match(r"^[?!]{0,2}(_?[a-z][a-z0-9_]*)\s*:", s)
        if m:
            current = m.group(1)
            bodies[current] = s[m.end() :]
        elif s.startswith("|") and current is not None:
            bodies[current] += " " + s
        else:
            current = None
    return bodies


def _grammar_bodies() -> dict[str, str]:
    """Every rule name in cardlang.lark mapped to its whole right-hand side."""
    return _bodies_of(_grammar_text())


def test_the_rule_scrape_reads_a_prefixed_rule() -> None:
    """A modifier is part of lark's rule SYNTAX, not part of the rule's name.

    Lark spells the modifiers `!`, `?`, `!?` and `?!` (its own
    `RULE_MODIFIERS`), and a rule carrying one is still referenced by its bare
    name — so a splitter that required the name to start the line would hold a
    body table with every prefixed rule missing, and a carrier referenced from
    one, or a walk passing through one, would be invisible to both scrape
    directions and to `_carrier_host` at once. The plant is a scratch copy of
    the grammar text; the file itself is never written.

    red under: drop the modifier prefix from `_bodies_of`'s rule pattern."""
    bodies = _bodies_of(_grammar_text() + "\n?planted_item: parameter\n")
    assert "parameter" in bodies.get("planted_item", ""), (
        "the scrape did not read `?planted_item: parameter` as the rule "
        "`planted_item`, so a prefixed rule is invisible to it — and to every "
        "derivation over its keys"
    )


def _grammar_carriers() -> set[str]:
    """Every production that references a type-carrying nonterminal."""
    bodies = _grammar_bodies()
    return {
        name
        for name, body in bodies.items()
        if name not in _TYPE_CARRIERS
        and re.search(rf"\b({'|'.join(_TYPE_CARRIERS)})\b", body)
    }


def _carrier_host(production: str) -> str | None:
    """The nearest production reachable from `production` that writes a type
    name — itself, if it references a carrier directly.

    A grid row whose production reaches its type name THROUGH another one is
    counted at that HOST, not at the row: the four `parameter` hosts gate one
    production differently, and a phase's outcome set is `define`'s read at
    another site. Both scrape directions translate a row through this walk, so
    neither keeps a list of its own and neither can hold a value the grammar
    does not back — the defect a hand-written host table had, where a wrong
    value left both directions green.

    The walk is breadth-first over the grammar's own RHS references and stops
    at the first depth that reaches a carrier; a tie at that depth is a
    production this walk cannot name, so it raises rather than picking one.
    """
    direct = _grammar_carriers()
    if production in direct:
        return production
    bodies = _grammar_bodies()

    def refs(name: str) -> set[str]:
        body = bodies.get(name, "")
        return {t for t in re.findall(r"\b_?[a-z][a-z0-9_]*\b", body) if t in bodies}

    seen = {production}
    frontier = deque([(production, 0)])
    hits: dict[int, set[str]] = {}
    while frontier:
        node, depth = frontier.popleft()
        if hits and depth > min(hits):
            break
        for reference in sorted(refs(node)):
            if reference in direct:
                hits.setdefault(depth + 1, set()).add(reference)
            if reference not in seen:
                seen.add(reference)
                frontier.append((reference, depth + 1))
    if not hits:
        return None
    nearest = hits[min(hits)]
    assert len(nearest) == 1, (
        f"'{production}' reaches {sorted(nearest)} at equal depth, so the "
        f"grid row has no single host — the walk cannot pick one for it"
    )
    return next(iter(nearest))


def _gridded_hosts() -> set[str]:
    """Every grid row's production, translated to the host that writes its
    type name. A row in `_EXPRESSION_POSITIONS` reaches none and is dropped
    here rather than compared against a carrier set it was never in."""
    hosts = set()
    for production, _ in POSITIONS.values():
        host = _carrier_host(production)
        if host is not None:
            hosts.add(host)
    return hosts


def test_the_position_axis_is_the_grammar_s() -> None:
    """The position axis is scraped, not hand-listed.

    A new production that carries a type name arrives as a missing row here,
    which is the whole point: a hand-listed axis is complete only by luck and
    goes stale silently when a parallel change extends the surface.

    red under: add a production referencing `type_name` to cardlang.lark
    without adding its row to POSITIONS.
    """
    carriers = _grammar_carriers()
    expanded = _gridded_hosts()
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
    # The `primitives` block's two reject arms carry a type name only so their
    # rejection can QUOTE it (`... : Integer`, naming the colon form). The
    # builder raises before any type-name gate runs, so there is no gate at
    # these productions to grid — their own cells are the rejection tests in
    # tests/test_primitives_block.py.
    reject_arms = {"primitive_arrow_decl", "primitive_default_decl"}
    missing = carriers - expanded - library_only - reject_arms
    assert not missing, (
        f"grammar productions carrying a type name with no grid row: {sorted(missing)}"
    )


def test_every_gridded_production_is_still_a_grammar_carrier() -> None:
    """The scrape's other direction: a row whose production no longer carries a
    type name.

    One direction alone is half a pin. A production that stops referencing the
    scraped nonterminals — by moving to a family of its own, say — drops out of
    the carrier set, and a subtraction-only assertion goes green on exactly the
    change that took the position's grammar backing away.

    red under: rename `primitive_type` in cardlang.lark without renaming it in
    `_TYPE_CARRIERS`.
    """
    carriers = _grammar_carriers()
    orphans = _gridded_hosts() - carriers - _EXPRESSION_POSITIONS
    assert not orphans, (
        f"grid rows whose production no longer carries a type name: "
        f"{sorted(orphans)} — the position lost its grammar backing and the "
        f"subtraction above cannot see it"
    )


@pytest.mark.parametrize("position", sorted(POSITIONS))
def test_every_grid_row_reaches_its_type_name_through_the_grammar(
    position: str,
) -> None:
    """The host walk itself, one cell per grid row.

    The two scrape directions above both translate a row through
    `_carrier_host`, so a row whose walk answers nothing would drop out of
    BOTH and neither would notice — which is the vacuity a hand-written host
    table had in a different shape. This asserts the walk lands: every row
    either writes its type name itself, reaches exactly one production that
    does, or is an expression position with no type nonterminal at all.

    red under: delete `parameter` from `function_def`'s right-hand side in
    cardlang.lark — `function_def`'s walk then reaches no carrier and this
    row fails while both scrape directions stay green.
    """
    production, _ = POSITIONS[position]
    host = _carrier_host(production)
    if production in _EXPRESSION_POSITIONS:
        assert host is None, (
            f"{position} is recorded as an expression position, but the "
            f"grammar reaches a type nonterminal from it through '{host}'"
        )
        return
    assert host is not None, (
        f"{position}'s production '{production}' reaches no type-carrying "
        f"nonterminal, so both scrape directions drop it silently"
    )
    assert host in _grammar_carriers(), (
        f"{position}'s host '{host}' is not a carrier — the walk returned a "
        f"production that writes no type name"
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
