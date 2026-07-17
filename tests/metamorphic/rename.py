"""T2: alpha-rename (docs/design-notes/metamorphic-suite.md, item 1).

Renames every ZONE and STATE VARIABLE declaration, and every reference to
one, through a generated map. This DSL has no separate player/team
IDENTIFIER syntax to rename alongside them — a named role like `dealer` or
`declarer` (Bridge) is a plain state variable of type `Player`
(`cardlang/ast/nodes.py`, `StateDecl`), so it is already covered by the
state-variable case; there is nothing left over for a third category.

Why a blind textual rename of every matching `NameRef` is sound here, pre-
resolve, with no scope information available yet: `resolve._classify`
(`cardlang/resolve.py`) resolves a bare name against ONE flat, ordered set of
namespaces — locals, then state vars, then zones, then enum values, then
pronouns, then stdlib functions — and only ZONES and STATE VARIABLES are
declared here (rule/move-type/procedure/function/define/type names live in
their own dedicated syntactic slots — `constrains:`, `active_rules:`,
`x.field`, `transition_to:` — never reachable as a bare `NameRef`; see
`resolve._check_duplicate_names`'s docstring). So the only way a blanket
rename of a zone/state name could change what some OTHER `NameRef` of the
same spelling denotes is if that other spelling is a LOCAL BINDER (a `let`,
a loop variable, a move/function/procedure parameter, a struct field)
somewhere in the same game shadowing the zone/state var being renamed — a
local's classification always wins under `_classify`'s ordering, so a
same-spelled local reference would otherwise get swept into the rename too,
denoting something it never denoted.

Two defenses close that gap:

1. Every rename TARGET is chosen fresh with respect to the WHOLE game — not
   just its other declarations, but every string that appears ANYWHERE in
   the parsed tree (`_all_string_tokens`). A target nothing in the game
   already spells cannot be captured by an existing binder, so applying the
   map cannot introduce a NEW shadow that did not exist before.
2. Every rename SOURCE is checked against every name ANY construct in the
   game binds locally, ANYWHERE (`_locally_bound_names` — a flat, not
   scope-precise, union; the same shape as `resolve._template_binders`'s own
   flat collision check, at game scope rather than one rule's, and reusing
   `resolve._walk`/`_introduced_binders` directly rather than
   re-enumerating the binder registry — CLAUDE.md "Stop-and-fix at write
   time": the resolver already owns this table). A source name present in
   that set is excluded from the rename (`RenamePlan.unsafe`) rather than
   renamed unsoundly: somewhere in the game a local of the identical
   spelling could shadow it, and pre-resolve there is no scope information
   to tell which occurrences are the zone/state var and which are the
   local.

`unsafe` is empty across the whole corpus today (test_rename.py pins this
with a test that can fail); a future corpus game that trips it renames
everything else and leaves that one name alone, which is safe, not silent —
the excluded names are on `RenamePlan.unsafe`, not swallowed.

Two more exclusions, found empirically by running this transform and
reading the resulting failures — both real, both OUT of T2's domain (the
spec does not say these names are meaningless), neither a bug in this
transform:

**`hand` is a language-wide magic name, not a renamable zone.** decisions.md
"Declared parameter domains": a `Card`-typed move parameter enumerates "the
acting player's live hand" and "a Card parameter in a game with no
`hand[player]` zone" is rejected with a message — `resolve.py` enforces this
structurally (`z.name == "hand" and z.index == "player"`), and the kernel's
legal-move engine (`runtime/rules.py::legal_cards`) and move-parameter
enumerator (`runtime/mechanics.py::param_domain`) both look it up by that
exact name. Renaming it produces a tree the PIPELINE rejects (or, if the game
declares no Card-parameterized move, one the RUNTIME cannot serve
`Card`-typed candidates for) — squarely a spec-documented exception, the same
shape as T5 excluding an order-sensitive declaration with a citation, not a
defect this transform papers over. `_GLOBAL_EXCLUSIONS` below excludes it
corpus-wide.

**Game-local runtime primitives are written against ONE game's specific
declared spelling.** Eleven corpus games ship a `cardlang/runtime/<game>.py`
module of bespoke Python (kernel-migration.md's sanctioned "game-local
stdlib primitive" pattern — Stud's `pot_share`, Skat's `skat_matadors`,
Tichu's `tichu_mahjong_holder`, …) that reads live `RuntimeState` DIRECTLY,
by the zone/state-variable name ITS AUTHOR gave it — a hardcoded Python
string literal, never derived from the AST the way `execute.py`/`evaluate.py`
read a `NameRef.name` off the tree. That coupling is invisible anywhere in
the DSL or the type checker: nothing about `zones { influence[player] :
Hand<player> }` says "and `coup.py` line 67 also spells this `influence`" —
so this transform's own pairing run is what surfaces it, empirically, as a
`KeyError`/`AttributeError` at PLAYOUT time (the tree passes resolve/
typecheck/expand — the pipeline has no way to know). This is real and worth
recording (CLAUDE.md's report obligation for a found divergence), but it is
not a cardlang defect to fix here: it is exactly the "hand"-name case's
cousin, discovered per name instead of declared as a wall, because no
registry of "which zone names a Python primitive reads" exists to derive it
from — so `_PRIMITIVE_COUPLED_NAMES` below is a hand-maintained, per-game,
file:line-cited exclusion table (the `tests/openspiel_ready/harness.py`
`GameSpec` precedent for per-game test-harness knowledge that cannot be
derived from a registry), not a hand-list standing in for one that could be.
A stale entry (a primitive file that stops reading a name) is harmless — it
just leaves one more name unrenamed than strictly necessary, silently within
this transform's own generosity, never within cardlang's; a MISSING entry
(a primitive starts reading a name not yet excluded) is not silent at all —
it fails the pairing test itself, the same way this whole class was first
found. Were some future game's SAFE set ever empty after every exclusion,
`test_every_game_renames_something` (test_rename.py) fails LOUDLY rather
than the pairing test passing vacuously over nothing renamed — a hard
failure, deliberately, rather than a quieter skip: an empty safe set means
this transform cannot exercise that game AT ALL, which is worth blocking on,
not stepping around — see `test_rename.py`.
"""

from __future__ import annotations

from dataclasses import dataclass, fields, is_dataclass, replace
from pathlib import Path
from typing import Callable, cast

from cardlang.ast import nodes as n
from cardlang.diagnostics import Span
from cardlang.resolve import _introduced_binders, _walk as _resolve_walk

from tests.metamorphic.pairing import Event

_PREFIX = "_mt_"

# The zone `Card`-typed move parameters are structurally required to name
# (decisions.md "Declared parameter domains"; resolve.py's
# `_check_card_vocabulary`: `z.name == "hand" and z.index == "player"`;
# `runtime/rules.py::legal_cards`; `runtime/mechanics.py::param_domain`'s
# Card branch). A language-wide magic name, not a per-game renamable zone —
# see the module docstring.
_GLOBAL_EXCLUSIONS: frozenset[str] = frozenset({"hand"})

# Per-game zone/state-variable names a `cardlang/runtime/<game>.py` game-local
# primitive reads by hardcoded Python string literal — see the module
# docstring's second exclusion. Each row is exactly the literals grepped out
# of the named file; keep the file:line citations current when either drifts.
_PRIMITIVE_COUPLED_NAMES: dict[str, frozenset[str]] = {
    "big-two.cardlang": frozenset({"opened"}),  # bigtwo.py:193
    "bridge.cardlang": frozenset(  # stdlib.py:407-429 (bridge_auction_outcome)
        {"made_bid", "high_bidder", "cur_strain", "cur_level", "doubled"}
    ),
    "coup.cardlang": frozenset(  # coup.py:21,46,52,62-68
        {"court_deck", "influence", "revealed", "alive", "coins", "treasury"}
    ),
    "cribbage.cardlang": frozenset(  # cribbage.py:148-172; stdlib.py:176,180 (play_pile)
        {"play_pile", "played", "starter", "crib", "seq_bits", "seq_len", "dealer"}
    ),
    "doppelkopf.cardlang": frozenset({"trick_pile"}),  # doko.py:56
    "pinochle.cardlang": frozenset(  # pinochle.py:60; stdlib.py:452-466 (pinochle_auction_outcome)
        {"trump_suit", "lead_bidder", "opener", "working_bid"}
    ),
    "schnapsen.cardlang": frozenset({"trick_pile"}),  # schnapsen.py:23
    "skat.cardlang": frozenset(  # skat.py:45,47,49,118-156
        {"trick_pile", "skat", "is_null", "is_grand", "trump_suit"}
    ),
    "seven-card-stud.cardlang": frozenset(  # stud.py:107-188
        {"upcards", "hole", "stack", "folded", "committed", "in_hand"}
    ),
    "french-tarot.cardlang": frozenset(  # tarot.py:79,143-147; stdlib.py:480-484 (tarot_auction_outcome)
        {
            "trick_pile", "captured", "chien", "discard",  # tarot.py zones
            "taker", "bid_level",  # tarot.py:143-144 (resolved auction result)
            "lead_taker", "current_level",  # stdlib.py:480-484 (live auction state)
        }
    ),
    "tichu.cardlang": frozenset({"captured", "out_first", "out_second"}),  # tichu.py:65-145
    # president.cardlang's game-local primitive (president.py) reads only
    # `hand` — already a global exclusion; no additional row needed.
}


def _all_string_tokens(game: n.Game) -> frozenset[str]:
    """Every string appearing anywhere in the parsed tree — deliberately
    broader than "every declared name": a maximally conservative freshness
    check (also sweeps `StrLit`/`CardLiteral` contents, phase names, move-type
    names, …), cheap at corpus scale."""
    tokens: set[str] = set()

    def walk(node: object) -> None:
        if isinstance(node, str):
            tokens.add(node)
        elif isinstance(node, tuple):
            for item in node:
                walk(item)
        elif is_dataclass(node) and not isinstance(node, Span):
            for f in fields(node):
                walk(getattr(node, f.name))

    walk(game)
    return frozenset(tokens)


def _locally_bound_names(game: n.Game) -> frozenset[str]:
    """Every name bound by a local-introducing construct anywhere in the
    game — see the module docstring, defense 2."""
    names: set[str] = set()
    for nd in _resolve_walk(game):
        names.update(_introduced_binders(nd))
        if isinstance(nd, (n.MoveTypeDef, n.FunctionDef, n.ProcedureDef, n.RuleDef)):
            names.update(p.name for p in nd.params)
        if isinstance(nd, n.TypeDef):
            names.update(f.name for f in nd.fields)
    return frozenset(names)


@dataclass(frozen=True)
class RenamePlan:
    """The rename this transform will apply. `name_map` covers both zones
    and state variables (safe to share one flat map — see the module
    docstring: their namespaces never collide, asserted below). `zone_map`
    is the subset the trace-level hook needs: state-variable names never
    appear inside an observation event (only VALUES are rendered, never a
    declaring variable's own name — `runtime/observe.py`'s closed event
    vocabulary), so only zone labels ever need translating back.

    `unsafe`, `excluded_global`, and `excluded_coupled` partition every name
    NOT in `name_map`, each for a different, documented reason (module
    docstring) — never a silent drop."""

    name_map: dict[str, str]
    zone_map: dict[str, str]
    unsafe: frozenset[str]
    excluded_global: frozenset[str]
    excluded_coupled: frozenset[str]


def build_rename_plan(game: n.Game) -> RenamePlan:
    zone_names = {z.name for z in game.zones}
    state_names = {
        sd.name for nd in _resolve_walk(game) if isinstance(nd, n.StateBlock) for sd in nd.decls
    }
    overlap = zone_names & state_names
    assert not overlap, (
        f"zone and state-variable namespaces share {sorted(overlap)} — T2's "
        "single flat rename map cannot tell which declaration a NameRef of "
        "that spelling denotes without resolving scope; this backstop has "
        "not fired against the current corpus (rename.py's module docstring)"
    )
    domain = zone_names | state_names
    unsafe = domain & _locally_bound_names(game)

    filename = Path(game.span.source_name).name if game.span is not None else ""
    excluded_global = domain & _GLOBAL_EXCLUSIONS
    excluded_coupled = domain & _PRIMITIVE_COUPLED_NAMES.get(filename, frozenset())

    safe = sorted(domain - unsafe - excluded_global - excluded_coupled)

    used = set(_all_string_tokens(game))
    name_map: dict[str, str] = {}
    counter = 0
    for old in safe:
        while True:
            candidate = f"{_PREFIX}{counter}"
            counter += 1
            if candidate not in used:
                used.add(candidate)
                name_map[old] = candidate
                break
    zone_map = {old: new for old, new in name_map.items() if old in zone_names}
    return RenamePlan(
        name_map=name_map,
        zone_map=zone_map,
        unsafe=frozenset(unsafe),
        excluded_global=frozenset(excluded_global),
        excluded_coupled=frozenset(excluded_coupled),
    )


def _rewrite(node: object, name_map: dict[str, str]) -> object:
    if isinstance(node, n.NameRef):
        new = name_map.get(node.name)
        return node if new is None else replace(node, name=new)
    if isinstance(node, n.ZoneDecl):
        new = name_map.get(node.name)
        if new is not None:
            node = replace(node, name=new)
    elif isinstance(node, n.StateDecl):
        new = name_map.get(node.name)
        if new is not None:
            node = replace(node, name=new)
    elif isinstance(node, n.Winner):
        # `winner: lowest/highest <target>` names its score state variable as
        # a bare string too (the grammar production has no room for a general
        # expression here), not a `NameRef`.
        new = name_map.get(node.target)
        if new is not None:
            node = replace(node, target=new)
    elif isinstance(node, n.Round):
        # The climbing/trick forms name their source/play zones as bare
        # strings (`source_zone`/`play_zone`), not a `NameRef` — the one
        # place a zone reference bypasses the expression sublanguage (every
        # other zone reference — `Movement.source/dest`, `CardQuery.source`,
        # `EpistemicOp`'s target — is an `Expr`, so a `NameRef` occurrence).
        sz = None if node.source_zone is None else name_map.get(node.source_zone, node.source_zone)
        pz = None if node.play_zone is None else name_map.get(node.play_zone, node.play_zone)
        if sz != node.source_zone or pz != node.play_zone:
            node = replace(node, source_zone=sz, play_zone=pz)
    if not is_dataclass(node) or isinstance(node, Span):
        return node
    changes: dict[str, object] = {}
    for f in fields(node):
        value = getattr(node, f.name)
        rewritten = _rewrite_value(value, name_map)
        if rewritten is not value:
            changes[f.name] = rewritten
    return replace(node, **changes) if changes else node  # type: ignore[type-var]


def _rewrite_value(value: object, name_map: dict[str, str]) -> object:
    if isinstance(value, tuple):
        return tuple(_rewrite_value(item, name_map) for item in value)
    if is_dataclass(value) and not isinstance(value, Span):
        return _rewrite(value, name_map)
    return value


def alpha_rename(game: n.Game) -> n.Game:
    """The T2 transform proper: `Game -> Game`, matching `pairing.Transform`."""
    plan = build_rename_plan(game)
    return cast(n.Game, _rewrite(game, plan.name_map))


def trace_rename(zone_map: dict[str, str]) -> Callable[[Event], Event]:
    """The trace-level `rename` hook `pairing.compare_traces` wants: labels
    in the TRANSFORMED side's "move"/"reveal" events carry the NEW zone
    spelling (`_label` in `runtime/observe.py`: `name` or `name[key]`); this
    maps them back to the original so the transformed side's trace compares
    byte-for-byte against the untransformed side's."""
    inverse = {new: old for old, new in zone_map.items()}

    def relabel(label: str) -> str:
        if "[" in label:
            base, rest = label.split("[", 1)
            return inverse.get(base, base) + "[" + rest
        return inverse.get(label, label)

    def rename(event: Event) -> Event:
        tag = event[0]
        if tag == "move":
            _, src, src_view, dst, dst_view = event
            return (tag, relabel(src), src_view, relabel(dst), dst_view)
        if tag == "reveal":
            _, label, card = event
            return (tag, relabel(label), card)
        return event

    return rename
