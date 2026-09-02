"""Declared reads for game-local runtime [[primitive]]s.

A game-local primitive (`cardlang/runtime/<game>.py`, plus the per-game
auction outcomes in `primitives.py`) is sanctioned Python for pure value
computation (library.md "Native functions"; kernel-migration.md). It reads
live `RuntimeState` by the zone / [[state-variable]] name the game file
declares —
a coupling the front-end pipeline cannot see: nothing about
`zones { influence[player] : Hand<player> }` tells resolve or typecheck that
`coup.py` also spells this name. Undeclared, that coupling surfaces as a
`KeyError` mid-playout the first time either side renames
(tests/metamorphic/rename.py first found it empirically).

This module is the declaration. `PRIMITIVE_READS` is the single registry of
every zone/state name each primitive module reads, keyed by (module, game
file); the accessors below are the only sanctioned way for a primitive to
touch state by name. The registry is pinned from both sides by
tests/test_primitive_reads.py: every declared name against the game file's
actual declarations (a rename in the `.cardlang` fails the test), and every
module's accessor-call literals against its rows exactly (an undeclared or
stale read fails the test). tests/metamorphic/rename.py derives its
coupled-name exclusions from this registry rather than keeping its own copy.

The declared-reads idea is stage 3 of
docs/design-notes/primitive-sidecars.md, landed at the Python layer: the
sidecar design moves these declarations into a `primitives { }` block in the
game file itself, at which point this table derives from the game files
instead of being authored here.

Contract:
  assumes      the game file named by a row parses and declares the names
               the row lists (pinned statically by tests/test_primitive_reads.py;
               re-checked at runtime by the accessors).
  establishes  every name-keyed primitive read is declared — in
               `PRIMITIVE_READS`, or in the `reads` clause of the game's own
               `primitives { }` entry — and fails as a typed
               `PrimitiveReadError` naming the declaration to extend, never
               as a bare `KeyError`, when either side of the coupling
               drifts. That holds through both doors onto a declared read:
               the accessors below, and a `GameReads` bundle's own halves,
               whose miss is the one the compile stage cannot pre-empt (that
               a declared read SUFFICES for its implementation is a fact
               about Python). A [[phase-scoped-read]] materializes through the
               same frame walk as a game-level one — there is no scope arm
               here — and the one miss a scope could explain names the phase
               and resolve's containment check as its Owner (`_scoped_state`).
  illegal after it
               direct name-keyed `RuntimeState`/`ZoneStore` access
               (`rs.get`/`rs.set`/`zones.single`/`zones.instance`/
               `zones.families[...]`/`zones.singles[...]`) in any
               `cardlang/runtime/` module outside the engine core's explicit
               exemption list (enforced by the AST scan in
               tests/test_primitive_reads.py).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Mapping
from collections.abc import Mapping as _Mapping
from collections.abc import Sequence as _Sequence
from collections.abc import Set as AbstractSet
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, cast

from cardlang.runtime.state import RuntimeState, Zone, elements
from cardlang.runtime.values import Card, Player
from cardlang.stdlib.zones import identity_to_all
from cardlang.types import TAny, TCollection

# Atomic leaves: immutable, never descended. `str`/`bytes` are sequences (of
# chars/ints) but must NOT be shredded; `bytearray` is deliberately ABSENT —
# it is a MUTABLE sequence and gets converted, not passed through.
_ATOMIC: tuple[type, ...] = (str, bytes, bool, int, float, type(None), Enum)


def coerce_args(sig: Any, args: list[Any]) -> list[Any]:
    """Freeze the argument list of one native call, before it crosses into
    Builtin or Primitive code.

    A collection-typed expression evaluates to either a Zone or a plain list
    (the zone facet is not part of assignability, so `gin_valid_meld(hand[p])`
    typechecks), and the adapters are bare Python that iterates — a
    TCollection param receives elements, never a Zone handle. `elements()`
    yields the Zone's LIVE `.cards` list, so the coercion additionally
    `deep_freeze`s it: the positional args are the second channel a primitive
    can touch (the bundles are the first), and `cards.clear()` on a live zone
    list would corrupt engine state exactly as a bundle write would.
    A SCALAR `Card` argument (a `TCard` param —
    `canasta_stage_ok(p, card)`) is frozen too: evaluation preserves the
    engine's `Card` by identity, and a frozen+slots `Card` is still mutable
    via `object.__setattr__`, so an unfrozen scalar card is the same leak as
    an unfrozen collection. The freeze is SIGNATURE-DRIVEN, not blanket: a
    TAny param passes RAW, because its adapter dispatches on the shape itself
    (`suit_of`: a card or a single-card zone — blanket coercion broke the
    schnapsen trump indicator, and `deep_freeze` would refuse a Zone). Every
    other param is `deep_freeze`d: a copy for a `Card`, a no-op for the
    immutable scalars (`Player`, `Integer`, `Rank`, ...). The registry side is
    pinned by tests/test_native_call_boundary.py (every TCollection param probed
    with a Zone, the TAny set pinned, no param zone=True).

    It lives here, with `deep_freeze`, rather than with either dispatch half:
    the two halves must not depend on each other, and one shared coercion is
    also the only affordable one — `deep_freeze` dominates playout cost, so
    coercing per half would double it for every Primitive call.
    """
    coerced: list[Any] = []
    for p, a in zip(sig.params, args):
        if isinstance(p, TCollection):
            coerced.append(deep_freeze(elements(a)))
        elif isinstance(p, TAny):
            coerced.append(a)  # raw: the adapter dispatches on the shape
        else:
            coerced.append(deep_freeze(a))  # copies a Card, no-ops scalars
    return coerced + args[len(sig.params) :]


def deep_freeze(value: Any) -> Any:
    """A structurally-immutable SNAPSHOT of `value`, recursively, to any depth.

    The bundles a primitive receives must expose nothing it can mutate: not
    just the outer container, but every mapping, sequence, set — and the
    mutable internals of any value WRAPPER — nested inside it, to the bottom.
    A shallow freeze is a false guarantee: an indexed state variable is a live
    `{player: value}` dict, a round-state frame nests a `played` list, and a
    `StructValue`'s `.fields` is a live dict behind a frozen dataclass, so
    `gr.state["coins"][p] = 0`, `facts.round_state["played"].append(...)` and
    `gr.state["contract"].fields[k] = ...` would each reach straight through
    and corrupt engine state.

    Every mutable level is REBUILT, so the result is a snapshot rather than a
    chain of read-only views over live objects. Mappings become
    `MappingProxyType`, sequences tuples, sets frozensets, `bytearray` bytes;
    a frozen+SLOTTED dataclass is rebuilt (never returned by identity) with
    each field frozen — `StructValue.fields` is where the field recursion
    bites, and the rebuild itself matters because `object.__setattr__` bypasses
    `frozen`, so returning the live `Card`/`Play` would let a primitive mutate
    the engine's value through that back door; a `replace` copy takes the hit
    on the copy instead. A dataclass that is NOT frozen, or is frozen but NOT
    slotted (so its `__dict__` stays writable and `obj.__dict__[f] = …`
    bypasses frozen), is refused. Anything that is neither a container nor a
    frozen+slotted dataclass must be a known atomic, or `deep_freeze` refuses
    it rather than passing a possibly-mutable object through as a false leaf.
    (Copying costs an allocation per value; the module-granular bundles make
    that a per-bind cost that stage 3's per-primitive `reads` will shrink.)"""
    if isinstance(value, _ATOMIC):
        return value
    if isinstance(value, _Mapping):
        # Keys are frozen too, not just values: a mapping keyed by a
        # mutable-but-hashable object (a dataclass with `unsafe_hash=True`)
        # would otherwise hand the live key back through iteration. A frozen
        # key (int/str/tuple/frozen dataclass) comes back equal with the same
        # hash, so lookups are unaffected; a mutable one is refused.
        return MappingProxyType(
            {deep_freeze(k): deep_freeze(v) for k, v in value.items()}
        )
    if isinstance(value, AbstractSet):
        return frozenset(deep_freeze(v) for v in value)
    if isinstance(value, bytearray):
        return bytes(value)  # a mutable builtin sequence -> immutable snapshot
    if isinstance(value, _Sequence):
        items = [deep_freeze(v) for v in value]
        if isinstance(value, tuple) and all(a is b for a, b in zip(items, value)):
            return value  # already an immutable tuple, unchanged: keep identity
        return tuple(items)
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        if not getattr(value, "__dataclass_params__").frozen:
            # A non-frozen dataclass cannot be snapshotted: even a field-frozen
            # `replace` copy stays writable (`box.value = …`), and the identity
            # fast path below would hand back the live object outright. Refuse,
            # same as a non-dataclass mutable leaf — the corpus value types are
            # all frozen, so this only fires on a NEW mutable one.
            raise TypeError(
                f"deep_freeze cannot snapshot the non-frozen dataclass "
                f"{type(value).__name__} — its attributes stay reassignable. "
                f"Make it frozen, or add a case."
            )
        if hasattr(value, "__dict__"):
            # `frozen=True` WITHOUT `slots=True` leaves a writable instance
            # `__dict__`: `obj.__setattr__` is blocked, but `obj.__dict__[f] =
            # …` bypasses it. Refuse rather than snapshot — the corpus value
            # types are all frozen+slots, so this only fires on a new one.
            raise TypeError(
                f"deep_freeze cannot treat {type(value).__name__} as immutable: "
                f"it is a frozen dataclass WITHOUT slots, so its __dict__ stays "
                f"writable (obj.__dict__[...] = ... bypasses frozen). Add "
                f"slots=True to the type."
            )
        # ALWAYS rebuild, never return by identity: `frozen=True, slots=True`
        # blocks `obj.field = …` but NOT `object.__setattr__(obj, field, …)`,
        # so returning the live object would let a primitive mutate the value
        # in engine state through that back door. A `replace` copy is a
        # distinct object — the same back door then hits the primitive's copy,
        # not `rs.mech_state`. (Python cannot fully sandbox a primitive, which
        # could `import` engine state or use `gc`; this closes the reachable-
        # through-a-handed-value channel, the one deep_freeze owns.)
        return dataclasses.replace(
            value, **{f.name: deep_freeze(getattr(value, f.name)) for f in dataclasses.fields(value)}
        )
    raise TypeError(
        f"deep_freeze cannot prove {type(value).__name__} immutable — it is "
        f"neither a known atomic, a container, nor a dataclass, so passing it "
        f"through as a leaf could expose mutable engine state. Add a case."
    )

_REGISTRY_NAME = "PRIMITIVE_READS (cardlang/runtime/reads.py)"


class PrimitiveReadError(RuntimeError):
    """A game-local primitive's state read failed its declaration: the name
    is not declared in `PRIMITIVE_READS`, or is declared but absent from the
    live runtime state (the game file and the primitive module drifted)."""


@dataclass(frozen=True)
class PrimitiveReads:
    """One primitive module's declared reads on behalf of one game.

    `module` is the repo-relative path of the Python module doing the
    reading; `game_file` the `docs/games/` basename whose declarations the
    names must match. A module serving several games (primitives.py's auction
    outcomes) has one row per game.

    `arrival_zones` declares which of the row's single zones the module also
    reads the [[arrival-record]] of — the (deciding actor, card) pairs the
    kernel retains per movement (issue #256). Bounded twice at bind time,
    loud on both: a name must be in the row's own `single_zones`, and the
    zone's declared type must project identity to EVERY observer
    (`stdlib.zones.identity_to_all`) — provenance of a concealed zone is not
    derivable from any observer's stream, so no primitive may range over it,
    legality context or otherwise. Zone FAMILIES are deliberately absent:
    no consumer reads a family's record, and the query surface over the
    recorded facts is issue #253's set of decisions."""

    module: str
    game_file: str
    state_vars: frozenset[str] = field(default=frozenset())
    zone_families: frozenset[str] = field(default=frozenset())
    single_zones: frozenset[str] = field(default=frozenset())
    arrival_zones: frozenset[str] = field(default=frozenset())


def _fs(*names: str) -> frozenset[str]:
    return frozenset(names)


PRIMITIVE_READS: tuple[PrimitiveReads, ...] = (
    PrimitiveReads(
        module="cardlang/runtime/bigtwo.py",
        game_file="big-two.cardlang",
        state_vars=_fs("opened"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/coup.py",
        game_file="coup.cardlang",
        state_vars=_fs("alive", "coins", "treasury"),
        zone_families=_fs("influence", "revealed"),
        single_zones=_fs("court_deck"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/cribbage.py",
        game_file="cribbage.cardlang",
        state_vars=_fs("seq_bits", "seq_len", "dealer"),
        zone_families=_fs("played"),
        single_zones=_fs("play_pile", "starter", "crib"),
    ),
    # An empty row, not a missing one: president.py's climb queries are pure
    # over their arguments, but the climb binder keys the module's bundle
    # from this row (primitives.climb_row), so the row must exist.
    PrimitiveReads(
        module="cardlang/runtime/president.py",
        game_file="president.cardlang",
    ),
    PrimitiveReads(
        module="cardlang/runtime/gin.py",
        game_file="gin-rummy.cardlang",
        zone_families=_fs("hand", "taken", "meldA", "meldB", "meldC"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/canasta.py",
        game_file="canasta.cardlang",
        state_vars=_fs(
            "pile_frozen", "team_melded", "meld_rank", "taking_pile", "score"
        ),
        zone_families=_fs(
            "hand", "stage",
            "meldA", "meldK", "meldQ", "meldJ", "meld10", "meld9",
            "meld8", "meld7", "meld6", "meld5", "meld4", "meld3b",
        ),
        single_zones=_fs("pile_top", "pile_rest"),
    ),
    # Tichu's CLIMB row, and its call-position Primitive is not on it: the
    # game declares `tichu_dragon_won` in its own block. What keeps the row is
    # `primitives.climb_row`, which hands the climb queries their module's row
    # at round time off a binding made at import — a namespace the block does
    # not cover. The queries take the hand as an argument, so the row declares
    # no zone or state read; it binds the module to its game.
    PrimitiveReads(
        module="cardlang/runtime/tichu.py",
        game_file="tichu.cardlang",
    ),
    # primitives.py's per-game functions: the auction outcomes and cribbage's
    # pegging-scorer call sites. One row per game served.
    PrimitiveReads(
        module="cardlang/runtime/primitives.py",
        game_file="bridge.cardlang",
        state_vars=_fs("made_bid", "high_bidder", "cur_strain", "cur_level", "doubled"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/primitives.py",
        game_file="cribbage.cardlang",
        single_zones=_fs("play_pile"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/primitives.py",
        game_file="pinochle.cardlang",
        state_vars=_fs("lead_bidder", "opener", "working_bid"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/primitives.py",
        game_file="french-tarot.cardlang",
        state_vars=_fs("lead_taker", "current_level"),
    ),
)

_BY_KEY: dict[tuple[str, str], PrimitiveReads] = {
    (r.module, r.game_file): r for r in PRIMITIVE_READS
}
# registry: a duplicate (module, game_file) key is an authoring defect in
# PRIMITIVE_READS itself, right above — unreachable from any game
# description; loud at first import of this module.
assert len(_BY_KEY) == len(PRIMITIVE_READS), "duplicate (module, game_file) row"


def row(module: str, game_file: str) -> PrimitiveReads:
    """The declared-reads row for `module` serving `game_file` — a module's
    one-time lookup of its own declaration. An unregistered pair is refused:
    a NEW primitive module (or a module serving a new game) declares its
    reads here first, and tests/test_primitive_reads.py then pins them."""
    r = _BY_KEY.get((module, game_file))
    if r is None:
        raise PrimitiveReadError(
            f"no declared-reads row for module {module!r} serving "
            f"{game_file!r} — declare the module's reads in {_REGISTRY_NAME} "
            f"before reading runtime state by name"
        )
    return r


def _undeclared(r: PrimitiveReads, kind: str, name: str, declared: frozenset[str]) -> PrimitiveReadError:
    return PrimitiveReadError(
        f"{r.module} (serving {r.game_file}) read undeclared {kind} {name!r} — "
        f"its row in {_REGISTRY_NAME} declares only {sorted(declared)}; "
        f"declare the read there (tests/test_primitive_reads.py pins the row "
        f"against {r.game_file}'s declarations)"
    )


def _missing(r: PrimitiveReads, kind: str, name: str) -> PrimitiveReadError:
    return PrimitiveReadError(
        f"{kind} {name!r}, declared in {_REGISTRY_NAME} for {r.module} "
        f"(serving {r.game_file}), is not in the live runtime state — the "
        f"game file and the primitive module have drifted; "
        f"tests/test_primitive_reads.py pins the row against "
        f"docs/games/{r.game_file}"
    )


def state(rs: RuntimeState, r: PrimitiveReads, name: str) -> Any:
    """A declared state-variable read (the accessor form of `rs.get`)."""
    if name not in r.state_vars:
        raise _undeclared(r, "state variable", name, r.state_vars)
    try:
        return rs.get(name)
    except KeyError:
        raise _missing(r, "state variable", name) from None


def family(rs: RuntimeState, r: PrimitiveReads, name: str) -> dict[int | str, Zone]:
    """A declared zone-family read (the accessor form of `zones.families[...]`)."""
    if name not in r.zone_families:
        raise _undeclared(r, "zone family", name, r.zone_families)
    fam = rs.zones.families.get(name)
    if fam is None:
        raise _missing(r, "zone family", name)
    return fam


def single(rs: RuntimeState, r: PrimitiveReads, name: str) -> Zone:
    """A declared single-zone read (the accessor form of `zones.single`)."""
    if name not in r.single_zones:
        raise _undeclared(r, "single zone", name, r.single_zones)
    z = rs.zones.singles.get(name)
    if z is None:
        raise _missing(r, "single zone", name)
    return z


def instance(rs: RuntimeState, r: PrimitiveReads, name: str, key: int | str) -> Zone:
    """A declared read of one instance of a zone family (the accessor form
    of `zones.instance`). The instance KEY is engine data (a seat or team id
    from `rs.seating`/`rs.teams`), not part of the declared coupling, but a
    wrong one still fails typed rather than as a bare `KeyError`."""
    fam = family(rs, r, name)
    try:
        return fam[key]
    except KeyError:
        raise PrimitiveReadError(
            f"zone family {name!r} (declared for {r.module} serving "
            f"{r.game_file}) has no instance keyed {key!r} — instance keys "
            f"come from the game's seating/teams, so a miss is the calling "
            f"primitive's error"
        ) from None


class _BundleHalf(dict[str, Any]):
    """One half of a `GameReads` bundle, whose MISS is typed.

    An undeclared name is absent from the bundle by design — that absence IS
    the narrowing — so reading one is a lookup miss, and a miss on a plain
    mapping raises a bare `KeyError` carrying the key and nothing else, from a
    module the reader has no reason to suspect. Whether a declared read
    SUFFICES for the implementation is the one thing the compile stage cannot
    settle (it is a fact about Python), so this miss is the channel that
    question is answered in, and it names the declaration to extend.

    A `dict` subclass rather than a wrapper, so `in`, iteration, equality and
    the freeze walk all behave exactly as before; the mapping the bundle holds
    is this wrapped in a `MappingProxyType`, which is what keeps a primitive
    from writing through the subclass's own mutability."""

    __slots__ = ("_kind", "_row", "_primitive")

    def __init__(
        self,
        values: Mapping[str, Any],
        kind: str,
        row: PrimitiveReads,
        primitive: str | None,
    ) -> None:
        super().__init__(values)
        self._kind = kind
        self._row = row
        self._primitive = primitive

    def get(self, key: str, default: Any = None) -> Any:
        """A miss refuses here too, default or no default.

        `dict.__missing__` fires on the SUBSCRIPT alone, so `.get` would walk
        past the whole guarantee and hand back `None` — an undeclared read
        reading exactly like a declared one whose value happens to be absent,
        which is the silent-wrong-answer shape this half exists to close. What
        a bundle carries is not a question with a sensible default: the
        declaration answers it exactly."""
        return self[key]

    def __missing__(self, key: str) -> Any:
        if self._primitive is not None:
            raise PrimitiveReadError(
                f"the Primitive `{self._primitive}` read the {self._kind} "
                f"{key!r}, which its bundle does not carry — a bundle holds "
                f"exactly the declared reads ({sorted(self)}), so extend that "
                f"entry's `reads` clause in {self._row.game_file}'s "
                f"`primitives {{ }}` block, or read a name it already names"
            )
        raise PrimitiveReadError(
            f"{self._row.module} (serving {self._row.game_file}) read the "
            f"{self._kind} {key!r}, which its bundle does not carry — a bundle "
            f"holds exactly the declared reads ({sorted(self)}); declare the "
            f"read in {_REGISTRY_NAME}"
        )


def _half(
    values: Mapping[str, Any], kind: str, row: PrimitiveReads, primitive: str | None
) -> Mapping[str, Any]:
    """One materialized half, read-only and with its miss typed."""
    return MappingProxyType(_BundleHalf(values, kind, row, primitive))


@dataclass(frozen=True, slots=True)
class GameReads:
    """One module's declared reads, materialized as plain immutable values.

    The bundle a narrowed primitive receives in place of `Ctx`. Its contents
    are bounded by the module's `PRIMITIVE_READS` row — an undeclared name is
    ABSENT, not merely unfetched — and every value is `deep_freeze`d, so a
    primitive can write back through nothing: not a `Zone.cards` list, not an
    indexed state variable's `{player: value}` dict, not anything nested
    inside them. That is the narrowing: what used to be a convention enforced
    by review ("primitives are pure reads") is now a property of what the
    value can express.

    `arrivals` carries, per declared `arrival_zones` name, the zone's
    Arrival Record as (deciding actor, card) pairs in arrival order — the
    kernel-retained attribution the trick winners consume in place of
    zipping seat order against pile contents (issue #256)."""

    state: Mapping[str, Any]
    families: Mapping[str, Mapping[int, tuple[Card, ...]]]
    singles: Mapping[str, tuple[Card, ...]]
    arrivals: Mapping[str, tuple[tuple[Player | None, Card], ...]] = field(
        default_factory=lambda: MappingProxyType({})
    )


def _arrival_pairs(
    rs: RuntimeState, r: PrimitiveReads, name: str
) -> list[tuple[Player | None, Card]]:
    """One declared arrival-zone read, validated at bind time (the
    decision-context rule — see `PrimitiveReads.arrival_zones`)."""
    if name not in r.single_zones:
        raise PrimitiveReadError(
            f"{r.module} (serving {r.game_file}) declares arrival_zones "
            f"{name!r} outside its own single_zones {sorted(r.single_zones)} — "
            f"the Arrival Record is a facet of a declared single-zone read, "
            f"never a separate channel"
        )
    ztype = rs.zones.zone_type.get(name)
    if ztype is None or not identity_to_all(ztype):
        raise PrimitiveReadError(
            f"{r.module} (serving {r.game_file}) declares arrival_zones "
            f"{name!r}, whose type {ztype!r} does not project identity to "
            f"every observer (cardlang/stdlib/zones.py ZONE_PROJECTIONS) — a "
            f"concealed zone's provenance is not derivable from any "
            f"observer's stream, so no primitive may range over it"
        )
    return [(a.actor, a.card) for a in single(rs, r, name).arrivals]


def _narrow(value: Any, key: int | str | None) -> Any:
    """One keyed value, narrowed to `key` — or whole when no key is given.

    A key the live value does not hold is refused rather than silently
    narrowing to nothing: a bundle whose family came back empty reads to the
    implementation exactly like a family with no members, which is the
    silent-wrong-answer shape these accessors exist to prevent."""
    if key is None:
        return value
    if not isinstance(value, _Mapping) or key not in value:
        held = sorted(value) if isinstance(value, _Mapping) else "no instances"
        raise PrimitiveReadError(
            f"a declared read narrowed to instance {key!r}, which the live "
            f"value does not hold (it has {held}) — an index binder keys the "
            f"instance the CALL names, so a miss is the calling primitive's "
            f"argument"
        )
    return {key: value[key]}


def _scoped_state(
    rs: RuntimeState,
    r: PrimitiveReads,
    name: str,
    scopes: Mapping[str, str] | None,
) -> Any:
    """One declared state read, with a [[phase-scoped-read]]'s miss renamed.

    shadow guard: resolve's `_check_scoped_read_containment` admits a call of a
    scoped entry only inside the declaring phase's subtree — or in a move type
    every offering mention of which sits there, or at a `run` site that does —
    and `run_phase` declares the phase's state before any of those run. So the
    frame stands and holds the name at every admitted call, and this arm is
    unreachable. It exists because the message the drift path would print names
    `PRIMITIVE_READS` and the game file, which is the wrong fix and the wrong
    Owner for a scoped read."""
    try:
        return state(rs, r, name)
    except PrimitiveReadError:
        phase = (scopes or {}).get(name)
        if phase is None:
            raise
        raise PrimitiveReadError(
            f"the state variable {name!r}, declared `{name} in {phase}` in "
            f"{r.game_file}'s `primitives {{ }}` block, is not in the live "
            f"runtime state — phase `{phase}` is not running here, which "
            f"resolve's containment check (cardlang/resolve.py, "
            f"`_check_scoped_read_containment`) is the Owner Guard for"
        ) from None


def game_reads(
    rs: RuntimeState,
    r: PrimitiveReads,
    keys: Mapping[str, int | str] | None = None,
    primitive: str | None = None,
    scopes: Mapping[str, str] | None = None,
) -> GameReads:
    """Materialize `r`'s declared row from live state.

    Built here rather than in the binder because this is the sanctioned
    raw-access site: the row's names are data, so the accessor calls below
    are non-literal, which `tests/test_primitive_reads.py` refuses in every
    other module precisely so a name-keyed read cannot escape the static pin.
    The pin still holds — the names come FROM the row, so the bundle is the
    declaration by construction. Every materialized value is `deep_freeze`d,
    so an indexed state variable's `{player: value}` dict — and anything
    nested inside a state value — is a snapshot the primitive cannot mutate,
    not the live engine object.

    `keys` narrows an INDEXED name to one instance: a `primitives { }` entry's
    `reads hand[p]` grants the hand the call names and no other. It is a
    per-call argument rather than part of the row because the key IS one, and
    it applies here, at the one materialization site, so what a primitive
    receives and what its declaration says can never be two derivations.

    `primitive` is the DECLARED entry's name, when a declaration is what built
    the row. It appears only in the miss message, where the addressee's fix
    differs by regime: a declared entry's is its own `reads` clause, an
    authored row's is `PRIMITIVE_READS`. The legacy binders pass none.

    `scopes` names the phase each [[phase-scoped-read]] was declared in, and is
    read by `_scoped_state` alone — the miss it renames is unreachable while
    resolve's containment check stands, so it is a [[shadow-guard]] and says
    so."""
    keys = keys or {}
    unknown = sorted(set(keys) - r.state_vars - r.zone_families)
    if unknown:
        raise PrimitiveReadError(
            f"{r.module} (serving {r.game_file}) narrows {unknown} to an "
            f"instance, but its row declares neither as an indexed read — a "
            f"key narrows a declared indexed name, never one the row omits"
        )
    return GameReads(
        state=_half(
            deep_freeze(
                {
                    n: _narrow(_scoped_state(rs, r, n, scopes), keys.get(n))
                    for n in sorted(r.state_vars)
                }
            ),
            "state variable",
            r,
            primitive,
        ),
        families=_half(
            deep_freeze(
                {
                    n: _narrow(
                        {k: list(z.cards) for k, z in family(rs, r, n).items()},
                        keys.get(n),
                    )
                    for n in sorted(r.zone_families)
                }
            ),
            "zone family",
            r,
            primitive,
        ),
        singles=_half(
            deep_freeze(
                {n: list(single(rs, r, n).cards) for n in sorted(r.single_zones)}
            ),
            "single zone",
            r,
            primitive,
        ),
        arrivals=_half(
            deep_freeze(
                {n: _arrival_pairs(rs, r, n) for n in sorted(r.arrival_zones)}
            ),
            "arrival record",
            r,
            primitive,
        ),
    )


def magic_hand(rs: RuntimeState) -> dict[int, Zone]:
    """The one game-INDEPENDENT zone read a general native function makes:
    `player_holding` scans `hand[player]`, the language-wide magic name
    (decisions.md "Declared parameter domains"). Not registry-keyed — the
    coupling is to the language rule, not to any one game file — but held to
    the same [[failure-channel]]: a game that declares no `hand[player]` family
    gets a typed error naming the rule, not a `KeyError`. (resolve's magic-
    name check only covers games with `Card`-typed move parameters, so this
    is an [[owner-guard]], not a [[shadow-guard]].)

    Returns player-keyed instances: `hand` is a `hand[player]` family by the
    magic-name rule, so its keys are seats even though the generic zone store
    types every family's keys as `int | str` (a board's cell family is keyed by
    name — a different family). The cast localizes that invariant here, where
    the rule is known, so `player_holding` returns a `Player` without a
    per-caller narrowing."""
    fam = rs.zones.families.get("hand")
    if fam is None:
        raise PrimitiveReadError(
            "player_holding: the game declares no `hand[player]` zone family "
            "— `hand` is the language-wide magic name (decisions.md "
            '"Declared parameter domains") this native function reads'
        )
    return cast("dict[int, Zone]", fam)
