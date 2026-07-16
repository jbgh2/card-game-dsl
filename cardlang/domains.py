"""The closed registry of *quantifiable domains* — the finite value sets the
language can range a binder or a move parameter over.

One row per domain, one column per facet the rest of the engine used to
re-derive for itself:

| domain   | type   | binder type   | binds actor | `for each` | `each … simultaneously` | move params      |
|----------|--------|---------------|-------------|------------|-------------------------|------------------|
| `player` | Player | `TPlayer`     | yes (seat)  | yes        | yes                     | `Player`         |
| `team`   | Team   | `TTeam`       | no          | yes        | no                      | —                |
| `suit`   | Suit   | `TEnum(Suit)` | no          | yes        | no                      | `Suit`, `Suit?`  |
| `rank`   | Rank   | `TEnum(Rank)` | no          | yes        | no                      | `Rank`           |

The two namespaces are now one row, not two tables: the lowercase `id` is the
role noun the *statement* surface spells (`for each player p`, `any suit
where …`), and `type_name` is the capitalised spelling the *declaration*
surface uses (`move_type bid(s: Suit)`). They were previously two disjoint
registries — `ROLES`/`ROLE_TYPES` keyed lowercase, `enumerate_domain` keyed
capitalised — with nothing relating `player` to `Player`.

`binds_actor` is the seat/value asymmetry as data. A SEAT domain's member *is*
an actor, so `for each player p:` rebinds `ctx.acting_as(p)` and a decision in
the body knows who is choosing; a VALUE domain's member is a bare enum value
and carries no actor. That fact was an if-chain in `runtime/execute.py::_for_each`;
it is now a column, and `_for_each` is a table walk.

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
  empty when the game declares none — hence resolve's `has_ranking` wall on
  Rank-parameterized moves.

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

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Callable, Sequence

from cardlang.types import TAny, TEnum, TPlayer, TTeam, Type

if TYPE_CHECKING:  # pragma: no cover - typing only, no runtime import cycle
    from cardlang.runtime.state import Ctx, RuntimeState


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


@dataclass(frozen=True)
class Domain:
    """One quantifiable domain, with every facet the engine derives from it."""

    # The canonical id: the `for each <id>` role noun, the `any <id> where`
    # quantifier noun, and the implicit binder name.
    id: str
    # The declared-type spelling, the other half of what used to be two
    # namespaces (`player` <-> `Player`).
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
    members: Callable[["Ctx"], list[Any]]
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
    zone_key_of: Callable[["RuntimeState", int], int | None] | None = None


DOMAINS: tuple[Domain, ...] = (
    Domain(
        id="player",
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
        id="team",
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
        id="suit",
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
        id="rank",
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

BY_ID: dict[str, Domain] = {d.id: d for d in DOMAINS}

# Roles `for each <role> <binder>` may range over (resolve's `_ITERATION_ROLES`).
ITERABLE_ROLES: frozenset[str] = frozenset(d.id for d in DOMAINS if d.iterable)

# Roles `each <role> simultaneously:` may range over — seat domains only.
SIMULTANEOUS_ROLES: frozenset[str] = frozenset(d.id for d in DOMAINS if d.simultaneous)

# Roles a zone family may be indexed by / a zone type owned by (`hand[player]`,
# `Hand<player>`, `captured[team]`): exactly the domains in which an observer
# has a key of their own. Resolve's wall, typecheck's subscript typing, the
# zone store's key sets, and the observation layer's ownership test all read
# this table rather than re-spelling {player, team}.
ZONE_INDEX_ROLES: frozenset[str] = frozenset(
    d.id for d in DOMAINS if d.zone_key_of is not None
)


def zone_observer_key(role: str, rs: "RuntimeState", observer: int) -> int | None:
    """The observer's own key in a zone family indexed by `role` — their seat,
    their team. The ownership half of `zone_key_of`; raises (rather than
    guessing player keying, as the old `== "team"` sites did) for a role no row
    marks zone-indexable, because resolve rejects those before a game runs."""
    row = BY_ID.get(role)
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


def role_type(role: str) -> Type:
    """The type a `for each <role>` / `any <role>` binder carries. The registry is
    closed and resolve rejects anything outside it; the `TAny` fallback is a
    backstop for the permissive walks that run before that rejection."""
    row = BY_ID.get(role)
    return row.binder_type if row is not None else TAny()


def binds_actor(role: str) -> bool:
    """Whether binding a member of this domain also rebinds the acting player —
    true for a seat domain, false for a value domain. The one place `for each`'s
    seat/value asymmetry is decided."""
    row = BY_ID.get(role)
    return row is not None and row.binds_actor


def role_members(role: str, ctx: "Ctx") -> list[Any]:
    """The runtime domain of one role: the players/teams/suits/ranks a `for each
    <role>` or a quantifier binds over, in iteration order. The ONE runtime
    member enumerator — `runtime/evaluate.py` (quantifiers) and
    `runtime/execute.py` (`for each`) both call it rather than re-deriving."""
    row = BY_ID.get(role)
    if row is None:
        raise AssertionError(f"unknown quantifier role '{role}' (resolve rejects these)")
    return row.members(ctx)


def role_static_members(role: str, sources: DomainSources) -> list[Any]:
    """A role's members at DECLARATION time — what a static analysis can know about
    `for each <role>` without running the game. The deck-capacity gate is the
    consumer: it must know how many times a loop body runs, and it used to assume
    "players, or once" — so `for each suit s: deal 15 cards …` counted as ONE
    iteration, demanded 4x what the gate checked, passed, and died mid-deal on a
    bare ValueError. Reading the row instead makes that count a fact of the table."""
    row = BY_ID.get(role)
    if row is None:
        raise AssertionError(f"unknown role '{role}' (resolve rejects these)")
    return row.static_members(sources)


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
    reaches it, and loud over what should not."""
    row = BY_PARAM_DOMAIN.get(type_name)
    if row is None:
        raise NotImplementedError(f"move parameter domain '{type_name}' not supported")
    values = row.static_members(sources)
    if type_name.endswith("?"):
        values.append(None)
    return values
