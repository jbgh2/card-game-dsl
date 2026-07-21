"""The narrow primitive interface — completeness ledger.

status:     stage 2 COMPLETE — all 15 game modules are free of every
            engine handle, so the crossed grid is green with nothing
            excused. Stage 3 (`primitives { }`) narrows the bundles from
            module- to primitive-granularity; residual (2) is its brief.

property:   a game-local primitive sees VALUES, never an engine handle. Its
            implementation names no `Ctx` and no `RuntimeState`; everything
            it may read arrives as the two bundles the binder builds — its
            module's declared name-keyed reads (`GameReads`, bounded by
            `PRIMITIVE_READS`) and the engine-structural facts
            (`EngineFacts`) — so "this primitive cannot mutate state, make a
            decision, or observe an undeclared name" is structural, not a
            property of review.
domain:     every game-local primitive (derived: the dispatch tables in
            `cardlang/runtime/stdlib.py`, mapped name -> implementing
            module by AST, restricted to modules outside the engine core)
            x every forbidden engine handle (derived: `Ctx`'s own field set
            plus the engine types, NOT the handles modules happen to use
            today) x every `EngineFacts` field (derived: the dataclass).
registry:   `_ENGINE_CORE` (the module axis's only hand-authored half, and
            the safe polarity — a NEW runtime module is a game module by
            default and must pass the wall); `NARROWED` (sites proven
            handle-free) and `MIGRATED` (primitives), both now covering
            everything the dispatch routes; `_STILL_REACHES` (the
            per-cell work list, now EMPTY — stage 2 is complete);
            `EMITS_TRACE` (primitives returning events alongside a value);
            `STDLIB_*` in `cardlang/stdlib/functions.py` (the name axis).
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
            second stops the bundle growing;
            (d) `GameReads`: the bundle carries exactly the module's
            declared row and nothing else — an undeclared name is absent,
            not merely unfetched; and NOTHING mutable is reachable through
            either bundle at any depth or shape (`deep_freeze`), proven by
            descending the whole materialized structure over a fixture that
            crosses every mutable shape the DSL can produce — nested
            dict/list/set/tuple, a plain `set` AND a `frozenset`, a
            `bytearray` (a mutable builtin), and a `StructValue` whose
            `.fields` is a live dict behind a frozen dataclass (a mutable
            WRAPPER, not a leaf). The walker recurses dataclass fields AND
            checks the wrapper's own frozen-ness, so it cannot share
            deep_freeze's blind spots, and deep_freeze REFUSES any leaf it
            cannot prove immutable — including a NON-frozen dataclass, which
            a field-frozen `replace` copy could not have fixed — rather than
            passing a possibly-mutable object through. The holes Codex found
            (indexed state dict, round-state `played` list, StructValue
            fields, bytearray, and the non-frozen-dataclass identity fast
            path) were each reproduced before the fix closed them;
            (d') the primitive boundary is TWO channels, both frozen: the
            bundles above, and the positional COLLECTION arguments — a
            collection arg from a zone reaches a primitive as the zone's
            live `.cards` list (`elements()` returns it by reference), so
            EVERY site handing a narrowed primitive a collection freezes
            it: the generic `call()` coercion (`_coerce_args`), the climb
            hand, and the direct sites that read live engine state rather
            than a bundle — the two cribbage peg arms and the trick
            `outcome_fn` (`played` + `rank_index`). Keys are frozen with
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
            `cardlang/runtime/stdlib.py`, which is engine core, so the
            game-module wall does not reach them; they are game knowledge
            in the language package and stage 4 (co-location) owns their
            move. Wall: `test_engine_core_game_knowledge_is_named`, which
            fails if that set changes without this ledger changing.
            Record: docs/roadmap.md, "Primitive sidecars".
            (2) `EngineFacts` is MODULE-granular by ratified stage-2 scope
            (2A): a primitive receives the facts bundle whole rather than
            the per-primitive `reads` clause of the design note's §2. The
            narrowing that remains is stage 3's, and until it lands a
            primitive can read a fact it does not need, and every call
            materializes its module's whole row whether or not it reads
            any of it. Wall: the field set is closed and every field is
            pinned to a consumer (c), so the bundle cannot grow
            speculatively; the per-call cost is recorded in
            docs/roadmap.md, "Primitive sidecars".

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
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from types import MappingProxyType
from typing import Any

import pytest

from cardlang.ast import nodes as n
from cardlang.runtime import reads as reads_mod
from cardlang.runtime.reads import PRIMITIVE_READS
from cardlang.runtime.state import RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating
from cardlang.stdlib.functions import (
    STDLIB_AUCTION_OUTCOMES,
    STDLIB_CALL_FUNCS,
    STDLIB_CLIMB_FOLLOWS,
    STDLIB_CLIMB_LEADS,
    STDLIB_EARLY_PREDICATES,
    STDLIB_TRICK_OUTCOMES,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
RUNTIME_DIR = REPO_ROOT / "cardlang" / "runtime"

# --- axis 1: the game-module set -------------------------------------------
#
# Hand-authored as the EXCLUSION half only, so the polarity is safe: a new
# file under cardlang/runtime/ is a game module until someone argues it into
# this table, and therefore has to pass the wall. Each row names why the
# engine core legitimately holds an engine handle.
_ENGINE_CORE: dict[str, str] = {
    "__init__.py": "package init",
    "chooser.py": "the decision seam itself",
    "driver.py": "engine core — builds and threads Ctx",
    "evaluate.py": "engine core — the expression interpreter",
    "execute.py": "engine core — the statement interpreter",
    "mechanics.py": "engine core — the round machinery",
    "observe.py": "engine core — the projection substrate",
    "phases.py": "engine core — phase sequencing",
    "reads.py": "the declared-reads accessors (the sanctioned raw-access site)",
    "rules.py": "engine core — rule application",
    "sidecar.py": "the binder — it BUILDS the bundles, so it holds the handle",
    "state.py": "engine core — defines RuntimeState and Ctx",
    "stdlib.py": "engine core — the dispatch layer that BUILDS the bundles",
    "values.py": "engine core — the value types",
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


@lru_cache(maxsize=None)
def _implementations() -> tuple[Impl, ...]:
    """Derive name -> implementation by parsing the dispatch layer's `match`
    arms. Derived, not listed: a primitive added to the dispatch enters this
    grid automatically, which is what stops the coverage domain from being
    whatever someone remembered to type."""
    tree = ast.parse((RUNTIME_DIR / "stdlib.py").read_text(encoding="utf-8"))
    found: list[Impl] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Match):
            continue
        for case in node.cases:
            pat = case.pattern
            if not (
                isinstance(pat, ast.MatchValue)
                and isinstance(pat.value, ast.Constant)
                and isinstance(pat.value.value, str)
            ):
                continue
            name = pat.value.value
            for mod, func in _dispatch_imports(case.body):
                found.append(Impl(primitive=name, module=mod, func=func))
    return tuple(sorted(found, key=lambda i: (i.primitive, i.module, i.func)))


_ALL_REGISTERED: frozenset[str] = (
    STDLIB_CALL_FUNCS
    | STDLIB_TRICK_OUTCOMES
    | STDLIB_AUCTION_OUTCOMES
    | STDLIB_EARLY_PREDICATES
    | STDLIB_CLIMB_LEADS
    | STDLIB_CLIMB_FOLLOWS
)

_GAME_IMPLS: tuple[Impl, ...] = tuple(
    i for i in _implementations() if i.module in _GAME_MODULES
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
        "belote.py::ROW",
        "belote.py::belote_best_is",
        "belote.py::belote_decl_class",
        "belote.py::belote_decl_height",
        "belote.py::belote_decl_points",
        "belote.py::belote_decl_size",
        "belote.py::belote_decl_slot",
        "belote.py::belote_decl_trump",
        "belote.py::belote_opp_winning",
        "belote.py::belote_royal_player",
        "belote.py::belote_trick_winner",
        "belote.py::belote_trump_height",
        "bigtwo.py::ROW",
        "bigtwo.py::bigtwo_follows",
        "bigtwo.py::bigtwo_lead_options",
        "bigtwo.py::bigtwo_universe",
        "bigtwo.py::first_leader_seat",
        "canasta.py::ROW",
        "canasta.py::canasta_add_ok",
        "canasta.py::canasta_black3_ok",
        "canasta.py::canasta_can_start",
        "canasta.py::canasta_can_take_pile",
        "canasta.py::canasta_canasta_bonus",
        "canasta.py::canasta_close_ok",
        "canasta.py::canasta_discard_ok",
        "canasta.py::canasta_hand_points",
        "canasta.py::canasta_is_black3",
        "canasta.py::canasta_is_red3",
        "canasta.py::canasta_meld_points",
        "canasta.py::canasta_must_take_pile",
        "canasta.py::canasta_pile_rank",
        "canasta.py::canasta_red3_bonus",
        "canasta.py::canasta_stage_ok",
        "canasta.py::canasta_top_is_wild",
        "canasta.py::canasta_top_starts_pile",
        "coup.py::ROW",
        "coup.py::coup_game_summary",
        "coup.py::coup_has_char",
        "coup.py::coup_next_in_game",
        "coup.py::coup_players_in",
        "cribbage.py::ROW",
        "cribbage.py::cribbage_crib_value",
        "cribbage.py::cribbage_show_value",
        "cribbage.py::peg_origin_of",
        "cribbage.py::peg_pair_points",
        "cribbage.py::peg_run_points",
        "cribbage.py::value",
        "doko.py::ROW",
        "doko.py::doko_trick_winner",
        "five_hundred.py::ROW",
        "five_hundred.py::five_hundred_bid_level",
        "five_hundred.py::five_hundred_bid_value",
        "five_hundred.py::five_hundred_follow_ok",
        "five_hundred.py::five_hundred_lead_ok",
        "five_hundred.py::five_hundred_next_bid",
        "five_hundred.py::five_hundred_trick_winner",
        "gin.py::ROW",
        "gin.py::card_points",
        "gin.py::gin_arrange_ok",
        "gin.py::gin_can_declare",
        "gin.py::gin_can_declare_free",
        "gin.py::gin_can_knock",
        "gin.py::gin_deadwood",
        "gin.py::gin_flat_points",
        "gin.py::gin_knock_ok",
        "gin.py::gin_lay_ok_a",
        "gin.py::gin_lay_ok_b",
        "gin.py::gin_lay_ok_c",
        "gin.py::gin_shown_points",
        "gin.py::gin_valid_meld",
        "pinochle.py::ROW",
        "pinochle.py::pinochle_meld_value",
        "president.py::ROW",
        "president.py::president_follows",
        "president.py::president_is_top_rank",
        "president.py::president_lead_options",
        "president.py::president_next_holder",
        "president.py::president_universe",
        "schnapsen.py::ROW",
        "schnapsen.py::schnapsen_trick_winner",
        "skat.py::ROW",
        "skat.py::skat_effective_loss",
        "skat.py::skat_follow_ok",
        "skat.py::skat_matadors",
        "skat.py::skat_next_bid",
        "skat.py::skat_trick_winner",
        "stud.py::ROW",
        "stud.py::bring_in_seat",
        "stud.py::first_to_act_seat",
        "stud.py::pot_share",
        "tarot.py::ROW",
        "tarot.py::tarot_card_points",
        "tarot.py::tarot_excuse_player",
        "tarot.py::tarot_led_suit",
        "tarot.py::tarot_per_opp",
        "tarot.py::tarot_trick_winner",
        "tarot.py::tarot_trump_height",
        "tichu.py::ROW",
        "tichu.py::TICHU_COMBO_CODEC",
        "tichu.py::tichu_card_points",
        "tichu.py::tichu_double_victory",
        "tichu.py::tichu_dragon_won",
        "tichu.py::tichu_first_out",
        "tichu.py::tichu_follows",
        "tichu.py::tichu_lead_options",
        "tichu.py::tichu_mahjong_holder",
        "tichu.py::tichu_next_holder",
        "tichu.py::tichu_opponent_team",
        "tichu.py::tichu_partner",
        "tichu.py::tichu_players_holding",
    }
)

# Primitives narrowed by stage 2 so far, for the module-level wall below.
MIGRATED: frozenset[str] = frozenset(
    {
        "belote_best_is",
        "belote_decl_class",
        "belote_decl_height",
        "belote_decl_points",
        "belote_decl_size",
        "belote_decl_slot",
        "belote_decl_trump",
        "belote_opp_winning",
        "belote_royal_player",
        "bigtwo_first_leader",
        "bigtwo_follows",
        "bigtwo_lead_options",
        "bring_in_seat",
        "canasta_add_ok",
        "canasta_black3_ok",
        "canasta_can_start",
        "canasta_can_take_pile",
        "canasta_canasta_bonus",
        "canasta_close_ok",
        "canasta_discard_ok",
        "canasta_hand_points",
        "canasta_is_black3",
        "canasta_is_red3",
        "canasta_meld_points",
        "canasta_must_take_pile",
        "canasta_pile_rank",
        "canasta_red3_bonus",
        "canasta_stage_ok",
        "canasta_top_is_wild",
        "canasta_top_starts_pile",
        "coup_game_summary",
        "coup_has_char",
        "coup_next_in_game",
        "coup_players_in",
        "cribbage_crib_value",
        "cribbage_show_value",
        "doko_trick_winner",
        "first_to_act_seat",
        "five_hundred_follow_ok",
        "five_hundred_lead_ok",
        "five_hundred_trick_winner",
        "gin_arrange_ok",
        "gin_can_declare",
        "gin_can_declare_free",
        "gin_can_knock",
        "gin_deadwood",
        "gin_flat_points",
        "gin_knock_ok",
        "gin_lay_ok_a",
        "gin_lay_ok_b",
        "gin_lay_ok_c",
        "gin_shown_points",
        "gin_valid_meld",
        "peg_origin_of",
        "pinochle_meld_value",
        "pot_share",
        "president_follows",
        "president_is_top_rank",
        "president_lead_options",
        "president_next_holder",
        "schnapsen_trick_winner",
        "skat_follow_ok",
        "skat_matadors",
        "skat_trick_winner",
        "tarot_excuse_player",
        "tarot_led_suit",
        "tarot_per_opp",
        "tichu_card_points",
        "tichu_double_victory",
        "tichu_dragon_won",
        "tichu_first_out",
        "tichu_follows",
        "tichu_lead_options",
        "tichu_mahjong_holder",
        "tichu_next_holder",
        "tichu_opponent_team",
        "tichu_partner",
        "tichu_players_holding",
    }
)

# Primitives that return `(value, events)` — they compute a real value AND
# emit the engine's own trace vocabulary from a game-local site, so the
# emission travels back as data and the dispatch layer performs it.
EMITS_TRACE: frozenset[str] = frozenset(
    {
        "schnapsen_trick_winner",
        "doko_trick_winner",
        "skat_trick_winner",
        "five_hundred_trick_winner",
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


@lru_cache(maxsize=None)
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
            if isinstance(base, ast.Name) and base.id == "ctx":
                if node.attr in _ctx_surface():
                    note(f"ctx.{node.attr}", node.lineno)
        # A parameter annotated with a forbidden type.
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for arg in [*node.args.args, *node.args.kwonlyargs]:
                ann = arg.annotation
                if isinstance(ann, ast.Name) and ann.id in _FORBIDDEN_TYPES:
                    ctx_params[node.name] = f"{path.name}:{node.lineno} ({arg.arg})"
    return ModuleScan(hits=hits, ctx_params=ctx_params, symbols=symbols)


@lru_cache(maxsize=None)
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
    """The crossed wall. A module is only green once EVERY primitive it
    implements is migrated; until then each of its cells is a strict xfail,
    so finishing a module without updating MIGRATED fails loudly."""
    scan = _scan_module(module)
    where = scan.hits.get(handle, [])
    assert not where, (
        f"{module} still reaches the engine handle {handle!r} at "
        f"{', '.join(where)} — a game module sees values only."
    )


# --- grid (c): EngineFacts ---------------------------------------------------


def _sidecar() -> Any:
    """The mechanism under test. Imported lazily so that, before it exists,
    the cells below fail with this message rather than collapsing the whole
    module into a collection error."""
    try:
        from cardlang.runtime import sidecar
    except ImportError as exc:  # pragma: no cover - the red state
        pytest.fail(
            f"cardlang/runtime/sidecar.py does not exist yet: {exc}. It owns "
            f"EngineFacts, GameReads and the binder."
        )
    return sidecar


# The engine expression each field mirrors. This IS the field axis: a field
# added to EngineFacts without a row here fails `test_every_engine_fact_is_
# pinned`, and a row naming a field that does not exist fails too.
_FACT_SOURCES: dict[str, str] = {
    "seating": "rs.seating",
    "teams": "rs.teams",
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
    "teams": ("facts.teams", "ctx.rs.teams"),
    "team_of": ("facts.team_of", "ctx.rs.team_of"),
    "rank_index": ("facts.rank_index", "ctx.rs.rank_index"),
    "round_state": ("facts.round_state", "ctx.rs.mech_state"),
    "last_round_state": ("facts.last_round_state", "ctx.rs.last_round_state"),
    "actor": ("facts.actor", "ctx.current_player"),
}


@lru_cache(maxsize=None)
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
    facts_cls = _sidecar().EngineFacts
    fields = frozenset(facts_cls.__dataclass_fields__)
    assert fields == frozenset(_FACT_CONSUMERS), (
        f"EngineFacts fields {sorted(fields)} disagree with the consumer map "
        f"{sorted(_FACT_CONSUMERS)} — a new field must name how a game module "
        f"spells its read, or be removed"
    )
    src = _game_module_sources()
    unread = sorted(
        field
        for field, spellings in _FACT_CONSUMERS.items()
        if not any(s in src for s in spellings)
    )
    assert not unread, (
        f"EngineFacts fields no game module reads: {unread}. Remove them, or "
        f"if a field is genuinely needed by work not yet landed, record it as "
        f"a named residual rather than carrying it silently."
    )


def _live_state() -> RuntimeState:
    decls = (
        n.ZoneDecl(name="hand", index="player", type_ref=n.TypeRef(name="Hand")),
        n.ZoneDecl(name="trick_pile", index=None, type_ref=n.TypeRef(name="Pile")),
    )
    rs = RuntimeState(Seating(2), ZoneStore(decls, (0, 1)), random.Random(0))
    rs.push_frame()
    rs.teams = (0, 1)
    rs.team_of = {0: 0, 1: 1}
    rs.rank_index = {"7": 0, "8": 1}
    rs.last_round_state = {"played": [], "marker": "terminal"}
    return rs


def test_every_engine_fact_is_pinned() -> None:
    """The field axis, both ways: EngineFacts' fields and `_FACT_SOURCES`'
    keys are the same set. A field with no named engine source cannot be
    reviewed for whether it is the RIGHT value."""
    facts_cls = _sidecar().EngineFacts
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
    sidecar = _sidecar()
    rs = _live_state()
    facts = sidecar.engine_facts(rs, actor=1)
    expected: dict[str, Any] = {
        "seating": rs.seating,
        "teams": reads_mod.deep_freeze(rs.teams),
        "team_of": reads_mod.deep_freeze(rs.team_of),
        "rank_index": reads_mod.deep_freeze(rs.rank_index),
        "round_state": reads_mod.deep_freeze(rs.last_round_state),
        "last_round_state": reads_mod.deep_freeze(rs.last_round_state),
        "actor": 1,
    }
    assert getattr(facts, field) == expected[field]


def test_the_two_round_state_views_are_distinct() -> None:
    """`round_state` is the `state` pronoun's view (the LIVE frame while a
    round runs); `last_round_state` is the terminal frame. Tarot and Belote
    read the first, Tichu's `tichu_dragon_won` the second — collapsing them
    changes behavior while a round is active, which is exactly what this
    stage must not do."""
    sidecar = _sidecar()
    rs = _live_state()
    rs.mech_state.append({"marker": "live"})
    facts = sidecar.engine_facts(rs, actor=None)
    assert facts.round_state == {"marker": "live"}
    assert facts.last_round_state is not None
    assert facts.last_round_state["marker"] == "terminal"
    assert facts.round_state != facts.last_round_state


def test_engine_facts_is_frozen() -> None:
    """Structural, not conventional: a primitive cannot write back."""
    sidecar = _sidecar()
    facts = sidecar.engine_facts(_live_state(), actor=None)
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
    rs = _live_state()
    row = next(
        r for r in PRIMITIVE_READS if r.module == "cardlang/runtime/schnapsen.py"
    )
    bundle = reads_mod.game_reads(rs, row)
    assert frozenset(bundle.singles) == row.single_zones
    assert frozenset(bundle.families) == row.zone_families
    assert frozenset(bundle.state) == row.state_vars
    assert "hand" not in bundle.families, (
        "the bundle exposed a zone the row does not declare — the binder is "
        "handing over more than the declaration bounds"
    )


def test_game_reads_cards_are_immutable() -> None:
    """Zone cards arrive as tuples: a primitive cannot mutate a live zone
    through the bundle (today it receives the Zone's own mutable list)."""
    rs = _live_state()
    rs.zones.single("trick_pile").cards.append(Card("7", "hearts"))
    row = next(
        r for r in PRIMITIVE_READS if r.module == "cardlang/runtime/schnapsen.py"
    )
    bundle = reads_mod.game_reads(rs, row)
    assert isinstance(bundle.singles["trick_pile"], tuple)


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
    from collections.abc import Set as _Set

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
    elif isinstance(value, _Set):
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
        # A non-frozen dataclass is itself writable (`box.value = …`) even
        # when every field is immutable — descending fields without checking
        # the wrapper is deep_freeze's own former blind spot, so flag it here.
        if not getattr(value, "__dataclass_params__").frozen:
            bad.append(f"{path}: mutable (non-frozen) dataclass {type(value).__name__}")
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

    sidecar = _sidecar()
    rs = _live_state()
    rs.mech_state.append({"played": [(0, "a"), (1, "b")], "nest": deepcopy(_NESTED)})
    rs.last_round_state = {"played": [], "nest": deepcopy(_NESTED)}
    facts = sidecar.engine_facts(rs, actor=0)

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
    (`elements()` returns it by reference), so `call()` freezes it. Without
    this a primitive could `cards.clear()` the argument and empty the zone."""
    from cardlang.runtime import stdlib
    from cardlang.runtime.state import Zone
    from cardlang.stdlib.signatures import CALL_SIGS

    sig = CALL_SIGS["gin_valid_meld"]  # its one parameter is a TCollection
    z = Zone()
    z.cards.extend([Card("7", "clubs"), Card("8", "clubs")])
    coerced = stdlib._coerce_args(sig, [z])[0]
    assert coerced is not z.cards, "the argument is still the live zone list"
    assert isinstance(coerced, tuple)  # an immutable snapshot
    assert list(coerced) == [Card("7", "clubs"), Card("8", "clubs")]  # same contents
    assert not _reachable_mutable(coerced)  # deeply immutable, like the bundles


def test_peg_direct_arm_args_are_frozen(monkeypatch: Any) -> None:
    """The two cribbage peg arms read live engine state directly (not through
    a bundle), so `call()` freezes their collection args at the site. Capture
    what the primitive actually receives and prove it is immutable."""
    from cardlang.runtime import cribbage, stdlib
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
        return 0  # a seat, satisfying the `isinstance(outcome, int)` assert

    form = object.__new__(TrickForm)
    form.outcome_fn = capture
    form.trump = None
    rs = RuntimeState(Seating(2), ZoneStore((), (0, 1)), random.Random(0))
    rs.rank_index = {"7": 0}
    rs.mech_state.append({"terminal": True})
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
    sidecar = _sidecar()
    rs = _live_state()
    rs.mech_state.append({"played": [(0, "a")], "nest": _NESTED})
    facts = sidecar.engine_facts(rs, actor=1)
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
    xfail — the same self-closing shape as the walls above."""
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
    implemented inside stdlib.py — engine core — so the game-module wall
    does not reach them; stage 4 (co-location) owns their move. A NEW
    per-game function added to stdlib.py fails here."""
    rows = {r.game_file for r in PRIMITIVE_READS if r.module == "cardlang/runtime/stdlib.py"}
    assert rows == {
        "bridge.cardlang",
        "cribbage.cardlang",
        "pinochle.cardlang",
        "french-tarot.cardlang",
    }, (
        f"stdlib.py's per-game declared-reads rows changed to {sorted(rows)} — "
        f"engine core is holding game knowledge for a different set of games "
        f"than this ledger's residual (1) records"
    )
    dispatched = {i.primitive for i in _implementations()}
    assert not (_ENGINE_CORE_GAME_KNOWLEDGE & dispatched), (
        "a residual primitive is now dispatched to a game module — move it "
        "out of this table and into the grid proper"
    )
