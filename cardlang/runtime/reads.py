"""Declared reads for game-local runtime primitives.

A game-local primitive (`cardlang/runtime/<game>.py`, plus the per-game
auction outcomes in `stdlib.py`) is sanctioned Python for pure value
computation (library.md "Stdlib functions"; kernel-migration.md). It reads
live `RuntimeState` by the zone/state-variable name the game file declares —
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
  establishes  every name-keyed primitive read is declared in
               `PRIMITIVE_READS` and fails as a typed `PrimitiveReadError`
               naming this registry — never a bare `KeyError` — when either
               side of the coupling drifts.
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
from collections.abc import Mapping as _Mapping
from collections.abc import Sequence as _Sequence
from collections.abc import Set as _Set
from dataclasses import dataclass, field
from enum import Enum
from types import MappingProxyType
from typing import Any, Mapping

from cardlang.runtime.state import RuntimeState, Zone
from cardlang.runtime.values import Card

# Atomic leaves: immutable, never descended. `str`/`bytes` are sequences (of
# chars/ints) but must NOT be shredded; `bytearray` is deliberately ABSENT —
# it is a MUTABLE sequence and gets converted, not passed through.
_ATOMIC: tuple[type, ...] = (str, bytes, bool, int, float, type(None), Enum)


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
    a frozen+SLOTTED dataclass is rebuilt with each field frozen
    (`StructValue.fields` is where this bites — the class is not assumed to be
    an immutable leaf just because it is a container of nothing), and one whose
    fields are all already immutable (`Card`, `Play`, `Seating`) is returned
    UNCHANGED by identity so the common per-bind path allocates nothing new. A
    dataclass that is NOT frozen, or is frozen but NOT slotted (so its
    `__dict__` stays writable and `obj.__dict__[f] = …` bypasses frozen), is
    refused rather than returned by identity — neither is actually immutable,
    and a field-frozen `replace` copy is the same mutable class. Anything that
    is neither a container nor an immutable dataclass must be a known
    atomic, or `deep_freeze` refuses it rather than passing a possibly-mutable
    object through as a false leaf."""
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
    if isinstance(value, _Set):
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
            # …` bypasses it, so the object is not actually immutable and the
            # identity fast path would leak it. A field-frozen `replace` copy
            # is the same class, so it does not help — the fix is `slots=True`
            # on the type. Refuse rather than hand back a false-frozen object.
            raise TypeError(
                f"deep_freeze cannot treat {type(value).__name__} as immutable: "
                f"it is a frozen dataclass WITHOUT slots, so its __dict__ stays "
                f"writable (obj.__dict__[...] = ... bypasses frozen). Add "
                f"slots=True to the type."
            )
        frozen: dict[str, Any] = {}
        changed = False
        for f in dataclasses.fields(value):
            old = getattr(value, f.name)
            new = deep_freeze(old)
            frozen[f.name] = new
            changed = changed or new is not old
        if not changed:
            return value  # frozen wrapper, every field already immutable
        return dataclasses.replace(value, **frozen)
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
    names must match. A module serving several games (stdlib.py's auction
    outcomes) has one row per game."""

    module: str
    game_file: str
    state_vars: frozenset[str] = field(default=frozenset())
    zone_families: frozenset[str] = field(default=frozenset())
    single_zones: frozenset[str] = field(default=frozenset())


def _fs(*names: str) -> frozenset[str]:
    return frozenset(names)


PRIMITIVE_READS: tuple[PrimitiveReads, ...] = (
    PrimitiveReads(
        module="cardlang/runtime/bigtwo.py",
        game_file="big-two.cardlang",
        state_vars=_fs("opened"),
        zone_families=_fs("hand"),
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
    PrimitiveReads(
        module="cardlang/runtime/doko.py",
        game_file="doppelkopf.cardlang",
        single_zones=_fs("trick_pile"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/pinochle.py",
        game_file="pinochle.cardlang",
        state_vars=_fs("trump_suit"),
        zone_families=_fs("hand"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/president.py",
        game_file="president.cardlang",
        zone_families=_fs("hand"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/schnapsen.py",
        game_file="schnapsen.cardlang",
        single_zones=_fs("trick_pile"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/skat.py",
        game_file="skat.cardlang",
        state_vars=_fs("is_null", "is_grand", "trump_suit"),
        zone_families=_fs("hand"),
        single_zones=_fs("trick_pile", "skat"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/stud.py",
        game_file="seven-card-stud.cardlang",
        state_vars=_fs("stack", "folded", "committed", "in_hand"),
        zone_families=_fs("upcards", "hole"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/tarot.py",
        game_file="french-tarot.cardlang",
        state_vars=_fs("taker", "bid_level"),
        zone_families=_fs("captured", "discard"),
        single_zones=_fs("trick_pile", "chien"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/five_hundred.py",
        game_file="five-hundred.cardlang",
        state_vars=_fs(
            "trump_suit", "is_misere", "is_open_misere", "joker_suit", "declarer"
        ),
        zone_families=_fs("hand", "exposed"),
        single_zones=_fs("trick_pile"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/belote.py",
        game_file="belote.cardlang",
        state_vars=_fs("trump_suit"),
        zone_families=_fs("hand"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/gin.py",
        game_file="gin-rummy.cardlang",
        zone_families=_fs(
            "hand", "taken", "shown_deadwood", "meldA", "meldB", "meldC"
        ),
    ),
    PrimitiveReads(
        module="cardlang/runtime/canasta.py",
        game_file="canasta.cardlang",
        state_vars=_fs(
            "pile_frozen", "team_melded", "meld_rank", "taking_pile", "score"
        ),
        zone_families=_fs(
            "hand", "stage", "red3",
            "meldA", "meldK", "meldQ", "meldJ", "meld10", "meld9",
            "meld8", "meld7", "meld6", "meld5", "meld4", "meld3b",
        ),
        single_zones=_fs("pile_top", "pile_rest"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/tichu.py",
        game_file="tichu.cardlang",
        state_vars=_fs("out_first", "out_second"),
        zone_families=_fs("hand"),
    ),
    # stdlib.py's per-game functions: the auction outcomes and cribbage's
    # pegging-scorer call sites. One row per game served.
    PrimitiveReads(
        module="cardlang/runtime/stdlib.py",
        game_file="bridge.cardlang",
        state_vars=_fs("made_bid", "high_bidder", "cur_strain", "cur_level", "doubled"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/stdlib.py",
        game_file="cribbage.cardlang",
        single_zones=_fs("play_pile"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/stdlib.py",
        game_file="pinochle.cardlang",
        state_vars=_fs("lead_bidder", "opener", "working_bid"),
    ),
    PrimitiveReads(
        module="cardlang/runtime/stdlib.py",
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


def family(rs: RuntimeState, r: PrimitiveReads, name: str) -> dict[int, Zone]:
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


def instance(rs: RuntimeState, r: PrimitiveReads, name: str, key: int) -> Zone:
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
            f"primitive's error, in the runtime's currency"
        ) from None


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
    value can express."""

    state: Mapping[str, Any]
    families: Mapping[str, Mapping[int, tuple[Card, ...]]]
    singles: Mapping[str, tuple[Card, ...]]


def game_reads(rs: RuntimeState, r: PrimitiveReads) -> GameReads:
    """Materialize `r`'s whole declared row from live state.

    Built here rather than in the binder because this is the sanctioned
    raw-access site: the row's names are data, so the accessor calls below
    are non-literal, which `tests/test_primitive_reads.py` refuses in every
    other module precisely so a name-keyed read cannot escape the static pin.
    The pin still holds — the names come FROM the row, so the bundle is the
    declaration by construction. Every materialized value is `deep_freeze`d,
    so an indexed state variable's `{player: value}` dict — and anything
    nested inside a state value — is a snapshot the primitive cannot mutate,
    not the live engine object."""
    return GameReads(
        state=deep_freeze({n: state(rs, r, n) for n in sorted(r.state_vars)}),
        families=deep_freeze(
            {
                n: {k: list(z.cards) for k, z in family(rs, r, n).items()}
                for n in sorted(r.zone_families)
            }
        ),
        singles=deep_freeze(
            {n: list(single(rs, r, n).cards) for n in sorted(r.single_zones)}
        ),
    )


def magic_hand(rs: RuntimeState) -> dict[int, Zone]:
    """The one game-INDEPENDENT zone read a general stdlib function makes:
    `player_holding` scans `hand[player]`, the language-wide magic name
    (decisions.md "Declared parameter domains"). Not registry-keyed — the
    coupling is to the language rule, not to any one game file — but held to
    the same failure currency: a game that declares no `hand[player]` family
    gets a typed error naming the rule, not a `KeyError`. (resolve's magic-
    name wall only covers games with `Card`-typed move parameters, so this
    backstop is reachable.)"""
    fam = rs.zones.families.get("hand")
    if fam is None:
        raise PrimitiveReadError(
            "player_holding: the game declares no `hand[player]` zone family "
            "— `hand` is the language-wide magic name (decisions.md "
            '"Declared parameter domains") this stdlib function reads'
        )
    return fam
