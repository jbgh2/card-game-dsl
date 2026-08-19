"""Typecheck stage.

Infers a :class:`~cardlang.types.Type` for every expression (`infer` over a
`TypeEnv` built from declared state vars, zone contents, and the deck / built-in
enum values) and validates: sensible player counts, assignment compatibility,
native argument types, subscripting only collections, and Boolean conditions
(`if` / `repeat until` / phase qualifiers). It accepts the whole corpus and
rejects real type errors.

Pragmatic by design: unrefined positions ([[pronoun]] member access, lambda values,
the `Resource`/`ChipStack` query API) infer the [[permissive-top]] `TAny`, which
propagates without error. Deferred to later stages: outcome types and
exhaustiveness (`TOutcome`), user-defined `type` declarations (`TStruct`), full
`ZoneContents`/`Resource` typing, and payload-type narrowing.

A pure validator: the (unchanged) :class:`Game` flows on, and the IR stays at
the resolved-AST level.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      a resolved AST (every ``NameRef`` classified, declarations
              unique, rule templates instantiated).
Establishes:  type validity only. The inferred :class:`~cardlang.types.Type`
              values are ephemeral — they are NOT written onto nodes.
              Downstream may assume every type Owner Guard held, but may not
              read types off the tree; a downstream consumer that needs a type
              is a signal to materialize it in this pass, never to re-infer it
              there.
Now illegal:  a type-invalid program, per the Owner Guards above and their
              completeness ledgers. Recorded residuals live in the tracker
              (issue #143 orders them) and in each Owner Guard module's ledger.
Verified by:  the Owner Guard test modules (operator, aggregation, context,
              ranking, rule-ref) and their ledgers.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import assert_never

from cardlang.ast import nodes as n
from cardlang.ast.nodes import Game
from cardlang.board_domains import directions_of
from cardlang.builtins.functions import TRICK_ORDER_GATED_WINNERS, TRICK_ORDER_ROWS
from cardlang.builtins.signatures import CALL_SIGS, ZONE_CONTENT, Sig
from cardlang.diagnostics import DiagnosticBag, DiagnosticError, Span
from cardlang.domains import require_role, role_type
from cardlang.runtime.values import component_set, content_kind_clause, content_noun
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES, rank_names, suit_names
from cardlang.stdlib.round_state import ROUND_STATE_FIELDS
from cardlang.types import (
    Flavor,
    TAny,
    TBoolean,
    TCard,
    TCell,
    TCollection,
    TDir,
    TEnum,
    TInteger,
    TLine,
    TNull,
    TOptional,
    TOutcome,
    TPlayer,
    TString,
    TStruct,
    TTeam,
    Type,
    coercible,
    join,
    subscriptable,
)


# Declared scalar type names → their Type. Enum names (`Suit`/`Rank`/`Direction`)
# and unknown names (user-defined types, deferred) are handled separately.
def _role_type(name: str) -> Type:
    """`role_type` reached through a parsed NAME.

    The one conversion site in this pass. Every caller here holds a role as it
    was written in the source — a `ForEach.role`, a `StateDecl.index` — and the
    registry takes a `Role`, so the string is classified once, here. A miss
    raises rather than falling back: resolve has already checked each of these
    positions against a subset of the registry, so an unclassifiable name means
    the two registries diverged, and the permissive `TAny` this used to return
    types the binder as the top and exempts every use of it from every type
    Owner Guard."""
    return role_type(require_role(name, "binder role"))


_SCALAR_TYPES: dict[str, type] = {
    "Integer": TInteger,
    "Boolean": TBoolean,
    "String": TString,
    "Player": TPlayer,
    "Team": TTeam,
    "Card": TCard,
}
_ENUM_TYPES = frozenset({"Suit", "Rank", "SeatDirection"})

# The closed set of built-in declared-type names (scalars + enums). resolve
# validates every declaration's type_name against this set plus the game's
# own struct names, so a typo ('Integar') is a diagnostic, never a silent
# TAny (closed-domain completeness, decisions.md).
KNOWN_TYPE_NAMES: frozenset[str] = frozenset(_SCALAR_TYPES) | _ENUM_TYPES

# A card's fields are a closed pair. One registry, shared by `infer` (typing
# a known-Card member access) and `_check_expr` (rejecting anything else) —
# a third field can be added to this dict and both sites see it, rather than
# two hand-enumerated pairs that could drift.
CARD_FIELDS: dict[str, Type] = {"rank": TEnum("Rank"), "suit": TEnum("Suit")}


def _axis_enum_names(game: Game) -> tuple[str, str]:
    """The enum type names for a game's two content axes (the suit slot, then
    the rank slot). A card game keeps the fixed `Suit`/`Rank` so its
    diagnostics and IR stay byte-stable; a piece set names its enums after its
    own axes (`side`/`kind`), which is also how its axis VALUES type in
    `value_enum_map` -- so a same-axis compare joins and a cross-axis one
    (`piece.side is mark`) hits the existing cross-enum Owner Guard."""
    cs = component_set(game.deck)
    if game.content_flavor == "card" or cs is None:
        return ("Suit", "Rank")
    return cs.axes


def item_field_table(game: Game) -> dict[str, Type]:
    """The content item's field table -- what `<binder>.<field>` may name and
    types to. A card game reproduces CARD_FIELDS exactly (`rank`/`suit` ->
    `Rank`/`Suit`); a piece set's axes ARE its fields (`side`/`kind`), each
    typed to its own enum. One source for `infer`'s field typing and
    `_check_expr`'s unknown-field Owner Guard, keyed off the game's flavor."""
    cs = component_set(game.deck)
    if cs is None:  # unknown set -- unreachable past resolve's component Owner Guard
        return dict(CARD_FIELDS)
    e0, e1 = _axis_enum_names(game)
    return {cs.axes[0]: TEnum(e0), cs.axes[1]: TEnum(e1)}

# `action` fields whose type is the same for every move type: the runtime
# `Move` payload (cardlang/runtime/state.py) carries exactly `card: Card` and
# `actor: Player`, always both present, for every move type. This is the
# sound subset of `action`'s shape — full move-type-aware typing (the
# per-move-type params reachable only as `action.<param name>`, e.g. an
# auction bid's `action.amount`) is out of scope; a field not in this
# registry stays `TAny` (residual — see the ledger in
# tests/test_zone_family_typing.py, which records it).
ACTION_FIELDS: dict[str, Type] = {"card": TCard(), "actor": TPlayer()}

# Native evaluations whose result depends on a declared `ranking:` — they
# index `rs.rank_index`, which is EMPTY when the game declares none (only
# `rs.ranks` falls back to deck order), so an ungated member is the
# accepted-then-crashes-bare class: a clean check, then a raw KeyError at
# playout. resolve.py already gates a bare `Rank` move-parameter domain on
# the same `has_ranking` condition (`_check_move_params`); these are the
# analogous compile-time gates for the three positions a member can be
# named from. Registries, not `if`s, so the next ranking-dependent function
# joins a set instead of a new branch.
#
# The member census (the #256 review round's class sweep — every call form
# and value callback whose evaluation reads rank_index, disposition per
# member; verified against bodies, not docstrings):
#   call forms, gated below: rank_value (builtins.py), the
#     highest_trump_or_led_suit call form (builtins.py, the Arrival Record
#     winner), peg_run_points / cribbage_show_value / cribbage_crib_value
#     (cribbage.py show/run scoring orders), belote_opp_winning (belote.py,
#     recomputes the live winner under the declared order).
#   winner callbacks, gated via RANKING_GATED_WINNERS at the trick round's
#     `winner` slot: highest_of_led_suit, highest_trump_or_led_suit
#     (winners.py), belote_trick_winner (belote.py). NON-member:
#     tarot_trick_winner — its body ranks atouts by their numerals and
#     plain suits by its own table, never rank_index, which is what keeps
#     french-tarot (a no-`ranking:` corpus game with trick rounds) legal.
#   climb queries, gated via RANKING_GATED_CLIMB_QUERIES at the climb
#     round's `combinations`/`follows` slots: president_lead_options,
#     president_follows (president.py reads facts.rank_index). NON-members:
#     the bigtwo_* and tichu_* engines, which carry their own orders.
#   NON-members elsewhere: peg_pair_points (rank equality only),
#     on_play_off_led_suit (suit only), and every auction outcome. The Rank
#     move-parameter domain is resolve's gate; `card_points` is gated by its
#     own clause-required guard, and a Trick Order's OMITTED `card_strength:`
#     row by `_check_trick_order`'s own ranking gate (the default is
#     `rank_value(card)`).
RANKING_GATED_FUNCS: frozenset[str] = frozenset(
    {
        "rank_value",
        "highest_trump_or_led_suit",
        "peg_run_points",
        "cribbage_show_value",
        "cribbage_crib_value",
        "belote_opp_winning",
    }
)
RANKING_GATED_WINNERS: frozenset[str] = frozenset(
    {"highest_of_led_suit", "highest_trump_or_led_suit", "belote_trick_winner"}
)
RANKING_GATED_CLIMB_QUERIES: frozenset[str] = frozenset(
    {"president_lead_options", "president_follows"}
)


def type_from_name(
    name: str,
    optional: bool,
    structs: Mapping[str, TStruct] | None = None,
    positions: Mapping[str, Type] | None = None,
    directions: Mapping[str, Type] | None = None,
) -> Type:
    """Map a declared type name (a `StateDecl` `type_name`) to a `Type`.

    User-defined struct names resolve to their `TStruct` (via the ``structs``
    registry); a declared POSITION domain resolves to its member type (via
    ``positions``, which maps each domain name to `TInteger` or, for the
    board-minted `cell` domain, `TCell`); a board-minted DIRECTION domain
    resolves to `TDir` (via ``directions``, the separate `dir` source);
    names unknown to scalars, enums, and every registry resolve to the
    permissive `TAny`. ``optional`` wraps the result in `TOptional`.

    Every position that admits a position/direction domain passes ``positions``/
    ``directions`` here rather than branching on it locally: the rule belongs to
    name resolution, and a caller that resolved the name without it would admit
    `slot`/`dir` at resolve and then map it to the top — the leak this module
    closes.
    """
    base: Type
    if positions is not None and name in positions:
        # A declared integer domain's member is `TInteger`; the board-minted
        # `cell` domain's is `TCell`. `positions` carries the member type so
        # the two are distinct (`at is 3` on a cell param is a type error).
        base = positions[name]
    elif directions is not None and name in directions:
        # The board-minted `dir` domain's member is `TDir` (the SEPARATE
        # source, so a direction parameter rejects a cell/integer/subscript
        # rather than reading as the permissive top).
        base = directions[name]
    elif name in _SCALAR_TYPES:
        base = _SCALAR_TYPES[name]()
    elif name in _ENUM_TYPES:
        base = TEnum(name)
    elif structs is not None and name in structs:
        base = structs[name]
    else:
        base = TAny()
    return TOptional(base) if optional else base


def value_enum_map(game: Game) -> dict[str, TEnum]:
    """Map each deck/kernel enum *value* to its enum type.

    `resolve` collapses suits, ranks, and seat directions into one
    `enum_value` ref_kind; the type checker re-derives which enum each value
    belongs to so a `Suit` is not confused with an `Integer` or a
    `SeatDirection`.
    """
    m: dict[str, TEnum] = {}
    suit_enum, rank_enum = _axis_enum_names(game)
    for suit in suit_names(game.deck):
        m[suit] = TEnum(suit_enum)
    # Membership comes from the deck alone (Coup/Tarot declare no
    # `ranking:`). resolve's `_resolve_ranking` guarantees ranking is a subset of deck
    # ranks (an unknown rank is a resolve-time error), and resolve always
    # runs before typecheck (cardlang/pipeline.py's `_check`), so unioning
    # `game.ranking` in here would add nothing beyond order.
    for rank in rank_names(game.deck):
        m[rank] = TEnum(rank_enum)
    for direction in SEAT_DIRECTION_VALUES:
        m[direction] = TEnum("SeatDirection")
    return m


def struct_registry(
    game: Game,
    functions: Mapping[str, Sig] | None = None,
    base: TypeEnv | None = None,
) -> dict[str, TStruct]:
    """Build the user-defined struct types. Declared fields resolve eagerly;
    derived fields are typed in the AMBIENT environment (``base``) extended
    with the declared fields and the user ``functions``, so each `TStruct`
    carries both declared and derived field types under one mapping.

    ``base`` matters because resolve scopes a derived body as the game's names
    PLUS the struct's own fields (`_classify_type_derived`), so a body may name
    a state variable, a zone, an enum value or a pronoun — none of which a bare
    `TypeEnv` carries. Omitting it does not merely lose precision now that a
    lookup miss is a hard `_env_miss`: `derived { s = hearts }` would abort the
    check outright. Callers that have the ambient environment must pass it.

    Structs are built in source order: a field whose type is another user type
    only resolves if that type was declared earlier (forward references resolve
    to `TAny` — acceptable for Stage 2, pinned by tests/test_permissive_top.py).

    ``functions`` closes a cycle, and must be supplied by any caller that wants
    precise derived types — see `_provisional_structs`."""
    structs: dict[str, TStruct] = {}
    # A derived BODY may name any declared type, including its own and one
    # declared later (`type R = { x : Integer } derived { copy = R { x: x } }`).
    # resolve validates a struct literal against every declared type, so those
    # are valid programs; inferring the body against the source-order-partial
    # map alone would hand `infer` a name resolve accepted and this pass could
    # not find, which is now a hard `_env_miss` rather than a silent top. Seed
    # the body environment with every declared type and let the ones already
    # completed win — a self- or forward-reference then types as the seed
    # entry, whose derived fields are still the top. That imprecision is
    # harmless: struct types compare NOMINALLY (`types.coercible`/`join`), so
    # the seed `R` and the final `R` are the same type to every consumer.
    #
    ambient = base if base is not None else TypeEnv()
    seed = _provisional_structs(game)
    for tdef in game.types:
        # Precedence, weakest first: every declared type by name (so a self- or
        # forward-reference resolves at all), the previous fixpoint round's
        # registry (more precise), then the types already completed in THIS
        # round (most precise). Declared field types read the SAME map as
        # derived bodies: resolving them against the partial map would let
        # declaration ORDER decide a field's type, so a container declared
        # above its member typed to the permissive top and every Owner Guard on
        # that field went dark.
        known = {**seed, **ambient.structs, **structs}
        fields: dict[str, Type] = {}
        for f in tdef.fields:
            fields[f.name] = type_from_name(f.type_name, f.optional, known)
        field_env = replace(
            ambient,
            locals={**ambient.locals, **fields},
            structs=known,
            functions=functions or {},
        )
        for d in tdef.derived:
            fields[d.name] = infer(d.value, field_env)
        structs[tdef.name] = TStruct(
            name=tdef.name,
            fields=fields,
            derived=frozenset(d.name for d in tdef.derived),
        )
    return structs


def _provisional_structs(game: Game) -> dict[str, TStruct]:
    """The fixpoint's starting point: declared fields resolved, DERIVED fields
    typed as the permissive top.

    Every field NAME exists here, which is what stops a function body reading a
    derived field from being falsely rejected as "has no field" before the
    field's type is known. The types themselves are refined by
    `struct_and_function_registries`.

    The top here is deliberate and local — written at the site that introduces
    it rather than reached as a lookup fallback (decisions.md, "`Any` means the
    top, never a failed lookup") — and it does not survive the fixpoint for
    any field whose type is derivable.
    """
    structs: dict[str, TStruct] = {}
    for tdef in game.types:
        fields: dict[str, Type] = {}
        for f in tdef.fields:
            fields[f.name] = type_from_name(f.type_name, f.optional, structs)
        for d in tdef.derived:
            fields[d.name] = TAny()
        structs[tdef.name] = TStruct(
            name=tdef.name,
            fields=fields,
            derived=frozenset(d.name for d in tdef.derived),
        )
    return structs


def _type_key(t: Type) -> object:
    """A type's identity for the fixpoint's convergence test, with any nested
    struct reduced to its NAME.

    Reducing to the name is sound only because a nested snapshot is never
    OBSERVED: every read of a struct-typed field resolves through the registry
    (`_canonical`), so what a round must compare is each type's OWN fields.
    Those the key does compare, and a nested type's refinement shows up under
    that type's own entry in the registry-wide fingerprint.

    An earlier version compared nested fields structurally to a bounded depth.
    That was two defects in one: unsound, because a RECURSIVE path stays
    observable past any fixed cutoff (`r.copy.copy.copy.flag` decayed to the
    permissive top); and exponential, because a declaration DAG whose types
    each hold two fields of the previous one revisits shared children once per
    path. Resolving reads through the registry removes the need for depth
    entirely, so the fingerprint is linear in the declared fields again.
    """
    if isinstance(t, TStruct):
        return ("struct", t.name)
    if isinstance(t, TOutcome):
        return ("outcome", t.name)
    if isinstance(t, TOptional):
        return ("optional", _type_key(t.inner))
    if isinstance(t, TCollection):
        return (
            "collection",
            _type_key(t.element),
            None if t.key is None else _type_key(t.key),
            t.zone,
        )
    return t


def _registry_key(structs: Mapping[str, TStruct]) -> object:
    """The whole registry's fingerprint: every type's own fields, nominal one
    level down. Linear in the declared fields — see `_type_key`."""
    return {
        name: (s.derived, {f: _type_key(ft) for f, ft in s.fields.items()})
        for name, s in structs.items()
    }


def struct_and_function_registries(
    game: Game, bag: DiagnosticBag
) -> tuple[dict[str, TStruct], dict[str, Sig]]:
    """The struct and user-function registries, solved together.

    The two are mutually dependent, in both directions and at arbitrary depth:
    a derived field's body may call a function (`derived { made = tag(a) }`),
    and a function's parameters and body may mention a struct
    (`function f(x : R) = x.made`). A function's RETURN type can therefore
    depend on a derived field's type, which can depend on another function's
    return type, and so on. No fixed number of passes is enough — a chain of
    N types and functions needs N rounds — so this iterates to a FIXPOINT.

    Getting this wrong is not a precision nicety, it is the accepted-but-ignored
    class: a derived field left at the permissive top silently exempts every
    expression that reads it from every Owner Guard. The version of this function
    that ran a fixed three passes accepted `score[p] := s.flag` — a Boolean into an
    Integer-declared state variable — because `s.flag`'s type was frozen at the
    top from the draft round.

    Each round is monotone in precision (a field only moves from the top toward
    a concrete type as the signatures feeding it sharpen), so the iteration
    settles; the bound below is an Owner Guard, and exceeding it is a checker bug
    rather than a program error. Intermediate rounds report into a SCRATCH bag:
    their diagnostics are recomputed by the final round, and reporting them per
    round would multiply every function-body diagnostic by the round count.
    """
    structs = _provisional_structs(game)
    # Each round promotes at least one derived field or one signature away from
    # the top; +2 covers the settling round that changes nothing.
    bound = sum(len(t.derived) for t in game.types) + len(game.functions) + 2
    for _ in range(bound):
        # The ambient environment for this round, which BOTH consumers need:
        # function bodies, and derived bodies (which may name a state variable,
        # a zone or an enum value just as any other expression can).
        ambient = env_from_game(game, structs)
        sigs = _function_sigs(game, ambient, DiagnosticBag())
        settled = struct_registry(game, sigs, base=ambient)
        done = _registry_key(settled) == _registry_key(structs)
        # Take the newer registry ALWAYS, including on the round that settles.
        # Testing first and keeping the older one threw away a strictly better
        # result: the round that reports "nothing changed" is the one built
        # against the fullest environment.
        structs = settled
        if done:
            break
    else:
        raise AssertionError(
            f"the struct/function type fixpoint did not settle in {bound} "
            f"rounds — each round should only sharpen a derived field or a "
            f"signature, so this is a checker bug (a non-monotone round), not "
            f"a program error"
        )
    # The final signatures are built against the settled registry and into the
    # REAL bag, so every function body is checked exactly once, against the
    # types everything else sees.
    env = env_from_game(game, structs)
    return structs, _function_sigs(game, env, bag)


def _payload_type(
    name: str,
    structs: Mapping[str, TStruct],
    positions: Mapping[str, Type] | None = None,
) -> Type:
    """Resolve a outcome payload type name; a trailing `?` marks it nullable.

    `positions` is threaded because resolve admits a declared position domain
    here: without it the name resolves to the top, and the `produces:` arm
    binder carrying that payload exempts its whole body from every type Owner Guard.
    The board-minted `dir` domain is deliberately NOT admitted here: `dir` is a
    move-parameter domain only, so resolve rejects a `dir` payload (`unknown
    type 'dir'`) before this pass -- the reason `directions` is not threaded.
    """
    if name.endswith("?"):
        return type_from_name(name[:-1], True, structs, positions)
    return type_from_name(name, False, structs, positions)


def _outcome_cases(
    cases: tuple[n.OutcomeCase, ...],
    structs: Mapping[str, TStruct],
    positions: Mapping[str, Type] | None = None,
) -> dict[str, tuple[Type, ...]]:
    return {
        c.tag: tuple(_payload_type(t, structs, positions) for t in c.payload_types)
        for c in cases
    }


def outcome_registry(
    game: Game,
    structs: Mapping[str, TStruct],
    positions: Mapping[str, Type] | None = None,
) -> dict[str, TOutcome]:
    """Build the outcome-outcome type of each `define` and each outcome-declaring
    `phase`: its case tags mapped to their declared payload types."""
    outcomes: dict[str, TOutcome] = {}
    for d in game.defines:
        outcomes[d.name] = TOutcome(
            name=d.name, cases=_outcome_cases(d.cases, structs, positions)
        )
    for phase in _all_phases(game):
        if phase.outcome_cases:
            outcomes[phase.name] = TOutcome(
                name=phase.name,
                cases=_outcome_cases(phase.outcome_cases, structs, positions),
            )
    return outcomes


@dataclass(frozen=True)
class TypeEnv:
    """The types a bare name resolves against during inference: declared state
    vars, zone contents, deck/kernel enum values, and scoped local binders."""

    state_vars: Mapping[str, Type] = field(default_factory=dict)
    zones: Mapping[str, Type] = field(default_factory=dict)
    # Zone FAMILIES (`hand[player]`, `captured[team]`) only, name -> the type
    # a subscript's index expression must be `coercible` to. A family zone's
    # bare name (no subscript) still resolves through `zones` above to its
    # content type — unaffected; this map exists so `Subscript` can tell a
    # family instance (`hand[p]`, itself a collection) apart from the generic
    # collection-element indexing every other subscript does.
    zone_families: Mapping[str, Type] = field(default_factory=dict)
    value_enums: Mapping[str, TEnum] = field(default_factory=dict)
    locals: Mapping[str, Type] = field(default_factory=dict)
    structs: Mapping[str, TStruct] = field(default_factory=dict)
    functions: Mapping[str, Sig] = field(default_factory=dict)  # user functions
    # User procedures, name -> declared parameter types (`Sig.ret` is unused: a
    # procedure is a statement, not an expression). This is what makes a
    # procedure's parameter annotations load-bearing rather than decorative —
    # `run` sites check their arguments against them exactly as a call checks its
    # arguments against a function signature. It is also why expansion runs AFTER
    # typecheck (cardlang/expand.py): once a body is spliced inline there is no
    # call site left to check.
    procedures: Mapping[str, Sig] = field(default_factory=dict)
    has_ranking: bool = False  # bool(game.ranking) — gates RANKING_GATED_FUNCS
    max_players: int = 0  # the game's maximum seat count — bounds player literals
    max_teams: int = 0  # len(game.teams) — bounds team literals (0: no teams)
    # Per-game position domains (decisions.md "Position domains and positional
    # zones", "Boards and cells") — name -> the member type a parameter, let
    # binder or subscript key over it carries: `TInteger` for a declared
    # integer domain (`positions { column : 1..7 }`), `TCell` for the
    # board-minted `cell` domain. Membership (`name in env.positions`) still
    # answers "is this a position domain?"; the value answers "of which member
    # kind?".
    positions: Mapping[str, Type] = field(default_factory=dict)
    # The board-minted movement-direction domains (decisions.md "Boards and
    # cells", rung-2 movement) — name -> the member type a `dir` move parameter,
    # let binder or payload carries: `TDir`. A SEPARATE map from `positions`
    # (the `dir` domain is deliberately absent from `game.positions`), so a
    # direction is admitted only at a move parameter / payload and the position
    # Owner Guards never see it. Membership (`name in env.directions`) answers "is this
    # a direction domain?".
    directions: Mapping[str, Type] = field(default_factory=dict)
    # `Game.content_flavor` and `Game.deck` — the dispatch key and set name for
    # the flavor-aware Owner Guards (decisions.md, "Component sets: cards and pieces");
    # `deck` names the kind in a piece game's card-content diagnostics.
    flavor: Flavor = "card"
    deck: str = ""
    # The content item's field table (`item_field_table`) -- `card.suit` types
    # off this, not the module CARD_FIELDS, so a piece's `side`/`kind` are its
    # only fields. Default is the card pair for envs built ad hoc (struct
    # inference), which `env_from_game` overrides per flavor.
    item_fields: Mapping[str, Type] = field(default_factory=lambda: dict(CARD_FIELDS))

    def with_local(self, name: str, t: Type) -> TypeEnv:
        return replace(self, locals={**self.locals, name: t})


def _canonical(t: Type, env: TypeEnv) -> Type:
    """A struct type read out of another struct's field map, resolved to the
    registry's entry for that name.

    A struct's field map holds a SNAPSHOT of each struct-typed field, taken
    while the registry was still being built, so a snapshot can be staler than
    the registry — unavoidably so for a recursive type, whose unrolled value
    has no finite form. Struct types are nominal (`types.coercible`/`join`
    compare by name), so the registry entry is the same type and strictly more
    refined: resolving by name at each read keeps a traversal exact at any
    depth, and keeps the registry's own representation finite.
    """
    if isinstance(t, TStruct):
        return _canonical_struct(t, env)
    return t


def _canonical_struct(t: TStruct, env: TypeEnv) -> TStruct:
    """`_canonical` for a receiver already known to be a struct, so the caller
    keeps its narrowing (and its field map)."""
    entry = env.structs.get(t.name)
    return entry if entry is not None else t


def _untyped_operator(op: str) -> AssertionError:
    """A `BinOp` operator `infer` has no result type for.

    Kept out of `infer`'s BinOp arm deliberately: that arm is scraped as the
    operator registry (tests/test_operator_guards.py reconciles it against
    `OP_CLASSES`), so a message with quoted text inside it would read as
    operators. The old blanket `TAny` here meant a NEW operator typed as the
    permissive top and passed every operand Owner Guard silently — the inference-side
    twin of `_op_class`'s refusal on the checking side.
    """
    return AssertionError(
        f"operator '{op}' has no result type in `infer` — every BinOp operator "
        f"the parser builds must be typed here (surface totality, "
        f"decisions.md); add it beside its OP_CLASSES entry"
    )


def infer(e: n.Expr, env: TypeEnv) -> Type:
    """Infer the type of an expression. Unrefined arms return `TAny` (the
    permissive top); precision is added construct by construct.

    A LOOKUP that cannot legitimately miss raises instead of returning the top
    (`_env_miss`, `_untyped_operator`): the top satisfies every constraint, so
    missed lookup would silently switch off every Owner Guard below it rather than
    merely losing precision. See decisions.md, "`Any` means the top, never a
    failed lookup"; the audited top sites are pinned by
    tests/test_permissive_top.py."""
    match e:
        case n.IntLit():
            return TInteger()
        case n.StrLit():
            return TString()
        case n.CardLiteral():
            return TCard()
        case n.AllPlayers():
            return TCollection(TPlayer())
        case n.NameRef():
            return _name_type(e, env)
        case n.Subscript():
            # A zone-FAMILY subscript (`hand[p]`) denotes one zone instance —
            # its type is the zone's *content* type (a collection), never the
            # element a generic collection subscript yields (a flat
            # `element`-of-collection read would treat `hand[p]` as a single
            # Card, degrading every aggregation/membership use downstream to
            # TAny or a spurious rejection). A non-family subscript (a state
            # var, a `[…]` list, a query result) keeps the generic behavior.
            obj_ref = e.obj
            if isinstance(obj_ref, n.NameRef) and obj_ref.ref_kind == "zone":
                family = env.zone_families.get(obj_ref.name)
                if family is not None:
                    zone_t = env.zones.get(obj_ref.name)
                    if zone_t is None:
                        raise _env_miss(
                            "zone", obj_ref.name, "zones", "`env_from_game`"
                        )
                    return zone_t
            obj = infer(e.obj, env)
            # A subscript of a non-collection is REJECTED by `_check_expr`
            # (`subscriptable`), which admits the permissive top; so the only
            # value reaching here is one already typed as the top (or one whose error is
            # already in the bag). Gradual, not a lookup miss.
            return obj.element if isinstance(obj, TCollection) else TAny()
        case n.Call():
            sig = CALL_SIGS.get(e.func) or env.functions.get(e.func)
            if sig is None:
                # `CALL_SIGS` covers `CALL_FUNCS` exactly (pinned by
                # tests/test_permissive_top.py), and resolve rejects a call to
                # any name that is neither a native function nor a declared
                # one — so a missing signature is a registry divergence.
                raise AssertionError(
                    f"call to '{e.func}' has no signature in CALL_SIGS and no "
                    f"declared function — resolve rejects unknown calls before "
                    f"this pass, so the native signature registry has drifted "
                    f"from the native function registry"
                )
            return sig.ret
        case n.BinOp():
            if e.op in ("is", "is_not", "<", ">", "<=", ">=", "and", "or", "in"):
                return TBoolean()
            if e.op in ("+", "-", "*"):
                return TInteger()
            if e.op in ("divided_by_rounded_up", "divided_by_rounded_down"):
                # Rounded division: Integer operands, Integer result.
                return TInteger()
            if e.op == "offset_by":
                # Seat arithmetic yields a seat, whatever the walk knows about
                # the operand — a binder-rooted receiver ((p offset_by left),
                # p untyped by the flat walk) must still hit the dot-form
                # rejection rather than fall through to a runtime assert.
                return TPlayer()
            # Every operator the parser builds is typed above; an unrecognized
            # one is loud (the message lives in `_untyped_operator` so this arm
            # holds operator literals ONLY — tests/test_operator_guards.py
            # scrapes it as the operator registry).
            raise _untyped_operator(e.op)
        case n.Not() | n.IsCheck() | n.Quantifier():
            return TBoolean()
        case n.Choose():
            return TInteger()
        case n.Comprehension():
            return TInteger() if e.agg == "sum" else TAny()
        case n.PlayerQuery():
            match e.kind:
                case "set":
                    return TCollection(TPlayer())
                case "count":
                    return TInteger()
                case "pick" | "first_from":
                    return TPlayer()
                case _:
                    raise AssertionError(f"unknown player-query kind '{e.kind}'")
        case n.CardQuery():
            match e.kind:
                case "set":
                    return TCollection(TCard())
                case "count":
                    return TInteger()
                case _:  # "any" | "all"
                    return TBoolean()
        case n.DomainQuery():
            # `number of <domain>s where …` counts; `any`/`all` are Boolean.
            return TInteger() if e.kind == "count" else TBoolean()
        case n.IfExpr():
            return _ifexpr_type(e, env)
        case n.StructLit():
            struct = env.structs.get(e.type_name)
            if struct is None:
                # resolve rejects a literal of an undeclared type
                # (`_validate_refs`, "unknown type"), and `struct_registry`
                # builds one entry per `game.types` — so a miss is a divergence
                # between the two, not a program error.
                raise _env_miss(
                    "struct type", e.type_name, "structs", "`struct_registry`"
                )
            return struct
        case n.Member():
            # `action.card` / `action.actor`: the sound subset of the `action`
            # pronoun's shape — typed directly off the pronoun,
            # not off `infer(e.obj, env)` (which stays TAny for `action`
            # itself, since most of its shape is move-type-specific).
            obj_ref = e.obj
            if (
                isinstance(obj_ref, n.NameRef)
                and obj_ref.ref_kind == "pronoun"
                and obj_ref.name == "action"
                and e.field in ACTION_FIELDS
            ):
                return ACTION_FIELDS[e.field]
            if (
                isinstance(obj_ref, n.NameRef)
                and obj_ref.ref_kind == "pronoun"
                and obj_ref.name == "state"
                and e.field in ROUND_STATE_FIELDS
            ):
                # The round's published state, typed off the registry rather than
                # left `TAny`. `TAny` would be contagious here: `card.suit is
                # state.idx` would compare a Suit to an Integer and slip past the
                # enum Owner Guard on an untyped right side. An unpublished field never
                # reaches this branch — `_check_expr` rejects it.
                return ROUND_STATE_FIELDS[e.field]
            obj = infer(e.obj, env)
            if isinstance(obj, TStruct):
                # Read struct fields through the REGISTRY, not off the snapshot
                # embedded in whatever value produced the receiver. A recursive
                # type (`derived { copy = R { x: x } }`) has no finite unrolled
                # form — each embedded copy is one round staler than the last —
                # so reading snapshots made `r.copy.flag` correct,
                # `r.copy.copy.flag` correct, and `r.copy.copy.copy.flag` the
                # permissive top: an Owner Guard that decayed with traversal depth.
                # Struct types are nominal, so the registry entry IS the type
                # and is never staler.
                #
                # BOTH ends are canonicalized, and each covers a different
                # producer. The receiver, because a struct-typed value can
                # arrive from a snapshot-bearing map (a derived body's sibling
                # binding, a field of a field) and its own map would then be
                # stale for SCALAR fields, which canonicalizing the result
                # cannot repair. The result, because that is what the next hop
                # of a chain becomes.
                receiver = _canonical_struct(obj, env)
                return _canonical(receiver.fields.get(e.field, TAny()), env)
            if isinstance(obj, TCard):
                # The content item's fields are a closed pair (flavor-keyed);
                # `_check_expr` rejects anything else on a known-item receiver.
                return env.item_fields.get(e.field, TAny())
            return TAny()  # pronoun member access / sugar: deferred
        case n.ListLit():
            elem: Type | None = infer(e.elements[0], env)
            for item in e.elements[1:]:
                elem = join(elem, infer(item, env)) if elem is not None else None
            return TCollection(elem if elem is not None else TAny())
        case _ as unreachable:
            assert_never(unreachable)


def _ifexpr_type(e: n.IfExpr, env: TypeEnv) -> Type:
    result = infer(e.then, env)
    for _cond, branch in e.elifs:
        merged = join(result, infer(branch, env))
        result = merged if merged is not None else TAny()
    merged = join(result, infer(e.otherwise, env))
    return merged if merged is not None else TAny()


def _env_miss(kind: str, name: str, env_field: str, builder: str) -> AssertionError:
    """A name resolve CLASSIFIED but this pass cannot type: the type environment
    is incomplete, which is a checker bug rather than a program error.

    This is the amplifier the permissive `TAny` used to hide (decisions.md
    "Closed-domain completeness"; the resolution recorded in
    decisions.md, "`Any` means the top, never a failed lookup"). A miss here
    used to return the
    permissive top, and `TAny` satisfies EVERY constraint — so one unthreaded
    binder silently exempted every expression below it from every type Owner Guard,
    and the checker reported success. Both bugs the split was motivated by had
    exactly this shape: a move parameter whose position domain was not threaded
    into the binder env typed `TAny`, so `src is hearts` passed.

    The fix for this exception is NEVER to bind `TAny` at the raising site to
    quiet it — that restores the hole. It is to thread the missing binder in
    the pass that owns the scope. A binder that is genuinely untypable today is
    a deliberate reclassification: bind it to `TAny` *explicitly* at the site
    that introduces it, where the choice is visible and auditable.
    """
    return AssertionError(
        f"{kind} '{name}' was classified by resolve but is absent from "
        f"`TypeEnv.{env_field}` — {builder} and the resolver's classification "
        f"have diverged, so this expression would type as the permissive top "
        f"and every type Owner Guard below it would silently pass. This is a checker "
        f"bug: thread the binding through, never bind `TAny` here to quiet it."
    )


def _name_type(e: n.NameRef, env: TypeEnv) -> Type:
    match e.ref_kind:
        case "local":
            t = env.locals.get(e.name)
            if t is None:
                # The headline case: a runtime binder the statement walk failed
                # to carry into scope. `_scoped_env` folds loop/parameter/`let`
                # binders; a construct whose binder it does not know reaches
                # here.
                raise _env_miss(
                    "binder", e.name, "locals", "the statement walk's binder fold"
                )
            return t
        case "state_var":
            t = env.state_vars.get(e.name)
            if t is None:
                raise _env_miss(
                    "state variable", e.name, "state_vars", "`env_from_game`"
                )
            return t
        case "zone":
            t = env.zones.get(e.name)
            if t is None:
                raise _env_miss("zone", e.name, "zones", "`env_from_game`")
            return t
        case "enum_value":
            t_enum = env.value_enums.get(e.name)
            if t_enum is None:
                raise _env_miss(
                    "enum value", e.name, "value_enums", "`value_enum_map`"
                )
            return t_enum
        case "bool":
            return TBoolean()
        case "null":
            return TNull()  # the `none` literal — fits only optionals
        case "pronoun":
            # `actor` is universally the acting player at runtime
            # (evaluate._pronoun -> ctx.current_player, and the `Move`
            # payload's own `actor` field is a bare `Player`, never
            # optional) — the other pronouns (`action`, `winner`,
            # `state`, `active_rules`) stay TAny; their shape is
            # move-type/mechanic-specific (see ACTION_FIELDS for the
            # sound subset of `action` typed via Member access).
            return TPlayer() if e.name == "actor" else TAny()
        case "function":
            # A bare function NAME in value position (a callback handed to a
            # round form, never applied here). Genuinely the top: its type is the
            # signature of whatever consumes it, which no `Type` in this model
            # can spell. One of the audited permissive sites.
            return TAny()
        case _:
            # Every `ref_kind` resolve stamps is handled above, and resolve
            # RAISES on an unclassified name before this pass runs — so an
            # unknown kind here is a resolver/checker divergence, not a program
            # error. Loud, per the same rule as `_env_miss`: the old blanket
            # `TAny` made a whole new ref kind type as the permissive top and
            # sail through every Owner Guard.
            raise AssertionError(
                f"name '{e.name}' has ref_kind {e.ref_kind!r}, which this pass "
                f"does not type — resolve classifies every name (and rejects "
                f"the unclassifiable), so a new ref kind must be given a type "
                f"here rather than defaulting to the permissive top"
            )


def _type_name(t: Type) -> str:
    if isinstance(t, TNull):
        return "none"
    if isinstance(t, TOptional):
        return f"{_type_name(t.inner)}?"
    if isinstance(t, TCollection):
        return f"Collection<{_type_name(t.element)}>"
    if isinstance(t, TEnum):
        return t.name
    if isinstance(t, (TStruct, TOutcome)):
        # These carry their declared name. Before the general disjointness rule
        # below, no Owner Guard ever printed one, so both rendered as the bare
        # kind — which made "comparing Struct with Struct can never be equal"
        # read as nonsense.
        return t.name
    return type(t).__name__[1:]  # TInteger -> "Integer", TPlayer -> "Player", …


def _state_blocks(game: Game) -> list[n.StateBlock]:
    # The walk lives with the AST (`nodes.state_blocks`) because it answers a
    # structural question two passes ask — this table, and the OpenSpiel returns
    # mapping reading a `winner:` target's declared index.
    return n.state_blocks(game)


def _position_types(game: Game) -> dict[str, Type]:
    """Each position domain's member type: `TInteger` for a declared integer
    domain, `TCell` for the board-minted named-member `cell` domain
    (`PositionDecl.members_named` distinguishes them). Resolve has already
    appended the board's `cell` domain into `game.positions`, so this reads the
    union uniformly."""
    return {
        p.name: (TCell() if p.members_named is not None else TInteger())
        for p in game.positions
    }


def _direction_types(game: Game) -> dict[str, Type]:
    """Each board-minted direction domain's member type: `TDir`. The `dir`
    source is SEPARATE from `game.positions` (`board_domains.directions_of`),
    so this is the sibling of `_position_types` -- the domain NAMES come from
    the seam (no drift), each mapped to its one member type."""
    return {name: TDir() for name in directions_of(game)}


def env_from_game(
    game: Game, structs: Mapping[str, TStruct] | None = None
) -> TypeEnv:
    """Build the top-level type environment: declared state vars (value types),
    zone contents, the deck/kernel enum value map, and the user struct types.

    ``structs`` lets the caller supply a registry it has already built — which
    `struct_and_function_registries` does on every round of its fixpoint, and
    which is the ONLY way to avoid re-solving it here.

    Omitted, the registry is solved from scratch through that same builder
    rather than a bare `struct_registry(game)` call. The bare call typed
    derived bodies against an empty `TypeEnv`, so a derived field naming any
    ambient thing — `derived { d = score }`, a zone, an enum value, a pronoun —
    aborted this helper with `_env_miss` for a perfectly valid game. That is
    the same defect the ambient-environment fix closed for the main pipeline,
    surviving in the branch the main pipeline no longer takes: a public helper
    is a caller too. Recursion is not a risk — the builder always calls back
    with a registry in hand, taking the branch above.

    That branch also keeps the SIGNATURES the builder solved on the way, and
    fills in the procedure signatures. Both are free here, and an env missing
    either silently disables an Owner Guard rather than losing precision: an empty
    `functions` made `infer` raise on any call to a user function, and an empty
    `procedures` made the `run`-site arity and argument-type check skip — the
    only place a procedure's parameter annotations bite at all.

    The supplied-registry branch deliberately fills in NEITHER: the fixpoint
    uses this env as the INPUT to `_function_sigs`, so handing it a half-built
    signature map would seed a round from itself, and `typecheck` sets both
    once, after the registries settle."""
    functions: Mapping[str, Sig] = {}
    procedures: Mapping[str, Sig] = {}
    if structs is None:
        structs, functions = struct_and_function_registries(game, DiagnosticBag())
        procedures = _procedure_sigs(game)
    state_vars: dict[str, Type] = {}
    for block in _state_blocks(game):
        for decl in block.decls:
            t = type_from_name(decl.type_name, decl.optional, structs)
            # An indexed state var (`score[player]`) is a per-key map — a
            # collection whose subscript yields the declared value type, KEYED
            # by the index domain's binder type so a wrong-domain key
            # (`score[hearts]`, `n[9]`'s read twin) is a check-time error
            # rather than a mid-playout one: the runtime indexes the map
            # directly and requires the key to be one it actually holds.
            state_vars[decl.name] = (
                TCollection(t, key=_role_type(decl.index))
                if decl.index is not None
                else t
            )
    # `ZONE_CONTENT` covers `LIBRARY_ZONE_TYPES` exactly (pinned by
    # tests/test_permissive_top.py) and resolve rejects an unknown zone type
    # before this pass runs, so every declared zone has a content type. The old
    # permissive fallback here would have typed an unknown zone's contents as
    # the top, sending every downstream Card/endpoint Owner Guard dark for that zone.
    def zone_content(z: n.ZoneDecl) -> Type:
        content = ZONE_CONTENT.get(z.type_ref.name)
        if content is None:
            raise AssertionError(
                f"zone '{z.name}' has library type '{z.type_ref.name}' with no "
                f"ZONE_CONTENT entry — resolve rejects unknown zone types "
                f"before this pass, so the content registry has drifted from "
                f"LIBRARY_ZONE_TYPES"
            )
        return content

    zones: dict[str, Type] = {z.name: zone_content(z) for z in game.zones}
    # `ZoneDecl.index` is `None` (a singleton zone) or one of the closed index
    # roles resolve.py validates (the domain table's `ZONE_INDEX_ROLES`, plus
    # the game's declared position domains — integer-keyed); a family's
    # subscript key types as the index domain's binder type — the same
    # table cell `for each <role>` reads, so `hand[p]` and `captured[t]` key by
    # TPlayer/TTeam without this site re-spelling the role list. (`role_type`
    # RAISES on a role outside the registry rather than falling back to the
    # permissive top; resolve rejects an unknown index role before this pass,
    # so reaching that raise would mean the two registries had diverged.)
    positions = _position_types(game)
    zone_families: dict[str, Type] = {
        z.name: (positions[z.index] if z.index in positions else _role_type(z.index))
        for z in game.zones
        if z.index is not None
    }
    return TypeEnv(
        state_vars=state_vars,
        zones=zones,
        zone_families=zone_families,
        value_enums=value_enum_map(game),
        structs=structs,
        functions=functions,
        procedures=procedures,
        has_ranking=bool(game.ranking),
        max_players=(
            game.players.high if game.players.high is not None else game.players.low
        ),
        max_teams=len(game.teams),
        positions=positions,
        directions=_direction_types(game),
        flavor=game.content_flavor,
        deck=game.deck,
        item_fields=item_field_table(game),
    )


# A statement's enclosing binders, outermost first. A parameter binder carries
# its Type directly; a `let` binder carries its `LetStmt` NODE and a `for each`
# binder its `ForEach` NODE, because their types are known only to the consumer
# — a let's is its initializer's type inferred *in the environment at that
# point*, and a for-each's is its role's member type, which for a position
# domain (a board's `cell`) is per-game. `_scoped_env` resolves all three.
_Binders = tuple[tuple[str, "Type | n.LetStmt | n.ForEach"], ...]


def _scoped_env(env: TypeEnv, binders: _Binders) -> TypeEnv:
    """The environment a statement sees: binders folded in scope order, with a
    `let` binder typed here by inferring its initializer in the environment
    built so far (earlier binders are visible — the walk's sequential fold
    guarantees that is exactly the let's own scope). The indexed form
    (`let base[p] = E`) is a per-player map: `p` types as Player inside E
    only, and `base` as a collection of E's type. This closes the let-TAny gap:
    without it, a `let`-bound name would infer `TAny` everywhere, so every Owner Guard
    would go dark one binding away (`hearts is 3` rejected; `let z = hearts`
    then `z is 3` accepted)."""
    for name, bound in binders:
        if isinstance(bound, n.LetStmt):
            if bound.index is not None:
                element = infer(bound.value, env.with_local(bound.index, TPlayer()))
                env = env.with_local(name, TCollection(element, key=TPlayer()))
            else:
                env = env.with_local(name, infer(bound.value, env))
        elif isinstance(bound, n.ForEach):
            # A position-domain role (a board's `cell`) takes its member type
            # from the game's declared domains, which only this consumer holds;
            # every other role is a closed registry row `role_type` answers.
            role = bound.role
            env = env.with_local(
                name,
                env.positions[role] if role in env.positions else _role_type(role),
            )
        else:
            env = env.with_local(name, bound)
    return env


def _stmt_tree_scoped(
    s: n.Stmt, binders: _Binders = ()
) -> Iterator[tuple[n.Stmt, _Binders]]:
    """The statement tree, each statement paired with the loop binders in
    scope at that point — the single traversal every statement walk views.

    Exhaustive over `Stmt`: a compound statement whose body this walk missed
    would leave that whole body unchecked (no expression Owner Guards, no semantic
    checks — accepted-but-ignored at subtree scale), so "descends nothing" is
    a decision each leaf kind states by name, never a default."""
    yield s, binders
    match s:
        case n.ForEach():
            yield from _stmt_tree_scoped(s.body, binders + ((s.binder, s),))
        case n.EachSimultaneous():
            yield from _stmt_tree_scoped(
                s.body, binders + ((s.role, _role_type(s.role)),)
            )
        case n.RepeatUntil():
            yield from _seq_tree_scoped(s.body, binders)
        case n.IfStmt():
            yield from _seq_tree_scoped(s.then_body, binders)
            yield from _seq_tree_scoped(s.else_body or (), binders)
        case n.AsBlock():
            # Rebinds the acting player, not a loop binder — its body sees the
            # same binders as the block, and its player expression is an
            # expression (checked by `_check_stmt_exprs`, typed to Player in
            # `_check_stmt`), so nothing new enters scope here.
            yield from _seq_tree_scoped(s.body, binders)
        case n.Turns():
            # The binder names the current player, one turn at a time —
            # typed Player like a `for each player` binder.
            yield from _seq_tree_scoped(s.body, binders + ((s.binder, TPlayer()),))
        case n.Block():
            # Synthetic, and created only by `expand`, which runs AFTER this
            # pass — so nothing here ever sees one today. The arm exists anyway:
            # a future pass ordering that did reach a block must not skip its
            # whole body without a word.
            yield from _seq_tree_scoped(s.body, binders)
        case n.Produces():
            # A deliberate leaf, not an oversight: arm bodies bind the arm's
            # payload binders, which this walk cannot know (they come from the
            # outcome registry). `_check_produces` runs the scoped sub-walk over
            # each arm body with those binders typed, and the outcome-plumbing
            # walks (`_produces_in`, `_control_flow_nodes`) descend arms
            # themselves.
            pass
        case (
            n.Transfer() | n.EpistemicOp() | n.RotateStmt() | n.LetStmt()
            | n.AssignStmt() | n.Offer() | n.TrickRound() | n.AuctionRound()
            | n.ClimbRound() | n.Produce()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt()
        ):
            pass  # no child statements
        case _:
            assert_never(s)


def _seq_tree_scoped(
    stmts: tuple[n.Stmt, ...], binders: _Binders
) -> Iterator[tuple[n.Stmt, _Binders]]:
    """A statement SEQUENCE with the sequential-`let` fold: a `let` binds its
    name for the REST of the tuple — the same fold resolve's `_rewrite_value`
    applies when it scopes the name, and the runtime's `run_body` applies when
    it binds the value. Every statement-tuple walk routes through here, so the
    three passes cannot disagree about where a `let` is visible."""
    current = binders
    for s in stmts:
        yield from _stmt_tree_scoped(s, current)
        if isinstance(s, n.LetStmt):
            current = current + ((s.name, s),)


def _stmt_tree(s: n.Stmt) -> Iterator[n.Stmt]:
    yield from (st for st, _ in _stmt_tree_scoped(s))


def _phase_statements_scoped(
    phase: n.Phase, binders: _Binders = ()
) -> Iterator[tuple[n.Stmt, _Binders]]:
    # The sequential-`let` fold runs across phase ITEMS too, and carries into
    # nested phases that follow the let — mirroring resolve's Phase fold and
    # the driver, which passes the threaded context into `run_phase`. HOOKS
    # deliberately get the phase-ENTRY binders, not the fold's: `before_each`/
    # `after_each` run at iteration boundaries with the entry context, before
    # any body `let` has executed, and resolve rejects a hook reading one.
    current = binders
    for item in phase.items:
        match item:
            case n.Phase():
                yield from _phase_statements_scoped(item, current)
            case n.BeforeEach() | n.AfterEach():
                yield from _seq_tree_scoped(item.body, binders)
            case n.StateBlock() | n.ActiveRules() | n.LegalMoves() | n.Mode():
                pass  # configuration blocks hold no statements
            case _:
                # The residue of PhaseItem is exactly Stmt — mypy checks that on
                # this call, so a new phase-item block kind fails here loudly
                # instead of being walked as a statement.
                yield from _stmt_tree_scoped(item, current)
                if isinstance(item, n.LetStmt):
                    current = current + ((item.name, item),)


def _non_define_statements(game: Game) -> Iterator[n.Stmt]:
    """Every statement outside a `define` body — where `produce` is illegal."""
    for move_type in game.move_types:
        for s in move_type.effect:
            yield from _stmt_tree(s)
    for phase in game.phases:
        yield from (st for st, _ in _phase_statements_scoped(phase))


def _parameter_binders(
    move_type: n.MoveTypeDef,
    positions: Mapping[str, Type],
    directions: Mapping[str, Type],
) -> _Binders:
    """A move type's parameters, typed from their declarations — bound in its
    guard and effect exactly as procedure parameters are bound in their body.
    Bound by resolve but NEVER typed, they would let `move_type m(s :
    Suit) { when: s is 3 … }` pass both positions while the inline spelling
    was rejected — the let-laundering shape, one binder kind over.

    `positions`/`directions` (the game's position and direction domains) must
    be threaded in: a move parameter may be a position domain (`build(src :
    column)`, `place(at : cell)`) or the board-minted direction domain
    (`step(along : dir)`), and `_param_type` types those as their member type
    (`TInteger` / `TCell` / `TDir`) only when the domain is in `env.positions`/
    `env.directions`. A fresh `TypeEnv()` would leave it `TAny`, so `src is
    hearts` / `along is a1` and other wrong-domain uses would pass —
    accepted-but-ignored, one binder kind over yet again. (Procedure params,
    by contrast, resolve gates to `Player`, so they never carry a position and
    their env needs none.)"""
    env = TypeEnv(positions=positions, directions=directions)
    return tuple((p.name, _param_type(p, env)) for p in move_type.params)


def _all_statements_scoped(game: Game) -> Iterator[tuple[n.Stmt, _Binders]]:
    positions = _position_types(game)
    directions = _direction_types(game)
    for move_type in game.move_types:
        yield from _seq_tree_scoped(
            move_type.effect, _parameter_binders(move_type, positions, directions)
        )
    for phase in game.phases:
        yield from _phase_statements_scoped(phase)
    for define in game.defines:
        yield from _seq_tree_scoped(define.body, ())
    # A procedure body is checked ONCE, here, at its declaration — with its
    # parameters bound to their declared types, which is what gives those
    # annotations force. It is not re-checked after expansion, because expansion
    # runs after this pass; the `run` sites check their arguments against the same
    # declared types, so the spliced result is covered from both ends.
    env = TypeEnv()
    for proc in game.procedures:
        binders: _Binders = tuple((p.name, _param_type(p, env)) for p in proc.params)
        yield from _seq_tree_scoped(proc.body, binders)


def _all_statements(game: Game) -> Iterator[n.Stmt]:
    yield from (st for st, _ in _all_statements_scoped(game))


def _arg_exprs(args: tuple[n.Arg, ...]) -> list[n.Expr]:
    """The positional expression arguments of a call (named args are not used by
    the native functions/methods being checked)."""
    return [a for a in args if not isinstance(a, n.NamedArg)]


def _child_exprs(e: n.Expr) -> list[n.Expr]:
    """Every expression's direct sub-expressions — exhaustive over `Expr`, so a
    new expression kind must declare its children (or its leafhood) here before
    anything compiles. A missed kind wouldn't crash anything; its children
    would simply never be walked, and every Owner Guard inside them would go dark."""
    match e:
        case n.Member():
            return [e.obj]
        case n.ListLit():
            return list(e.elements)
        case n.StructLit():
            return [fi.value for fi in e.fields]
        case n.Subscript():
            return [e.obj, e.index]
        case n.Call():
            return _arg_exprs(e.args)
        case n.BinOp():
            return [e.left, e.right]
        case n.Not() | n.IsCheck():
            return [e.operand]
        case n.Quantifier():
            return [e.body]
        case n.Comprehension():
            out = [e.source, e.body]
            if e.where is not None:
                out.append(e.where)
            if e.default is not None:
                out.append(e.default)
            return out
        case n.Choose():
            return [e.lo, e.hi]
        case n.PlayerQuery():
            return [e.start, e.where] if e.start is not None else [e.where]
        case n.CardQuery():
            return [e.source, e.where] if e.where is not None else [e.source]
        case n.DomainQuery():
            return [e.source, e.where] if e.source is not None else [e.where]
        case n.IfExpr():
            out = [e.cond, e.then]
            for cond, branch in e.elifs:
                out += [cond, branch]
            out.append(e.otherwise)
            return out
        case n.NameRef() | n.IntLit() | n.StrLit() | n.CardLiteral() | n.AllPlayers():
            return []  # leaves
        case _:
            assert_never(e)


def _called_functions(e: n.Expr, fn_names: set[str]) -> set[str]:
    """The user-function names called anywhere in `e`."""
    out: set[str] = set()
    if isinstance(e, n.Call) and e.func in fn_names:
        out.add(e.func)
    for child in _child_exprs(e):
        out |= _called_functions(child, fn_names)
    return out


def _function_sigs(game: Game, env: TypeEnv, bag: DiagnosticBag) -> dict[str, Sig]:
    """Each user function's signature: declared parameter types and the return type
    inferred from the body. Built in dependency order (callees first — the call
    graph is acyclic, enforced by resolve) so a body's calls see their callees'
    return types; each body is checked against its parameters."""
    func_defs = {f.name: f for f in game.functions}
    fn_names = set(func_defs)
    sigs: dict[str, Sig] = {}

    def param_type(p: n.Parameter) -> Type:
        # The one parameter-typing rule, shared with every other parameter
        # position. Kept as a call rather than a second copy: a local copy
        # that missed `env.positions` would type a position-domain parameter
        # as the permissive top, which is the hole this module closes.
        return _param_type(p, env)

    def visit(name: str, on_stack: frozenset[str]) -> None:
        if name in sigs or name in on_stack:  # done, or a cycle resolve already flagged
            return
        f = func_defs[name]
        for callee in _called_functions(f.body, fn_names):
            visit(callee, on_stack | {name})
        func_env = replace(env, functions=sigs)
        param_types: list[Type] = []
        for p in f.params:
            t = param_type(p)
            param_types.append(t)
            func_env = func_env.with_local(p.name, t)
        _check_expr(f.body, func_env, bag)
        sigs[name] = Sig(tuple(param_types), infer(f.body, func_env))

    for fname in func_defs:
        visit(fname, frozenset())
    return sigs


def _param_type(p: n.Parameter, env: TypeEnv) -> Type:
    optional = p.type_name.endswith("?")
    base = p.type_name[:-1] if optional else p.type_name
    # Position domains resolve inside `type_from_name`, which maps `column` to
    # `TInteger` and the board-minted `cell` to `TCell`; a board-minted `dir`
    # maps to `TDir` via `env.directions`; and it keeps `slot?`/`dir?` optional
    # instead of flattening it.
    return type_from_name(base, optional, env.structs, env.positions, env.directions)


def _procedure_sigs(game: Game) -> dict[str, Sig]:
    """Each user procedure's parameter types. No dependency order is needed (a
    procedure may not run another — resolve rejects it) and there is no return
    type: `Sig.ret` is `TAny` and never read. The bodies themselves are checked by
    the statement walk, which binds these same parameter types as locals."""
    env = TypeEnv()  # `type_from_name` needs structs only for struct params, which
    # the procedure param domain does not admit (resolve gates it to Player).
    return {
        p.name: Sig(tuple(_param_type(x, env) for x in p.params), TAny())
        for p in game.procedures
    }


def _enum_domain(env: TypeEnv, enum_name: str) -> frozenset[str]:
    """Every value of a deck/kernel enum, from the value->enum map."""
    return frozenset(v for v, t in env.value_enums.items() if t.name == enum_name)


def _check_enum_operand(
    enum: TEnum, other: n.Expr, other_bare: Type, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """The enum-comparison Owner Guard: an equality (or membership element) against a
    known enum-typed operand must be able to be true. Cross-enum comparisons,
    Integer operands (a bare `10` is an Integer, never the rank "10"), and
    string literals outside the enum's value set are all silently-false traps
    at run time — reject them here. A name-form value written as a string is
    a second spelling of the bare literal and is rejected too (one spelling
    per concept). Non-literal String expressions stay unchecked (gradual);
    every OTHER concrete type (Card, Player, Boolean, a collection, …) is
    rejected by the default arm — an enum value equals only a value of its
    own enum, so the Owner Guard is total over the operand-type axis, not just the
    three shapes that motivated it."""
    if isinstance(other_bare, TEnum):
        if other_bare.name != enum.name:
            bag.error(
                f"comparing {enum.name} with {other_bare.name} can never be "
                f"equal",
                other.span,
            )
        return
    if isinstance(other_bare, TInteger):
        hint = (
            ' — numeric ranks are written as strings ("10")'
            if enum.name == "Rank"
            else ""
        )
        bag.error(
            f"comparing {enum.name} with Integer can never be equal{hint}",
            other.span,
        )
        return
    if isinstance(other, n.StrLit):
        domain = _enum_domain(env, enum.name)
        if other.value not in domain:
            bag.error(
                f'"{other.value}" is not a {enum.name} value of this deck',
                other.span,
            )
        elif not other.value.isdigit():
            bag.error(
                f"write the {enum.name} value bare — {other.value}, not "
                f'"{other.value}" (strings spell only the numeric ranks, '
                f"which would otherwise read as Integers)",
                other.span,
            )
        return
    if isinstance(other_bare, TAny):
        # Gradual: an unrefined `infer` arm must not manufacture errors.
        #
        # `TString` does NOT return here, though a String-typed variable holding a
        # rank NAME is the one shape that could arguably equal an enum value —
        # Coup's `card.rank is block_claim`, with `block_claim` a `String`. That is
        # not a feature; it is a silently-false comparison with a carve-out around
        # it, and the cure is to give the variable its real type
        # (`block_claim : Rank?`), which Coup has. No corpus game declares a String
        # at all. So String is rejected like any other disjoint type, and a string
        # LITERAL is still checked against the deck's values by the branch above
        # (`card.rank is "10"`, the numeric-rank spelling).
        return
    hint = (
        " — compare the whole card (`x is Q of spades`) or a field against "
        "its own kind (`x.suit is spades`)"
        if isinstance(other_bare, TCard)
        else ""
    )
    bag.error(
        f"comparing {enum.name} with {_type_name(other_bare)} can never be "
        f"equal{hint}",
        other.span,
    )


# --- BinOp operand Owner Guards: one dispatcher over the operator-class registry ---
#
# `infer`'s BinOp arm (above) is the operator registry: every op string a
# `BinOp` node can carry. `OP_CLASSES` classifies each into the operand-shape
# family that determines what a *sound* operand looks like — this is a
# second, independent read of the same registry (not derived from
# `infer`'s tuples in code, since their grouping is by *result* type, not
# operand legality), so `tests/test_operator_guards.py` pins the two against
# each other: a new operator landing in `infer` without a matching
# `OP_CLASSES` entry fails that test instead of silently reaching runtime
# unchecked.


class OpClass(Enum):
    EQUALITY = "equality"
    ORDERING = "ordering"
    ARITHMETIC = "arithmetic"
    LOGICAL = "logical"
    MEMBERSHIP = "membership"
    OFFSET_BY = "offset_by"


OP_CLASSES: dict[str, OpClass] = {
    "is": OpClass.EQUALITY,
    "is_not": OpClass.EQUALITY,
    "<": OpClass.ORDERING,
    ">": OpClass.ORDERING,
    "<=": OpClass.ORDERING,
    ">=": OpClass.ORDERING,
    "+": OpClass.ARITHMETIC,
    "-": OpClass.ARITHMETIC,
    "*": OpClass.ARITHMETIC,
    "divided_by_rounded_up": OpClass.ARITHMETIC,
    "divided_by_rounded_down": OpClass.ARITHMETIC,
    "and": OpClass.LOGICAL,
    "or": OpClass.LOGICAL,
    "in": OpClass.MEMBERSHIP,
    "offset_by": OpClass.OFFSET_BY,
}


# The surface spelling of each operator whose internal op string is not its
# own surface phrase — diagnostics render through this map so an internal
# spelling never reaches a designer. Symbols and `offset_by` are their own
# surface; only the rounded-division ops differ.
OP_SURFACE: dict[str, str] = {
    "divided_by_rounded_up": "divided by ... rounded up",
    "divided_by_rounded_down": "divided by ... rounded down",
}


def _op_word(op: str) -> str:
    return OP_SURFACE.get(op, op)


def _op_class(op: str) -> OpClass:
    cls = OP_CLASSES.get(op)
    if cls is None:
        # A future operator reached `infer`'s BinOp arm without an entry
        # here — loud, not a silent unchecked pass-through.
        raise AssertionError(
            f"operator '{op}' has no entry in OP_CLASSES — every BinOp "
            "operator the parser builds must be classified (surface "
            "totality, decisions.md); add it to the registry"
        )
    return cls


def _bare(t: Type) -> Type:
    """Unwrap a `T?` to `T` for operand-shape checks — an optional operand
    rejects/accepts exactly like its payload (sweep-the-class: every operand
    Owner Guard in this module applies to the optional wrapper of its rejection
    domain, not just the bare form)."""
    return t.inner if isinstance(t, TOptional) else t


def _check_binop(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    cls = _op_class(e.op)
    match cls:
        case OpClass.EQUALITY:
            _check_equality_operands(e, env, bag)
        case OpClass.ORDERING:
            _check_ordering_operands(e, env, bag)
        case OpClass.ARITHMETIC:
            _check_arithmetic_operands(e, env, bag)
        case OpClass.LOGICAL:
            _check_logical_operands(e, env, bag)
        case OpClass.MEMBERSHIP:
            _check_membership_operands(e, env, bag)
        case OpClass.OFFSET_BY:
            _check_offset_by_operands(e, env, bag)
        case _ as unreachable:
            assert_never(unreachable)


def _check_equality_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`==`/`!=` (surface `is`/`is not`): two operands can only be equal if one's
    type is coercible to the other's. Anything else is a comparison that is
    *always false* — the silently-wrong shape this Owner Guard exists to catch.

    The enum rows come first and keep their own nuanced diagnostics
    (`_check_enum_operand`: the name-form-vs-string spelling, the not-a-value-of-
    this-deck message, the Rank-vs-Integer hint). Every other pair falls to the
    general disjointness rule below.

    That general rule closes a hole an enum-centric Owner Guard leaves wide:
    such a guard fires only when one side is a `TEnum`, so `Boolean` would have
    no row at all (`flag is hearts`, `flag is 1`, `flag is "x"` all passing),
    and neither would `Integer is "x"` or `Player is "x"`. It was found by
    typing the round-state pronoun (stdlib/round_state.py):
    `state.trick_terminated_early` became a real `Boolean` and immediately
    exposed that comparing one to a suit was accepted.
    Per decisions.md "Closed-domain completeness", the fix sweeps the class rather
    than patching the instance — the class being "equality between disjoint
    concrete types", and the layer that owns it being the type layer every
    comparison consults.

    `TAny` passes on either side (gradual typing — an unrefined `infer` arm must
    not manufacture errors). `Player`/`Integer` stay comparable in BOTH directions
    because a player IS an integer seat here (`coercible(TInteger, TPlayer)`), so
    `turn is 0` and `responder is actor` keep working."""
    lbare, rbare = _bare(infer(e.left, env)), _bare(infer(e.right, env))
    if isinstance(lbare, TEnum):
        _check_enum_operand(lbare, e.right, rbare, env, bag)
        return
    if isinstance(rbare, TEnum):
        _check_enum_operand(rbare, e.left, lbare, env, bag)
        return
    if isinstance(lbare, TAny) or isinstance(rbare, TAny):
        return
    compatible = (
        coercible(lbare, rbare)  # choke-point-exempt: symmetric equality, two operands and no single `expected` — not an operand coercion
        or coercible(rbare, lbare)  # choke-point-exempt: the reverse direction of the same symmetric check
        # `join` as well as `coercible`, because `coercible` honours `TAny` only at
        # the TOP level: a deliberately-unrefined element type (a chip stack is
        # `Collection<Any>` precisely because that part of the object model is
        # unrefined) would be judged disjoint from `Collection<Card>`, and this
        # Owner Guard would MANUFACTURE an error — the exact thing its own
        # gradual-typing promise forbids. `coercible` alone is also not enough in
        # the other direction, so both are consulted: `Player`/`Integer` must stay
        # comparable (a player IS an integer seat), and only `coercible` says so.
        or join(lbare, rbare) is not None
    )
    if not compatible:
        bag.error(
            f"comparing {_type_name(lbare)} with {_type_name(rbare)} can never be "
            f"equal",
            e.span,
        )


def _check_ordering_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`< > <= >=`: only Integers have an order in this language. A concrete
    Rank operand is the plausible mistake (its declared order lives in
    `ranking:`, not code-point order — Python would compare the rank
    *strings*, e.g. "10" < "9"), so it gets a named fix; every other
    concrete non-Integer operand (another enum, Boolean, Card, Player, Team,
    a collection) is equally nonsensical and rejected the same way.
    TAny/TInteger pass (gradual)."""
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if isinstance(bare, (TAny, TInteger)):
            continue
        if isinstance(bare, TEnum) and bare.name == "Rank":
            bag.error(
                f"'{e.op}' compares Integers — enum values have no "
                "arithmetic order — compare strength via rank_value(...)",
                operand.span,
            )
        elif isinstance(bare, TEnum):
            bag.error(
                f"'{e.op}' compares Integers — {bare.name} enum values have "
                "no arithmetic order",
                operand.span,
            )
        else:
            bag.error(
                f"'{e.op}' compares Integers, got {_type_name(bare)}",
                operand.span,
            )


def _check_arithmetic_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`+ - *` and rounded division: only Integers are numeric in this
    language. A concrete enum operand is the worst case for `+` — it
    string-concatenates at runtime instead of raising, so a bug like
    `card.rank + 1` reads as legal and is silently wrong every time it runs;
    the concatenation clause is stated only for the ops it is true of. Every
    other concrete non-Integer operand rejects the same way as ordering.
    TAny/TInteger pass. Messages render the op through `_op_word` so the
    rounded-division ops speak their surface phrase, never the internal
    spelling."""
    word = _op_word(e.op)
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if isinstance(bare, (TAny, TInteger)):
            continue
        if isinstance(bare, TEnum) and bare.name == "Rank":
            bag.error(
                f"'{word}' expects Integer operands — enum values have no "
                "numeric value — compare strength via rank_value(...)",
                operand.span,
            )
        elif isinstance(bare, TEnum) and e.op in ("+", "-", "*"):
            bag.error(
                f"'{word}' expects Integer operands, got {bare.name} — an "
                "enum value concatenates as a string at runtime, not adds",
                operand.span,
            )
        elif isinstance(bare, TEnum):
            bag.error(
                f"'{word}' expects Integer operands, got {bare.name} — an "
                "enum value has no numeric value",
                operand.span,
            )
        else:
            bag.error(
                f"'{word}' expects Integer operands, got {_type_name(bare)}",
                operand.span,
            )


def _check_logical_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`and or`: both operands must be Boolean. This checks the operator's own
    operands, independent of `_check_bool` on whatever *contains* the
    expression — `if (a and 3) { … }` is Boolean overall (`and`'s `infer()`
    arm is a fixed `TBoolean`, regardless of its operands), so a top-level
    Boolean check on the whole `if` condition never sees the smuggled
    Integer. TAny passes (gradual)."""
    for operand in (e.left, e.right):
        bare = _bare(infer(operand, env))
        if not isinstance(bare, (TAny, TBoolean)):
            bag.error(
                f"'{e.op}' expects Boolean operands, got {_type_name(bare)}",
                operand.span,
            )


def _check_membership_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`in`: the right-hand side must be a collection (unchanged Owner Guard); the
    left operand must be a plausible element of it. A `[...]` literal against
    a known enum-typed left operand keeps the existing per-element literal
    validation (`card.rank in [A, "10"]` — doppelkopf), since that catches
    misspelled/mistyped *literals* `join` cannot see (a bad numeral, a
    cross-enum literal). Every other combination is checked generally: when
    both the left type and the collection's element type are concrete and
    `join` finds them incompatible, the membership can never be true."""
    right_t = infer(e.right, env)
    if not isinstance(right_t, (TCollection, TAny)):
        bag.error(
            "the right-hand side of `in` must be a collection (a zone or "
            f"a `[…]` list), got {_type_name(right_t)}",
            e.span,
        )
        return
    if isinstance(right_t, TCollection) and right_t.key is not None:
        # A keyed map is ambiguous under `in`: the sentence reads as a VALUE
        # test, but the runtime store is a dict, whose `in` asks about KEYS —
        # `2 in m` with every value 99 answered True because seat 2 exists.
        # Reject rather than pick a side silently; both meanings have direct
        # spellings. A TAny key means SOME branch of a merge is a map (the
        # sticky rule in `types.join`), which is exactly as ambiguous.
        what_map = (
            f"a map keyed by {_type_name(right_t.key)}"
            if not isinstance(right_t.key, TAny)
            else "a value that may be a keyed map (one branch of its "
            "conditional is)"
        )
        bag.error(
            f"`in` on {what_map} is ambiguous (keys or values?) — test a "
            f"specific entry (`m[k] is …`) or quantify over the key domain "
            f"instead",
            e.span,
        )
        return
    lbare = _bare(infer(e.left, env))
    if isinstance(lbare, TEnum) and isinstance(e.right, n.ListLit):
        for item in e.right.elements:
            ibare = _bare(infer(item, env))
            _check_enum_operand(lbare, item, ibare, env, bag)
        return
    if not isinstance(right_t, TCollection):
        return  # a TAny collection: nothing more `join` can say
    ebare = _bare(right_t.element)
    if isinstance(lbare, TAny) or isinstance(ebare, TAny):
        return
    if join(lbare, ebare) is None:
        bag.error(
            f"membership compares {_type_name(lbare)} with a collection of "
            f"{_type_name(ebare)} — never true",
            e.span,
        )


def _check_offset_by_operands(e: n.BinOp, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`offset_by`: rotates a Player around the seating ring by a
    SeatDirection (`runtime.values.Seating.offset_by`) — the left operand must
    be a Player, the right a SeatDirection-enum value
    (`hand[player offset_by pass_direction]`
    in hearts.cardlang reads the direction off a declared `Direction` state
    var, not only a bare `left`/`right`/`across`/`hold` literal, so this
    checks the *type*, not the ref-kind)."""
    lbare = _bare(infer(e.left, env))
    if not isinstance(lbare, (TAny, TPlayer)):
        bag.error(
            "'offset_by' rotates a Player around the seating ring — the "
            f"left operand must be a Player, got {_type_name(lbare)}",
            e.left.span,
        )
    rbare = _bare(infer(e.right, env))
    if isinstance(rbare, TAny):
        return
    if not (isinstance(rbare, TEnum) and rbare.name == "SeatDirection"):
        bag.error(
            "'offset_by' expects a SeatDirection (left/right/across/hold) on "
            f"the right, got {_type_name(rbare)}",
            e.right.span,
        )


def _check_card_source(source: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Both `cards in <source>` (CardQuery) and `over cards in <source>` (an
    aggregation) expect a zone or a collection of cards — the shared source
    Owner Guard, since a wrong source degrades every downstream Card Owner Guard
    to `TAny` (the `card` binder types off this same inference — the zone-family
    subscript-typing case in tests/test_zone_family_typing.py covers exactly
    this failure mode). A non-collection source and a collection of the wrong
    element type both fail the same way: `join` against `TCard` finds nothing
    in common."""
    src_t = infer(source, env)
    bare_src = _bare(src_t)
    if isinstance(bare_src, TAny):
        return
    if not isinstance(bare_src, TCollection):
        # A non-collection source is wrong even when it is card-TYPED: a
        # single Card unifies with TCard, but iterating it at runtime is a
        # crash, not a one-card query.
        hint = (
            " — a single Card is not a collection of cards"
            if isinstance(bare_src, TCard)
            else ""
        )
        bag.error(
            f"'cards in ...' expects a zone or collection of cards, got "
            f"{_type_name(src_t)}{hint}",
            source.span,
        )
        return
    ebare = _bare(bare_src.element)
    if isinstance(ebare, TAny):
        return
    if join(ebare, TCard()) is None:
        bag.error(
            f"'cards in ...' expects a zone or collection of cards, got "
            f"{_type_name(src_t)}",
            source.span,
        )


def _check_agg_body(e: n.Comprehension, scoped: TypeEnv, bag: DiagnosticBag) -> None:
    """`sum`/`max`/`min` all fold Integers, and an enum-typed body (most
    plausibly a bare `card.rank`/`card.suit` where the author meant its
    strength) is the plausible-mistake case, so it gets the rank_value hint
    — but the two aggregators diverge at runtime (evaluate._comprehension),
    so the message names what actually happens: `sum` folds Python's
    `sum()`, whose zero-valued start makes `0 + "hearts"` a `TypeError` —
    loud, but only at play time, arbitrarily deep into a game; `max`/`min`
    fold Python's `max()`/`min()`, which silently compare the enum values
    *lexicographically as strings* — no crash, just the wrong card, forever.
    Every other concrete non-Integer body is equally nonsensical and gets
    the generic message. TAny/TInteger pass (gradual)."""
    bare = _bare(infer(e.body, scoped))
    if isinstance(bare, (TAny, TInteger)):
        return
    if isinstance(bare, TEnum):
        runtime_note = (
            "summing enum values type-errors at runtime (adding a string "
            "to an integer)"
            if e.agg == "sum"
            else "comparing enum values folds the underlying strings "
            "lexicographically at runtime, not the card's actual strength"
        )
        bag.error(
            f"'{e.agg}' aggregates a numeric strength — rank_value(card) — "
            f"not the enum value itself ({runtime_note})",
            e.body.span,
        )
        return
    bag.error(
        f"'{e.agg}' expects an Integer body, got {_type_name(bare)}",
        e.body.span,
    )


def _check_agg_default(
    e: n.Comprehension, env: TypeEnv, scoped: TypeEnv, bag: DiagnosticBag
) -> None:
    """The order aggregators' mandatory `or <default>` clause shares its
    leading `or` with a compound `where` predicate — `where A or B` reads as
    where=A, default=B, the headline misparse this Owner Guard exists to catch. A
    Boolean default is the tell (a real default is body-shaped, e.g. an
    Integer for a `rank_value(card)` body; a leftover predicate is not) —
    flagged whenever there IS a `where` clause for the `or` to have been
    split from (no `where`, no ambiguity: a Boolean default there is an
    ordinary type mismatch, handled by the generic check below). Otherwise, a
    concrete body/default type mismatch `join` can't reconcile is rejected
    generically."""
    assert e.default is not None
    dbare = _bare(infer(e.default, env))
    if isinstance(dbare, TBoolean) and e.where is not None:
        bag.error(
            "the aggregation default is Boolean — this is almost always the "
            "last disjunct of the `where` predicate, absorbed by the "
            "mandatory `or <default>` clause: parenthesize the whole `where` "
            "predicate, or supply a real default after `or`",
            e.default.span,
        )
        return
    bbare = _bare(infer(e.body, scoped))
    if isinstance(bbare, TAny) or isinstance(dbare, TAny):
        return
    if join(bbare, dbare) is None:
        bag.error(
            f"'{e.agg}' aggregation default type mismatch: the body is "
            f"{_type_name(bbare)}, the default is {_type_name(dbare)}",
            e.default.span,
        )


def _check_is_check(e: n.IsCheck, env: TypeEnv, bag: DiagnosticBag) -> None:
    """`is empty`/`is not empty` ask a zone or collection; `is none`/`is not
    none` ask an optional. A concrete operand outside that domain isn't
    merely wrong, it's dead: both checks then have a fixed truth value
    regardless of the game's live state — never a check worth writing.
    TAny passes (gradual); TOptional/TNull pass the none-checks (their whole
    point)."""
    t = infer(e.operand, env)
    bare = _bare(t)
    if e.kind in ("empty", "not_empty"):
        if isinstance(bare, (TAny, TCollection)):
            return
        surface = "is empty" if e.kind == "empty" else "is not empty"
        bag.error(
            f"`{surface}` asks a zone or collection — got {_type_name(bare)}",
            e.operand.span,
        )
    else:  # "none" | "not_none"
        if isinstance(t, (TAny, TOptional, TNull)):
            return
        surface = "is none" if e.kind == "none" else "is not none"
        always = "always false" if e.kind == "none" else "always true"
        bag.error(
            f"`{surface}` on a non-optional {_type_name(bare)} is {always} "
            "— never a check worth writing",
            e.operand.span,
        )


# The two collection quantifier nouns and the member type each binds
# (decisions.md "Boards and cells"): `any line in <lines> …` walks a
# collection of lines binding `line`:TLine; `all cells in <line> …` walks one
# line binding `cell`:TCell. Fixed at rung 1; resolve rejects any other noun.
_COLLECTION_BINDER_TYPES: Mapping[str, Type] = {"line": TLine(), "cell": TCell()}

# The dot-form (`Member`) receiver classes, by the diagnostic each earns. They
# are module constants, not inline `isinstance` tuples, because
# tests/test_typecheck_errors.py cross-checks them against `get_args(Type)`:
# every member of the `Type` union must be classified by exactly one arm, so a
# newly declared type fails that pin instead of silently reaching no arm and
# inferring `TAny` (the permissive-top gap this class of Owner Guard exists to close).
# Adding a type means classifying it here -- or, if it genuinely carries fields,
# giving it its own arm beside `TStruct`/`TCard` and recording it there.
_INDEXABLE_RECEIVERS = (TPlayer, TTeam, TInteger, TBoolean)
_FIELDLESS_RECEIVERS = (TCell, TDir, TLine, TEnum, TString, TNull, TOutcome)


def _domain_query_binder_type(
    e: n.DomainQuery, env: TypeEnv, bag: DiagnosticBag
) -> Type:
    """The type a DomainQuery binds its element to, plus (for collection forms)
    the source-shape Owner Guard. A BARE form binds the position domain's member type
    (`TCell` for a board's `cell`, `TInteger` for an integer domain -- resolve
    validated the noun, so a lookup miss falls back to the permissive top). A
    COLLECTION form's noun fixes BOTH the binder type and the required source
    type: `line` iterates a collection of lines, `cell` iterates one line."""
    if e.source is None:
        return env.positions.get(e.binder, TAny())
    want, desc = (
        (TCollection(TLine()), "a collection of lines (e.g. `lines(3)`)")
        if e.binder == "line"
        else (TLine(), "a single line")  # e.binder == "cell" (resolve gates the rest)
    )
    src_t = infer(e.source, env)
    _check_operand(
        e.source, src_t, want, env, bag,
        f"`{e.kind} {e.spelled} in …` iterates {desc}, but the source is "
        f"{_type_name(src_t)}",
        e.span,
    )
    return _COLLECTION_BINDER_TYPES.get(e.binder, TAny())


def _check_role_literal(index: n.Expr, expected: Type, env: TypeEnv, bag: DiagnosticBag) -> None:
    """A `Player`/`Team` literal names a 0-based identity, so it must be one the
    game has. An integer literal coerces to both (`coercible(Integer, Player)`,
    `coercible(Integer, Team)` -- both are int identities), and an unchecked
    out-of-range literal -- `reserve[2]`/`home(2)` on a two-seat game, `melds[2]`
    on a two-team game -- names a seat or team with no member; the reader (a zone
    family with no such instance, a board frame's per-seat sign, a per-team score)
    then fails at runtime, a typechecked game crashing. The bound is the game's
    MAXIMUM count -- a range game's `high` for players, `len(teams)` for
    teams -- and is two-sided: the `0 <=` lower bound rejects a NEGATIVE literal
    (an `IntLit` with a negative value; there is no separate negative-literal
    node), so `reserve[-1]` is caught too.

    Called from ONE place -- `_check_operand`, the choke point every operand
    coercion routes through -- so the check applies at EVERY position an integer
    literal reaches a Player or Team, by construction (the pin
    tests/test_operand_choke_point.py enforces it). A non-role `expected` is a
    no-op, and a count of 0 (a game with no teams has `max_teams == 0`)
    disables the team bound, mirroring `max_players <= 0`.

    An OPTIONAL expectation (`Player?`/`Team?`) is unwrapped first: `coercible`
    coerces an Integer into the optional by reaching its payload, so a literal in
    a `Player?` position is the same seat a bare `Player` position is."""
    bare = expected.inner if isinstance(expected, TOptional) else expected
    if not isinstance(index, n.IntLit):
        return
    if isinstance(bare, TPlayer):
        # A game always declares `players:`, so `max_players` is the real seat
        # count; 0 would mean "no player info" (a partial env, not reached in a
        # real check) and is skipped defensively.
        if env.max_players <= 0:
            return
        bound, noun, label = env.max_players, "player", "seat"
    elif isinstance(bare, TTeam):
        # `max_teams == 0` is the COMMON no-`teams:` case: a KNOWN EMPTY
        # team domain, NOT an unknown bound -- so it is NOT skipped, and every
        # team literal (even `0`) is rejected as naming a team the game has none
        # of (`0 <= k < 0` is always false). A team-KEYED zone/state already
        # requires teams at resolve, but a Team-TYPED operand -- a `state`
        # default, a Team call arg, a struct field, a outcome payload -- does
        # not, and reaches here.
        bound, noun, label = env.max_teams, "team", "team"
    else:
        return
    if not 0 <= index.value < bound:
        ids = f"0..{bound - 1}" if bound > 1 else ("0" if bound == 1 else "none")
        bag.error(
            f"{label} {index.value} is out of range: the game has "
            f"{bound} {noun}(s) ({ids})",
            index.span,
        )


def _check_operand(
    node: n.Expr,
    got: Type,
    expected: Type,
    env: TypeEnv,
    bag: DiagnosticBag,
    msg: str,
    span: Span | None,
) -> None:
    """The ONE operand-coercion check every `coercible(_, expected)` site routes
    through, so the seat-range check is applied at EVERY position an integer
    literal reaches a Player (or Team), not at a hand-picked subset. Two things
    happen here and nowhere else:

      1. the coercion Owner Guard -- if `got` cannot stand where `expected` is
         wanted, the site's own `msg` is reported at `span`; and
      2. the role-literal range check -- an out-of-range integer literal
         (`hand[5]` on a two-seat game) is rejected, a non-role `expected` making
         it a no-op so every operand routes through uniformly.

    `node` (the operand, for the literal check) and `span` (the error location)
    are separate arguments BECAUSE they differ at nearly every site: an operand's
    coercion error belongs to its ENCLOSING construct -- the call, the
    assignment, the struct literal -- whose span the caller passes, while the
    range error fires at the literal WITHIN it (`node.span`, inside the helper).
    Passing `node.span` as the error span would move ~every coercion
    diagnostic; keeping them separate means routing a site through here moves no
    diagnostic.

    Keeping the two checks together at one call is what lets the completeness pin
    (tests/test_operand_choke_point.py) enforce by construction that no
    `coercible(_, Player)` coercion escapes the range check: the pin reddens the
    day a new operand position calls `coercible` directly instead of routing
    here."""
    if not coercible(got, expected):
        bag.error(msg, span)
    _check_role_literal(node, expected, env, bag)


def _check_round_actors(
    stmt: n.TrickRound | n.AuctionRound | n.ClimbRound,
    env: TypeEnv,
    bag: DiagnosticBag,
) -> None:
    """The `from <leader> over <participants>` pair every round form carries.

    Shared across the three forms because it is the same contract in each, the
    one `turns` carries too: before the operand choke point neither half was
    type- or range-checked (only `until` was), so `round … from 5` on a
    two-seat game passed.
    """
    lt = infer(stmt.leader, env)
    _check_operand(
        stmt.leader, lt, TPlayer(), env, bag,
        f"`round … from` names the first player — expected a Player, "
        f"got {_type_name(lt)}",
        stmt.span,
    )
    _check_participants(
        stmt.participants, env, bag,
        "`round … over` names the participants",
        stmt.span,
    )


def _check_round_ranking(
    stmt: n.TrickRound | n.AuctionRound | n.ClimbRound,
    env: TypeEnv,
    bag: DiagnosticBag,
) -> None:
    """The ranking demand of a round's NAMED callbacks — the slot twin of the
    `RANKING_GATED_FUNCS` call gate (same condition, same message shape). A
    winner or climb query that indexes `rank_index` is named bare in its
    slot, never called, so the Call-site gate cannot see it; without this, a
    no-`ranking:` game naming one checks clean and crashes bare at the first
    trick's resolution. The auction form names no ranking-reading callback
    (its outcomes read the bid history), so it contributes no members —
    included in the signature because the dispatch calls this for every
    round form and a future member would join a set, not a new branch."""
    demanded: list[str] = []
    if isinstance(stmt, n.TrickRound) and stmt.winner_fn in RANKING_GATED_WINNERS:
        demanded.append(f"round winner {stmt.winner_fn}")
    if isinstance(stmt, n.ClimbRound):
        for q in (stmt.combos_fn, stmt.follows_fn):
            if q in RANKING_GATED_CLIMB_QUERIES:
                demanded.append(f"climb query {q}")
    if demanded and not env.has_ranking:
        for name in demanded:
            bag.error(
                f"{name} reads a card's rank strength from ranking:, "
                f"but the game declares no ranking: — declare one, or declare "
                f"a `trick_order {{ }}` with a `card_strength:` row and name "
                f"{min(TRICK_ORDER_GATED_WINNERS)}",
                stmt.span,
            )


def _check_trick_order(game: n.Game, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Each [[trick-order]] row types EXACTLY its reader's return type.

    The required type is `CALL_SIGS[reader].ret` — read back from the
    signature the language mints, so the demand is stated once and a row and
    its reader can never disagree. Strictness is the point (issue #250 PR 1,
    ruled point 2): `trump:` and `card_strength:` compare by type EQUALITY, so
    an optional cannot slip in. A `Boolean?` trump row whose value went absent
    would read as not-a-trump, silently, for the rest of the game; only
    `follow_class:` is genuinely optional-typed, and it routes through
    `_check_operand` because `none` and a bare `Suit` both legitimately stand
    where `Suit?` is wanted.

    `TAny`, the [[permissive-top]], is refused in both arms. It is what the
    checker returns when it CANNOT type an expression — a mixed-branch `if`,
    an untyped read — so accepting it would let exactly the rows nobody could
    check through the strictest gate in the construct.
    """
    if game.trick_order is None:
        return
    row_env = _scoped_env(env, (("card", TCard()),))
    for row in game.trick_order.rows:
        # Through the generic expression walk first, so a row gets every
        # ordinary diagnostic (an unknown card field, a call arity, the
        # `ranking:` gate on `rank_value`) from the pass that owns it, and
        # this check adds only the demand that is the ROW's own.
        _check_expr(row.body, row_env, bag)
        reader = next(r for k, r in TRICK_ORDER_ROWS if k == row.key)
        expected = CALL_SIGS[reader].ret
        got = infer(row.body, row_env)
        if isinstance(got, TAny):
            bag.error(
                f"`{row.key}:` row types as `Any`, the permissive top (a value "
                f"the checker cannot type — a mixed-branch `if`, an untyped "
                f"read); a Trick Order row must type exactly "
                f"{_type_name(expected)}",
                row.span or game.span,
            )
            continue
        if isinstance(expected, TOptional):
            _check_operand(
                row.body, got, expected, row_env, bag,
                _row_type_message(row.key, got, expected, game),
                row.span or game.span,
            )
        elif got != expected:
            bag.error(
                _row_type_message(row.key, got, expected, game), row.span or game.span
            )
    if game.trick_order.row("card_strength") is None and not env.has_ranking:
        # The omitted row defaults to `rank_value(card)` (the driver's table),
        # which reads `ranking:` — so the default silently demands a clause
        # the game may not declare. Named at the BLOCK, not through the
        # RANKING_GATED sentence: the reader here is a default nobody wrote.
        bag.error(
            "`trick_order` declares no `card_strength:` row, so strength "
            "defaults to `rank_value(card)`, which reads `ranking:` — but the "
            "game declares no `ranking:`; declare one, or write a "
            "`card_strength:` row",
            game.trick_order.span or game.span,
        )


def _row_type_message(key: str, got: Type, expected: Type, game: n.Game) -> str:
    """A row's type refusal, with the hint its most plausible wrong spelling
    earns. Each hint answers a specific confusion the row invites, so a
    designer who wrote the wrong thing is told what the RIGHT thing looks
    like rather than only that the type is wrong."""
    gname = _type_name(got)
    if key == "trump":
        msg = f"`trump:` row must type Boolean (is this card a trump?), got {gname}"
        if isinstance(got, TEnum) and got.name == "Suit":
            # A concrete suit of THIS deck, so the remedy is a sentence the
            # designer can paste (resolve already refused an unknown deck, the
            # `_suit_types` precedent above).
            known = sorted(suit_names(game.deck))
            suit = known[0] if known else "spades"
            return msg + f" — for a fixed trump suit write `trump: card.suit is {suit}`"
        if isinstance(got, TOptional) and isinstance(got.inner, TBoolean):
            return msg + (
                " — a Trick Order row is never absent-valued (a `none` would "
                "read as not-a-trump silently)"
            )
        return msg
    if key == "follow_class":
        msg = (
            f"`follow_class:` row must type Suit? (the class the card follows "
            f"as, or none for class-less), got {gname}"
        )
        if isinstance(got, TString):
            return msg + (
                " — a trump follows as a trump by the `trump:` row, never by a "
                "class value; the class of a trump card is not consulted"
            )
        return msg
    return (
        f"`card_strength:` row must type Integer (strength within its class; "
        f"higher beats lower), got {gname}"
    )


def _check_round_trump(stmt: n.TrickRound, env: TypeEnv, bag: DiagnosticBag) -> None:
    """The trick round's `trump <expr>` names the trump suit for the pass —
    or `none` for no trump (Bridge's no-trump contract) — so it is held to
    `Suit?`, exactly the type the call form's trump argument already carries
    (`CALL_SIGS["highest_trump_or_led_suit"]`). Before this the clause was
    only walked as an expression: `trump 3`, `trump "hearts"`, `trump J`
    all checked clean and the runtime compared card suits against an
    Integer, a String, a Rank — no suit ever matched, and the game silently
    played no-trumps while its rules still enforced the trump obligations
    (accepted-with-different-semantics). Through the operand choke point,
    so an out-of-range seat literal and the coercion rules are the same
    ones every other operand gets. Whether the WINNER reads the clause at
    all is resolve's (`TRUMP_READING_WINNERS`), settled before this runs."""
    if stmt.trump is None:
        return
    got = infer(stmt.trump, env)
    _check_operand(
        stmt.trump, got, TOptional(TEnum("Suit")), env, bag,
        f"round `trump` names the trump suit — expected Suit? (a suit, or "
        f"none for no trump), got {_type_name(got)}",
        stmt.span,
    )


def _check_participants(
    node: n.Expr, env: TypeEnv, bag: DiagnosticBag, where: str, span: Span | None
) -> None:
    """A `turns`/`round` `over <participants>` names a player COLLECTION. A LIST
    literal (`over [0, 2]`) is checked element by element -- each element is a
    Player operand, so an out-of-range seat in `over [5]` is caught by the same
    range check every other operand gets. Any other collection expression
    (`all players`, a player-collection variable) is checked whole against
    `Collection<Player>`. The two are split, not merged, so a mistyped element in
    a literal draws ONE error -- its own -- not both a per-element and a
    whole-collection one."""
    if isinstance(node, n.ListLit):
        for elem in node.elements:
            et = infer(elem, env)
            _check_operand(
                elem, et, TPlayer(), env, bag,
                f"{where} — expected players, got {_type_name(et)}",
                elem.span,
            )
    else:
        pt = infer(node, env)
        _check_operand(
            node, pt, TCollection(TPlayer()), env, bag,
            f"{where} — expected a collection of players, got {_type_name(pt)}",
            span,
        )


def _check_expr(e: n.Expr, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Recursively validate a single expression: native argument types and
    subscript legality. Types of unrefined sub-parts are `TAny` (permissive).

    Binder-introducing expressions extend the environment for their body, so
    type-directed checks (the dot-form rejection above all) see quantifier,
    player-query, card-query, and aggregation binders at their real types
    rather than `TAny`."""
    if isinstance(e, n.Quantifier):
        scoped = env.with_local(e.binder, _role_type(e.role))
        _check_expr(e.body, scoped, bag)
        _check_bool(e.body, scoped, bag, f"'{e.kind} {e.role}' quantifier body")
        return
    if isinstance(e, n.PlayerQuery):
        if e.start is not None:
            # The ring search's start seat evaluates in the ENCLOSING scope
            # (the comprehension-source split; nodes.PlayerQuery docstring),
            # routed through the operand choke point so the literal seat
            # range check applies here as at every other Player position.
            _check_expr(e.start, env, bag)
            st = infer(e.start, env)
            _check_operand(
                e.start, st, TPlayer(), env, bag,
                f"`the first player from` names the start seat — expected a "
                f"Player, got {_type_name(st)}",
                e.span,
            )
        scoped = env.with_local("player", TPlayer())
        _check_expr(e.where, scoped, bag)
        _check_bool(e.where, scoped, bag, "player-query predicate")
        return
    if isinstance(e, n.CardQuery):
        if env.flavor == "piece":
            # `cards in ... / any card in ... / number of cards in ...` all
            # hardcode the card noun; a piece game has no such form (the piece
            # twin is grammatically inexpressible -- a recorded residual).
            bag.error(
                f"{content_kind_clause(env.flavor, env.deck)} -- a card query "
                f"(`{e.kind}`) reads a zone as cards; count/scan pieces with the "
                f"generic collection forms",
                e.span,
            )
            return
        _check_expr(e.source, env, bag)
        _check_card_source(e.source, env, bag)
        if e.where is not None:
            scoped = env.with_local("card", TCard())
            _check_expr(e.where, scoped, bag)
            _check_bool(e.where, scoped, bag, "card-query predicate")
        return
    if isinstance(e, n.DomainQuery):
        binder_t = _domain_query_binder_type(e, env, bag)
        if e.source is not None:
            _check_expr(e.source, env, bag)  # the `in` source is in enclosing scope
        scoped = env.with_local(e.binder, binder_t)
        _check_expr(e.where, scoped, bag)
        phrase = n.DOMAIN_QUERY_KIND_PHRASE[e.kind]
        _check_bool(e.where, scoped, bag, f"`{phrase} {e.spelled}` predicate")
        return
    if isinstance(e, n.Comprehension):
        if env.flavor == "piece":
            # `sum of ... over cards in ...` and the RANK_DIR order aggregators
            # hardcode "cards"; rejected in a piece game (no piece twin form).
            bag.error(
                f"{content_kind_clause(env.flavor, env.deck)} -- an aggregation "
                f"over `cards in ...` reads a zone as cards; a piece set has no "
                f"such form",
                e.span,
            )
            return
        _check_expr(e.source, env, bag)
        _check_card_source(e.source, env, bag)
        src = infer(e.source, env)
        elem: Type = src.element if isinstance(src, TCollection) else TAny()
        scoped = env.with_local(e.binder, elem)
        if e.where is not None:
            _check_expr(e.where, scoped, bag)
            _check_bool(e.where, scoped, bag, "aggregation `where` filter")
        _check_expr(e.body, scoped, bag)
        _check_agg_body(e, scoped, bag)
        if e.default is not None:
            _check_expr(e.default, env, bag)
            _check_agg_default(e, env, scoped, bag)
        return
    for child in _child_exprs(e):
        _check_expr(child, env, bag)
    if isinstance(e, n.Call):
        sig = CALL_SIGS.get(e.func) or env.functions.get(e.func)
        if sig is not None:
            args = _arg_exprs(e.args)
            if len(args) != len(sig.params):
                bag.error(
                    f"{e.func}() expects {len(sig.params)} argument(s), got {len(args)}",
                    e.span,
                )
            else:
                for arg, param in zip(args, sig.params):
                    got = infer(arg, env)
                    _check_operand(
                        arg, got, param, env, bag,
                        f"{e.func}() expects {_type_name(param)}, got {_type_name(got)}",
                        e.span,
                    )
        if e.func in RANKING_GATED_FUNCS and not env.has_ranking:
            bag.error(
                f"{e.func}() reads a card's rank strength from ranking:, "
                f"but the game declares no ranking: — declare one, or declare "
                f"a `trick_order {{ }}` with a `card_strength:` row and name "
                f"{min(TRICK_ORDER_GATED_WINNERS)}",
                e.span,
            )
    elif isinstance(e, n.Subscript):
        obj_ref = e.obj
        if isinstance(obj_ref, n.NameRef) and obj_ref.ref_kind == "zone":
            # A zone-family subscript (`hand[p]`) is checked against the
            # zone's declared index role, not the generic
            # subscriptable-collection check below — a family isn't a
            # collection being indexed, it's ONE zone instance among many
            # selected by key.
            family = env.zone_families.get(obj_ref.name)
            if family is None:
                bag.error(
                    f"zone '{obj_ref.name}' is not indexed — drop the "
                    f"brackets",
                    e.span,
                )
            else:
                idx_t = infer(e.index, env)
                _check_operand(
                    e.index, idx_t, family, env, bag,
                    f"`{obj_ref.name}` is keyed by {_type_name(family)}"
                    f" — got {_type_name(idx_t)}",
                    e.span,
                )
        else:
            obj = infer(e.obj, env)
            if not subscriptable(obj):
                bag.error(f"cannot index {_type_name(obj)} (not a collection)", e.span)
            elif isinstance(obj, TCollection) and obj.key is not None:
                # A KEYED map (a per-player/team state var, an indexed `let`)
                # is addressed by its key domain, and the checker knows both
                # sides — without this, `n[hearts]` would sail through to a
                # runtime that indexes the map directly and requires the key
                # to be one it actually holds.
                idx_t = infer(e.index, env)
                what = (
                    f"`{obj_ref.name}`"
                    if isinstance(obj_ref, n.NameRef)
                    else "this map"
                )
                _check_operand(
                    e.index, idx_t, obj.key, env, bag,
                    f"{what} is keyed by {_type_name(obj.key)} — got "
                    f"{_type_name(idx_t)}",
                    e.span,
                )
    elif isinstance(e, n.StructLit):
        _check_struct_lit(e, env, bag)
    elif isinstance(e, n.Member):
        obj_ref = e.obj
        if (
            isinstance(obj_ref, n.NameRef)
            and obj_ref.ref_kind == "pronoun"
            and obj_ref.name == "state"
            and e.field not in ROUND_STATE_FIELDS
        ):
            # `state.` names a round's PUBLISHED state, and that is a closed set.
            # Without this Owner Guard the receiver inferred `TAny`, every arm below
            # missed, and the read went through: a typo (`state.lead_suit`)
            # failed only at play time, where the running round refuses a field
            # it does not publish, and — far worse — a form's
            # private working memory (`state.idx`, the trick's ring cursor) read
            # clean, ran, and silently changed the game. See stdlib/round_state.py.
            field_list = ", ".join(f"`{f}`" for f in sorted(ROUND_STATE_FIELDS))
            bag.error(
                f"a round publishes no `{e.field}` — `state.` names a round's "
                f"published state, which is {field_list}",
                e.span,
            )
            return
        obj = infer(e.obj, env)
        # Optionals reject like their payload: `d : Player?` is as much a
        # non-object receiver as `d : Player` (the closed rejection domain
        # includes the optional wrappers of its members).
        bare = obj.inner if isinstance(obj, TOptional) else obj
        if isinstance(obj, TStruct) and e.field not in obj.fields:
            bag.error(f"{obj.name} has no field '{e.field}'", e.span)
        elif isinstance(bare, TCard) and e.field not in env.item_fields:
            # The content item's fields are a closed pair — an unknown one (a
            # card axis on a piece, or vice versa) would read as `TAny` and only
            # fail (or worse, not fail) at play time. Noun and fields are
            # flavor-keyed; a card game reproduces the CARD_FIELDS message.
            noun = content_noun(env.flavor, plural=False).capitalize()
            field_list = " and ".join(f"`{f}`" for f in sorted(env.item_fields))
            bag.error(
                f"{noun} has no field '{e.field}' (its fields are {field_list})",
                e.span,
            )
        elif isinstance(bare, TCollection):
            # A zone-family subscript (`hand[p]`) is typed as the zone's
            # content collection rather than a single Card, so a dot-form
            # access on it (`hand[p].rank`) needs its own Owner Guard — without it
            # this would silently read as TAny and only fail at play time,
            # where field access is not defined over a zone's contents.
            bag.error(
                "a collection has no fields — aggregate over it ('sum of … "
                "over cards in …') or take a specific card",
                e.span,
            )
        elif isinstance(bare, _INDEXABLE_RECEIVERS):
            # The dot form is object-member access only (Card, Move, and
            # struct fields). Zone/state indexing is the bracket form, and
            # relational chains derive through functions and state
            # (decisions.md "Typed object model", access discipline).
            bag.error(
                f"cannot read field '{e.field}' of {_type_name(obj)}: the dot "
                f"form is object-member access only — index with brackets "
                f"('{e.field}[...]') instead",
                e.span,
            )
        elif isinstance(bare, _FIELDLESS_RECEIVERS):
            # The fieldless value types: a position (TCell), a movement
            # direction (TDir), a line/region (TLine), an enum value, a string,
            # none, or an outcome. None has user-accessible fields, so a
            # dot form on one would otherwise reach no arm and infer TAny with
            # no diagnostic -- the permissive-top gap a `cell`/`dir` binder or a
            # movement verb's TCell return could slip through. The whole
            # fieldless class has its Owner Guard here, at the layer that owns operand
            # kinds, not per producer (decisions.md "Closed-domain
            # completeness"). TNull and TOutcome are classified rather than
            # probed: `none` is a comparison-only operand and no `infer` arm
            # returns a outcome (it is a registry entry for `produce` /
            # `produces:` checking), so neither is reachable from a receiver
            # position today -- they are rejected ahead of the reach, so a later
            # arm that does return one cannot reopen the gap.
            bag.error(
                f"cannot read field '{e.field}' of {_type_name(obj)}: the dot "
                f"form is object-member access only (Card, Move, and struct "
                f"fields) — a {_type_name(obj)} has no fields",
                e.span,
            )
    elif isinstance(e, n.BinOp):
        _check_binop(e, env, bag)
    elif isinstance(e, n.IsCheck):
        _check_is_check(e, env, bag)


def _check_struct_lit(e: n.StructLit, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Validate a struct literal against its declared type: every declared
    (non-derived) field is provided exactly once, no unknown fields, and each
    field value is assignable to the field's declared type."""
    struct = env.structs.get(e.type_name)
    if struct is None:
        return  # unknown type: flagged by resolve (`_validate_refs`)
    declared = {k for k in struct.fields if k not in struct.derived}
    provided = {fi.name for fi in e.fields}
    for missing in sorted(declared - provided):
        bag.error(f"{e.type_name} {{}} is missing field '{missing}'", e.span)
    for extra in sorted(provided - declared):
        if extra in struct.derived:
            bag.error(f"{e.type_name} {{}} cannot supply derived field '{extra}'", e.span)
        else:
            bag.error(f"{e.type_name} {{}} has unknown field '{extra}'", e.span)
    for fi in e.fields:
        expected = struct.fields.get(fi.name)
        if expected is None or fi.name in struct.derived:
            continue
        got = infer(fi.value, env)
        _check_operand(
            fi.value, got, expected, env, bag,
            f"field '{fi.name}' expects {_type_name(expected)}, "
            f"got {_type_name(got)}",
            e.span,
        )


def _check_bool(e: n.Expr, env: TypeEnv, bag: DiagnosticBag, where: str) -> None:
    t = infer(e, env)
    if not isinstance(t, (TBoolean, TAny)):
        bag.error(f"{where} must be Boolean, got {_type_name(t)}", e.span)


def _stmt_exprs(s: n.Stmt) -> list[n.Expr]:
    """The expressions held directly by a statement (its child *statements* are
    visited separately by the statement walk). Exhaustive over `Stmt`: a kind
    missed here has its expressions silently skipped by every check downstream
    of the walk, so "holds no expressions" is stated per kind, not defaulted."""
    match s:
        case n.AssignStmt():
            # `s.target` is deliberately absent: a write target is validated by
            # resolve (`_bad_write_target`) and typed by `_check_assign`, not
            # walked as a value read.
            return [s.value] + ([s.index] if s.index is not None else [])
        case n.LetStmt():
            return [s.value]
        case n.Transfer():
            out: list[n.Expr] = []
            if not isinstance(s.amount, str):
                out.append(s.amount)
            for opt in (s.source, s.dest, s.visibility, s.where):
                if opt is not None:
                    out.append(opt)
            return out
        case n.EpistemicOp():
            return [s.zone] if s.where is None else [s.zone, s.where]
        case n.Offer():
            return [s.player]
        case n.TrickRound():
            exprs = [s.leader, s.participants]
            if s.trump is not None:  # the form's one optional expression clause
                exprs.append(s.trump)
            return exprs
        case n.AuctionRound() | n.ClimbRound():
            return [s.leader, s.participants, s.until]
        case n.IfStmt():
            return [s.cond]
        case n.RepeatUntil():
            return [s.until]
        case n.AsBlock():
            return [s.player]
        case n.Turns():
            # `again` is a state-var NAME (a string, validated by resolve),
            # not an expression — only the three expr positions walk here.
            return [s.leader, s.participants, s.until]
        case n.Produce():
            return list(s.payloads)
        case n.RunStmt():
            return list(s.args)
        case n.ForEach() | n.EachSimultaneous() | n.RotateStmt():
            # ForEach/EachSimultaneous hold a role name and a binder (strings,
            # not expressions); RotateStmt's target is a write target, validated
            # by resolve like AssignStmt's.
            return []
        case n.Produces() | n.ContinueTo() | n.SkipToNextHand() | n.Block():
            # Produces holds statements only (its arms' bodies are walked by
            # `_check_produces` with the arm binders in scope); the control-flow
            # pair hold a phase name / nothing; Block holds child statements.
            return []
        case _:
            assert_never(s)


def _check_stmt_exprs(s: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Check every expression `_stmt_exprs` holds directly, binding an
    implicit name where the construct's own runtime semantics require one.

    `Transfer.where` and `EpistemicOp.where` are evaluated with `card`
    bound per candidate (runtime/execute.py's shared `_card_pred`:
    `ctx.with_local("card", c)`, used by both the movement selection and
    `reveal`) — the *only* two `_stmt_exprs` members whose
    predicate binds an implicit name (every other branch — AssignStmt,
    LetStmt, Offer, Round, IfStmt/RepeatUntil, Produce — holds plain value
    expressions in the ambient environment, no binder). Without this, both
    filters would run through the flat, unbound `env`, so `card.<field>` inside
    a `deal`/`move`/`reveal` filter would type as `TAny` (Member on an untyped
    `card` local) and every Card Owner Guard — the closed CARD_FIELDS pair among
    them — would be dark there. The filter must also itself be Boolean; the
    other direct expressions on these two node kinds (source/dest/amount/
    visibility, target) carry no binder and stay in the ambient `env`."""
    if isinstance(s, (n.Transfer, n.EpistemicOp)) and s.where is not None:
        # A joint filter (`where jointly`) binds `cards` — the candidate SET,
        # a card collection — where a per-card filter binds each `card`
        # (runtime `_select_joint` vs `_card_pred`; decisions.md
        # "Joint-predicate selection").
        if isinstance(s, n.Transfer) and s.joint:
            scoped = env.with_local(content_noun(env.flavor, plural=True), TCollection(TCard()))
        else:
            scoped = env.with_local(content_noun(env.flavor, plural=False), TCard())
        _check_expr(s.where, scoped, bag)
        verb = s.verb if isinstance(s, n.Transfer) else s.op
        _check_bool(s.where, scoped, bag, f"'{verb}' filter")
        for expr in _stmt_exprs(s):
            if expr is not s.where:
                _check_expr(expr, env, bag)
        return
    if isinstance(s, n.LetStmt) and s.index is not None:
        # The indexed form's key binder (`let base[p] = E`) is bound to each
        # player inside E only — check E in that scope, the same binding
        # `_scoped_env` uses to type `base` and the runtime `_let` uses to
        # evaluate it.
        _check_expr(s.value, env.with_local(s.index, TPlayer()), bag)
        return
    if isinstance(s, n.RunStmt):
        # Arity and argument types against the declared parameters — the same
        # check a `Call` gets against a function signature, and the only place a
        # procedure's parameter annotations can bite (after expansion, the call
        # site is gone). Resolve has already established that the procedure exists.
        sig = env.procedures.get(s.name)
        if sig is None:
            # Not `if sig is not None:`. The comment above states the
            # invariant — resolve has established that the procedure exists,
            # and `_procedure_sigs` builds one entry per declared procedure —
            # so a miss is a divergence between the two, exactly like the name
            # lookups in `_name_type`. Guarding leniently on an invariant you
            # have just asserted is how the check goes dark: an env built
            # without procedures silently skipped this arity and argument-type
            # Owner Guard rather than failing, and it is the ONLY place a procedure's
            # parameter annotations bite (after expansion the call site is
            # gone). See decisions.md, "`Any` means the top,
            # never a failed lookup" — a fallback standing in for an answer the program has is
            # a silent wrong answer.
            raise _env_miss(
                "procedure", s.name, "procedures", "`_procedure_sigs`"
            )
        if len(s.args) != len(sig.params):
            bag.error(
                f"procedure '{s.name}' expects {len(sig.params)} argument(s), "
                f"got {len(s.args)}",
                s.span,
            )
        else:
            for arg, param in zip(s.args, sig.params):
                got = infer(arg, env)
                # Procedure expansion runs AFTER typechecking, so an out-of-range
                # seat literal in a Player param becomes an unchecked
                # `score[5] := 1` in the spliced body -- the same coercion the
                # call-arg and subscript sites check, reached one construct later.
                _check_operand(
                    arg, got, param, env, bag,
                    f"procedure '{s.name}' expects {_type_name(param)}, got "
                    f"{_type_name(got)}",
                    arg.span,
                )
    for expr in _stmt_exprs(s):
        _check_expr(expr, env, bag)


def _all_phases(game: Game) -> Iterator[n.Phase]:
    def rec(phase: n.Phase) -> Iterator[n.Phase]:
        yield phase
        for item in phase.items:
            if isinstance(item, n.Phase):
                yield from rec(item)

    for phase in game.phases:
        yield from rec(phase)


def _check_assign(stmt: n.AssignStmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    name = stmt.target.name
    target = env.state_vars.get(name)
    if target is None:
        # Resolve guarantees a write target classifies as a state variable — a binder,
        # a zone and an unknown name are all rejected there — so this is unreachable
        # for a checked game.
        return
    if stmt.index is not None and isinstance(target, TCollection):
        if target.key is not None:
            # The write twin of the subscript key check: `n[hearts] := 1` on a
            # player-keyed store is a check-time error here; the runtime's
            # domain Owner Guard (execute._assign) stays behind it for computed keys.
            idx_t = infer(stmt.index, env)
            _check_operand(
                stmt.index, idx_t, target.key, env, bag,
                f"`{name}` is keyed by {_type_name(target.key)} — got "
                f"{_type_name(idx_t)}",
                stmt.span,
            )
        target = target.element  # an indexed assignment writes one element
    rhs = infer(stmt.value, env)
    if stmt.op in ("+=", "-="):
        _check_operand(
            stmt.value, rhs, TInteger(), env, bag,
            f"'{name}' {stmt.op} expects an Integer, got {_type_name(rhs)}",
            stmt.span,
        )
    else:
        _check_operand(
            stmt.value, rhs, target, env, bag,
            f"cannot assign {_type_name(rhs)} to '{name}' ({_type_name(target)})",
            stmt.span,
        )


def _check_state_default_type(
    decl: n.StateDecl, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """A state variable's default must be assignable to its declared type. The
    twin of `_check_assign` for the initial value: `env_from_game` reads the
    declared `type_name` for later reads but never checks the default against
    it, so `v : Integer = "s"` typed the variable Integer and ignored the
    String default.

    Compared against `type_from_name` — the VALUE type, not the collection an
    indexed var is stored in — because an indexed default (`score[player] = 0`)
    broadcasts one value to every key, so it is the element type it must fit.
    As sharp as `infer` and no sharper: a default whose inferred type is `TAny`
    (an unrefined `infer` arm) passes, which is the type system's permissive top
    at work, not a hole here (see the ledger in
    `tests/test_state_default_type.py`)."""
    declared = type_from_name(decl.type_name, decl.optional, env.structs)
    got = infer(decl.default, env)
    _check_operand(
        decl.default, got, declared, env, bag,
        f"state variable '{decl.name}' is declared {_type_name(declared)}, "
        f"but its default has type {_type_name(got)}",
        decl.span,
    )


def _check_stmt_semantics(stmt: n.Stmt, env: TypeEnv, bag: DiagnosticBag) -> None:
    """The non-expression checks a statement carries: assignment compatibility,
    Boolean conditions, and movement-combination validity. Used by the flat walk
    and the scoped produces walk.

    Exhaustive over `Stmt` so that "this kind needs no semantic check" is a
    recorded decision per kind. A silent default here is how a new statement
    ships with its expressions typed but its own rules unenforced."""
    match stmt:
        case n.AssignStmt():
            _check_assign(stmt, env, bag)
        case n.IfStmt():
            _check_bool(stmt.cond, env, bag, "if condition")
        case n.RepeatUntil():
            _check_bool(stmt.until, env, bag, "repeat-until condition")
        case n.TrickRound():
            _check_round_actors(stmt, env, bag)
            _check_round_ranking(stmt, env, bag)
            _check_round_trump(stmt, env, bag)
        case n.AuctionRound() | n.ClimbRound():
            # `until` is mandatory on exactly the two forms that loop, so it is
            # checked without asking whether it is there — which is the split's
            # point: the form that has no termination predicate cannot reach here.
            _check_round_actors(stmt, env, bag)
            _check_round_ranking(stmt, env, bag)
            _check_bool(stmt.until, env, bag, "round `until` condition")
        case n.Transfer():
            _check_transfer(stmt, env, bag)
        case n.EpistemicOp():
            # The type half of the zone-target rule, like `_check_transfer`'s
            # endpoints: a `local` root passes resolve's classification, and
            # the binder's inferred type decides here.
            t = infer(stmt.zone, env)
            if not _is_zone_type(t):
                bag.error(
                    f"'{stmt.op}' target must be a zone, got "
                    f"{_type_name(t)}{_zone_hint(t, filterable=False)}",
                    stmt.span,
                )
        case n.AsBlock():
            # The block binds the acting player to one player, so its expression
            # must BE a player. Integer stands for player (`coercible`), like
            # `dealer : Player = 0` and a zone-family index.
            t = infer(stmt.player, env)
            _check_operand(
                stmt.player, t, TPlayer(), env, bag,
                f"`as` binds one player — its expression must be a Player, "
                f"got {_type_name(t)}",
                stmt.span,
            )
        case n.Turns():
            # The form's three expression positions carry its contract: `from`
            # is the first player, `over` the participants (a player
            # collection, re-evaluated per advance), `until` the turn-boundary
            # termination. `again`, when present, is a declared Boolean state
            # var (resolve checks the declaration; the TYPE is checked here).
            lt = infer(stmt.leader, env)
            _check_operand(
                stmt.leader, lt, TPlayer(), env, bag,
                f"`turns … from` names the first player — expected a "
                f"Player, got {_type_name(lt)}",
                stmt.span,
            )
            _check_participants(
                stmt.participants, env, bag,
                "`turns … over` names the participants",
                stmt.span,
            )
            _check_bool(stmt.until, env, bag, "turns `until` condition")
            if stmt.again is not None:
                at = env.state_vars.get(stmt.again)
                # choke-point-exempt: `again` is a state-var NAME resolved to a
                # type, not an operand expression — a name->declared-type check,
                # Boolean-expected, with no literal to range.
                if at is not None and not coercible(at, TBoolean()):  # choke-point-exempt
                    bag.error(
                        f"`again {stmt.again}`: the go-again flag must be "
                        f"Boolean, got {_type_name(at)}",
                        stmt.span,
                    )
        case n.Offer():
            # `offer to <player>` names the acting player. Before the operand
            # choke point this carried NO player check at all -- `offer to 5` and
            # even `offer to "x"` passed -- so it both types and ranges here now.
            pl = infer(stmt.player, env)
            _check_operand(
                stmt.player, pl, TPlayer(), env, bag,
                f"`offer to` names the acting player — expected a Player, "
                f"got {_type_name(pl)}",
                stmt.span,
            )
        case (
            n.RotateStmt() | n.EachSimultaneous() | n.ForEach()
            | n.LetStmt() | n.Produce() | n.Produces()
            | n.ContinueTo() | n.SkipToNextHand() | n.RunStmt() | n.Block()
        ):
            # No statement-level semantics beyond what resolve checks (write
            # targets, rotate enum values, simultaneous bodies, run arity is
            # `_check_stmt_exprs`'s RunStmt arm) and the expression walk covers.
            pass
        case _:
            assert_never(stmt)


def _is_zone_type(t: Type) -> bool:
    """Whether a value of this type IS a zone at runtime: the `zone` marker
    (`ZONE_CONTENT`, a zone-family subscript), or TAny (a deliberately-loose
    value the runtime Owner Guard owns). The marker matters twice over: `all
    players` is a collection of the wrong element, and a card QUERY is a
    collection of the RIGHT element that still evaluates to a plain list —
    only the marker separates `hand[0]` from `cards in hand[0] where …`."""
    if isinstance(t, TAny):
        return True
    return isinstance(t, TCollection) and t.zone


def _zone_hint(t: Type, filterable: bool) -> str:
    """A computed card collection fails the zone check with the RIGHT element,
    which reads as a contradiction without this: say why it is still not a
    zone, and what to write instead. The `where`-filter suggestion is offered
    only where the grammar can actually take one (`filterable` — a movement's
    FROM position); destinations, the gather form, and epistemic targets have
    no filter slot, and a hint naming unwritable syntax is worse than none."""
    if isinstance(t, TCollection) and isinstance(t.element, TCard) and not t.zone:
        fix = (
            "name the zone itself, or narrow the movement with a `where` filter"
            if filterable
            else "name the zone itself"
        )
        return f" (a computed card collection — a query result or list — is not a zone; {fix})"
    return ""


def _check_transfer(stmt: n.Transfer, env: TypeEnv, bag: DiagnosticBag) -> None:
    """Combination validity for the movement production (decisions.md, "Surface
    totality"): every combination the grammar accepts is either implemented by
    the executor or rejected here with a clear message — a clause the runtime
    would silently ignore must not reach it."""
    # The TYPE half of the endpoint rule. Resolve rejects an endpoint whose
    # root CLASSIFIES as a non-zone (a state var, a deck value); a `local`
    # root passes classification because a binder may hold a zone — and because
    # lets are typed, the type says whether this one does. A zone value
    # types as a CARD collection (ZONE_CONTENT), and the element matters:
    # `let z = all players` is a collection too, and waving it through on the
    # container shape alone would send it to the runtime's Owner Guard with a
    # message claiming the checker couldn't know — when it knows
    # Collection<Player> exactly.
    for endpoint, what, filterable in (
        # Only the from-position takes a `where` filter; the in-form's zone
        # parses into `source` but has no dest, hence no filter slot either.
        (stmt.source, "source", stmt.dest is not None),
        (stmt.dest, "destination", False),
    ):
        if endpoint is None:
            continue
        t = infer(endpoint, env)
        if not _is_zone_type(t):
            bag.error(
                f"movement {what} must be a zone, got "
                f"{_type_name(t)}{_zone_hint(t, filterable)}",
                stmt.span,
            )
    own = (content_noun(env.flavor, plural=False), content_noun(env.flavor, plural=True))
    other_flavor: Flavor = "card" if env.flavor == "piece" else "piece"
    other = (content_noun(other_flavor, plural=False), content_noun(other_flavor, plural=True))
    if stmt.item in other:
        # The other flavor's content noun: name the kind and the right spelling.
        bag.error(
            f"{content_kind_clause(env.flavor, env.deck)} -- move its {own[1]} "
            f"(`move ... {own[1]} ...`), not '{stmt.item}'",
            stmt.span,
        )
    elif stmt.item not in own:
        # A truly unknown noun (`chips`, `coins`): the deferred-resource Owner Guard,
        # unchanged (card games are byte-identical -- own is card/cards there).
        bag.error(
            f"movements move cards; '{stmt.item}' is not a supported item noun "
            "(resource movements are deferred — roadmap.md)",
            stmt.span,
        )
    if stmt.source is not None and stmt.dest is None:
        bag.error(
            f"the `{stmt.verb} ... in <zone>` form is not yet supported by the "
            "runtime (roadmap.md); name the destination with `to <zone>`",
            stmt.span,
        )
    if stmt.visibility is not None:
        bag.error(
            "per-movement visibility overrides are not yet honored by the "
            "runtime — visibility derives from the declared zone types "
            "(roadmap.md)",
            stmt.span,
        )
    if stmt.source is None and stmt.dest is not None:  # a gather
        if stmt.amount != "all" or stmt.selection_mode is not None:
            bag.error(
                "a gather (`move ... to <zone>` with no `from`) collects every "
                "card: write `move all cards to <zone>`",
                stmt.span,
            )
        if stmt.dest_each:
            bag.error(
                "a gather collects into one zone; `to each` is not supported — "
                "gather to a single zone, then deal from it",
                stmt.span,
            )
    if stmt.distribution is not None:
        if not stmt.dest_each:
            bag.error(
                "`as-equally-as-possible` distributes a `to each` deal; it has "
                "no meaning with a single destination",
                stmt.span,
            )
        if stmt.amount != "all":
            bag.error(
                "an `as-equally-as-possible` deal distributes the whole source "
                "(or the whole `where` pool): the amount must be `all`",
                stmt.span,
            )
        if stmt.selection_mode is not None:
            bag.error(
                f"`as-equally-as-possible` deals round-robin; a `{stmt.selection_mode}` "
                "selection cannot combine with it",
                stmt.span,
            )
    elif stmt.dest_each and stmt.amount == "all":
        bag.error(
            "`deal all ... to each` would give the whole source to the first "
            "player; use `as-equally-as-possible` to distribute it",
            stmt.span,
        )


def _check_produce_stmt(
    sub: n.Produce, outcome: TOutcome, owner: str, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """One `produce` names a declared outcome and supplies payloads of the
    declared arity and types."""
    if sub.tag not in outcome.cases:
        bag.error(f"{owner} produces unknown outcome case '{sub.tag}'", sub.span)
        return
    payload_types = outcome.cases[sub.tag]
    if len(sub.payloads) != len(payload_types):
        bag.error(
            f"outcome case '{sub.tag}' takes {len(payload_types)} payload(s), "
            f"got {len(sub.payloads)}",
            sub.span,
        )
        return
    for expr, expected in zip(sub.payloads, payload_types):
        got = infer(expr, env)
        _check_operand(
            expr, got, expected, env, bag,
            f"outcome case '{sub.tag}' expects {_type_name(expected)}, "
            f"got {_type_name(got)}",
            sub.span,
        )


def _check_define_outcomes(
    define: n.DefineDef, outcome: TOutcome, env: TypeEnv, bag: DiagnosticBag
) -> None:
    """Every `produce` in a define's body names a declared outcome and supplies
    payloads of the declared arity and types — checked in the SCOPED
    environment, so a payload routed through a `let` types like its inline
    twin (without it, `let z = hearts / produce Won(z)` would pass a `Player`
    payload the inline spelling had just been rejected for)."""
    for sub, binders in _seq_tree_scoped(define.body, ()):
        if isinstance(sub, n.Produce):
            _check_produce_stmt(
                sub, outcome, f"define '{define.name}'", _scoped_env(env, binders), bag
            )


def _check_misplaced_produce(
    game: Game, outcomes: Mapping[str, TOutcome], env: TypeEnv, bag: DiagnosticBag
) -> None:
    """`produce` is legal only inside a `define` body (checked elsewhere) or the
    body of an outcome-declaring phase. Flag it anywhere else, and type-check the
    legal phase produces against the enclosing phase's outcome."""
    for move_type in game.move_types:
        for s in move_type.effect:
            for sub in _stmt_tree(s):
                if isinstance(sub, n.Produce):
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
    for phase in game.phases:
        _check_phase_produces(phase, None, outcomes, env, bag)


def _produces_in(stmt: n.Stmt) -> Iterator[n.Produces]:
    """Every `produces:` consumer reachable from a root statement, descending into
    if/repeat/for-each bodies and (unlike `_stmt_tree`) into `produces:` arm bodies
    too — so a consumer nested in an arm is still validated. Call on root
    statements only (it walks if/repeat itself, so feeding it pre-flattened
    statements would double-count)."""
    for sub in _stmt_tree(stmt):
        if isinstance(sub, n.Produces):
            yield sub
            for arm in sub.arms:
                for s in arm.body:
                    yield from _produces_in(s)


def _continue_targets_in_item(item: n.PhaseItem) -> set[str]:
    """Every `continue to` target reachable while executing one phase-body item,
    recursing into nested phases (a jump there can unwind to this body) and
    statement bodies. Hooks/config carry none (control flow in hooks is rejected)."""
    targets: set[str] = set()
    if isinstance(item, n.Phase):
        for sub in item.items:
            targets |= _continue_targets_in_item(sub)
        # A jump to one of this phase's own children is caught by its own
        # `run_body` and never unwinds to the parent, so it doesn't escape.
        targets -= {it.name for it in item.items if isinstance(it, n.Phase)}
    elif isinstance(
        item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.Mode,
               n.BeforeEach, n.AfterEach)
    ):
        pass
    else:
        for node in _control_flow_nodes(item):
            if isinstance(node, n.ContinueTo):
                targets.add(node.phase)
    return targets


def _item_can_skip(item: n.PhaseItem) -> bool:
    """Whether executing one phase-body item can `skip to next hand` against *this*
    body's hand loop. A nested `repeat until` catches its own skips, so they don't
    unwind here."""
    if isinstance(item, n.Phase):
        if item.qualifier is not None and item.qualifier.kind == "repeat_until":
            return False
        return any(_item_can_skip(sub) for sub in item.items)
    if isinstance(
        item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.Mode,
               n.BeforeEach, n.AfterEach)
    ):
        return False
    return any(isinstance(node, n.SkipToNextHand) for node in _control_flow_nodes(item))


def _mode_names(game: Game) -> set[str]:
    """Every mode declared anywhere in the game, for kind-aware diagnostics.

    Game-wide, not per phase, because that is the scope mode names are unique
    over (`resolve._check_duplicate_names`). Scoping the lookup to the phase
    holding the jump answered only when the mode happened to live there, and
    the two cases it missed — a mode of a different phase, and one of a nested
    phase — are exactly the confusion the diagnostic exists to clear up: a
    designer told the name is "not a sibling phase" while looking straight at
    its declaration."""
    out: set[str] = set()

    def walk(items: tuple[n.PhaseItem, ...]) -> None:
        for item in items:
            if isinstance(item, n.Mode):
                out.add(item.name)
            elif isinstance(item, n.Phase):
                walk(item.items)

    for phase in game.phases:
        walk(phase.items)
    return out


def _control_flow_nodes(stmt: n.Stmt) -> Iterator[n.Stmt]:
    """Yield ContinueTo/SkipToNextHand within a statement, descending through
    if/repeat/for-each, `produces:` arm bodies, and blocks. Exhaustive over
    `Stmt`: a compound kind missed here hides its jumps from `_check_outcome_
    scope`, which then under-reports skippable producers — a wrong info-set-
    adjacent conclusion, not just a missed diagnostic."""
    match stmt:
        case n.ContinueTo() | n.SkipToNextHand():
            yield stmt
        case n.Produces():
            for arm in stmt.arms:
                for s in arm.body:
                    yield from _control_flow_nodes(s)
        case n.ForEach() | n.EachSimultaneous():
            yield from _control_flow_nodes(stmt.body)
        case n.RepeatUntil():
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case n.IfStmt():
            for s in stmt.then_body:
                yield from _control_flow_nodes(s)
            for s in stmt.else_body or ():
                yield from _control_flow_nodes(s)
        case n.AsBlock():
            # Transparent to control flow, like `IfStmt`/`Block`: a jump written
            # inside `as <p> { … }` unwinds past the actor rebind exactly as it
            # would inline.
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case n.Turns():
            # Transparent like the other compound statements: a jump inside a
            # turn body unwinds out of the loop to the enclosing construct.
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case n.Block():
            # A block is transparent to control flow: a jump written in a
            # procedure body unwinds exactly as it would inline. Unreachable
            # today (resolve rejects non-local control flow in procedure bodies,
            # and expansion runs after this pass) — but "unreachable today" is
            # what silent defaults always say right before they bite.
            for s in stmt.body:
                yield from _control_flow_nodes(s)
        case (
            n.Transfer() | n.EpistemicOp() | n.RotateStmt() | n.LetStmt()
            | n.AssignStmt() | n.Offer() | n.TrickRound() | n.AuctionRound()
            | n.ClimbRound() | n.Produce() | n.RunStmt()
        ):
            pass  # no jumps, no child statements to hold any
        case _:
            assert_never(stmt)


def _check_single_outcome_consumer(game: Game, bag: DiagnosticBag) -> None:
    """A phase produces one outcome and the runtime `pop`s it on the first
    consumer, so an outcome phase may have at most one `produces:` block (a second
    would deterministically find nothing). Defines, re-invoked per consumer, are
    unrestricted."""
    outcome_phases = {p.name for p in _all_phases(game) if p.outcome_cases}
    seen: set[str] = set()
    for stmt in _all_statements(game):
        # `_all_statements` is pre-flattened, so only expand the Produces roots
        # (each into itself + any arm-nested consumers) to avoid double-counting.
        if not isinstance(stmt, n.Produces):
            continue
        for sub in _produces_in(stmt):
            if sub.define not in outcome_phases:
                continue
            if sub.define in seen:
                bag.error(
                    f"phase outcome '{sub.define}' is consumed by more than one "
                    "produces: block",
                    sub.span,
                )
            seen.add(sub.define)


def _check_outcome_name_collisions(game: Game, bag: DiagnosticBag) -> None:
    """Outcome phases dispatch by name through one shared registry / runtime dict,
    so an outcome-phase name must be unique and must not collide with a `define`
    (either would silently shadow the other in a `produces:` consumer)."""
    define_names = {d.name for d in game.defines}
    seen: set[str] = set()
    for phase in _all_phases(game):
        if not phase.outcome_cases:
            continue
        if phase.name in define_names:
            bag.error(
                f"outcome phase '{phase.name}' collides with a define of the same "
                "name",
                phase.span,
            )
        if phase.name in seen:
            bag.error(
                f"duplicate outcome phase name '{phase.name}'", phase.span
            )
        seen.add(phase.name)


def _check_outcome_scope(game: Game, bag: DiagnosticBag) -> None:
    """The phase-outcome constructs resolve only within sibling scope, matching the
    runtime (which dispatches by name against phases that ran / sit in an enclosing
    body):

    - a `produces:` consumer naming an outcome phase needs that phase to be an
      *earlier-executed* sibling (in this body or an enclosing one), so the
      producer ran first in the same pass;
    - `continue to <phase>` resolves to a *later* sibling in this or an enclosing
      body (it is forward-only and unwinds outward to a body that holds the target);
    - `skip to next hand` sits inside a phase-level `repeat until` hand loop (a
      statement-level trick `repeat until` does not count).

    `before`/`after` carry the sibling phase names that execute before/after the
    current point, accumulated down the ancestor chain."""
    mode_names = _mode_names(game)
    define_names = {d.name for d in game.defines}
    outcome_phases = {p.name for p in _all_phases(game) if p.outcome_cases}

    def check_produces_scope(stmt: n.Stmt, avail: set[str]) -> None:
        """Validate a `produces:` consumer (and any nested in arms/blocks) against
        the available producers. A statement-level `repeat until` reruns, but phase
        producers run once, so none are available inside its body."""
        if isinstance(stmt, n.Produces):
            if (
                stmt.define not in define_names
                and stmt.define in outcome_phases
                and stmt.define not in avail
            ):
                bag.error(
                    f"produces names phase '{stmt.define}', which is not an earlier "
                    "sibling that has run",
                    stmt.span,
                )
            for arm in stmt.arms:
                for s in arm.body:
                    check_produces_scope(s, avail)  # the arm runs at this position
        elif isinstance(stmt, (n.RepeatUntil, n.ForEach, n.EachSimultaneous, n.Turns)):
            # Any statement-level loop reruns its body; a run-once phase producer
            # is gone after the first iteration, so none are available inside.
            bodies = (
                stmt.body
                if isinstance(stmt, (n.RepeatUntil, n.Turns))
                else (stmt.body,)
            )
            for s in bodies:
                check_produces_scope(s, set())
        elif isinstance(stmt, n.IfStmt):
            for s in stmt.then_body:
                check_produces_scope(s, avail)
            for s in stmt.else_body or ():
                check_produces_scope(s, avail)
        elif isinstance(stmt, n.AsBlock):
            # Runs once at this position (not a loop), like `IfStmt` — producers
            # available here stay available inside the block.
            for s in stmt.body:
                check_produces_scope(s, avail)

    def walk(
        phase: n.Phase,
        before_outcomes: set[str],
        after_phases: set[str],
        in_hand_loop: bool,
    ) -> None:
        here_loop = in_hand_loop or (
            phase.qualifier is not None and phase.qualifier.kind == "repeat_until"
        )
        items = phase.items
        # All child phases are valid `continue to` targets; only *unqualified*
        # outcome phases are reliable `produces:` producers — a `when`/`repeats`
        # phase may not run (or produce), so a consumer can't depend on it.
        child_at = {
            idx: it.name for idx, it in enumerate(items) if isinstance(it, n.Phase)
        }
        child_outcome_at = {
            idx: it.name
            for idx, it in enumerate(items)
            if isinstance(it, n.Phase) and it.outcome_cases and it.qualifier is None
        }
        # A `continue to T` at position j jumps over items (j, k) where k is T's
        # index (or the body's end if T is an outer phase). A producer in that gap
        # may be skipped, so it is not reliably available to any later consumer.
        child_idx_by_name = {name: idx for idx, name in child_at.items()}
        skippable: set[str] = set()
        for j, it in enumerate(items):
            for target in _continue_targets_in_item(it):
                # A target outside this body unwinds past it, skipping the rest.
                k = child_idx_by_name.get(target, len(items))
                for i, nm in child_outcome_at.items():
                    if j < i < k:
                        skippable.add(nm)
        # A `skip to next hand` aborts the body from its position on, but after_each
        # still runs — so producers at or after the first possible skip aren't
        # available to after_each.
        first_skip = next(
            (j for j, it in enumerate(items) if _item_can_skip(it)), len(items)
        )
        for idx, item in enumerate(items):
            earlier = (
                before_outcomes
                | {nm for j, nm in child_outcome_at.items() if j < idx}
            ) - skippable
            later = after_phases | {nm for j, nm in child_at.items() if j > idx}
            if isinstance(item, n.Phase):
                # A consumer inside a `repeat until` body can only rely on a
                # producer that reruns each pass — i.e. one inside the same loop —
                # so outer producers don't carry in (continue-to targets still do).
                child_before = (
                    set()
                    if item.qualifier is not None and item.qualifier.kind == "repeat_until"
                    else earlier
                )
                walk(item, child_before, later, here_loop)
            elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.Mode)):
                pass
            else:
                in_hook = isinstance(item, (n.BeforeEach, n.AfterEach))
                # Inline isinstance (not the `in_hook` flag) so mypy narrows the
                # `(item,)` branch to a Stmt.
                stmts = (
                    item.body
                    if isinstance(item, (n.BeforeEach, n.AfterEach))
                    else (item,)
                )
                # Hooks run by timing, not lexical position: before_each runs
                # before the whole body (no producer has run), after_each after it
                # (all body producers have).
                if isinstance(item, n.BeforeEach):
                    # Runs before the body: only ancestor producers have run (and
                    # `before_outcomes` is already empty inside a repeats loop).
                    avail = before_outcomes
                elif isinstance(item, n.AfterEach):
                    # Runs after the body: ancestor producers plus this body's own
                    # producers that are reached before any skip.
                    avail = before_outcomes | (
                        {nm for i, nm in child_outcome_at.items() if i < first_skip}
                        - skippable
                    )
                else:
                    avail = earlier
                for s in stmts:
                    for node in _control_flow_nodes(s):
                        if in_hook:
                            # `run_phase` only catches `_SkipHand`/`_ContinueTo`
                            # around the phase body, not the hooks — a skip from a
                            # hook would abort the whole run, not the hand.
                            bag.error(
                                "'continue to' / 'skip to next hand' is not allowed "
                                "in a before_each/after_each hook",
                                node.span,
                            )
                        elif isinstance(node, n.ContinueTo) and node.phase not in later:
                            # A mode name reaching here is the phase/mode
                            # confusion itself: before modes had their own
                            # keyword, `continue to <config-only sub-phase>`
                            # was accepted and jumped to an item the driver
                            # skips. Say which kind the name is, or the
                            # designer reads "not a sibling" as "no such name"
                            # while looking straight at the declaration.
                            if node.phase in mode_names:
                                bag.error(
                                    f"continue to '{node.phase}' names a mode, not a "
                                    f"phase — a mode is entered by a sibling mode's "
                                    f"`transition_to:` when its event fires, never "
                                    f"jumped to",
                                    node.span,
                                )
                            else:
                                bag.error(
                                    f"continue to '{node.phase}' is not a later sibling "
                                    "phase",
                                    node.span,
                                )
                        elif isinstance(node, n.SkipToNextHand) and not here_loop:
                            bag.error(
                                "'skip to next hand' must be inside a `repeat until` "
                                "hand loop",
                                node.span,
                            )
                    check_produces_scope(s, avail)

    # Top-level phases are siblings of each other (they run in sequence), so a
    # `produces:` consumer in a later top-level phase can name an earlier one
    # (hence `before`). But `after` stays empty: `play_game` iterates top-level
    # phases with a plain loop (no enclosing `run_body`), so a `continue to`
    # targeting a *later top-level* phase has nowhere to be caught and must be
    # rejected — only later phases within a `run_body` are valid jump targets.
    top_outcome_at = {
        idx: p.name
        for idx, p in enumerate(game.phases)
        if p.outcome_cases and p.qualifier is None
    }
    for idx, phase in enumerate(game.phases):
        # Same rule as the recursion: a top-level `repeat until` body can't rely
        # on an earlier top-level producer (it ran once, the loop reruns).
        is_repeat = phase.qualifier is not None and phase.qualifier.kind == "repeat_until"
        before = (
            set()
            if is_repeat
            else {nm for j, nm in top_outcome_at.items() if j < idx}
        )
        walk(phase, before, set(), False)

    # `continue to` / `skip to next hand` are phase control flow. Outside a phase
    # body — in a define or move-type body — they would unwind out of
    # `play_game` uncaught, so reject them there.
    non_phase_bodies = (
        [d.body for d in game.defines]
        + [m.effect for m in game.move_types]
    )
    for body in non_phase_bodies:
        for s in body:
            for node in _control_flow_nodes(s):
                bag.error(
                    "'continue to' / 'skip to next hand' may only appear in a phase "
                    "body",
                    node.span,
                )


def _check_phase_produces(
    phase: n.Phase,
    enclosing: n.Phase | None,
    outcomes: Mapping[str, TOutcome],
    env: TypeEnv,
    bag: DiagnosticBag,
    binders: _Binders = (),
) -> None:
    # The nearest outcome-declaring phase owns the produces in this body. The
    # binder fold mirrors `_phase_statements_scoped`, so a payload routed
    # through a preceding `let` types exactly like its inline twin.
    owner = phase if phase.outcome_cases else enclosing
    current = binders
    for item in phase.items:
        if isinstance(item, n.Phase):
            _check_phase_produces(item, owner, outcomes, env, bag, current)
        elif isinstance(item, (n.StateBlock, n.ActiveRules, n.LegalMoves, n.Mode)):
            pass
        elif isinstance(item, (n.BeforeEach, n.AfterEach)):
            for s in item.body:
                for sub in _stmt_tree(s):
                    if isinstance(sub, n.Produce):
                        bag.error("'produce' may not appear in a before_each/after_each hook", sub.span)
        else:
            for sub, sub_binders in _stmt_tree_scoped(item, current):
                if not isinstance(sub, n.Produce):
                    continue
                if owner is None:
                    bag.error("'produce' may only appear in a define or outcome-phase body", sub.span)
                else:
                    _check_produce_stmt(
                        sub,
                        outcomes[owner.name],
                        f"phase '{owner.name}'",
                        _scoped_env(env, sub_binders),
                        bag,
                    )
            if isinstance(item, n.LetStmt):
                current = current + ((item.name, item),)


def _check_produces(
    stmt: n.Produces,
    outcomes: Mapping[str, TOutcome],
    env: TypeEnv,
    bag: DiagnosticBag,
) -> None:
    """A `produces:` consumer: arms name declared outcomes, are exhaustive and
    non-duplicated, bind the right payload arity, and have their bodies checked
    with the payload binders typed (a scoped sub-walk, since the flat walk treats
    `Produces` as a leaf). A consumer nested in an arm is checked recursively with
    the enclosing arm binders in scope."""
    outcome = outcomes.get(stmt.define)
    if outcome is None:
        return
    seen: set[str] = set()
    for arm in stmt.arms:
        if arm.tag not in outcome.cases:
            bag.error(
                f"produces names unknown outcome case '{arm.tag}' of '{stmt.define}'",
                arm.span,
            )
            continue
        if arm.tag in seen:
            bag.error(f"duplicate arm '{arm.tag}' in produces", arm.span)
        seen.add(arm.tag)
        payload_types = outcome.cases[arm.tag]
        if len(arm.binders) != len(payload_types):
            bag.error(
                f"arm '{arm.tag}' binds {len(arm.binders)} value(s), "
                f"expected {len(payload_types)}",
                arm.span,
            )
        arm_env = env
        for binder, t in zip(arm.binders, payload_types):
            arm_env = arm_env.with_local(binder, t)
        # Arm bodies carry the same binder typing as the main walk — a `for
        # each` or a sequential `let` inside an arm is not a TAny loophole.
        for sub, loop_binders in _seq_tree_scoped(arm.body, ()):
            sub_env = _scoped_env(arm_env, loop_binders)
            if isinstance(sub, n.Produce):
                # `_stmt_tree` does not descend into `produces:` arms, so the
                # outer misplaced-produce walk never sees this — reject it here.
                bag.error("'produce' may not appear in a produces: arm", sub.span)
            if isinstance(sub, n.Produces):
                # Nested consumer: check it with the enclosing arm binders in
                # scope (so outer payload binders are typed, not TAny).
                _check_produces(sub, outcomes, sub_env, bag)
            _check_stmt_exprs(sub, sub_env, bag)
            _check_stmt_semantics(sub, sub_env, bag)
    missing = sorted(set(outcome.cases) - seen)
    if missing:
        bag.error(
            f"produces on '{stmt.define}' is not exhaustive: missing "
            f"{', '.join(missing)}",
            stmt.span,
        )


def typecheck(game: Game) -> Game:
    bag = DiagnosticBag()

    players = game.players
    if players.low < 1:
        bag.error(f"a game needs at least one player, got {players.low}", players.span)
    if players.high is not None and players.high < players.low:
        bag.error(
            f"player range upper bound {players.high} precedes lower bound {players.low}",
            players.span,
        )

    # Structs and user functions are solved together, to a fixpoint — they
    # depend on each other in both directions and at arbitrary depth.
    structs, functions = struct_and_function_registries(game, bag)
    env = replace(env_from_game(game, structs), functions=functions)
    env = replace(env, procedures=_procedure_sigs(game))
    outcomes = outcome_registry(game, env.structs, env.positions)
    for stmt, binders in _all_statements_scoped(game):
        senv = _scoped_env(env, binders)
        _check_stmt_exprs(stmt, senv, bag)
        if isinstance(stmt, n.Produces):
            # `_check_produces` recurses into arm-nested consumers itself, carrying
            # the arm binders into their environment.
            _check_produces(stmt, outcomes, senv, bag)
        else:
            _check_stmt_semantics(stmt, senv, bag)
    for define in game.defines:
        outcome = outcomes.get(define.name)
        if outcome is not None:
            _check_define_outcomes(define, outcome, env, bag)
    _check_misplaced_produce(game, outcomes, env, bag)
    _check_outcome_scope(game, bag)
    _check_outcome_name_collisions(game, bag)
    _check_single_outcome_consumer(game, bag)

    def check_phase_positions(phase: n.Phase, binders: _Binders) -> None:
        """Phase-level expression positions, typed with the binders the runtime
        actually evaluates them under. A nested phase's qualifier and a
        transition predicate run mid-body with the THREADED context (a
        preceding body `let` is bound — checking them with the bare env made
        the same expression get three different verdicts by position); state
        defaults run at ENTRY, so they see enclosing binders only (resolve
        rejects a same-phase body `let` in them, like the hooks)."""
        current = binders
        for item in phase.items:
            match item:
                case n.Phase():
                    if item.qualifier is not None:
                        qenv = _scoped_env(env, current)
                        _check_expr(item.qualifier.expr, qenv, bag)
                        _check_bool(
                            item.qualifier.expr,
                            qenv,
                            bag,
                            f"phase '{item.name}' condition",
                        )
                    check_phase_positions(item, current)
                case n.Mode():
                    # Reached via the mode, since a transition is no longer a
                    # phase item. NO binders at all: a transition predicate may
                    # not read any `let` (resolve rejects the reference — it is
                    # fired by whichever round matches its event, and no lexical
                    # position makes a binding reliably live then), so the
                    # bare env is exactly its scope.
                    for transition in item.transitions:
                        if transition.event.where is not None:
                            _check_expr(transition.event.where, env, bag)
                case n.StateBlock():
                    entry_env = _scoped_env(env, binders)
                    for decl in item.decls:
                        _check_expr(decl.default, entry_env, bag)
                        _check_state_default_type(decl, entry_env, bag)
                case n.LetStmt():
                    current = current + ((item.name, item),)
                case _:
                    pass

    for phase in game.phases:
        if phase.qualifier is not None:
            # Top-level: nothing can precede a top-level phase, so the bare env
            # is exactly its entry scope.
            _check_expr(phase.qualifier.expr, env, bag)
            _check_bool(
                phase.qualifier.expr, env, bag, f"phase '{phase.name}' condition"
            )
        check_phase_positions(phase, ())
    _check_trick_order(game, env, bag)
    if game.loser is not None:
        _check_expr(game.loser.selection, env, bag)
        # `loser:` names a player directly (unlike `winner:`, which ranks a score
        # variable). Before the operand choke point it carried NO player check --
        # `loser: 5` and even `loser: "x"` passed -- so it types and ranges here.
        lsel = infer(game.loser.selection, env)
        _check_operand(
            game.loser.selection, lsel, TPlayer(), env, bag,
            f"`loser:` names the losing player — expected a Player, got "
            f"{_type_name(lsel)}",
            game.loser.span,
        )

    # The remaining expression positions: a function call in any of these needs the
    # same arity/type validation as one in a statement, but the statement walk above
    # does not reach them. This is every place a call can appear that isn't already
    # covered (statements, round over/until, phase qualifiers, loser, function
    # bodies): move guards, rule predicates, state defaults, transition predicates,
    # and derived type-field bodies.
    for move_type in game.move_types:
        if move_type.when is not None:
            _check_expr(
                move_type.when,
                _scoped_env(
                    env, _parameter_binders(move_type, env.positions, env.directions)
                ),
                bag,
            )
    for rule in game.rules:
        if rule.applies_when is not None and rule.applies_when.pred is not None:
            _check_expr(rule.applies_when.pred, env, bag)
        if rule.demands is not None:
            _check_expr(rule.demands.expr, env, bag)
        if rule.if_impossible is not None:
            _check_expr(rule.if_impossible, env, bag)
        if rule.exempts is not None:
            _check_expr(rule.exempts, env, bag)
    # Phase-level state defaults and transition predicates are checked by
    # `check_phase_positions` above, with their real binder scope; only the
    # game-level state block remains here (nothing can precede it).
    if game.state is not None:
        for decl in game.state.decls:
            _check_expr(decl.default, env, bag)
            _check_state_default_type(decl, env, bag)
    for tdef in game.types:
        # A derived body reads sibling fields by bare name (resolve scopes
        # them); their declared types are in the struct registry, so bind
        # them — without this, `derived { bad = seat is hearts }` on a Player
        # field would type `seat` as TAny and accept the always-false comparison.
        struct = env.structs.get(tdef.name)
        denv = env
        if struct is not None:
            for fname, ftype in struct.fields.items():
                denv = denv.with_local(fname, ftype)
        for derived in tdef.derived:
            _check_expr(derived.value, denv, bag)

    if bag.has_errors:
        error = DiagnosticError(bag.items[0])
        if len(bag.items) > 1:
            error.add_note(bag.format())
        raise error
    return game
