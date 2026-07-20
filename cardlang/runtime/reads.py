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

from dataclasses import dataclass, field
from typing import Any

from cardlang.runtime.state import RuntimeState, Zone

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
