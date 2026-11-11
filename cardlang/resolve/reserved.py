"""Spellings the resolver reserves: pronouns, value names, the Play Source.

A shared module: the steps read it, and it imports no step.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Establishes:  the reserved spellings every step refuses a declaration or
              binder by, each named once here.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.attribution import cite_named
from cardlang.diagnostics import DiagnosticBag

# The three domain-registry views the resolve pass gates on, all derived from the one
# table in `cardlang.domains` (which also owns typecheck's binder typing and the
# runtime's member enumerators, so the sites can't drift):
#
# - `_ITERATION_ROLES` — the roles `for each <role> <binder>` may range over
#   (the registry's `iterable` column). Quantifier roles are fixed by their
#   grammar productions instead, so they need no set here.
# - `SIMULTANEOUS_ROLES` — the roles `each <role> simultaneously:` may range
#   over (the `simultaneous` column): seat domains only, since a value domain
#   has no actor to move simultaneously.
# - `_FIXED_DOMAINS` / `PARAM_DOMAIN_ORDER` — the statically enumerable
#   move-parameter domains (the union of the rows' `param_domains`), as a set
#   for the membership gate and as a sequence for the diagnostic that lists them.

# The magic namespaces a bare name may resolve to.
_PRONOUNS = frozenset({"state", "action", "winner", "active_rules", "actor"})

# The spelling a rule clause reads the Play Source by: the cards the player on
# turn plays from at the trick round's card decision, the one decision a rule
# is asked at (decisions.md "Rule demand forms").
PLAY_SOURCE_NAME = "hand"
_PLAY_SOURCE_READING = (
    "inside a rule, `hand` is the cards the player on turn plays from"
)
_SUBSCRIPTED_PLAY_SOURCE = (
    "inside a rule, `hand` is already the cards the player on turn plays from; "
    "write `hand` alone (this game declares no `hand` for a subscript to name)"
)

# Pronouns that name call-site context (`_user_function` clears them before a
# function body runs). A hermetic body may not read them — it would see None;
# pass the value in as a parameter instead. `state`/`active_rules` are game/phase
# context and remain readable.
_CALL_SITE_PRONOUNS = frozenset({"actor", "action", "winner"})

# Reserved because the language spells them as CLAUSE KEYWORDS, not because a
# pronoun namespace claims them. `outcome` opens a phase's `-> outcome { }`,
# but nothing binds it as a value (a phase's tagged result reaches its consumer
# through the produce path — `execute.py`'s `_ProduceSignal` — never a context
# slot). Keeping it reserved
# is what makes the pre-#205 spelling of a trick winner (`leader := outcome`)
# fail loudly rather than bind to whatever state variable a game happens to
# declare. Un-reserving it would widen the accepted surface, so it waits for its
# own change. The Stake words (`n.STAKES`) are a move type's row and never a
# value either, so a declaration spelled like one would read, at every bare use,
# as something the row is not. Move-type names stay free of the sweep, as for
# `outcome`: a move type's name is never a bare value.
_KEYWORD_RESERVED = frozenset({"outcome", *n.STAKES})

# Value-words a DECLARATION may never take, because a bare NameRef spelling
# the same word can never mean "the declaration" — some other fixed reading
# always wins, silently: `none`/`true`/`false` are literals `_classify` (below)
# intercepts before any declaration namespace even runs; `empty` is intercepted
# earlier still, at PARSE time (`x is empty` always builds an `IsCheck`, never a
# `NameRef`, no matter what `empty` is declared as — parse.py's `compare_is`/
# `compare_is_not`); and each `_PRONOUNS` word is a fixed context namespace
# (`state.led_suit`, bare `actor`, …) a same-named declaration would instead
# shadow — silently changing what `state.foo` means rather than erroring.
# `card`/`player` are deliberately absent: both are established, corpus-wide
# LEXICAL shadow idioms (a card-query/quantifier binder, always scoped strictly
# narrower than a same-named outer declaration — see `_BINDER_SCOPE_FIELDS`),
# which is the intended shadowing `_check_duplicate_names`'s docstring already
# carves out, not a defect this reservation needs to close.
# The third arm, `_KEYWORD_RESERVED`, has its own mechanism (above): the word is
# a clause keyword rather than a namespace.
RESERVED_VALUE_NAMES: frozenset[str] = (
    frozenset({"none", "empty", "true", "false"}) | _PRONOUNS | _KEYWORD_RESERVED
)

_RESERVED_WHY: dict[str, str] = {
    "none": "`x is none` always reads it as the null check",
    "empty": "`x is empty` always reads it as the emptiness check",
    "true": "it is the boolean literal",
    "false": "it is the boolean literal",
    "state": "it is the round state pronoun (`state.led_suit`)",
    "action": "it is the call-site action pronoun",
    "winner": "it is the call-site winner pronoun",
    "outcome": "it is a clause keyword (a phase's `-> outcome`)",
    **{stake: "it is a clause keyword (a move type's Stake row)" for stake in n.STAKES},
    "active_rules": "it is the active-rules pronoun",
    "actor": "it is the call-site actor pronoun",
}


def _refuse_play_source_params(rule: n.RuleDef, bag: DiagnosticBag) -> bool:
    """A rule parameter spelled like the Play Source would take the place of
    every bare `hand` its clauses read. The Owner Guard for a rule wherever it
    is written: a game's template, a family library's, the stdlib's. True when
    it fired."""
    fired = False
    for p in rule.params:
        if p.name == PLAY_SOURCE_NAME:
            bag.error(
                f"a rule's parameter cannot be named `{PLAY_SOURCE_NAME}`: "
                f"{_PLAY_SOURCE_READING} — rename the parameter of rule "
                f"" + cite_named(rule, f"'{rule.name}'"),
                p.span or rule.span,
                code=Code.RESERVED_WORD,
            )
            fired = True
    return fired


# The param-bearing declaration kinds: node type -> (how to reach them from a
# `Game`, the diagnostic noun, the reserved set their parameters check
# against). This table is pinned to the AST by tests/test_node_registry.py —
# every `Node` member with a `params` field must have a row — so a new
# parameterized declaration form cannot ship with its parameters silently
# exempt from the reserved-word sweep. The reach is a CALLABLE rather than an
# attribute name because a declaration form's holder need not be a top-level
# `Game` list: a `primitives { }` entry lives inside the block, and reaching
# it by attribute would mean either a special case here or a second top-level
# field mirroring the block. (The pronoun carve-out below: function
# and procedure bodies are hermetic — forbidden from READING the call-site
# pronouns — so naming a parameter after one is that error message's own
# prescribed fix, not a hijack. Move-type/rule bodies read the pronouns live,
# so all five stay reserved there. A Primitive's parameters read nothing at
# all — they label the declaration and key its `reads` binders — so the full
# set stays reserved for them. See `_check_reserved_params`.)
_ParamBearer = n.FunctionDef | n.ProcedureDef | n.MoveTypeDef | n.RuleDef | n.PrimitiveDecl


@dataclass(frozen=True, slots=True)
class _ParamBearing:
    """One param-bearing declaration kind's row."""

    reach: Callable[[n.Game], tuple[_ParamBearer, ...]]
    noun: str
    reserved: frozenset[str]
    library_field: str | None
    """The `n.Library` field holding this kind, or None for a kind a library
    cannot hold. `primitives { }` is a game clause and no `?library_item`, so
    a Primitive declaration has no library home — stated here so the family-
    library sweep derives which kinds it must cover instead of intersecting
    two name lists that happen to coincide."""
    scopes_body: bool
    """Whether DSL text sits inside these parameters' scope — the region where a
    bare `NameRef` means the parameter rather than a state variable. True for
    the four kinds `_classify_names` widens `cats.locals` for; False for a
    Primitive declaration, whose parameters label a Python signature and key its
    `reads` binders, so no DSL body is scoped by them and nothing can shadow.
    Declared rather than read off `library_field is None`, which happens to
    agree today and means something else entirely — the sweeps that must skip a
    body-less kind ask this question, so a sixth row answers it rather than
    inheriting an answer. Pinned against `_rewrite`'s own params-scoping arms by
    `tests/test_family_libraries.py::test_every_param_bearing_row_agrees_with_
    the_pass_that_scopes_it`."""


_PARAM_BEARING: dict[type, _ParamBearing] = {
    n.FunctionDef: _ParamBearing(
        lambda game: game.functions,
        "function parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
        "functions",
        scopes_body=True,
    ),
    n.ProcedureDef: _ParamBearing(
        lambda game: game.procedures,
        "procedure parameter",
        RESERVED_VALUE_NAMES - _CALL_SITE_PRONOUNS,
        "procedures",
        scopes_body=True,
    ),
    n.MoveTypeDef: _ParamBearing(
        lambda game: game.move_types,
        "move-type parameter",
        RESERVED_VALUE_NAMES,
        "move_types",
        scopes_body=True,
    ),
    n.RuleDef: _ParamBearing(
        lambda game: game.rules,
        "rule parameter",
        RESERVED_VALUE_NAMES,
        "rules",
        scopes_body=True,
    ),
    n.PrimitiveDecl: _ParamBearing(
        lambda game: () if game.primitives is None else game.primitives.decls,
        "Primitive parameter",
        RESERVED_VALUE_NAMES,
        None,
        scopes_body=False,
    ),
}
