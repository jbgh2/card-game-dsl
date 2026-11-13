"""The name classifier: the one walk that stamps `ref_kind`.

A shared module with two drivers: the classification step runs it over the
game, and `library_alone` over a library judged alone. Classification is the
resolve pass's alone, and within the pass this module's alone.

Contract (decisions.md "Closed-domain completeness", write-time triage)
-----------------------------------------------------------------------
Assumes:      the categories a tree is classified against (``_categories``).
Establishes:  every ``NameRef`` the walk meets carries its ``ref_kind``.
Now illegal:  an undeclared ``always`` standing as the whole
              predicate of a clause ``_ALWAYS_SITES`` names, refused with
              the fix by ``_refuse_bare_always`` (its Owner Guard) where the
              predicate is classified, and read off the classified tree by
              ``_library_reach`` for a library's clauses.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, is_dataclass, replace
from typing import TypeGuard, cast
from cardlang.diagnostic_codes import Code
from cardlang.ast import nodes as n
from cardlang.board_domains import LINE_NOUN
from cardlang.builtins.functions import VALUE_NAMES
from cardlang.primitives_block import walled_namespace_of
from cardlang.diagnostics import DiagnosticBag, Span
from cardlang.domains import Role, role_names, role_of
from cardlang.catalogue_pass import shape_labels
from cardlang.runtime.values import content_noun
from cardlang.stdlib.enums import SEAT_DIRECTION_VALUES, enum_values, rank_names, suit_names
from cardlang.types import Flavor
from cardlang.resolve.walk import _traverse, _walk
from cardlang.resolve.binders import _BINDER_SCOPE_FIELDS, _introduced_binders
from cardlang.resolve.reserved import PLAY_SOURCE_NAME, _PRONOUNS, _SUBSCRIPTED_PLAY_SOURCE
from cardlang.resolve.slots import _ROUND_QUERY_SLOT_SPELLINGS
from cardlang.resolve.declared import _component_known
from cardlang.resolve.reaches import (
    _ReadLimits,
    _answer_read_refusal,
    _arrival_pile_refusal,
    _hosted_read_refused,
    _play_source_refused,
)
from cardlang.resolve.scope import (
    _bare_family_refused,
    _bare_seat_family_in_default,
    _pronoun_refused,
    _state_out_of_scope,
)


@dataclass(frozen=True)
class _Categories:
    """The namespaces a bare name resolves against, collected once per game.

    Every field but `locals` is game-wide and fixed by `_categories` below.
    `locals` is lexical, not game-wide: it starts empty (a bare binder name
    resolves nowhere until something scopes it in) and `_rewrite` extends it
    with `replace(cats, locals=cats.locals | {...})` for exactly the sub-fields
    of a binder-introducing node (`_BINDER_SCOPE_FIELDS`, keyed by
    `_introduced_binders`) or the tail of a statement tuple after a `let`
    (the sequential fold in `_rewrite_value`) — never wider than that subtree."""

    locals: frozenset[str]
    state_vars: frozenset[str]
    zones: frozenset[str]
    enums: frozenset[str]
    ranks: frozenset[str]
    suits: frozenset[str]
    # Every definition name that is not a value — a function, procedure, move
    # type, rule, phase or position domain — so a bare name a definition
    # holds is never read as a name nothing declares.
    definitions: frozenset[str]
    # `Game.content_flavor` — the dispatch key for the flavor-aware Owner Guards
    # (decisions.md, "Component sets: cards and pieces").
    flavor: Flavor = "card"
    # Inside a rule's clauses, where a bare `hand` is the Play Source.
    rule_clause: bool = False
    # The game's catalogue row labels, the values a play's `.shape` takes
    # (also in `enums`, where a bare label resolves).
    shapes: frozenset[str] = frozenset()
    # The nouns a collection form ranges by (`collection_nouns`), and every
    # name the game binds (`_names_bound_anywhere`): what the membership
    # capture check reads at a collection set's node.
    collection_nouns: frozenset[str] = frozenset()
    bound_names: frozenset[str] = frozenset()
    # Each zone's index role, None for a single zone: what the bare-family and
    # `to each` positions read of a zone a Near Miss names.
    zone_index: Mapping[str, str | None] = field(default_factory=dict)
    # What a bare name may denote where it stands, by the name's node
    # (`_name_positions`), over the tree `_classify_names` classifies.
    positions: Mapping[int, _NamePosition] = field(default_factory=dict)
    # What a name written at a node may read whatever slot it fills, by every
    # node (`_scope_facts`): what the Scope Record reads at a node that is no
    # name.
    scope_facts: Mapping[int, _ScopeFacts] = field(default_factory=dict)
    # The names a node's refused binder source would bind were it fixed, by
    # the node (`_refused_binder_sources`): the node binds nothing, and a
    # name in its scope spelled as one of them is withheld.
    refused_binders: Mapping[int, frozenset[str]] = field(default_factory=dict)
    # Lexical, like `locals`: names in scope that a refused binder source's
    # fix would bind. Unresolved, such a name is a consequence of that
    # refusal and is not told.
    withheld: frozenset[str] = frozenset()
    # The Scope Record a Checker Query asks for (`resolve(scopes=...)`),
    # filled by `_rewrite` at every node it classifies under; None otherwise.
    scopes: dict[n.NodeKey, NamesInScope] | None = None


@dataclass(frozen=True)
class NamesInScope:
    """What a bare name written at one node would resolve to: each name this
    pass classifies there, with its classification, less any the scope rules
    refuse at the node (`_scope_refuses`: the State Variable scope rules, the
    Pronouns a definition body may not read, a default's reads) and, at a
    name, any a positional Owner Guard of this pass refuses in the slot the
    name fills (`_position_refuses`; `at_a_name`). The rules of who is acting
    and of a Hosted Poll's body are not applied (issue #1089)."""

    names: tuple[tuple[str, n.RefKind], ...]
    at_a_name: bool


def _record_scope(node: object, cats: _Categories) -> None:
    """Record, in the Scope Record, what a bare name at `node` resolves to:
    `_classify` over every name `cats` holds, with a rule clause's bare `hand`
    the Play Source, exactly as the `NameRef` arm of `_rewrite` classifies."""
    assert cats.scopes is not None
    key = n.node_key(node)
    if key is None:
        return
    position = cats.positions.get(id(node)) if isinstance(node, n.NameRef) else None
    facts = cats.scope_facts.get(id(node))
    named: list[tuple[str, n.RefKind]] = []
    for name in sorted({*cats.locals, *cats.state_vars, *cats.zones, *cats.enums, *_PRONOUNS}):
        kind: n.RefKind | None = _classify(name, cats)
        if cats.rule_clause and name == PLAY_SOURCE_NAME and name not in cats.locals:
            kind = "play_source"
        if kind is None:
            continue
        if position is not None:
            if _position_refuses(position, name, kind, cats.zone_index):
                continue
        elif facts is not None and _scope_refuses(facts, name, kind):
            continue
        named.append((name, kind))
    cats.scopes[key] = NamesInScope(tuple(named), at_a_name=position is not None)


_NO_LIMITS = _ReadLimits(frozenset(), frozenset(), frozenset())


@dataclass(frozen=True)
class _ScopeFacts:
    """What a name written at a node may read, whatever slot it fills: the
    facts the scope rules of this pass refuse a classified name by, each
    recorded from the walk its rule refuses by.

    `live_state` is the state live at a phase-scoped node
    (`_phase_scoped_nodes`, `_check_state_scope`) or at a node of a `state { }`
    default (`_default_reads`, `_check_state_default_scope`), None where no
    scope rule judges (a callable body, issue #242). `refused_pronouns` are
    the pronouns the enclosing definition or default may not read
    (`_refused_call_site_pronouns`, `_DEFAULT_REFUSED_PRONOUNS`), and
    `in_default` marks a node of a `state { }` block. A rule judging a name
    wherever it stands joins as a field here, filled by `_scope_facts` from
    the walk it refuses by, and as a disjunct of `_scope_refuses`."""

    live_state: frozenset[str] | None = None
    refused_pronouns: frozenset[str] = frozenset()
    in_default: bool = False


@dataclass(frozen=True)
class _NamePosition:
    """What a bare name may denote where it stands: the facts the positional
    Owner Guards of this pass refuse a classified name by. `scope` is what
    any name written there may read (`_ScopeFacts`); `slot` is the kinds the
    name slot the name roots takes (`_NAME_SLOTS`), `each_destination` marks a
    `to each` destination, and `keyed` a name a subscript keys or a `to each`
    names whole (`_keyed_ids`)."""

    scope: _ScopeFacts = _ScopeFacts()
    slot: frozenset[n.RefKind] | None = None
    each_destination: bool = False
    keyed: bool = False
    answer_through: frozenset[bool] = frozenset()
    play_source_names: frozenset[str] = frozenset()
    arrival_pile: bool = False
    hosted: bool = False
    subscripted: bool = False
    limits: _ReadLimits = _NO_LIMITS


def _scope_refuses(facts: _ScopeFacts, name: str, kind: n.RefKind) -> bool:
    """Whether a scope rule of this pass refuses a name of `kind` written
    where `facts` hold, whatever slot it fills."""
    return _state_out_of_scope(name, kind, facts.live_state) or _pronoun_refused(
        name, kind, facts.refused_pronouns
    )


def _position_refuses(
    position: _NamePosition, name: str, kind: n.RefKind, zone_index: Mapping[str, str | None]
) -> bool:
    """Whether some positional Owner Guard of this pass refuses a name of
    `kind` at `position`: each disjunct is the predicate its guard refuses by."""
    return (
        _scope_refuses(position.scope, name, kind)
        or (position.slot is not None and _slot_refuses(position.slot, kind))
        or (position.each_destination and _each_destination_refuses(zone_index, name, kind))
        or _bare_family_refused(zone_index, name, kind, position.keyed)
        or (
            position.scope.in_default
            and _bare_seat_family_in_default(zone_index, name, kind, position.keyed)
        )
        or any(
            _answer_read_refusal(name, kind, through, position.subscripted, position.limits) is not None
            for through in position.answer_through
        )
        or _play_source_refused(name, kind, position.play_source_names, position.subscripted)
        or (position.arrival_pile and _arrival_pile_refusal(name, kind, position.limits) is not None)
        or (position.hosted and _hosted_read_refused(name, kind))
    )


def _categories(game: n.Game) -> _Categories:
    # `locals` starts empty here: binders (comprehension/quantifier/query/
    # for-each/each-simultaneous/movement-filter/let) are lexically scoped by
    # `_rewrite`, not collected game-wide — see the `_Categories` docstring.
    # State vars remain game-wide: `state { }` (top-level or phase-local) is a
    # single flat declaration namespace (`_check_duplicate_names` enforces
    # uniqueness across it), not a binder any construct introduces.
    state_vars = {nd.name for nd in _walk(game) if isinstance(nd, n.StateDecl)}
    definitions = {
        nd.name
        for nd in _walk(game)
        if isinstance(nd, n.FunctionDef | n.ProcedureDef | n.MoveTypeDef | n.RuleDef | n.Phase | n.PositionDecl)
    }
    return _Categories(
        locals=frozenset(),
        state_vars=frozenset(state_vars),
        definitions=frozenset(definitions),
        zones=frozenset(z.name for z in game.zones),
        enums=(enum_values(game.deck) if _component_known(game.deck) else SEAT_DIRECTION_VALUES)
        | shape_labels(game),
        # Card-literal validation asks "does this card EXIST in the deck",
        # so ranks derive from the deck like `suits` below — never from
        # `ranking:`, which is an ORDERING (optional, and legitimately
        # partial: it narrows the Rank move-param domain, not which cards
        # can be named). Deck-vs-ranking is the same two-source divergence
        # `_resolve_ranking` guards from the other side.
        ranks=rank_names(game.deck) if _component_known(game.deck) else frozenset(),
        suits=suit_names(game.deck) if _component_known(game.deck) else frozenset(),
        flavor=game.content_flavor,
        shapes=shape_labels(game),
        collection_nouns=collection_nouns(game),
        bound_names=_names_bound_anywhere(game),
        zone_index={z.name: z.index for z in game.zones},
    )


def _classify(name: str, cats: _Categories) -> n.RefKind | None:
    if name == "none":
        return "null"  # the universal absence literal (any optional's null)
    if name in ("true", "false"):
        return "bool"  # boolean literals
    if name in cats.locals:
        return "local"
    if name in cats.state_vars:
        return "state_var"
    if name in cats.zones:
        return "zone"
    if name in cats.enums:
        return "enum_value"
    if name in _PRONOUNS:
        return "pronoun"
    return None


def _rewrite_produce_arm(
    arm: n.ProduceArm, cats: _Categories, bag: DiagnosticBag
) -> n.ProduceArm:
    """Rewrite one produces-arm body with the arm's payload binders in local
    scope — so bare binder references resolve, without leaking into other arms or
    the enclosing game."""
    scoped = replace(cats, locals=cats.locals | frozenset(arm.binders))
    # Route through `_rewrite_value` (not a bare per-item `_rewrite` map) so a
    # `let` inside the arm body scopes to the arm's later statements too — the
    # same sequential fold every other statement tuple gets.
    body = _rewrite_value(arm.body, scoped, bag)
    return replace(arm, body=body)  # type: ignore[arg-type]


def _callback_outside_slot(name: str) -> str:
    """A trick winner named where an expression stands. Its one reading is the
    round slot that takes it (`TrickRound.winner_fn`), a name the round calls,
    never a value, so no expression position classifies it. `VALUE_NAMES` is
    exactly the trick winners, pinned by tests/test_bare_callback_names.py."""
    slot = _ROUND_QUERY_SLOT_SPELLINGS[(n.TrickRound, "winner_fn")].format(name=name)
    return (
        f"`{name}` is a trick winner, read only in {slot}; it is not a value an "
        f"expression can hold — name it in its round"
    )


def _slot_name_outside_slot(name: str) -> str | None:
    """The refusal for a name only a round slot reads, written where an
    expression stands — a call, a bare name, the `winner:` clause's state
    variable — or None for any other name. One sentence per namespace: a trick
    winner's own, and for a walled Primitive the label the `primitives { }`
    block gives the same name."""
    if name in VALUE_NAMES:
        return _callback_outside_slot(name)
    walled = walled_namespace_of(name)
    if walled is None:
        return None
    return (
        f"`{name}` is {walled}, read only in that slot; it is not a value an "
        f"expression can hold — name it in its round"
    )


@dataclass(frozen=True)
class _AlwaysSite:
    """A clause whose whole predicate a designer writes as `always`: the node
    field holding the predicate, the clause spelling, and the holder the
    refusal names."""

    field: str
    clause: str
    holder: str


#: The clauses whose whole predicate a designer writes as `always`, by holder
#: node. A clause that holds unconditionally is written by leaving the clause
#: out, so the wildcard is a second spelling of an omission and is refused
#: with that fix — by `_rewrite` where it classifies the predicate, and by
#: `_library_reach`, which reads the refusal off the classified tree so a
#: library's clause is refused in the same words rather than reported as a
#: read past the contract. Everywhere else `always` is an ordinary name:
#: declared as a value, a condition like any other; undeclared as an operand,
#: or naming a definition that is no value, an unresolved name.
_ALWAYS_SITES: dict[type, _AlwaysSite] = {
    n.AppliesWhen: _AlwaysSite("pred", "applies_when:", "a rule that applies every time"),
    n.MoveTypeDef: _AlwaysSite("when", "when:", "a move type that is always legal"),
}
ALWAYS_HOLDERS: dict[str, str] = {site.clause: site.holder for site in _ALWAYS_SITES.values()}


#: The refusal of `max_length` read as a value, undeclared. The bound is a game
#: clause the engine stops at (decisions.md "Game length as a declared
#: contract"), not state a rule can read, and the two things a designer
#: writing it means each have a spelling.
MAX_LENGTH_AS_VALUE = (
    "`max_length` is the bound the engine stops a game at, not a value a rule "
    "can read. To end the game after a number of turns by its rules, count the "
    "turns in a state variable and compare it to a number. To say what a game "
    "is worth when the engine stops it, write `at max_length: tie`, `at "
    "max_length: as it stands`, or `at max_length: highest <variable>`."
)


def _always_message(clause: str) -> str:
    return f"`always` is not a condition — {ALWAYS_HOLDERS[clause]} has no `{clause}` line; leave it out"


def _is_bare_always(pred: object) -> TypeGuard[n.NameRef]:
    return isinstance(pred, n.NameRef) and pred.name == "always"


def _refuse_bare_always(pred: object, clause: str, cats: _Categories, bag: DiagnosticBag) -> bool:
    """Record the refusal for an undeclared `always` standing as the whole
    predicate of `clause`; True when it fired, so the caller leaves the
    predicate unrewritten rather than reporting it unresolved as well. The
    Owner Guard of the spelling: name classification is what decides that
    `always` names nothing, so the refusal stands where that is decided."""
    if not (
        _is_bare_always(pred)
        and _classify("always", cats) is None
        and "always" not in cats.definitions
    ):
        return False
    bag.error(_always_message(clause), pred.span, code=Code.HAS_NO_EFFECT)
    return True


def _unknown_shape_label(node: n.BinOp, cats: _Categories) -> n.NameRef | None:
    """The bare name a `<x>.shape is <name>` comparison sets against a play's
    shape when it names nothing of the game, or None."""
    for side, other in ((node.left, node.right), (node.right, node.left)):
        if (
            isinstance(side, n.Member)
            and side.field == "shape"
            and isinstance(other, n.NameRef)
            and other.ref_kind is None
            and other.name not in cats.locals
            and _classify(other.name, cats) is None
        ):
            return other
    return None


def _rewrite_refused_binder(
    node: object, fixes: frozenset[str], cats: _Categories, bag: DiagnosticBag
) -> object:
    """Rewrite a node whose binder source is refused: it binds nothing, and
    the fields its binder would scope withhold `fixes`, the binders a fix of
    the source would bind, and the binder the source as written would bind,
    so the names they read are not refused for the source's refusal."""
    scope_fields = _BINDER_SCOPE_FIELDS[type(node)]
    written = frozenset(_introduced_binders(node, cats.flavor))
    withheld = replace(cats, withheld=cats.withheld | fixes | written)
    return _traverse(
        node, lambda f, v: _rewrite_value(v, withheld if f in scope_fields else cats, bag)
    )


def _resolving_here(node: n.NameRef, names: Sequence[str], cats: _Categories) -> tuple[str, ...]:
    """The `names` that resolve where `node` stands: each classifies there and
    no positional Owner Guard refuses it at `node`'s position."""
    position = cats.positions.get(id(node), _NamePosition())
    out: list[str] = []
    for name in names:
        kind: n.RefKind | None = (
            "play_source"
            if cats.rule_clause and name == PLAY_SOURCE_NAME and name not in cats.locals
            else _classify(name, cats)
        )
        if kind is not None and not _position_refuses(position, name, kind, cats.zone_index):
            out.append(name)
    return tuple(out)


def _rewrite(node: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if cats.scopes is not None:
        _record_scope(node, cats)
    if isinstance(node, n.DomainQuery) and _may_be_a_membership(node, cats):
        # The Owner Guard `_check_domain_query` leaves to the lexical scope. A
        # refused capture's predicate is written over the outer binder, so it
        # is not read under the captured noun.
        fixes = _membership_capture(node, cats, bag)
        if fixes is None:
            return node
        return _rewrite_refused_binder(node, fixes, cats, bag)
    if id(node) in cats.refused_binders:
        return _rewrite_refused_binder(node, cats.refused_binders[id(node)], cats, bag)
    if isinstance(node, n.AppliesWhen) and _refuse_bare_always(
        node.pred, _ALWAYS_SITES[n.AppliesWhen].clause, cats, bag
    ):
        return node
    if (
        isinstance(node, n.TrickRound)
        and isinstance(node.trump, n.NameRef)
        and node.trump.ref_kind is None
        and cats.suits
        and _classify(node.trump.name, cats) is None
    ):
        # A fixed trump is a suit of the deck, so a name that is none is told
        # the deck's suits, where an unresolved name would say only that.
        bag.unknown(
            f"round `trump` names '{node.trump.name}', which is neither a suit of "
            f"this deck ({', '.join(sorted(cats.suits))}) nor a state variable — "
            f"write the suit, or a `Suit?` state variable the game sets",
            node.trump.name,
            _resolving_here(node.trump, (*cats.suits, *cats.state_vars), cats),
            node.trump.span,
            code=Code.UNKNOWN_SUIT,
        )
        rest = _rewrite(replace(node, trump=None), cats, bag)
        assert isinstance(rest, n.TrickRound)
        return replace(rest, trump=node.trump)
    if (
        isinstance(node, n.BinOp)
        and node.op in ("is", "is_not")
        and cats.shapes
        and (label := _unknown_shape_label(node, cats)) is not None
    ):
        bag.unknown(
            f"`{label.name}` is no row label of this game's catalogue — a "
            f"play's `.shape` is one of "
            f"{', '.join(f'`{x}`' for x in sorted(cats.shapes))}",
            label.name,
            cats.shapes,
            label.span,
            code=Code.UNKNOWN_PLAY_SHAPE,
        )
        # The label is told once here; its side stays unclassified.
        other = node.left if node.right is label else node.right
        side = cast(n.Expr, _rewrite(other, cats, bag))
        if other is node.left:
            return replace(node, left=side)
        return replace(node, right=side)
    if isinstance(node, n.NameRef):
        if node.ref_kind is not None:
            # Classified by an earlier step of this pass from a fact it held
            # first: a `card_points { }` key is a rank of the deck
            # (`_resolve_card_points`), whatever else the game spells so.
            return node
        if cats.rule_clause and node.name == PLAY_SOURCE_NAME and node.name not in cats.locals:
            return replace(node, ref_kind="play_source")
        kind = _classify(node.name, cats)
        if kind is None and node.name in cats.withheld:
            return node
        if kind is None:
            hint = ""
            noun = content_noun(cats.flavor, plural=False)
            if node.name == noun:
                where = (
                    "a card query, an aggregation, or a `where` filter"
                    if cats.flavor == "card"
                    else "a movement's `where` filter"
                )
                hint = f" (`{noun}` is bound only inside {where})"
            # Not a role dispatch: `player` is the unresolved NAME this hint
            # is about, so it stays a string (guarded as a coincidence in
            # tests/test_role_comparison_pin.py).
            elif node.name == "player":
                hint = " (`player` is bound only inside a player query or quantifier)"
            elif (outside := _slot_name_outside_slot(node.name)) is not None:
                bag.error(outside, node.span, code=Code.WRONG_SORT_OF_NAME)
                return replace(node, ref_kind=kind)
            elif node.name == "max_length":
                bag.error(MAX_LENGTH_AS_VALUE, node.span, code=Code.WRONG_SORT_OF_NAME)
                return replace(node, ref_kind=kind)
            bag.unknown(
                f"unresolved name '{node.name}'{hint}",
                node.name,
                _resolving_here(
                    node,
                    (
                        *cats.locals, *cats.state_vars, *cats.zones, *cats.enums,
                        *_PRONOUNS, "none", "true", "false",
                        *((PLAY_SOURCE_NAME,) if cats.rule_clause else ()),
                    ),
                    cats,
                ),
                node.span,
                code=Code.UNKNOWN_NAME,
            )
        return replace(node, ref_kind=kind)
    if isinstance(node, n.Produces):
        # Each arm's payload binders scope to that arm's body only — they must not
        # leak into the global `locals` set (which would shadow same-named state
        # vars across the whole game).
        arms = tuple(_rewrite_produce_arm(arm, cats, bag) for arm in node.arms)
        return replace(node, arms=arms)
    if isinstance(node, n.MoveTypeDef):
        # The parameters bind only in this move's guard/effect — scope them here
        # rather than the game-wide `locals` set (which would shadow a same-named
        # state var everywhere; mirrors the produce-arm binders above, and the
        # function-parameter branch below for the identical params-tuple shape).
        scoped = (
            replace(cats, locals=cats.locals | {p.name for p in node.params})
            if node.params
            else cats
        )
        when_pred = (
            node.when
            if node.when is None
            or _refuse_bare_always(node.when, _ALWAYS_SITES[n.MoveTypeDef].clause, scoped, bag)
            else _rewrite_value(node.when, scoped, bag)
        )
        # `_rewrite_value` (not a bare per-item `_rewrite` map): a `let` in a
        # move's effect scopes to the statements after it, like everywhere else.
        effect = _rewrite_value(node.effect, scoped, bag)
        return replace(node, when=when_pred, effect=effect)  # type: ignore[arg-type]
    if isinstance(node, n.RuleDef):
        # A rule's clauses read a bare `hand` as the Play Source, below the
        # binders a clause introduces and above every game namespace. A
        # template's parameters bind in its clauses, exactly as a move type's do
        # in its guard and effect; the game path instantiates templates before
        # `_classify_names` runs, so they are in scope here only for
        # `_library_reach`, which classifies a library's rules where written.
        scoped = replace(
            cats, locals=cats.locals | {p.name for p in node.params}, rule_clause=True
        )
        return _traverse(node, lambda _field, v: _rewrite_value(v, scoped, bag))
    if (
        cats.rule_clause
        and isinstance(node, n.Subscript)
        and isinstance(node.obj, n.NameRef)
        and node.obj.name == PLAY_SOURCE_NAME
        and PLAY_SOURCE_NAME not in cats.locals
    ):
        # A subscripted `hand` names the declaration, not the Play Source.
        plain = replace(cats, rule_clause=False)
        obj: object = node.obj
        if _classify(PLAY_SOURCE_NAME, plain) is None:
            bag.error(_SUBSCRIPTED_PLAY_SOURCE, node.obj.span, code=Code.WRONG_SUBSCRIPT)
        else:
            obj = _rewrite(node.obj, plain, bag)
        return replace(node, obj=obj, index=_rewrite_value(node.index, cats, bag))  # type: ignore[arg-type]
    if isinstance(node, n.FunctionDef):
        # The parameters bind only in this function's body — scope them here rather
        # than the game-wide `locals` set (mirrors the move-type/produce-arm binders
        # above). A bare name in the body that is neither a parameter nor a binding
        # it introduces stays un-shadowed, so the hermeticity check can catch it.
        scoped = replace(cats, locals=cats.locals | {p.name for p in node.params})
        body = _rewrite_value(node.body, scoped, bag)
        return replace(node, body=body)  # type: ignore[arg-type]
    if isinstance(node, n.ProcedureDef):
        # Same isolation as a function: the parameters bind only in this body, and
        # a bare name that is neither a parameter nor a binding the body introduces
        # stays un-shadowed so `_check_procedures` can catch it. `_rewrite_value`
        # (not a per-item map) so a `let` in the body scopes to the statements after
        # it, exactly as it will once the body is spliced inline.
        scoped = replace(cats, locals=cats.locals | {p.name for p in node.params})
        body = _rewrite_value(node.body, scoped, bag)
        return replace(node, body=body)  # type: ignore[arg-type]
    if isinstance(node, n.LetStmt):
        # `index` (the indexed form's per-key binder, `let base[p] = …`) scopes
        # only to this let's own `value` — evaluated once per key and gone
        # afterward (`runtime/execute.py:_let`), unlike `name`. `name` is NOT
        # scoped here: it becomes visible to statements after this one in the
        # same tuple, folded by `_rewrite_value`'s tuple arm below.
        scoped = replace(cats, locals=cats.locals | {node.index}) if node.index is not None else cats
        value = _rewrite_value(node.value, scoped, bag)
        return replace(node, value=value)  # type: ignore[arg-type]
    if isinstance(node, n.Phase):
        # The items fold with the configuration carve-out. A body `let` scopes
        # over later statements and nested phases (their qualifiers included) —
        # what the driver evaluates mid-body with the threaded context — but
        # NOT over this phase's own hooks, state defaults, or TRANSITION
        # predicates. Hooks and state declare/run at entry, before any body
        # `let` has executed (`run_phase` declares state and captures hooks
        # first); a transition predicate is CONFIGURATION collected
        # position-independently and evaluated with the context captured at
        # whichever round fires it — which may run before the `let`. The
        # generic tuple fold would scope all three anyway, so `let z = 5`
        # followed by `before_each { n[1] := z }` (or a transition reading a
        # body let, fired by an earlier round) would resolve, type-check, and
        # then ask the runtime's scope stack for a binding no live frame holds
        # — a lookup it requires to succeed, mid-playout.
        entry = cats
        current = cats
        out_items: list[object] = []
        for item in node.items:
            if isinstance(item, n.Mode):
                # A MODE reads no `let` at all — not even an enclosing one —
                # and that covers its whole body, not just its transitions.
                # A transition is fired by whichever round matches its event,
                # and rounds both before and after any given `let` can be in
                # scope, so no lexical position makes a binding reliably live
                # at evaluation time; a mode's `active_rules:` are collected
                # the same way, applying whenever the mode holds rather than
                # where they are written. Configuration reads state and the
                # action; body bindings are the body's.
                no_locals = replace(entry, locals=frozenset())
                out_items.append(_rewrite_value(item, no_locals, bag))
            elif isinstance(item, (n.BeforeEach, n.AfterEach, n.StateBlock)):
                out_items.append(_rewrite_value(item, entry, bag))
            else:
                rewritten = _rewrite_value(item, current, bag)
                out_items.append(rewritten)
                if isinstance(rewritten, n.LetStmt):
                    current = replace(
                        current, locals=current.locals | {rewritten.name}
                    )
        qualifier = (
            _rewrite_value(node.qualifier, entry, bag)
            if node.qualifier is not None
            else None
        )
        return replace(
            node,
            qualifier=qualifier,  # type: ignore[arg-type]
            items=tuple(out_items),  # type: ignore[arg-type]
        )
    if isinstance(node, n.HostedPoll):
        _check_hosted_binder(node, cats, bag)
    scope_fields = _BINDER_SCOPE_FIELDS.get(type(node))
    if scope_fields is not None:
        binders = _introduced_binders(node, cats.flavor)
        if binders:  # a filter-less Transfer/EpistemicOp introduces nothing
            scoped = replace(cats, locals=cats.locals | frozenset(binders))
            return _traverse(
                node,
                lambda f, v: _rewrite_value(v, scoped if f in scope_fields else cats, bag),
            )
    return _traverse(node, lambda _field, v: _rewrite_value(v, cats, bag))


def _rewrite_value(value: object, cats: _Categories, bag: DiagnosticBag) -> object:
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, cats, bag)
    if isinstance(value, tuple):
        # A `let` binds its name for the REST of this tuple (the sequential-`let`
        # idiom every statement-sequence site shares — Phase.items, if/else
        # bodies, repeat/lifecycle-hook bodies, move-type effects, produce-arm
        # bodies: every tuple a `Stmt`/`PhaseItem` sequence can occur in). This
        # fold is safe to apply to EVERY tuple field generically, not just
        # statement sequences: a `LetStmt` node can only ever appear inside one
        # of those Stmt-typed tuples (the grammar has no other production that
        # embeds a statement), so the `isinstance` check below is a no-op on
        # every other kind of tuple (zones, rule params, call args, …).
        out: list[object] = []
        current = cats
        for item in value:
            rewritten = _rewrite_value(item, current, bag)
            out.append(rewritten)
            if isinstance(rewritten, n.LetStmt):
                current = replace(current, locals=current.locals | {rewritten.name})
        return tuple(out)
    return value


def _slot_refuses(takes: frozenset[n.RefKind], kind: n.RefKind | None) -> bool:
    """Whether a slot taking `takes` refuses a root name of `kind`; an
    unresolved name is the classifier's."""
    return kind is not None and kind not in takes


def _each_destination_refuses(
    zone_index: Mapping[str, str | None], name: str, kind: n.RefKind | None
) -> bool:
    """Whether `to each <name>` refuses a name of `kind`: it deals into the
    family named by name, one zone per player."""
    if kind is None:
        return False
    index = zone_index.get(name)
    return kind != "zone" or index is None or role_of(index) is not Role.PLAYER


def _check_hosted_binder(poll: n.HostedPoll, cats: _Categories, bag: DiagnosticBag) -> None:
    """A Hosted Poll's binder is a fresh name: one that classifies as nothing
    where the clause is written. The body reads it beside the game's own names
    and the enclosing binders, and a binder spelled like one of them would
    change what that name means inside the body alone. The reserved
    spellings (the pronouns, `none`, `true`, `false`) are
    `_check_reserved_binders`'s, which refuses them for every binder."""
    kind = _classify(poll.binder, cats)
    if kind is None or kind in ("null", "bool", "pronoun"):
        return
    what = {
        "local": "a name already bound here",
        "state_var": "a state variable",
        "zone": "a zone",
        "enum_value": "an enum value",
        "function": "a function",
    }[kind]
    bag.error(
        f"the Hosted Poll's binder '{poll.binder}' shadows {what} of the same "
        f"name — inside `before asking {poll.binder} {{ … }}` the name would "
        f"mean the seat about to be asked; pick a fresh name",
        poll.span,
        code=Code.NAME_TAKEN,
    )


def collection_nouns(game: n.Game) -> frozenset[str]:
    """The nouns a collection form ranges by: the game's position domains,
    and, where the game has a board, its lines (decisions.md "Boards and
    cells")."""
    lines = {LINE_NOUN} if game.board is not None else set()
    return frozenset({p.name for p in game.positions} | lines)


def _names_bound_anywhere(game: n.Game) -> frozenset[str]:
    """Every name the game binds or declares as a value somewhere: its
    binders (`_introduced_binders`), its definitions' parameters, its state
    variables and the pronouns. A collection set whose noun is one of these
    may be a membership written without its parentheses."""
    names: set[str] = set(_PRONOUNS)
    for nd in _walk(game):
        names.update(_introduced_binders(nd))
        if isinstance(nd, n.LetStmt):
            names.add(nd.name)
        if isinstance(nd, n.StateDecl):
            names.add(nd.name)
        params = getattr(nd, "params", None)
        if isinstance(params, tuple):
            names.update(p.name for p in params if isinstance(p, n.Parameter))
    return frozenset(names)


def _may_be_a_membership(nd: n.DomainQuery, cats: _Categories) -> bool:
    """Whether a collection set may be `x in <query>` written without its
    parentheses: its noun as written is a name the game binds, and is not the
    plural of a noun a collection form ranges by."""
    return (
        nd.kind == "set"
        and nd.source is not None
        and nd.spelled in cats.bound_names
        and (nd.binder not in cats.collection_nouns or not nd.spelled.endswith("s"))
    )


def _membership_capture(
    nd: n.DomainQuery, cats: _Categories, bag: DiagnosticBag
) -> frozenset[str] | None:
    """A collection set over a noun nothing ranges by, read in the noun's
    lexical scope: where the noun names a value there, it is `x in <query>`
    written without its parentheses, and the refusal names the sentence that
    checks; elsewhere the noun is refused. None where the refusal is the
    capture's, else the binders the refused noun's fixes would bind."""
    assert nd.source is not None
    fixes = frozenset((*cats.collection_nouns, content_noun(cats.flavor, plural=False)))
    if _classify(nd.spelled, cats) is None and nd.binder in cats.collection_nouns:
        plural = n.collection_query_head(nd.kind, nd.spelled + "s")
        bag.error(f"`{nd.spelled} in …` needs the plural noun -- write `{plural} in …`", nd.span, code=Code.WRONG_SPELLING)
        return fixes
    if _classify(nd.spelled, cats) is None:
        universe = (
            f"declared position domains: {', '.join(sorted(cats.collection_nouns - {LINE_NOUN}))}"
            if cats.collection_nouns - {LINE_NOUN}
            else "this game declares no position domains"
        )
        # A collection set (the one kind this capture reads) takes the plural
        # of a collection noun or of the content noun.
        bag.unknown(
            f"unknown collection noun '{nd.binder}' -- {universe}",
            nd.spelled,
            {noun + "s" for noun in fixes},
            nd.span,
            code=Code.UNKNOWN_NAME,
        )
        return fixes
    source = n.short_spelling(nd.source)
    if isinstance(nd.source, n.NameRef) and nd.source.name in _query_nouns(cats):
        # `cells`, `players`: the source is a query's own noun, so the query
        # it began is parenthesized.
        fixed = f"{nd.spelled} in ({source} where <pred>)"
    else:
        fixed = f"{nd.spelled} in {source or '<collection>'} and <pred>"
    bag.error(
        f"`{nd.spelled} in {source or '…'} where …` reads as a set gathered over "
        f"`{nd.spelled}`, and `{nd.spelled}` is a value here -- a membership "
        f"test against a query is parenthesized, and a membership beside a "
        f"condition is joined with `and`: write `{fixed}`",
        nd.span,
        code=Code.NEEDS_PARENTHESES,
    )
    return None


def _query_nouns(cats: _Categories) -> frozenset[str]:
    """The plural nouns a query begins with where a membership's right side
    would be one: the position domains' plurals and the player register's."""
    positions = cats.collection_nouns - {LINE_NOUN}
    players = {name + "s" for name in role_names(frozenset({Role.PLAYER}))}
    return frozenset({noun + "s" for noun in positions} | players)
