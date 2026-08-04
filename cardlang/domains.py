"""The closed registry of *quantifiable domains* — the finite value sets the
language can range a binder or a move parameter over.

One row per domain, one column per facet the rest of the engine needs —
derived once here rather than re-derived by each consumer:

| domain   | type   | binder type   | binds actor | `for each` | `each … simultaneously` | move params      |
|----------|--------|---------------|-------------|------------|-------------------------|------------------|
| `player` | Player | `TPlayer`     | yes (seat)  | yes        | yes                     | `Player`         |
| `team`   | Team   | `TTeam`       | no          | yes        | no                      | —                |
| `suit`   | Suit   | `TEnum(Suit)` | no          | yes        | no                      | `Suit`, `Suit?`  |
| `rank`   | Rank   | `TEnum(Rank)` | no          | yes        | no                      | `Rank`           |

The two namespaces are one row, not two tables: the `id` is the role noun
the *statement* surface spells (`for each player p`, `any suit where …`),
and `type_name` is the capitalised spelling the *declaration* surface uses
(`move_type bid(s: Suit)`). One row relates `player` to `Player`; split
across two registries keyed differently, nothing would.

The `id` is a `Role` — the enum below, which is THE definition site for the
role ids and the type every consumer dispatches over. A role that
participates in a decision is a `Role` all the way to the decision, so
comparing one against a string literal is a `mypy --strict` error; the one
bridge from parsed text is `role_of`. Two functions here deliberately still
take a NAME (`role_static_members`, `zone_observer_key`), because their
domain is the registry PLUS the calling game's declared position domains,
so classifying the name is part of what they answer.

`binds_actor` is the seat/value asymmetry as data. A SEAT domain's member *is*
an actor, so `for each player p:` rebinds `ctx.acting_as(p)` and a decision in
the body knows who is choosing; a VALUE domain's member is a bare enum value
and carries no actor. That fact is a column here rather than an if-chain in
`runtime/execute.py::_for_each`, which is a table walk over it.

Consumers: `resolve.py` (`_ITERATION_ROLES` = the `iterable` column,
`_FIXED_DOMAINS` = the union of `param_domains`, the `each … simultaneously`
gate = the `simultaneous` column), `typecheck.py` (`role_type`),
`runtime/evaluate.py` and `runtime/execute.py` (`role_members`, `binds_actor`),
`runtime/mechanics.py` and `openspiel/encoding.py` (`enumerate_domain`).

A leaf module (it imports only `cardlang.types`; `Ctx` is a `TYPE_CHECKING`
import), so the parse front end, the checker and the runtime can all read the
one table without a cycle.

Two members, one domain — the deliberate divergence
---------------------------------------------------
`members` (runtime, per-`Ctx`) and `static_members` (the action space's
declaration-time domain) are separate columns *on purpose*, and `rank` is why:

- `for each rank` / `any rank where …` iterate `rs.ranks` — the declared
  `ranking:` if there is one, else deck order. Always non-empty.
- a `Rank` *move parameter* enumerates the declared `ranking:` only
  (`rs.rank_index` at runtime, `game.ranking` in the action space), which is
  empty when the game declares none — hence resolve's `has_ranking`
  Owner Guard on Rank-parameterized moves.

A game with `for each rank` and no `ranking:` is legal and iterates deck order;
a `Rank` parameter in that same game is a compile error. Folding the two
accessors into one would break one of those two facts, so the table keeps both
columns.

Known outlier / residual: `Card`
--------------------------------
`Card` is deliberately NOT a row. It is a legal move-parameter domain, but its
domain is *state-dependent* (the actor's live hand, which changes every play)
and *container-anchored* (it reads `hand[actor]`, not the deck's value sets),
and its OpenSpiel action ids are the shared card block rather than a vocab
entry. `mechanics.param_domain` handles it specially, ahead of this table, and
`enumerate_domain` refuses it. It is neither iterable as a role nor a binder
type here — so it has no honest row, and a fabricated one would be four dead
cells plus a lie in the `members` column.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from cardlang.types import TEnum, TPlayer, TTeam, Type

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cycle
    from cardlang.runtime.state import Ctx, RuntimeState


class Role(enum.Enum):
    """The role ids, as a type the checker dispatches over.

    THE definition site: `Domain.id` is a `Role`, so the enum and the table
    cannot disagree — there is no second list to keep in step. Widening the
    registry means adding a member here, and every exhaustive `match` over
    `Role` then fails to compile until it answers for the new row, which is
    what makes this a rung-1 Owner Guard (decisions.md "Prefer the guard you
    cannot need") rather than a scrape that has to be maintained.

    Deliberately NOT a `str` subclass. A `StrEnum` would compare equal to its
    own spelling, so `role == "team"` would keep type-checking and keep
    working — the whole class of drift this type exists to end
    (`tests/test_role_comparison_pin.py`) would stay invisible. As a plain
    `Enum` under `mypy --strict`, comparing a `Role` against a string literal
    is a `comparison-overlap` error and so is `role in ("team", "player")`:
    the checker owns what a token scrape used to.

    The VALUE is the surface spelling — the `for each <id>` role noun and the
    `any <id> where` quantifier noun — and is what a diagnostic prints. It is
    also the only bridge from parsed text, crossed in exactly one place
    (`role_of`), because a name arriving from a game's source is not yet known
    to be a role at all.
    """

    PLAYER = "player"
    TEAM = "team"
    SUIT = "suit"
    RANK = "rank"


@dataclass(frozen=True)
class DomainSources:
    """The declaration-time value sets a move-parameter domain enumerates from.

    Two call sites build one of these, from the two origins that must agree:
    `mechanics.param_domain` from the live runtime state (`rs.suits`,
    `rs.rank_index`, `rs.seating.players`) and `openspiel/encoding.py` from the
    game AST (`deck_suits(game.deck)`, `game.ranking`, `game.players.low`).
    Passing them as one struct — rather than three positional kwargs threaded
    through every enumerator — is what lets the domain table own the lookup:
    a row says *which* source it reads, the caller only says *where the sources
    came from*."""

    suits: Sequence[Any]
    ranks: Sequence[str]
    players: Sequence[int]
    teams: Sequence[Any] = ()
    # Declared position domains (decisions.md "Position domains and
    # positional zones"): name -> ordered members. Per-game, unlike every
    # other source (which reads a fixed table through per-game values):
    # `driver.py` builds it from `rs.position_domains` and
    # `openspiel/encoding.py` from `game.positions` — the same origin
    # (`PositionDecl.members`) both ways, so the runtime candidate
    # enumeration and the static action space cannot diverge. A declared
    # name can never collide with a built-in spelling (resolve rejects the
    # collision), so the lookup order below is unambiguous.
    positions: Mapping[str, Sequence[int] | Sequence[str]] = field(default_factory=dict)
    # The board-minted movement-direction domain (decisions.md "Boards and
    # cells", rung-2 movement): name -> ordered members. A SEPARATE source
    # from `positions` (the `dir` domain is deliberately absent from
    # `game.positions`), consulted ONLY by the move-parameter enumeration --
    # never a zone index, quantifier binder or `for each` role. Both builders
    # read it off the same board family entry (`board_domains.directions_of`):
    # `driver.py` via `rs.direction_domains`, `openspiel/encoding.py` from the
    # game AST -- so the runtime candidate enumeration and the static action
    # space cannot diverge. A minted name can never collide with `positions`
    # or a built-in spelling (resolve rejects the collision).
    directions: Mapping[str, Sequence[str]] = field(default_factory=dict)


@dataclass(frozen=True)
class Domain:
    """One quantifiable domain, with every facet the engine derives from it."""

    # The canonical id. A `Role`, not a string: the enum above is the one
    # definition site, and this field is what ties each row to its member.
    id: Role
    # The declared-type spelling (`Player` to the id's `player`).
    type_name: str
    # What a `for each`/quantifier binder over this domain types as.
    binder_type: Type
    # A SEAT domain (its members are actors): `for each` rebinds `acting_as`.
    # A VALUE domain does not.
    binds_actor: bool
    # Legal in `for each <id> <binder>:`.
    iterable: bool
    # Legal in `each <id> simultaneously:` — seat-only: a value domain has no
    # actor to move simultaneously.
    simultaneous: bool
    # The move-parameter spellings this domain admits, in enumeration order.
    # `()` = not a declarable parameter domain. An admitted `?` spelling
    # enumerates the domain plus the `None` member (`Suit?` = the suits plus the
    # no-trump strain, which ranks last); a `?` spelling NOT listed here is
    # rejected rather than silently read as its plain form.
    param_domains: tuple[str, ...]
    # The domain's members at runtime, in iteration order.
    members: Callable[[Ctx], list[Any]]
    # The domain's members at declaration time, for the static action space.
    static_members: Callable[[DomainSources], list[Any]]
    # The observer's own key in a zone family indexed by this domain — their seat
    # for `player`, their team for `team`. `None` means the domain cannot index
    # or own a zone at all: a suit has no member an observer IS, so `hand[suit]`
    # is meaningless. This one column is therefore BOTH facts the zone layer
    # needs: `ZONE_INDEX_ROLES` (which roles `hand[<role>]` / `Hand<role>` may
    # name) derives from it being non-None, and ownership visibility (does this
    # observer see the family instance at `key`?) is the function itself. It
    # replaces an `== "team"` re-spelling at five consumer sites (resolve,
    # typecheck, state, driver, observe), each of which silently defaulted every
    # non-team role to player keying.
    zone_key_of: Callable[[RuntimeState, int], int | None] | None = None


DOMAINS: tuple[Domain, ...] = (
    Domain(
        id=Role.PLAYER,
        type_name="Player",
        binder_type=TPlayer(),
        binds_actor=True,
        iterable=True,
        simultaneous=True,
        param_domains=("Player",),
        members=lambda ctx: list(ctx.rs.seating.players),
        static_members=lambda src: list(src.players),
        zone_key_of=lambda rs, observer: observer,
    ),
    Domain(
        id=Role.TEAM,
        type_name="Team",
        binder_type=TTeam(),
        binds_actor=False,
        iterable=True,
        simultaneous=False,
        param_domains=(),
        members=lambda ctx: list(ctx.rs.teams),
        static_members=lambda src: list(src.teams),
        zone_key_of=lambda rs, observer: rs.team_of.get(observer),
    ),
    Domain(
        id=Role.SUIT,
        type_name="Suit",
        binder_type=TEnum("Suit"),
        binds_actor=False,
        iterable=True,
        simultaneous=False,
        param_domains=("Suit", "Suit?"),
        # Deck order (`rs.suits` is the deck's actual card suits, so a
        # non-standard deck enumerates its own).
        members=lambda ctx: list(ctx.rs.suits),
        static_members=lambda src: list(src.suits),
    ),
    Domain(
        id=Role.RANK,
        type_name="Rank",
        binder_type=TEnum("Rank"),
        binds_actor=False,
        iterable=True,
        simultaneous=False,
        param_domains=("Rank",),
        # `ranking:` order (strongest first) when declared, else deck order —
        # NOT the same source as `static_members`; see the module docstring.
        members=lambda ctx: list(ctx.rs.ranks),
        static_members=lambda src: list(src.ranks),
    ),
)

# --- the derived views the consumers read ----------------------------------

BY_ID: dict[Role, Domain] = {d.id: d for d in DOMAINS}

# The ONE bridge from parsed text to the type. A name reaching this function is
# whatever a game's source said; only a name the registry knows comes back as a
# `Role`, and everything downstream of the answer is typed.
#
# `None` is not "invalid" — a role slot's domain is the registry PLUS a game's
# declared position domains (decisions.md "Position domains and positional
# zones"), which the registry cannot know about. So the caller decides what a
# miss means: resolve's `for each` Owner Guard consults its game's positions
# and only then refuses, while `role_type` treats a miss as a registry
# divergence and raises. Returning `None` rather than raising is what lets
# both readings exist without a second lookup.
_BY_NAME: dict[str, Role] = {r.value: r for r in Role}


def role_of(name: str) -> Role | None:
    """The registry role `name` spells, or `None` if the registry has no such
    row. See `_BY_NAME` on why a miss is the caller's to interpret."""
    return _BY_NAME.get(name)


def require_role(name: str, what: str) -> Role:
    """`role_of` for a position resolve has ALREADY checked against a subset of
    the registry — a quantifier's four grammar productions, a `for each` role
    after the iteration-role check, a state variable's index.

    Those callers hold a name that must classify, so a miss is a registry
    divergence (a compiler bug) rather than an author error, and it raises in
    compiler currency naming the position. Distinct from `role_of`, which the
    Owner Guards themselves call: an Owner Guard must be able to see a miss
    and report it as a diagnostic, which is why the two readings are two
    functions rather than one with a flag. `what` names the position, so the
    crash says which pass's Owner Guard was supposed to have run."""
    role = role_of(name)
    if role is None:
        raise AssertionError(
            f"'{name}' is not a {what} (resolve rejects these) — a role "
            f"reaching here without a registry row means a wall was bypassed, "
            f"not that the game is wrong"
        )
    return role


def role_names(roles: frozenset[Role]) -> list[str]:
    """The surface spellings of a role set, sorted — for a diagnostic that
    lists what it would have accepted. One helper rather than a
    `sorted(r.value for r in …)` at each of the six sites that print one."""
    return sorted(r.value for r in roles)


# Roles `for each <role> <binder>` may range over (resolve's `_ITERATION_ROLES`).
ITERABLE_ROLES: frozenset[Role] = frozenset(d.id for d in DOMAINS if d.iterable)

# Roles `each <role> simultaneously:` may range over — seat domains only.
SIMULTANEOUS_ROLES: frozenset[Role] = frozenset(d.id for d in DOMAINS if d.simultaneous)

# Roles that enumerate deck content (`rs.suits`/`rs.ranks`) rather than seats —
# the ones whose parameter domain is a card axis (`Suit`/`Suit?`/`Rank`). A
# piece game has no role surface for its own axes (side/kind), so the flavor
# guards reject these roles there; derived here so a new card-axis domain joins
# the set rather than a hand-kept `{suit, rank}`.
CARD_AXIS_ROLES: frozenset[Role] = frozenset(
    d.id for d in DOMAINS if any(pd.rstrip("?") in ("Suit", "Rank") for pd in d.param_domains)
)

# Roles a zone family may be indexed by / a zone type owned by (`hand[player]`,
# `Hand<player>`, `captured[team]`): exactly the domains in which an observer
# has a key of their own. Resolve's Owner Guard, typecheck's subscript typing,
# the zone store's key sets, and the observation layer's ownership test all
# read this table rather than re-spelling {player, team}.
ZONE_INDEX_ROLES: frozenset[Role] = frozenset(
    d.id for d in DOMAINS if d.zone_key_of is not None
)


def index_phrase(index: Role | None) -> str:
    """How a state variable's index reads in a diagnostic: "a scalar" when it
    has none, else "per-<role>".

    Rendered from the ROLE, never from the truthiness of the field. Both sides
    of the library `requires` contract used to render as `"per-player" if
    have.index else "a scalar"`, which collapses a closed domain to a boolean
    and prints "requires it to be per-player, but declares it as per-player"
    for a `[team]`-against-`[player]` mismatch — the two roles Bridge and
    Belote both use (issue #144)."""
    return "a scalar" if index is None else f"per-{index.value}"


def zone_observer_key(role: str, rs: RuntimeState, observer: int) -> int | None:
    """The observer's own key in a zone family indexed by `role` — their seat,
    their team. The ownership half of `zone_key_of`; raises (rather than guessing
    player keying) for a role no row marks zone-indexable, because resolve
    rejects those before a game runs.

    A declared POSITION domain (decisions.md "Position domains and positional
    zones") is indexable but unowned — no observer *is* a column — so it
    returns `None`: never equal to any instance key, hence every observer
    projects such a family through the zone type's `others` column. Both
    ownership consumers (runtime `observe._is_owner` and the proof oracle
    `tests/openspiel_ready/partition._is_owner`) read this one function, so
    the unowned rule cannot drift between them.

    Takes a NAME, not a `Role`, and is one of the two functions here that
    genuinely should: its domain is the registry plus the calling game's
    declared position domains, so the argument is an index-domain name whose
    class is exactly what this function decides. The conversion is the first
    thing it does after the position branch."""
    if role in rs.position_domains:
        return None
    id_ = role_of(role)
    row = BY_ID[id_] if id_ is not None else None
    if row is None or row.zone_key_of is None:
        raise AssertionError(
            f"'{role}' is not a zone-index role (resolve rejects these)"
        )
    return row.zone_key_of(rs, observer)

# The closed set of statically enumerable move-parameter domains (resolve's
# `_FIXED_DOMAINS`), matched by exact string — never by stripping a trailing
# `?`. `Card` is absent: state-dependent, handled ahead of this table.
PARAM_DOMAIN_ORDER: tuple[str, ...] = tuple(s for d in DOMAINS for s in d.param_domains)
PARAM_DOMAINS: frozenset[str] = frozenset(PARAM_DOMAIN_ORDER)
BY_PARAM_DOMAIN: dict[str, Domain] = {s: d for d in DOMAINS for s in d.param_domains}

# Move-parameter domains that enumerate deck content: the card-axis roles'
# domains (Suit/Suit?/Rank) plus the state-dependent Card. A piece game rejects
# a move parameterized by one; Player (a seat) and declared position domains
# stay legal in both flavors.
CARD_PARAM_DOMAINS: frozenset[str] = frozenset(
    pd for d in DOMAINS if d.id in CARD_AXIS_ROLES for pd in d.param_domains
) | {"Card"}


# Every `Role` has a row, which is what makes the three lookups below total by
# construction — `BY_ID[role]`, no miss branch. Each of them used to take a
# `str` and raise on an unknown one, and that raise was the guard: it proved
# the lookup could not degrade to a silent default (`binds_actor` answering
# `False` for a missing seat domain would have run the loop with the wrong
# actor). The `Role` parameter now makes an unknown role unwritable, so the
# only way the lookup could still miss is a member declared here without a row
# — which is this one assert, over a four-element domain, instead of three
# raises no caller can reach (decisions.md "Prefer the guard you cannot need":
# the fact moved from rung 2 to rung 1, and this is the residue that has to
# stay).
assert set(BY_ID) == set(Role), (
    f"every Role must carry a row: {sorted(r.value for r in set(Role) - set(BY_ID))} "
    f"declared with no row in DOMAINS"
)


def role_type(role: Role) -> Type:
    """The type a `for each <role>` / `any <role>` binder carries.

    Every role-bearing surface draws from this registry: quantifier roles are
    fixed by the parser (four hard-coded spellings), and `for each` /
    simultaneous / zone-index / state-index roles are each guarded by resolve
    against a subset of the registry (`tests/test_permissive_top.py` pins all
    five role sets as subsets). It used to return the permissive `TAny` for an
    unknown role, which types the binder as the top and silently exempts every
    use of it from every type check."""
    return BY_ID[role].binder_type


def binds_actor(role: Role) -> bool:
    """Whether binding a member of this domain also rebinds the acting player —
    true for a seat domain, false for a value domain. The one place `for each`'s
    seat/value asymmetry is decided."""
    return BY_ID[role].binds_actor


def role_members(role: Role, ctx: Ctx) -> list[Any]:
    """The runtime domain of one role: the players/teams/suits/ranks a `for each
    <role>` or a quantifier binds over, in iteration order. The ONE runtime
    member enumerator — `runtime/evaluate.py` (quantifiers) and
    `runtime/execute.py` (`for each`) both call it rather than re-deriving."""
    row = BY_ID[role]
    return row.members(ctx)


def role_static_members(role: str, sources: DomainSources) -> list[Any]:
    """A role's members at DECLARATION time — what a static analysis can know about
    `for each <role>` without running the game. The deck-capacity gate is the
    consumer: it must know how many times a loop body runs. Without this, it would
    assume "players, or once" — so `for each suit s: deal 15 cards …` would count
    as ONE iteration, demand 4x what the gate checked, pass, and fail mid-deal,
    where the executor requires a source to hold at least the cards a deal asks
    for. Reading the row makes that count a fact of the table.

    A declared position domain resolves ahead of the table (its name can never
    collide with a row id — resolve rejects the collision), so the zone store
    can key a position-indexed family from the same sources struct.

    The second of the two functions here that take a NAME rather than a `Role`,
    and for the same reason as `zone_observer_key`: the domain really is the
    registry plus this game's declared positions, so classifying the name is
    part of the answer. The raise below is therefore still live — it is the
    Shadow Guard over what is left after the position branch, not a lookup a
    `Role` parameter could have made total."""
    if role in sources.positions:
        return list(sources.positions[role])
    id_ = role_of(role)
    if id_ is None:
        raise AssertionError(f"unknown role '{role}' (resolve rejects these)")
    return BY_ID[id_].static_members(sources)


def enumerate_domain(type_name: str, sources: DomainSources) -> list[Any]:
    """The *static* value-domain a parameterized move ranges over, in a fixed
    order so the flattened candidate list is deterministic — a table lookup on
    the declared-type spelling, not a hand-written dispatch.

    Matched by exact string, never by stripping a trailing `?`: only the
    spellings a row actually lists are admitted. `Suit?` is listed and appends
    the `None` member (the no-trump strain, which ranks last); `Rank?`/`Player?`
    parse (payload types are generically optional-able) but are not listed by
    any row, so they raise here rather than silently enumerating the plain
    `Rank`/`Player` domain instead. `Card` is likewise absent (state-dependent;
    `mechanics.param_domain` handles it ahead of this table) and bounded-`Integer`
    is rejected at resolve time (deferred) — so this lookup is total over what
    reaches it, and loud over what should not.

    A declared position domain (`src : column`) enumerates its declared
    members, checked ahead of the table — resolve's collision Owner Guard
    guarantees a declared name never shadows a built-in spelling. A
    board-minted direction domain (`along : dir`) is the SIBLING branch: a
    separate source, checked the same way, so it enumerates its members
    without riding `positions`."""
    if type_name in sources.positions:
        return list(sources.positions[type_name])
    if type_name in sources.directions:
        return list(sources.directions[type_name])
    row = BY_PARAM_DOMAIN.get(type_name)
    if row is None:
        raise NotImplementedError(f"move parameter domain '{type_name}' not supported")
    values = row.static_members(sources)
    if type_name.endswith("?"):
        values.append(None)
    return values
