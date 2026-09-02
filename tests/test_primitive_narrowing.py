"""The narrow primitive interface — completeness ledger.

status:     stage 2 COMPLETE — every module in `_GAME_MODULES` is free of every
            engine handle, so the crossed grid is green with nothing
            excused. Stage 3 (`primitives { }`) narrows the bundles from
            module- to primitive-granularity; residual (2) is its execution brief.

property:   a game-local primitive sees VALUES, never an engine handle. Its
            implementation names no `Ctx` and no `RuntimeState`; everything
            it may read arrives as the two bundles the binder builds — its
            module's declared name-keyed reads (`GameReads`, bounded by
            `PRIMITIVE_READS`) and the engine-structural facts
            (`EngineFacts`) — so "this primitive cannot mutate state, make a
            decision, or observe an undeclared name" is structural, not a
            property of review.
domain:     every game-local primitive (derived from all THREE routes to a
            Primitive's Python — the two dispatch tables' `match` arms mapped
            name -> implementing module by AST, and the declaration index
            `PRIMITIVE_IMPLEMENTATIONS`, which is how a DECLARED Primitive is
            reached and therefore what keeps a game's move onto a
            `primitives { }` block from carrying its primitives out of this
            domain — restricted to modules outside the engine core)
            x every forbidden engine handle (derived: `Ctx`'s own field set
            plus the engine types, NOT the handles modules happen to use
            today) x every `EngineFacts` field (derived: the dataclass).
registry:   `_ENGINE_CORE` (the module axis's only hand-authored half, and
            the safe polarity — a NEW runtime module is a game module by
            default and must pass the guard); `PRIMITIVE_IMPLEMENTATIONS`
            (`cardlang/primitives_block.py`), the declaration half of the
            name -> module derivation, and the half a DECLARED Primitive is
            reached through; `NARROWED` (sites proven
            handle-free) and `MIGRATED` (primitives), both now covering
            everything the dispatch routes; `_STILL_REACHES` (the
            per-cell work list, now EMPTY — stage 2 is complete);
            `EMITS_TRACE` (primitives returning events alongside a value);
            `BUILTIN_*` / `PRIMITIVE_*` in `cardlang/builtins/functions.py`
            (the name axis); the bundle probes' kind axis is
            `PrimitiveReads`' own fields minus the two that identify a row,
            and the row they narrow against is SYNTHETIC — declaring one
            name of every kind, so the shape claim is the fixture's own
            rather than a reading of whichever kinds the live registry
            happens to carry while the corpus migrates off it.
covered:    (a) per-implementation-SITE: the site's signature names no
            forbidden handle — exhaustive over the derived site set (one
            cell per `module::func`, NOT per primitive: the dispatch routes
            one name to several implementations). Stage 2 being complete,
            every cell asserts green; the `xfail(strict=True)` machinery
            stays as the mechanism for the next module to arrive, and a
            site that reacquires a handle fails rather than being excused;
            (b) per-module x per-handle: the whole crossed grid, so a
            module that drops `Ctx` from its signatures but keeps an
            import, a `.chooser` reach, or a `RuntimeState` annotation
            still fails its own cell;
            (c) `EngineFacts`: every field populated from a NAMED engine
            expression, each pinned against a live `RuntimeState`, with
            the two round-state views proven distinct (collapsing them is
            a behavior change, not a refactor); and every field pinned to
            a real CONSUMER in a game module — value-correctness and
            non-speculativeness are separate properties, and only the
            second stops the bundle growing. engine_facts freezes EVERY
            field uniformly (not a hand-picked subset), and a separate
            guard pins that no field is the engine's live object by
            identity — the immutability WALK cannot catch that (a
            frozen+slots value passed by identity looks safe to it but is
            an `object.__setattr__` leak), which is how `seating` slipped;
            (d) `GameReads`: the bundle carries exactly the module's
            declared row and nothing else — an undeclared name is absent,
            not merely unfetched, and reading one fails in the declaration's
            own typed channel rather than as a bare `KeyError`, over every
            half `GameReads` declares rather than the halves a corpus
            primitive happens to read; and NOTHING mutable is reachable through
            either bundle at any depth or shape (`deep_freeze`), proven by
            descending the whole materialized structure over a fixture that
            crosses every mutable shape the DSL can produce — nested
            dict/list/set/tuple, a plain `set` AND a `frozenset`, a
            `bytearray` (a mutable builtin), and a `StructValue` whose
            `.fields` is a live dict behind a frozen dataclass (a mutable
            WRAPPER, not a leaf). The walker recurses dataclass fields AND
            checks the wrapper is both frozen AND slotted, so it cannot share
            deep_freeze's blind spots, and deep_freeze REFUSES any leaf it
            cannot prove immutable — a non-frozen dataclass, OR a frozen but
            non-SLOTTED one (whose `__dict__` stays writable, so
            `obj.__dict__[f] = …` bypasses frozen), neither fixable by a
            field-frozen `replace` copy — rather than passing a
            possibly-mutable object through. The holes Codex found (indexed
            state dict, round-state `played` list, StructValue fields,
            bytearray, the non-frozen-dataclass identity fast path, and the
            frozen-but-non-slotted `Play`) were each reproduced before the
            fix closed them. deep_freeze never returns a dataclass by
            identity, even frozen+slots: `object.__setattr__` bypasses
            `frozen`, so it COPIES (a `replace`), and the back door then
            hits the primitive's copy, not the value in engine state — the
            three climb `Play` types are frozen+slots so they copy cleanly;
            (d') the primitive boundary is TWO channels, both frozen: the
            bundles above, and the positional COLLECTION arguments — a
            collection arg from a zone reaches a primitive as the zone's
            live `.cards` list (`elements()` returns it by reference), so
            EVERY site handing a narrowed primitive a value that could be
            (or contain) a mutable engine object freezes it: the generic
            `call()` coercion (`_coerce_args`, which copies both TCollection
            args AND scalar `TCard` args — a frozen+slots `Card` is still
            mutable via `object.__setattr__`), the climb hand AND the
            standing `Play` (`state["current"]`), and the direct sites that
            read live engine state rather than a bundle — the two cribbage
            peg arms and the trick `outcome_fn` (`played` + `rank_index`). Keys are frozen with
            values, so a mutable-hashable key cannot be recovered by
            iterating a proxy. Each channel is proven: the boundary
            snapshot is a tuple not the live list (captured at the peg and
            outcome sites), and a mutable key/arg is refused. The auction
            outcomes are excluded on purpose — they are residual (1),
            still holding `ctx`, so freezing one of their args would be
            theater;
            (e) `EMITS_TRACE` two ways: every listed primitive returns
            `(value, events)`, no unlisted migrated primitive does.
sampled:    behavioral identity rides the byte-identical goldens and the
            playout suites, which is the whole gauge for this stage — a
            moved golden means the refactor changed behavior.
residual:   (1) the three auction outcomes (`bridge_`/`pinochle_`/
            `tarot_auction_outcome`) are implemented INSIDE
            `cardlang/runtime/primitives.py`, which is engine core, so the
            game-module guard does not reach them; they are game knowledge
            in the language package and stage 4 (co-location) owns their
            move. Guard: `test_engine_core_game_knowledge_is_named`, which
            fails if that set changes without this ledger changing.
            Record: issue #142.
            (2) `EngineFacts` is MODULE-granular by ratified stage-2 scope
            (2A): a primitive receives the facts bundle whole rather than
            the per-primitive `reads` clause of the design note's §2. The
            narrowing that remains is stage 3's, and until it lands a
            primitive can read a fact it does not need, and every call
            materializes its module's whole row whether or not it reads
            any of it. Guard: the field set is closed and every field is
            pinned to a consumer (c), so the bundle cannot grow
            speculatively; the per-call cost is recorded in
            issue #142.

red under (born-green cells):
- `combinations.py` passes (b) on arrival: it is the Tichu combination
  engine, already pure. Reddening mutation: annotate any of its functions
  `ctx: Ctx` — `test_game_module_is_free_of_engine_handle[combinations.py
  -Ctx]` fails. Run and reverted.
- `test_every_engine_fact_has_a_consumer` passes on arrival (all seven
  fields have readers). Reddening mutation: add a field to `EngineFacts`
  — it fails on the field-set comparison; give it a `_FACT_CONSUMERS` row
  with no real reader and it fails on the unread check. Run and reverted.
- the deep-immutability walk is only as honest as its fixture reaches: a
  `deep_freeze` that dropped the `bytearray` or dataclass-recursion branch
  leaves those cells vacuous. Reddening mutation (RUN, not stated): freeze
  `_nested()` with a blind version missing those two branches — the walker
  flags `[…]['raw']: mutable sequence bytearray` and `[…]['sv'].fields:
  mutable mapping dict` (descending into the wrapper), so the fixture's
  extra shapes are load-bearing, not decoration.
- the non-frozen-dataclass case can't live in the fixture (deep_freeze
  refuses it, so `game_reads` would raise): it is a rejection test
  (`test_deep_freeze_and_walker_reject_a_non_frozen_dataclass`), and the
  reddening is the pre-fix behavior itself — `deep_freeze(Box(1)) is Box(1)`
  with the field-frozen result still writable, RUN and shown before the
  frozen-check landed.
"""

from __future__ import annotations

import ast
import random
from dataclasses import dataclass, fields as _dc_fields
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.builtins.functions import (
    CALL_FUNCS,
    PRIMITIVE_AUCTION_OUTCOMES,
    PRIMITIVE_CLIMB_FOLLOWS,
    PRIMITIVE_CLIMB_LEADS,
    PRIMITIVE_EARLY_PREDICATES,
    TRICK_WINNER_NAMES,
)
from cardlang.primitives_block import PRIMITIVE_IMPLEMENTATIONS
from cardlang.runtime import reads as reads_mod
from cardlang.runtime.reads import PRIMITIVE_READS, PrimitiveReads
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "cardlang" / "runtime"

# --- axis 1: the game-module set -------------------------------------------
#
# Hand-authored as the EXCLUSION half only, so the polarity is safe: a new
# file under cardlang/runtime/ is a game module until someone argues it into
# this table, and therefore has to pass the guard. Each row names why the
# engine core legitimately holds an engine handle.
_ENGINE_CORE: dict[str, str] = {
    "__init__.py": "package init",
    "chooser.py": "the decision seam itself",
    "delegation.py": "engine core — routes the decider and source at the seam",
    "driver.py": "engine core — builds and threads Ctx",
    "evaluate.py": "engine core — the expression interpreter",
    "execute.py": "engine core — the statement interpreter",
    "mechanics.py": "engine core — the round machinery",
    "observe.py": "engine core — the projection substrate",
    "active_rules.py": "engine core — active-rule computation for a phase",
    "reads.py": "the declared-reads accessors (the sanctioned raw-access site)",
    "rules.py": "engine core — rule application",
    "narrowing.py": "the binder — it BUILDS the bundles, so it holds the handle",
    "state.py": "engine core — defines RuntimeState and Ctx",
    "builtins.py": "engine core — the generic native functions",
    "primitives.py": "engine core — the dispatch layer that BUILDS the bundles",
    "values.py": "engine core — the value types",
    "trick_order.py": "engine core — materializes the game's Trick Order, so it\n        threads Ctx into the row callables",
}

_GAME_MODULES: tuple[str, ...] = tuple(
    sorted(p.name for p in RUNTIME_DIR.glob("*.py") if p.name not in _ENGINE_CORE)
)


def test_engine_core_exemptions_are_live() -> None:
    """The exclusion table pinned non-stale: every named file exists. A
    deleted engine-core module must leave this table, or the next file to
    take its name inherits an exemption nobody argued for."""
    names = {p.name for p in RUNTIME_DIR.glob("*.py")}
    for exempt, why in _ENGINE_CORE.items():
        assert exempt in names, f"stale exemption {exempt!r} ({why}) — file is gone"


# --- axis 2: the primitive name -> implementing module map ------------------


@dataclass(frozen=True)
class Impl:
    """One primitive's implementation site, as the dispatch layer names it."""

    primitive: str
    module: str  # bare file name, e.g. "gin.py"
    func: str  # the implementation's own name, which may differ


def _dispatch_imports(body: list[ast.stmt]) -> list[tuple[str, str]]:
    """Every `from cardlang.runtime.<mod> import <f>` inside one match arm."""
    out: list[tuple[str, str]] = []
    for node in body:
        for sub in ast.walk(node):
            if isinstance(sub, ast.ImportFrom) and (sub.module or "").startswith(
                "cardlang.runtime."
            ):
                mod = (sub.module or "").rsplit(".", 1)[-1]
                out.extend((f"{mod}.py", a.name) for a in sub.names)
    return out


@cache
def _implementations() -> tuple[Impl, ...]:
    """Derive name -> implementation from every route a Primitive's Python is
    reached by. Derived, not listed: a primitive added to any of them enters
    this grid automatically, which is what stops the coverage domain from
    being whatever someone remembered to type.

    THREE homes. Two are `match` arms — a generic arm that lazily imported a
    game module would otherwise escape this grid by living in the half nobody
    parsed. The third is `PRIMITIVE_IMPLEMENTATIONS`, the declaration index
    `call_declared` derives a DECLARED Primitive's call from: a declared entry
    has no arm, so a game adopting a `primitives { }` block would otherwise
    carry its primitives out of this domain — the property would stop being
    checked at exactly the point the bundle narrows. The index is total over
    `PRIMITIVE_CALL_FUNCS` (its own module asserts that), so it also holds the
    arm-reached names, and the union deduplicates."""
    found: set[Impl] = set()
    for home in ("builtins.py", "primitives.py"):
        found.update(_impls_in(RUNTIME_DIR / home))
    found.update(
        Impl(
            primitive=name,
            module=impl.module.rsplit(".", 1)[-1] + ".py",
            func=impl.attribute,
        )
        for name, impl in PRIMITIVE_IMPLEMENTATIONS.items()
    )
    return tuple(sorted(found, key=lambda i: (i.primitive, i.module, i.func)))


def _impls_in(path: Path) -> list[Impl]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found: list[Impl] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            names = _arm_names(case.pattern)
            for name in names:
                for mod, func in _dispatch_imports(case.body):
                    found.append(Impl(primitive=name, module=mod, func=func))
    return found


def _arm_names(pattern: ast.pattern) -> list[str]:
    """The Primitive names one `match` arm routes — BOTH pattern shapes.

    An arm may name one Primitive (`case "gin_deadwood":`) or several
    (`case "tichu_lead_options" | "tichu_follows":`, the climb binder's shape,
    where one row serves a module's whole climb pair). Reading only the first
    shape would leave every implementation an or-patterned arm imports outside
    this grid's domain, which is the coverage hole that looks like a green."""
    alternatives = (
        pattern.patterns if isinstance(pattern, ast.MatchOr) else [pattern]
    )
    return [
        alt.value.value
        for alt in alternatives
        if isinstance(alt, ast.MatchValue)
        and isinstance(alt.value, ast.Constant)
        and isinstance(alt.value.value, str)
    ]


_ALL_REGISTERED: frozenset[str] = (
    CALL_FUNCS
    | TRICK_WINNER_NAMES
    | PRIMITIVE_AUCTION_OUTCOMES
    | PRIMITIVE_EARLY_PREDICATES
    | PRIMITIVE_CLIMB_LEADS
    | PRIMITIVE_CLIMB_FOLLOWS
)

_GAME_IMPLS: tuple[Impl, ...] = tuple(
    i for i in _implementations() if i.module in _GAME_MODULES
)


def test_the_arm_scrape_still_sees_every_climb_name() -> None:
    """The scrape's name-grain floor over the one namespace that enters this
    domain through `match` arms alone: climb leads and follows have no
    `PRIMITIVE_IMPLEMENTATIONS` row, so a scrape blind to every shape their
    arms use drops them from the domain with only the coarse size floor to
    notice. SITE-grain shape blindness has its own Owner —
    `test_progress_registries_name_real_things` reddens when a listed
    `NARROWED` symbol's or-patterned route goes unread, because every climb
    name also sits in singular arms and only the sites vanish. This floor
    guards the residue: a climb name losing its LAST scraped route.

    red under: blind `_impls_in` to arm names entirely (`names = []`) — the
    climb names leave the scrape and this set difference goes non-empty,
    naming them."""
    scraped = {i.primitive for i in _implementations()}
    missing = (PRIMITIVE_CLIMB_LEADS | PRIMITIVE_CLIMB_FOLLOWS) - scraped
    assert not missing, (
        f"climb names the arm scrape no longer sees: {sorted(missing)} — "
        f"`_arm_names` is blind to the match shape their arms use"
    )


def test_every_dispatched_primitive_is_a_registered_name() -> None:
    """The derivation's own sanity pin: the dispatch cannot route a name the
    front end never signatured (that would be unreachable code claiming
    coverage)."""
    unknown = sorted({i.primitive for i in _implementations()} - _ALL_REGISTERED)
    assert not unknown, f"dispatch arms for unregistered names: {unknown}"


def test_the_derived_axis_is_not_empty() -> None:
    """A scraper that silently matches nothing would make every grid below
    vacuously green — the failure mode this repo ranks with
    accepted-but-ignored."""
    assert len(_GAME_IMPLS) > 50, (
        f"derived only {len(_GAME_IMPLS)} game primitives — the dispatch "
        f"scraper has stopped matching; every cell below would be vacuous"
    )


# --- stage-2 progress registries -------------------------------------------

# Implementation SITES (`module::func`) that take no engine handle. Cells for
# anything not here are xfail(strict=True): narrowing a site without adding it
# fails as an unexpected pass, so the grid cannot silently under-report.
#
# Seeded with the sites that already qualify — the pure card-math scorers and
# the two climb helpers the OpenSpiel adapter calls. They are not stage-2 work;
# they are the shape stage 2 generalises, and pinning them now means a later
# change cannot quietly give one of them a handle.
NARROWED: frozenset[str] = frozenset(
    {
        "belote.py::belote_best_is",
        "belote.py::belote_decl_class",
        "belote.py::belote_decl_height",
        "belote.py::belote_decl_points",
        "belote.py::belote_decl_size",
        "belote.py::belote_decl_slot",
        "belote.py::belote_decl_trump",
        "belote.py::belote_royal_player",
        "bigtwo.py::ROW",
        "bigtwo.py::bigtwo_follows",
        "bigtwo.py::bigtwo_lead_options",
        "bigtwo.py::bigtwo_universe",
        "canasta.py::canasta_can_start",
        "canasta.py::canasta_can_take_pile",
        "canasta.py::canasta_canasta_bonus",
        "canasta.py::canasta_close_ok",
        "canasta.py::canasta_must_take_pile",
        "canasta.py::canasta_stage_ok",
        "coup.py::ROW",
        "coup.py::coup_game_summary",
        "cribbage.py::ROW",
        "cribbage.py::cribbage_crib_value",
        "cribbage.py::cribbage_show_value",
        "cribbage.py::peg_origin_of",
        "cribbage.py::peg_pair_points",
        "cribbage.py::peg_run_points",
        "five_hundred.py::five_hundred_bid_level",
        "five_hundred.py::five_hundred_bid_value",
        "five_hundred.py::five_hundred_next_bid",
        "gin.py::GIN_MELD_CODEC",
        "gin.py::ROW",
        "gin.py::gin_arrange_ok",
        "gin.py::gin_can_declare",
        "gin.py::gin_can_declare_free",
        "gin.py::gin_can_knock",
        "gin.py::gin_deadwood",
        "gin.py::gin_knock_ok",
        "gin.py::gin_lay_ok_a",
        "gin.py::gin_lay_ok_b",
        "gin.py::gin_lay_ok_c",
        "gin.py::gin_valid_meld",
        "holdem.py::holdem_pot_share",
        "holdem_heads_up.py::holdem_heads_up_pot_share",
        "pinochle.py::pinochle_meld_value",
        "president.py::ROW",
        "president.py::president_follows",
        "president.py::president_lead_options",
        "president.py::president_universe",
        "salvo.py::salvo_combos",
        "skat.py::skat_matadors",
        "skat.py::skat_next_bid",
        "stud.py::bring_in_seat",
        "stud.py::first_to_act_seat",
        "stud.py::pot_share",
        "tarot.py::tarot_excuse_player",
        "tarot.py::tarot_per_opp",
        "tichu.py::ROW",
        "tichu.py::TICHU_COMBO_CODEC",
        "tichu.py::tichu_dragon_won",
        "tichu.py::tichu_follows",
        "tichu.py::tichu_lead_options",
    }
)

# Primitives narrowed by stage 2 so far, for the module-level guard below.
MIGRATED: frozenset[str] = frozenset(
    {
        "belote_best_is",
        "belote_decl_class",
        "belote_decl_height",
        "belote_decl_points",
        "belote_decl_size",
        "belote_decl_slot",
        "belote_decl_trump",
        "belote_royal_player",
        "bigtwo_follows",
        "bigtwo_lead_options",
        "bring_in_seat",
        "canasta_can_start",
        "canasta_can_take_pile",
        "canasta_canasta_bonus",
        "canasta_close_ok",
        "canasta_must_take_pile",
        "canasta_stage_ok",
        "coup_game_summary",
        "cribbage_crib_value",
        "cribbage_show_value",
        "first_to_act_seat",
        "gin_arrange_ok",
        "gin_can_declare",
        "gin_can_declare_free",
        "gin_can_knock",
        "gin_deadwood",
        "gin_knock_ok",
        "gin_lay_ok_a",
        "gin_lay_ok_b",
        "gin_lay_ok_c",
        "gin_valid_meld",
        "holdem_heads_up_pot_share",
        "holdem_pot_share",
        "peg_origin_of",
        "pinochle_meld_value",
        "pot_share",
        "president_follows",
        "president_lead_options",
        "salvo_combos",
        "skat_matadors",
        "tarot_excuse_player",
        "tarot_per_opp",
        "tichu_dragon_won",
        "tichu_follows",
        "tichu_lead_options",
    }
)

# Primitives that return `(value, events)` — they compute a real value AND
# emit the engine's own trace vocabulary from a game-local site, so the
# emission travels back as data and the dispatch layer performs it.
EMITS_TRACE: frozenset[str] = frozenset(
    {
        "coup_game_summary",
    }
)


def test_progress_registries_name_real_things() -> None:
    """No progress claimed for a site or name the dispatch does not route."""
    known = {i.primitive for i in _GAME_IMPLS}
    assert MIGRATED <= known, f"MIGRATED names nothing real: {sorted(MIGRATED - known)}"
    sites = {s.key for s in _SITES}
    assert NARROWED <= sites, f"NARROWED names no site: {sorted(NARROWED - sites)}"


def test_emits_trace_names_are_real_primitives() -> None:
    known = {i.primitive for i in _GAME_IMPLS}
    assert EMITS_TRACE <= known, (
        f"EMITS_TRACE names nothing real: {sorted(EMITS_TRACE - known)}"
    )


# --- axis 3: the forbidden handles -----------------------------------------
#
# Derived from what `Ctx` actually offers, not from what game modules happen
# to reach for today: every public field of the dataclass, its two methods
# that hand out engine power, and the engine types themselves. A handle that
# is added to Ctx later joins this axis automatically.


@cache
def _ctx_surface() -> tuple[str, ...]:
    """`Ctx`'s own attribute names, read off state.py's class body."""
    tree = ast.parse((RUNTIME_DIR / "state.py").read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == "Ctx":
            fields = [
                s.target.id
                for s in node.body
                if isinstance(s, ast.AnnAssign) and isinstance(s.target, ast.Name)
            ]
            methods = [s.name for s in node.body if isinstance(s, ast.FunctionDef)]
            return tuple(sorted(set(fields + methods)))
    raise AssertionError("Ctx not found in state.py — the handle axis lost its source")


_FORBIDDEN_TYPES: tuple[str, ...] = ("Ctx", "RuntimeState", "ZoneStore", "Chooser")


def test_ctx_surface_is_derived_not_empty() -> None:
    surface = _ctx_surface()
    # The fields this grid was authored against; a NEW one is not an error
    # (the axis is derived) but losing one silently would shrink the domain.
    for expected in ("rs", "chooser", "tracer", "locals", "observer", "acting_as"):
        assert expected in surface, (
            f"Ctx no longer exposes {expected!r} — if it moved, the handle "
            f"axis must follow it; if it is gone, drop it from this pin"
        )


# --- the scan ---------------------------------------------------------------


@dataclass
class ModuleScan:
    """One module's engine-handle contacts, by handle name."""

    hits: dict[str, list[str]]
    ctx_params: dict[str, str]  # function name -> where it takes a handle
    symbols: dict[str, str]  # top-level name -> "function" | "data"


def _scan(path: Path) -> ModuleScan:
    src = path.read_text(encoding="utf-8")
    tree = ast.parse(src, filename=path.name)
    hits: dict[str, list[str]] = {}
    ctx_params: dict[str, str] = {}
    symbols: dict[str, str] = {}
    for top in tree.body:
        if isinstance(top, (ast.FunctionDef, ast.AsyncFunctionDef)):
            symbols[top.name] = "function"
        elif isinstance(top, ast.ClassDef):
            symbols[top.name] = "data"
        elif isinstance(top, ast.Assign):
            for t in top.targets:
                if isinstance(t, ast.Name):
                    symbols[t.id] = "data"
        elif isinstance(top, ast.AnnAssign) and isinstance(top.target, ast.Name):
            symbols[top.target.id] = "data"

    def note(handle: str, lineno: int) -> None:
        hits.setdefault(handle, []).append(f"{path.name}:{lineno}")

    for node in ast.walk(tree):
        # A forbidden TYPE named anywhere: annotation, import, isinstance.
        if isinstance(node, ast.Name) and node.id in _FORBIDDEN_TYPES:
            note(node.id, node.lineno)
        elif isinstance(node, ast.ImportFrom):
            for a in node.names:
                if a.name in _FORBIDDEN_TYPES:
                    note(a.name, node.lineno)
        # A reach through a value spelled `ctx` for any of Ctx's own surface.
        elif isinstance(node, ast.Attribute):
            base = node.value
            if isinstance(base, ast.Name) and base.id == "ctx" and node.attr in _ctx_surface():
                note(f"ctx.{node.attr}", node.lineno)
        # A parameter annotated with a forbidden type.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                ann = arg.annotation
                if isinstance(ann, ast.Name) and ann.id in _FORBIDDEN_TYPES:
                    ctx_params[node.name] = f"{path.name}:{node.lineno} ({arg.arg})"
    return ModuleScan(hits=hits, ctx_params=ctx_params, symbols=symbols)


@cache
def _scan_module(name: str) -> ModuleScan:
    return _scan(RUNTIME_DIR / name)


# --- grid (a): per-primitive, the implementation takes no handle ------------


@dataclass(frozen=True)
class Site:
    """One implementation SITE: `module::func`. The cell key is the site, not
    the primitive name, because the dispatch layer routes one name to several
    implementations — `climb_universe_function` sends `bigtwo_lead_options` to
    `bigtwo_universe`, `climb_codec_function` sends `tichu_lead_options` to
    `TICHU_COMBO_CODEC`. Keying by name let a handle-free sibling mask a
    `Ctx`-taking function, so the name is NOT the domain."""

    module: str
    func: str

    @property
    def key(self) -> str:
        return f"{self.module}::{self.func}"


_SITES: tuple[Site, ...] = tuple(
    sorted(
        {Site(module=i.module, func=i.func) for i in _GAME_IMPLS},
        key=lambda s: s.key,
    )
)


def _pending(reason: str) -> tuple[Any, ...]:
    """A not-yet-migrated cell. DECLARATIVE `xfail(strict=True)`, never the
    imperative `pytest.xfail()`: the imperative form aborts the test body, so
    it reports xfail whether or not the cell would now pass — a check that
    cannot fail. Strict marks run the body and turn an unexpected pass into a
    FAILURE, which is what forces `MIGRATED` to be updated in the same change
    that narrows a primitive."""
    return (pytest.mark.xfail(strict=True, reason=reason),)


_STAGE2 = "not yet narrowed (stage 2, by family)"


@pytest.mark.parametrize(
    "site",
    [
        pytest.param(
            s,
            marks=() if s.key in NARROWED else _pending(f"{s.key} {_STAGE2}"),
            id=s.key,
        )
        for s in _SITES
    ],
)
def test_implementation_site_takes_no_engine_handle(site: Site) -> None:
    """One cell per implementation site: it does not take `Ctx` (or any other
    engine handle) as a parameter. A site the scan cannot classify fails
    LOUD rather than passing by absence — an unresolvable symbol is exactly
    how a handle-taking implementation would slip through unanalysed."""
    scan = _scan_module(site.module)
    kind = scan.symbols.get(site.func)
    assert kind is not None, (
        f"{site.key}: the dispatch routes to this name but the module defines "
        f"no top-level symbol by it — the scan cannot analyse it, so this cell "
        f"would otherwise pass vacuously"
    )
    if kind == "data":
        # A dispatched constant (a codec object). It takes no parameters at
        # all, so the parameter property is trivially true; the handle it
        # could still hold is its CLASS's, which grid (b) covers module-wide.
        return
    where = scan.ctx_params.get(site.func)
    assert where is None, (
        f"{site.key} still takes an engine handle at {where}. The binder "
        f"passes values: the module's declared reads (GameReads) and the "
        f"engine facts (EngineFacts)."
    )


# --- grid (b): per-module x per-handle --------------------------------------


_HANDLES: tuple[str, ...] = (
    *_FORBIDDEN_TYPES,
    *(f"ctx.{a}" for a in _ctx_surface()),
)

# The stage-2 work list, authored per CELL rather than per module. Marking a
# whole module pending would assert nonsense — that `belote.py` must contain
# `ctx.chooser` — and would hide a real regression behind an expected failure.
# Only these (module, handle) pairs are red today; the other 332 cells are
# pinned GREEN right now, which is what stops a migration from introducing a
# handle a module never had.
# EMPTY: stage 2 is complete. Every game module is free of every engine
# handle, so all 368 cells below assert green and none is excused. The table
# stays because it is the mechanism, not a note — a module that reacquires a
# handle fails its cell, and re-adding a row here is the only way to excuse
# that, which is a visible edit rather than a silent regression.
_STILL_REACHES: dict[str, tuple[str, ...]] = {}


def test_the_work_list_names_real_modules() -> None:
    """`_STILL_REACHES` cannot outlive its modules: a stale key would quietly
    shrink the red set to nothing."""
    unknown = sorted(set(_STILL_REACHES) - set(_GAME_MODULES))
    assert not unknown, f"work list names non-game-modules: {unknown}"


_MODULE_HANDLE_CELLS = [
    pytest.param(
        m,
        h,
        marks=()
        if h not in _STILL_REACHES.get(m, ())
        else _pending(f"{m} still reaches {h} (stage 2, by family)"),
        id=f"{m}-{h}",
    )
    for m in _GAME_MODULES
    for h in _HANDLES
]


@pytest.mark.parametrize(("module", "handle"), _MODULE_HANDLE_CELLS)
def test_game_module_is_free_of_engine_handle(module: str, handle: str) -> None:
    """The crossed grid. A module is only green once EVERY primitive it
    implements is migrated; until then each of its cells is a strict xfail,
    so finishing a module without updating MIGRATED fails loudly."""
    scan = _scan_module(module)
    where = scan.hits.get(handle, [])
    assert not where, (
        f"{module} still reaches the engine handle {handle!r} at "
        f"{', '.join(where)} — a game module sees values only."
    )


# --- grid (c): EngineFacts ---------------------------------------------------


def _narrowing() -> Any:
    """The mechanism under test. Imported lazily so that, before it exists,
    the cells below fail with this message rather than collapsing the whole
    module into a collection error."""
    try:
        from cardlang.runtime import narrowing
    except ImportError as exc:  # pragma: no cover - the red state
        pytest.fail(
            f"cardlang/runtime/narrowing.py does not exist yet: {exc}. It owns "
            f"EngineFacts, GameReads and the binder."
        )
    return narrowing


# The engine expression each field mirrors. This IS the field axis: a field
# added to EngineFacts without a row here fails `test_every_engine_fact_is_
# pinned`, and a row naming a field that does not exist fails too.
_FACT_SOURCES: dict[str, str] = {
    "seating": "rs.seating",
    "team_of": "rs.team_of",
    "rank_index": "rs.rank_index",
    "round_state": "rs.mech_state[-1] if rs.mech_state else rs.last_round_state",
    "last_round_state": "rs.last_round_state",
    "actor": "ctx.current_player",
}


# Each fact's spellings in a game module: the narrowed one, and the
# pre-migration one it replaces. Both count, so this pin stays meaningful
# THROUGHOUT the migration — a fact whose only consumers are not yet
# narrowed is still a consumed fact, not a speculative field.
_FACT_CONSUMERS: dict[str, tuple[str, ...]] = {
    "seating": ("facts.seating", "ctx.rs.seating"),
    "team_of": ("facts.team_of", "ctx.rs.team_of"),
    "rank_index": ("facts.rank_index", "ctx.rs.rank_index"),
    "round_state": ("facts.round_state", "ctx.rs.mech_state"),
    "last_round_state": ("facts.last_round_state", "ctx.rs.last_round_state"),
    "actor": ("facts.actor", "ctx.current_player"),
}

# Fields NO game module reads any more, with the reason each is still
# declared. A named residual is what the pin below asks for in place of a
# silent carry, and it is checked in BOTH directions: an unread field with no
# row here is the original failure, and a row naming a field that IS read is a
# stale exemption. So the exemption cannot outlive its reason.
_UNREAD_RESIDUALS: dict[str, str] = {
    # `belote_opp_winning` was the last reader, and it did not move -- it
    # RETIRED (issue #250 PR 4): the acting seat's team gate is now a designer
    # function over the game's Trick Order, which takes `actor` as an ordinary
    # DSL argument, so the fact a Primitive needed the engine to hand it is now
    # one the language passes. Removing the field is a change to the binder's
    # signature (`engine_facts`, `bind`, every dispatch call site), which
    # belongs to the narrowing contract's own change rather than to a game
    # migration. That is WORK, not a recorded constraint, so it carries a
    # tracker record and not just this prose: issue #383.
    "actor": (
        "no Primitive reads it since issue #250 PR 4 retired "
        "belote_opp_winning; removal is issue #383"
    ),
}


@cache
def _game_module_sources() -> str:
    return "\n".join(
        (RUNTIME_DIR / m).read_text(encoding="utf-8") for m in _GAME_MODULES
    )


def test_every_engine_fact_has_a_consumer() -> None:
    """`EngineFacts` cannot grow speculatively. A field nothing reads is
    surface a primitive can see for no reason — and since stage 3 turns this
    set into an information-flow declaration, an unread field is a claim that
    primitives may observe something they never needed. Without this pin the
    ledger's "every field is consumed" would be prose, not a guarantee:
    adding a field to the dataclass, `_FACT_SOURCES` and the value matrix
    would leave the suite entirely green."""
    facts_cls = _narrowing().EngineFacts
    fields = frozenset(facts_cls.__dataclass_fields__)
    assert fields == frozenset(_FACT_CONSUMERS), (
        f"EngineFacts fields {sorted(fields)} disagree with the consumer map "
        f"{sorted(_FACT_CONSUMERS)} — a new field must name how a game module "
        f"spells its read, or be removed"
    )
    src = _game_module_sources()
    unread = {
        field
        for field, spellings in _FACT_CONSUMERS.items()
        if not any(s in src for s in spellings)
    }
    assert not sorted(unread - set(_UNREAD_RESIDUALS)), (
        f"EngineFacts fields no game module reads: "
        f"{sorted(unread - set(_UNREAD_RESIDUALS))}. Remove them, or "
        f"if a field is genuinely needed by work not yet landed, record it as "
        f"a named residual in `_UNREAD_RESIDUALS` rather than carrying it "
        f"silently."
    )
    assert not sorted(set(_UNREAD_RESIDUALS) - unread), (
        f"`_UNREAD_RESIDUALS` names "
        f"{sorted(set(_UNREAD_RESIDUALS) - unread)}, which a game module DOES "
        f"read — a stale exemption reads as a live carve-out while covering "
        f"nothing; drop the row"
    )


def _live_state() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="TrickPile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    rs.teams = (0, 1)
    rs.team_of = {0: 0, 1: 1}
    rs.rank_index = {"7": 0, "8": 1}
    rs.last_round_state = {"played": [], "marker": "terminal"}
    return rs


# The declared-reads row the bundle probes below narrow against. SYNTHETIC, and
# specified by SHAPE: it declares one name of every kind the bundle carries, so
# "every declared name present, no undeclared name reachable" is a claim with
# all of those kinds in it. A live registry row cannot serve — the rows are the
# thing the corpus is migrating off, so any one of them can be deleted by a
# migration that has no reason to look here, and the kinds a row happens to
# carry are the game's business, not the fixture's. (Doppelkopf's row served
# until the Trick Order retired it, then Five Hundred's until the same construct
# retired that one — and with it the registry's last `arrival_zones`
# declaration, which is why a registry-derived shape claim could no longer reach
# that kind at all.)
#
# The bundle's kinds, each as the row attribute that declares it — derived from
# `PrimitiveReads`' own fields minus the two that IDENTIFY a row, so a kind
# added to the registry's shape lands as a cell rather than as an omission.
_BUNDLE_KIND_FIELDS = tuple(
    f.name
    for f in _dc_fields(PrimitiveReads)
    if f.name not in ("module", "game_file")
)

_BUNDLE_ROW = PrimitiveReads(
    module="cardlang/runtime/probe.py",
    game_file="probe.cardlang",
    state_vars=frozenset({"declared_var"}),
    zone_families=frozenset({"declared_family"}),
    single_zones=frozenset({"declared_single"}),
    arrival_zones=frozenset({"declared_single"}),
)

# A zone family the fixture declares and the row does not — asserted
# absent from the bundle below. Pinned outside the row by the fixture
# itself, so the negative witness cannot silently become a name the row
# grew (which is how it stopped discriminating once before).
_UNDECLARED_FAMILY = "decoy"


def _bundle_row() -> PrimitiveReads:
    return _BUNDLE_ROW


def _bundle_state() -> RuntimeState:
    """`_live_state` extended with exactly what the fixture's row declares — the
    row is the fixture's specification, read from it rather than transcribed
    (zones included), so a row that grows a name fails loudly here instead of
    being silently under-satisfied. Every single zone is declared public because
    `arrival_zones` is a subset of them and an arrival read requires identity to
    every observer; the probes below are about the binder's narrowing, not about
    any one game's zone types."""
    row = _bundle_row()
    decls = (
        *(
            n.ZoneDecl(name=z, index=None, type_ref=n.TypeRef(name="TrickPile"))
            for z in sorted(row.single_zones)
        ),
        *(
            n.ZoneDecl(name=z, index="player", type_ref=n.TypeRef(name="Hand"))
            for z in sorted(row.zone_families)
        ),
        # The UNDECLARED family, the negative half of the narrowing claim: the
        # store holds it, the row does not name it, so the bundle must not
        # carry it. Without a zone outside the row the equality assertions
        # below hold vacuously.
        n.ZoneDecl(name=_UNDECLARED_FAMILY, index="player", type_ref=n.TypeRef(name="Hand")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    for var in sorted(row.state_vars):
        rs.declare(var, False, None)
    rs.teams = (0, 1)
    rs.team_of = {0: 0, 1: 1}
    rs.rank_index = {"7": 0, "8": 1}
    return rs


def test_the_bundle_row_covers_every_declared_kind() -> None:
    """The fixture's row is a SHAPE choice, and this is what enforces it:
    EVERY kind the bundle carries is declared on it, unconditionally. The
    condition this once carried — "every kind some registry row declares" —
    made the guard as narrow as the corpus happened to be, so the day the last
    row declaring a kind was retired that kind's equality below quietly went
    back to comparing two empty sets and nothing said so.

    red under: drop `arrival_zones` from `_BUNDLE_ROW`."""
    row = _bundle_row()
    assert _BUNDLE_KIND_FIELDS, "the kind axis came up empty — wrong dataclass"
    unmet = [field for field in _BUNDLE_KIND_FIELDS if not getattr(row, field)]
    assert not unmet, (
        f"the fixture's row declares no {unmet} — the bundle probes would "
        f"compare two empty sets for those kinds; declare one name of each"
    )


def test_every_engine_fact_is_pinned() -> None:
    """The field axis, both ways: EngineFacts' fields and `_FACT_SOURCES`'
    keys are the same set. A field with no named engine source cannot be
    reviewed for whether it is the RIGHT value."""
    facts_cls = _narrowing().EngineFacts
    fields = frozenset(facts_cls.__dataclass_fields__)
    assert fields == frozenset(_FACT_SOURCES), (
        f"EngineFacts fields {sorted(fields)} disagree with the pinned "
        f"sources {sorted(_FACT_SOURCES)}"
    )


@pytest.mark.parametrize("field", sorted(_FACT_SOURCES), ids=lambda f: f)
def test_engine_fact_carries_the_engine_value(field: str) -> None:
    """One cell per fact: the binder's bundle equals the engine expression
    `_FACT_SOURCES` names — compared as the deep-frozen SNAPSHOT the fact now
    is, so a round-state frame's `played: []` reads as the `played: ()` the
    freeze produces (same value, immutable shape) rather than failing on the
    list-vs-tuple the purity guarantee deliberately introduces."""
    narrowing = _narrowing()
    rs = _live_state()
    facts = narrowing.engine_facts(rs, actor=1)
    expected: dict[str, Any] = {
        "seating": rs.seating,
        "team_of": reads_mod.deep_freeze(rs.team_of),
        "rank_index": reads_mod.deep_freeze(rs.rank_index),
        "round_state": reads_mod.deep_freeze(rs.last_round_state),
        "last_round_state": reads_mod.deep_freeze(rs.last_round_state),
        "actor": 1,
    }
    assert getattr(facts, field) == expected[field]


def test_engine_facts_holds_no_live_engine_object_by_identity() -> None:
    """The immutability walk is NOT enough on its own: post the copy rule, a
    frozen+slots value passed by identity is still a leak (`object.__setattr__`
    reaches the engine's object), yet the walker treats frozen+slots as safe.
    So pin the copy directly — engine_facts freezes every field, so no
    dataclass/mapping fact is the engine's live object. This is the guard that
    would have caught `seating` being passed by identity. (A scalar like
    `actor` may keep identity — safe, nothing to setattr.)"""
    narrowing = _narrowing()
    rs = _live_state()
    facts = narrowing.engine_facts(rs, actor=0)
    sources = {
        "seating": rs.seating,  # a frozen+slots dataclass -> must be a copy
        "team_of": rs.team_of,
        "rank_index": rs.rank_index,
        "last_round_state": rs.last_round_state,
    }
    for field, src in sources.items():
        got = getattr(facts, field)
        assert got is not src, f"engine_facts exposed the live rs {field} by identity"
        # value-equal to the FROZEN form (a round-state `played` list reads as
        # a tuple after the freeze, so compare against deep_freeze, not src).
        assert got == reads_mod.deep_freeze(src), f"the {field} copy changed value"


def test_the_two_round_state_views_are_distinct() -> None:
    """`round_state` is the `state` pronoun's view (the LIVE frame while a
    round runs); `last_round_state` is the terminal frame. Tarot and Belote
    read the first, Tichu's `tichu_dragon_won` the second — collapsing them
    changes behavior while a round is active, which is exactly what this
    stage must not do."""
    narrowing = _narrowing()
    rs = _live_state()
    rs.mech_state.append({"marker": "live"})
    facts = narrowing.engine_facts(rs, actor=None)
    assert facts.round_state == {"marker": "live"}
    assert facts.last_round_state is not None
    assert facts.last_round_state["marker"] == "terminal"
    assert facts.round_state != facts.last_round_state


def test_engine_facts_is_frozen() -> None:
    """Structural, not conventional: a primitive cannot write back."""
    narrowing = _narrowing()
    facts = narrowing.engine_facts(_live_state(), actor=None)
    with pytest.raises((AttributeError, TypeError)):
        # `facts` is typed Any here (the module is imported lazily), so this
        # is a RUNTIME check that frozen+slots really refuses the write —
        # which is the point: the guarantee must hold for a game module that
        # mypy never sees as anything but values.
        facts.actor = 3


# --- grid (d): GameReads carries exactly the declared row -------------------


def test_game_reads_carries_exactly_the_declared_row() -> None:
    """The bundle is bounded by PRIMITIVE_READS: every declared name present,
    no undeclared name reachable. This is the property that makes the binder
    a narrowing rather than a rename of `Ctx`."""
    rs = _bundle_state()
    row = _bundle_row()
    bundle = reads_mod.game_reads(rs, row)
    assert frozenset(bundle.singles) == row.single_zones
    assert frozenset(bundle.families) == row.zone_families
    assert frozenset(bundle.state) == row.state_vars
    assert frozenset(bundle.arrivals) == row.arrival_zones
    # Anti-vacuity for the four equalities above: each compares a NON-EMPTY
    # pair, so a half the binder stopped materializing fails rather than
    # agreeing with an empty declaration.
    empty = [f.name for f in _dc_fields(bundle) if not getattr(bundle, f.name)]
    assert not empty, (
        f"the bundle materialized no {empty} — those equalities compare two "
        f"empty sets; `_BUNDLE_ROW` declares a name of every kind"
    )
    assert _UNDECLARED_FAMILY not in row.zone_families, (
        f"{_UNDECLARED_FAMILY!r} is in the row now — the negative witness below "
        f"no longer discriminates; pick another name outside the row"
    )
    assert _UNDECLARED_FAMILY not in bundle.families, (
        "the bundle exposed a zone the row does not declare — the binder is "
        "handing over more than the declaration bounds"
    )


def test_every_bundle_half_refuses_an_absent_name_typed() -> None:
    """An undeclared name is ABSENT from the bundle, which makes reading one a
    lookup miss — and a miss on a plain mapping is a bare `KeyError` naming the
    key and nothing else, in a module the reader has no reason to suspect. The
    declaration is what bounds the bundle, so the miss is the declaration's
    error and says so.

    Quantified over `GameReads`' own fields rather than the two halves a
    corpus primitive happens to read, so a fifth half arrives covered.

    does not prove: the INSTANCE grain — an absent instance key inside a
    present half (`families[name][seat]`, a narrowed half's seat, an indexed
    state variable's inner dict) is still a bare `KeyError`, because the
    typed miss guards the half's outer mapping only (issue #501)."""
    bundle = reads_mod.game_reads(_bundle_state(), _bundle_row())
    halves = [f.name for f in _dc_fields(bundle)]
    assert halves, "GameReads carries no half — the cells below would be vacuous"
    for half in halves:
        with pytest.raises(reads_mod.PrimitiveReadError, match="no_such_name"):
            getattr(bundle, half)["no_such_name"]
        # `.get` is the second read form the mapping protocol offers, and
        # `dict.__missing__` does not reach it: unguarded it answers `None`,
        # which reads exactly like a declared name whose value is absent.
        with pytest.raises(reads_mod.PrimitiveReadError, match="no_such_name"):
            getattr(bundle, half).get("no_such_name")
        with pytest.raises(reads_mod.PrimitiveReadError, match="no_such_name"):
            getattr(bundle, half).get("no_such_name", "a default")


def test_a_bundle_half_stays_immutable_and_iterable() -> None:
    """The typed miss is a facet of the half, not a replacement for it: the
    bundle is still a read-only mapping a primitive iterates, and still refuses
    a write. A half that gained a miss and lost the freeze would trade one
    silent-wrong-answer shape for a worse one."""
    row = _bundle_row()
    bundle = reads_mod.game_reads(_bundle_state(), row)
    assert frozenset(bundle.state) == row.state_vars
    assert dict(bundle.state) == {n: bundle.state[n] for n in row.state_vars}
    assert "no_such_name" not in bundle.state
    with pytest.raises(TypeError):
        bundle.state["injected"] = 1  # type: ignore[index]


def test_game_reads_cards_are_immutable() -> None:
    """Zone cards arrive as tuples: a primitive cannot mutate a live zone
    through the bundle (today it receives the Zone's own mutable list)."""
    rs = _bundle_state()
    row = _bundle_row()
    probe = min(row.single_zones)
    rs.zones.single(probe).cards.append(Card("7", "hearts"))
    bundle = reads_mod.game_reads(rs, row)
    assert isinstance(bundle.singles[probe], tuple)


# --- grid (d'): NOTHING mutable is reachable through a bundle, at any depth --
#
# A shallow freeze (proxy the outer dict only) is a false guarantee: an
# indexed state variable is a live `{player: value}` dict, and a round-state
# frame nests a `played` list, so `gr.state["coins"][p] = 0` or
# `facts.round_state["played"].append(...)` reaches straight through and
# corrupts engine state. The property is deep and shape-agnostic, so the
# check walks the WHOLE materialized structure rather than the two shapes we
# happen to know about today.

# str/bytes are the ONLY atomic sequences; `bytearray` is deliberately absent
# — it is mutable and must be flagged if it survives unfrozen (deep_freeze's
# blind spot the first time, so the walker must NOT share it).
_ATOMIC: tuple[type, ...] = (str, bytes)

# A deliberately deep, mixed-shape value: dict -> list -> dict -> set/tuple,
# with atomics (str) that must NOT be shredded into characters; BOTH a plain
# `set` (must be converted) and a `frozenset` (passes through); a `bytearray`
# (a mutable builtin the freeze must convert); and a `StructValue` whose
# `.fields` is a live dict behind a frozen dataclass (a mutable WRAPPER, not a
# leaf). Injected into both bundles so the walker has every shape to descend.
def _nested() -> dict[int, Any]:
    from cardlang.runtime.state import StructValue

    return {
        0: {
            "layer": [1, {"deep": (2, 3), "mset": {4, 5}, "fset": frozenset({6, 7})}],
            "raw": bytearray(b"ab"),
            "sv": StructValue("Contract", {"level": 3, "nest": [8, {"z": {9}}]}),
            "tag": "keep",
        },
        1: [{"pair": (10, 11)}, [12, [13, {"k": [14]}]]],
    }


_NESTED: dict[int, Any] = _nested()


def _reachable_mutable(value: Any, path: str = "") -> list[str]:
    """Every path at which a MUTABLE container — or a mutable field behind a
    value WRAPPER — is reachable inside `value`. Empty means the whole
    structure is immutable at every depth and through every dataclass. This
    walker recurses into dataclass fields on purpose: a `StructValue` is not a
    Mapping/Sequence/Set, so a walker that stopped at it (as deep_freeze first
    did) would call its live `.fields` dict a leaf and stay vacuously green."""
    import dataclasses as _dc
    from collections.abc import Mapping as _Map
    from collections.abc import Sequence as _Seq
    from collections.abc import Set as AbstractSet

    bad: list[str] = []
    if isinstance(value, _ATOMIC):
        return bad
    if isinstance(value, _Map):
        if not isinstance(value, MappingProxyType):
            bad.append(f"{path}: mutable mapping {type(value).__name__}")
        for k, v in value.items():
            # KEYS are traversed too, not just values — a mutable-hashable key
            # is reachable by iterating the proxy, deep_freeze's former blind
            # spot. Descending each key catches it independently.
            bad += _reachable_mutable(k, f"{path}.key({k!r})")
            bad += _reachable_mutable(v, f"{path}[{k!r}]")
    elif isinstance(value, AbstractSet):
        if not isinstance(value, frozenset):
            bad.append(f"{path}: mutable set {type(value).__name__}")
        for i, v in enumerate(sorted(value, key=repr)):
            bad += _reachable_mutable(v, f"{path}{{{i}}}")
    elif isinstance(value, _Seq):  # bytearray lands here (not atomic) -> flagged
        if not isinstance(value, tuple):
            bad.append(f"{path}: mutable sequence {type(value).__name__}")
        for i, v in enumerate(value):
            bad += _reachable_mutable(v, f"{path}[{i}]")
    elif _dc.is_dataclass(value) and not isinstance(value, type):
        # A dataclass is writable unless it is BOTH frozen AND slotted: a
        # non-frozen one takes `box.value = …`; a frozen-but-non-slotted one
        # takes `box.__dict__["value"] = …` (a writable __dict__ bypasses
        # frozen). Descending fields without checking the wrapper is
        # deep_freeze's own former blind spot, so flag both here.
        if not getattr(value, "__dataclass_params__").frozen:
            bad.append(f"{path}: mutable (non-frozen) dataclass {type(value).__name__}")
        elif hasattr(value, "__dict__"):
            bad.append(f"{path}: frozen-but-non-slotted dataclass {type(value).__name__}")
        for f in _dc.fields(value):
            bad += _reachable_mutable(getattr(value, f.name), f"{path}.{f.name}")
    return bad


_COUP_ROW = reads_mod.row("cardlang/runtime/coup.py", "coup.cardlang")


def _coup_row_state() -> RuntimeState:
    """A state populated for the WHOLE of coup's declared row — `game_reads`
    materializes every declared name, so a partial fixture would fail the
    read before the immutability check it exists to make."""
    decls = (
        n.ZoneDecl(name="influence", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="revealed", index="player", type_ref=n.TypeRef(name="Pile")),
        n.ZoneDecl(name="court_deck", index=None, type_ref=n.TypeRef(name="Deck")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    rs.declare("coins", False, {0: 2, 1: 2})
    rs.declare("alive", False, {0: True, 1: True})
    rs.declare("treasury", False, 44)
    return rs


def test_game_reads_is_deeply_immutable_at_any_depth() -> None:
    """A primitive cannot mutate engine state through GameReads at ANY depth
    or shape — not just the zone-card list. Inject arbitrary nesting into a
    declared state variable and prove nothing mutable survives, and that the
    bundle is a SNAPSHOT (mutating the live source afterward does not leak)."""
    from copy import deepcopy

    rs = _coup_row_state()
    live = deepcopy(_NESTED)
    rs.set("coins", live)  # coins is a declared indexed state var of coup's row
    bundle = reads_mod.game_reads(rs, _COUP_ROW)

    # Walk EVERY field of the bundle, not just the one carrying the nesting —
    # state, families and singles all go through the same freeze.
    bad: list[str] = []
    for fname in ("state", "families", "singles"):
        bad += _reachable_mutable(getattr(bundle, fname), f"gr.{fname}")
    assert not bad, "mutable containers reachable through GameReads:\n" + "\n".join(bad)

    before = repr(bundle.state["coins"])
    live[0]["layer"].append("intrusion")  # mutate the ORIGINAL after building
    assert repr(bundle.state["coins"]) == before, (
        "the bundle tracked a later mutation of live engine state — it is a "
        "view, not the snapshot the purity guarantee requires"
    )


def test_engine_facts_round_state_is_deeply_immutable_at_any_depth() -> None:
    """Both round-state facts are deep snapshots: a primitive cannot mutate
    `rs.mech_state` / `rs.last_round_state` through them at any depth."""
    from copy import deepcopy

    narrowing = _narrowing()
    rs = _live_state()
    rs.mech_state.append({"played": [(0, "a"), (1, "b")], "nest": deepcopy(_NESTED)})
    rs.last_round_state = {"played": [], "nest": deepcopy(_NESTED)}
    facts = narrowing.engine_facts(rs, actor=0)

    for name in ("round_state", "last_round_state"):
        bad = _reachable_mutable(getattr(facts, name), f"facts.{name}")
        assert not bad, f"mutable through facts.{name}:\n" + "\n".join(bad)

    before = repr(facts.round_state)
    rs.mech_state[-1]["played"].append((2, "c"))  # mutate live frame after bind
    assert repr(facts.round_state) == before, (
        "facts.round_state tracked a later mutation of rs.mech_state — a view, "
        "not a snapshot"
    )


def test_deep_freeze_and_walker_reject_a_non_frozen_dataclass() -> None:
    """A non-frozen dataclass whose fields are already immutable would pass
    the identity fast path (`deep_freeze(box) is box`) and stay writable.
    deep_freeze refuses it, and the walker flags it independently — neither
    shares the blind spot, so the immutability guarantee is not vacuous for
    the one wrapper shape a `replace` copy could not have fixed."""
    from dataclasses import dataclass as _dataclass

    @_dataclass
    class Box:  # deliberately NOT frozen
        value: int

    box = Box(1)
    with pytest.raises(TypeError, match="non-frozen dataclass"):
        reads_mod.deep_freeze(box)
    assert any("non-frozen" in b for b in _reachable_mutable(box, "box")), (
        "the walker treated a writable dataclass as an immutable leaf"
    )


def test_deep_freeze_and_walker_reject_a_frozen_but_non_slotted_dataclass() -> None:
    """`frozen=True` alone is not immutability: without `slots=True` the
    instance keeps a writable `__dict__`, so `obj.__dict__[f] = …` bypasses
    frozen. deep_freeze refuses it (a `replace` copy is the same mutable
    class) and the walker flags it — the corpus `Play` types were the real
    instance, now slotted, so this only fires on a new one."""
    from dataclasses import dataclass as _dataclass

    @_dataclass(frozen=True)  # frozen, but NOT slotted
    class LooseFrozen:
        value: int

    obj = LooseFrozen(1)
    assert hasattr(obj, "__dict__")  # the writable escape hatch
    with pytest.raises(TypeError, match="WITHOUT slots"):
        reads_mod.deep_freeze(obj)
    assert any("non-slotted" in b for b in _reachable_mutable(obj))


def test_corpus_play_types_are_slotted() -> None:
    """The three climb `Play` types flow through `round_state["current"]`, so
    they must be truly immutable (frozen AND slotted), not just frozen —
    otherwise deep_freeze would refuse them mid-playout."""
    from cardlang.runtime.bigtwo import Play as BigTwoPlay
    from cardlang.runtime.president import Play as PresidentPlay
    from cardlang.runtime.tichu_combinations import Play as CombinationsPlay

    for cls in (BigTwoPlay, CombinationsPlay, PresidentPlay):
        # The `key` field types differ across the three (tuple/float/int); the
        # values are irrelevant to the slots check, so ignore the arg types.
        inst = cls("single", 1, 5, ())  # type: ignore[arg-type]
        assert not hasattr(inst, "__dict__"), f"{cls.__module__}.Play is not slotted"
        # deep_freeze does not refuse it (frozen+slots), but COPIES it — never
        # returns the engine's live object by identity (see the confinement
        # test below for why).
        frozen = reads_mod.deep_freeze(inst)
        assert frozen == inst and frozen is not inst


def test_deep_freeze_copies_frozen_dataclasses_to_confine_object_setattr() -> None:
    """`frozen=True, slots=True` blocks `c.rank = …` but NOT
    `object.__setattr__(c, "rank", …)`. So deep_freeze must not return the
    live engine object by identity: it copies, and the back door then hits the
    copy, leaving the original (the one in engine state) untouched."""
    original = Card("7", "hearts")
    frozen = reads_mod.deep_freeze(original)
    assert frozen is not original, "deep_freeze returned the live engine object"
    object.__setattr__(frozen, "rank", "K")  # the back door, on the copy
    assert original.rank == "7", "mutating the copy reached the engine's Card"

    # And the same inside a bundle-shaped structure: the Card in the frozen
    # snapshot is a distinct object from the one in the source list.
    src = [Card("8", "spades")]
    snap = reads_mod.deep_freeze({0: src})
    assert snap[0][0] is not src[0]


def test_deep_freeze_freezes_mapping_keys_not_just_values() -> None:
    """A mapping keyed by a mutable-but-hashable object (a dataclass with
    `unsafe_hash=True`) would hand the live key back through iteration. Freezing
    values only left that key writable — deep_freeze refuses the key too, and
    the walker traverses keys so it doesn't share the blind spot. A safe key
    (str/tuple) is preserved, so lookups still work."""
    from dataclasses import dataclass as _dataclass

    @_dataclass(unsafe_hash=True)
    class MutableKey:  # hashable, but its fields can be reassigned
        n: int

    with pytest.raises(TypeError, match="non-frozen dataclass"):
        reads_mod.deep_freeze({MutableKey(1): "v"})
    assert any("non-frozen" in b for b in _reachable_mutable({MutableKey(1): "v"}))

    # A safe key survives with lookups intact.
    frozen = reads_mod.deep_freeze({("a", 1): {"x": [2]}})
    assert not _reachable_mutable(frozen)
    assert frozen[("a", 1)]["x"] == (2,)


def test_collection_args_are_frozen_at_the_call_boundary() -> None:
    """The positional-argument channel, not just the bundles: a collection
    argument from a zone reaches a primitive as the zone's LIVE `.cards` list
    (`elements()` returns it by reference), so the native-call boundary freezes
    it. Without this a primitive could `cards.clear()` the argument and empty
    the zone."""
    from cardlang.builtins.signatures import CALL_SIGS
    from cardlang.runtime.reads import coerce_args
    from cardlang.runtime.state import Zone

    sig = CALL_SIGS["gin_valid_meld"]  # its one parameter is a TCollection
    z = Zone()
    z.cards.extend([Card("7", "clubs"), Card("8", "clubs")])
    coerced = coerce_args(sig, [z])[0]
    assert coerced is not z.cards, "the argument is still the live zone list"
    assert isinstance(coerced, tuple)  # an immutable snapshot
    assert list(coerced) == [Card("7", "clubs"), Card("8", "clubs")]  # same contents
    assert not _reachable_mutable(coerced)  # deeply immutable, like the bundles


def test_scalar_card_args_are_copied_at_the_call_boundary() -> None:
    """A scalar `Card` argument (a `TCard` param) is the same leak as a
    collection: a frozen+slots Card is mutable via `object.__setattr__`, so
    `coerce_args` copies it rather than passing the engine's live card.
    Immutable scalars (`Player`, ...) pass through unchanged."""
    from cardlang.builtins.signatures import CALL_SIGS
    from cardlang.runtime.reads import coerce_args

    card = Card("3", "hearts")
    (coerced,) = coerce_args(CALL_SIGS["card_points"], [card])
    assert coerced == card and coerced is not card, "the live engine Card leaked"
    object.__setattr__(coerced, "rank", "K")  # back door, on the copy
    assert card.rank == "3", "mutating the copy reached the engine's Card"

    # An immutable scalar (a TPlayer int) is a no-op, not refused.
    p_sig = CALL_SIGS["canasta_stage_ok"]  # [TPlayer, TCard]
    assert coerce_args(p_sig, [1, card])[0] == 1


def test_climb_follow_freezes_the_standing_play() -> None:
    """`ClimbForm.candidates` passes the live standing `Play` (`state["current"]`)
    to the follow query; freeze it there, or a follow primitive could
    `object.__setattr__` its key/kind/cards and corrupt the engine's play.
    Driven via `object.__new__` with a capturing follow query."""
    from cardlang.runtime import reads as reads_mod2
    from cardlang.runtime.bigtwo import Play
    from cardlang.runtime.mechanics import ClimbForm
    from cardlang.runtime.state import Ctx, RuntimeState, Zone, ZoneStore

    seen: dict[str, Any] = {}

    def follow(facts: Any, gr: Any, hand: Any, current: Any) -> list[Any]:
        seen["current"] = current
        return []

    form = object.__new__(ClimbForm)
    form.climb_row = reads_mod2.PrimitiveReads(module="x", game_file="y")  # empty
    form.hands = {0: Zone([Card("7", "hearts")])}
    form.lead_query = lambda f, g, h: []
    form.follow_query = follow
    rs = RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))
    standing = Play("single", 1, (5,), (Card("8", "spades"),))
    form.candidates(0, {"current": standing, "last": 0}, ctx)

    assert seen["current"] == standing and seen["current"] is not standing, (
        "the follow query received the engine's live standing Play"
    )


def test_peg_direct_arm_args_are_frozen(monkeypatch: Any) -> None:
    """The two cribbage peg arms read live engine state directly (not through
    a bundle), so `call()` freezes their collection args at the site. Capture
    what the primitive actually receives and prove it is immutable."""
    from cardlang.runtime import cribbage
    from cardlang.runtime import primitives as stdlib
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore

    decls = (n.ZoneDecl(name="play_pile", index=None, type_ref=n.TypeRef(name="Pile")),)
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.zones.single("play_pile").cards.extend([Card("7", "clubs"), Card("7", "hearts")])
    rs.rank_index = {"7": 0}
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))

    seen: dict[str, Any] = {}

    def capture_pair(seq: Any) -> int:
        seen["pair"] = seq
        return 0

    def capture_run(seq: Any, order: Any) -> int:
        seen["seq"], seen["order"] = seq, order
        return 0

    monkeypatch.setattr(cribbage, "peg_pair_points", capture_pair)
    monkeypatch.setattr(cribbage, "peg_run_points", capture_run)
    stdlib.call("peg_pair_points", [], ctx)
    stdlib.call("peg_run_points", [], ctx)

    live_cards = rs.zones.single("play_pile").cards
    for key in ("pair", "seq", "order"):
        assert not _reachable_mutable(seen[key], f"peg {key}"), f"{key} not frozen"
    assert seen["pair"] is not live_cards and seen["seq"] is not live_cards  # snapshots
    assert isinstance(seen["order"], MappingProxyType)  # rank_index frozen too


def test_trick_outcome_freezes_its_collection_args() -> None:
    """TrickForm.outcome hands the outcome callback its plays and rank index
    directly, so both are frozen at the site — the direct-call analogue of the
    argument boundary. Driven via `object.__new__` so no full form is built."""
    from cardlang.runtime.mechanics import TrickForm
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore

    seen: dict[str, Any] = {}

    def capture(played: Any, led_suit: Any, trump: Any, rank_index: Any) -> int:
        seen["played"], seen["rank_index"] = played, rank_index
        return 0  # a seat, satisfying the `isinstance(winner, int)` assert

    form = object.__new__(TrickForm)
    form.winner_fn = capture
    # The uniform contract: `outcome` selects the call shape from the winner's
    # NAME against `TRICK_ORDER_GATED_WINNERS`, so the probe must say which
    # contract it is standing in for (cardlang/builtins/functions.py).
    form.winner_fn_name = "highest_of_led_suit"
    form.trump = None
    rs = RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))
    rs.rank_index = {"7": 0}
    # No `mech_state` frame is seeded: `outcome` reads only the accumulator it is
    # handed. It needed one when the hook still popped the frame stack itself
    # (tests/test_round_state_registry.py::test_outcome_hook_leaves_the_frame_stack_alone).
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k]))
    state = {
        "trick_terminated_early": False,
        "led_suit": "hearts",
        "played": [(0, Card("7", "hearts"))],
    }
    form.outcome(state, ctx)

    assert not _reachable_mutable(seen["played"], "played"), "played not frozen"
    assert not _reachable_mutable(seen["rank_index"], "rank_index"), "rank_index not frozen"
    assert seen["played"] is not state["played"]  # a snapshot, not the live list


def test_every_engine_facts_field_is_deeply_immutable() -> None:
    """The whole bundle, not two chosen fields: EVERY EngineFacts field is
    immutable at every depth. Nested data is injected into the round-state
    frames; the scalar/tuple/frozen-dataclass fields pass by construction."""
    narrowing = _narrowing()
    rs = _live_state()
    rs.mech_state.append({"played": [(0, "a")], "nest": _NESTED})
    facts = narrowing.engine_facts(rs, actor=1)
    offenders: list[str] = []
    for name in facts.__dataclass_fields__:
        offenders += _reachable_mutable(getattr(facts, name), f"facts.{name}")
    assert not offenders, "mutable containers in EngineFacts:\n" + "\n".join(offenders)


# --- grid (e): the trace-returning registry, two ways -----------------------


@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            nm,
            marks=() if nm in MIGRATED else _pending(f"{nm} {_STAGE2}"),
            id=nm,
        )
        for nm in sorted(EMITS_TRACE)
    ],
)
def test_tracing_primitive_returns_events(name: str) -> None:
    """A listed primitive hands its events back as data. Until it is
    migrated it still emits through `ctx.trace`, so the cell is a strict
    xfail — the same self-closing shape as the guards above."""
    impl = next(i for i in _GAME_IMPLS if i.primitive == name)
    scan = _scan_module(impl.module)
    assert "ctx.trace" not in scan.hits, (
        f"{name} still emits through ctx.trace — a narrowed primitive returns "
        f"(value, events) and the dispatch layer performs the emission"
    )


def test_no_unlisted_migrated_primitive_emits_traces() -> None:
    """The other direction: a module that still touches `ctx.trace` after
    migration means a tracing primitive escaped EMITS_TRACE."""
    for impl in _GAME_IMPLS:
        if impl.primitive not in MIGRATED or impl.primitive in EMITS_TRACE:
            continue
        scan = _scan_module(impl.module)
        assert "ctx.trace" not in scan.hits, (
            f"{impl.module} still reaches ctx.trace but {impl.primitive} is "
            f"not in EMITS_TRACE — list it, or route the emission back as data"
        )


# --- residual (1): the game knowledge that stays in engine core -------------

_ENGINE_CORE_GAME_KNOWLEDGE: frozenset[str] = frozenset(
    {
        "bridge_auction_outcome",
        "pinochle_auction_outcome",
        "tarot_auction_outcome",
    }
)


def test_engine_core_game_knowledge_is_named() -> None:
    """The residual, pinned so it cannot grow quietly. These primitives are
    implemented inside primitives.py — engine core — so the game-module
    guard does not reach them; stage 4 (co-location) owns their move. A NEW
    per-game function added to primitives.py fails here."""
    rows = {r.game_file for r in PRIMITIVE_READS if r.module == "cardlang/runtime/primitives.py"}
    assert rows == {
        "bridge.cardlang",
        "cribbage.cardlang",
        "pinochle.cardlang",
        "french-tarot.cardlang",
    }, (
        f"primitives.py's per-game declared-reads rows changed to {sorted(rows)} — "
        f"engine core is holding game knowledge for a different set of games "
        f"than this ledger's residual (1) records"
    )
    dispatched = {i.primitive for i in _implementations()}
    assert not (_ENGINE_CORE_GAME_KNOWLEDGE & dispatched), (
        "a residual primitive is now dispatched to a game module — move it "
        "out of this table and into the grid proper"
    )
