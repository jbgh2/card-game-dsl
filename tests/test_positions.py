"""Position domains (decisions.md "Position domains and positional zones").

Completeness ledger (decisions.md "Surface totality" / "Closed-domain
completeness")
----------------------------------------------------------------------
property:   a declared position domain works in exactly two slots — zone-
            family index and move-parameter domain — with identical member
            enumeration at runtime and in the static action space, and is
            rejected with a diagnostic everywhere else a domain/role/type
            name can appear.
domain:     (a) the surface slots a domain id can occupy: zone index, zone
            type-arg, move/rule/procedure/function parameter type, state
            index, state type, `for each` role, `each … simultaneously`
            role, quantifier noun, `to each` destination, bare zone
            reference; (b) the declaration's own value space (bounds,
            duplicates, name collisions); (c) the consumers of the domain
            (ZoneStore keys, observation ownership, runtime candidate
            enumeration, static vocab enumeration).
registry:   cardlang/domains.py (built-in rows; DomainSources.positions) +
            n.Game.positions; the collision wall `_resolve_positions` is the
            reconciliation between the two definition sites — swept here
            registry-derived, so neither source can grow past it.
covered:    zone index + type arg (Klondike/FreeCell corpus + this module);
            move params (both games + the vocab-order pin below); the
            collision sweep (every built-in id and spelling, derived from
            the registries); bounds walls incl. the 256-member ceiling
            boundary; unowned ownership (`zone_observer_key` -> None,
            hence the `others` projection for every observer — pinned in
            the proof modules' fact matrices); bare-family references
            (rejection corpus + the runtime backstop probe below); state
            index/type, for-each, simultaneous, param typos (rejection
            corpus tests/rejections/positions_*); `to each` (existing
            player-index wall, probed below); quantifier nouns
            (grammatically inexpressible — the quantifier production is a
            closed alternative set).
sampled:    the canonical gather over a position family (order-preserving
            per the canonical zone-collection rule; no corpus game gathers
            one — decisions.md states the interaction explicitly).
residual:   `for each <position>` and position-indexed state stores are
            walled with diagnostics (roadmap.md, "Positional zones —
            walled residuals"); `top_of`/`bottom_of` in a move GUARD over
            a non-identity zone is policed per game by the openspiel_ready
            legal-action-agreement proofs, not statically (same roadmap
            entry).

`top_of`/`bottom_of` share this module: the sequence-orientation pin
(top = the sequence end, bottom = the front) is what the positional games'
movement semantics rest on.
"""

from __future__ import annotations

import random

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.domains import (
    DOMAINS,
    DomainSources,
    enumerate_domain,
    zone_observer_key,
)
from cardlang.ir import emit
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game
from cardlang.runtime.mechanics import param_domain
from cardlang.typecheck import KNOWN_TYPE_NAMES


def _game(
    positions: str = "positions { column : 1..3 }",
    zones: str = "pile[column] : Cascade<column>",
    stmt: str = "",
    vocab: str = "",
    moves: str = "",
) -> str:
    return (
        "game G {\n"
        "  players: 1\n"
        "  direction: clockwise\n"
        "  max_length: 100\n"
        "  cards: standard52\n"
        f"  {positions}\n"
        "  zones {\n"
        "    deck : Deck\n"
        f"    {zones}\n"
        "  }\n"
        "  state { resigned : Boolean = false\n"
        "          score[player] : Integer = 0 }\n"
        "  phase setup { shuffle deck }\n"
        "  phase play {\n"
        "    turns t from 0 over all players until resigned {\n"
        f"      offer to t one of [quit{vocab}]\n"
        "    }\n"
        f"    {stmt}\n"
        "  }\n"
        "  winner: highest score\n"
        "}\n"
        f"{moves}"
        "move_type quit { effect { resigned := true } }\n"
    )


# --- the declaration's value space ------------------------------------------


def test_single_member_and_zero_based_domains_are_legal() -> None:
    check_dsl(
        _game(positions="positions { column : 1..1  slot : 0..2 }",
              zones="pile[column] : Cascade<column>  s[slot] : Cell<slot>"),
        "t",
    )


def test_member_ceiling_boundary() -> None:
    check_dsl(_game(positions="positions { column : 1..256 }"), "t")  # at the ceiling
    with pytest.raises(DiagnosticError, match="more than the ceiling"):
        check_dsl(_game(positions="positions { column : 1..257 }"), "t")


def test_every_builtin_domain_id_and_type_spelling_is_a_rejected_position_name() -> None:
    """The reconciliation sweep, derived from BOTH source registries (never
    from the wall's own set): every domain id, every declared-type spelling,
    and every KNOWN_TYPE_NAMES member must be rejected as a position name —
    the two definition sites can never disagree about a spelling."""
    spellings = (
        {d.id for d in DOMAINS}
        | {d.type_name for d in DOMAINS}
        | set(KNOWN_TYPE_NAMES)
    )
    assert "Card" in spellings and "player" in spellings  # the sweep is real
    for name in sorted(spellings):
        with pytest.raises(DiagnosticError, match="collides with a built-in"):
            check_dsl(
                _game(positions=f"positions {{ {name} : 1..3 }}",
                      zones=f"pile[{name}] : Cascade<{name}>"),
                "t",
            )


# --- enumeration agreement (runtime = static) --------------------------------


_PARAM_GAME = _game(
    vocab=", mv",
    moves=(
        "move_type mv(c : column, d : column) {\n"
        "  when: c is not d\n"
        "  effect { resigned := true }\n"
        "}\n"
    ),
)


def test_runtime_and_static_member_enumeration_agree() -> None:
    game = check_dsl(_PARAM_GAME, "t")
    static = enumerate_domain(
        "column",
        DomainSources(
            suits=(), ranks=(), players=(0,),
            positions={p.name: p.members for p in game.positions},
        ),
    )
    assert static == [1, 2, 3]

    seen: dict[str, list[object]] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        seen["candidates"] = list(candidates)
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(game, random.Random(0), chooser=chooser)
    # The guard-filtered cross-product, declaration order, c-major — and the
    # runtime enumerated the same 1..3 members the static space did.
    assert [c for c in seen["candidates"] if c != ("quit", None)] == [
        ("mv", (1, 2)), ("mv", (1, 3)),
        ("mv", (2, 1)), ("mv", (2, 3)),
        ("mv", (3, 1)), ("mv", (3, 2)),
    ]


def test_param_domain_reads_the_live_position_table() -> None:
    from cardlang.runtime.state import Ctx, RuntimeState

    game = check_dsl(_PARAM_GAME, "t")
    mv = next(m for m in game.move_types if m.name == "mv")

    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    ctx = Ctx(rs=captured["rs"], chooser=chooser)
    assert param_domain(mv.params[0], 0, ctx) == [1, 2, 3]


# --- ownership: positions are unowned ----------------------------------------


def test_positions_are_unowned_for_every_observer() -> None:
    from cardlang.runtime.state import RuntimeState

    game = check_dsl(_game(), "t")
    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    # No observer has a key of their own in a position domain, so ownership
    # never matches and every observer projects the zone type's `others`
    # column (runtime observe._is_owner and the proof oracle both read this
    # one function).
    assert zone_observer_key("column", captured["rs"], 0) is None


# --- the runtime backstop behind the bare-reference wall ---------------------


def test_bare_position_family_read_is_a_typed_runtime_error() -> None:
    """resolve walls the DSL spelling (rejection corpus); the runtime
    backstop must fail typed — never a phantom-key KeyError — if a
    construction path ever bypasses it."""
    from cardlang.ast import nodes as n
    from cardlang.runtime.evaluate import evaluate
    from cardlang.runtime.state import Ctx, RuntimeState

    game = check_dsl(_game(), "t")
    captured: dict[str, RuntimeState] = {}

    def chooser(player: int, candidates: list[object], k: int) -> list[object]:
        return [next(c for c in candidates if c == ("quit", None))]

    play_game(
        game, random.Random(0), chooser=chooser,
        on_first_decision=lambda rs: captured.__setitem__("rs", rs),
    )
    ctx = Ctx(rs=captured["rs"], chooser=chooser).acting_as(0)
    ref = n.NameRef("pile", ref_kind="zone")
    with pytest.raises(RuntimeError, match="must be subscripted"):
        evaluate(ref, ctx)


# --- `to each` over a position family (the existing wall owns the class) -----


def test_to_each_position_family_is_rejected() -> None:
    with pytest.raises(DiagnosticError, match="deals one parcel per player"):
        check_dsl(
            _game(stmt="deal 1 card from deck to each pile"),
            "t",
        )


# --- IR ----------------------------------------------------------------------


def test_positions_appear_in_the_ir() -> None:
    game = check_dsl(_game(), "t")
    assert emit(game)["positions"] == [
        {"kind": "position", "name": "column", "lo": 1, "hi": 3}
    ]


# --- top_of / bottom_of: the sequence-orientation pin ------------------------


def test_top_is_the_sequence_end_and_bottom_the_front() -> None:
    """The orientation the positional movement semantics rest on
    (decisions.md, sequence orientation): arrivals append at the end, so
    `top_of` reads the last arrival and `bottom_of` the first; an empty
    collection and a non-card element each fail typed at the cause."""
    from cardlang.runtime import stdlib
    from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
    from cardlang.runtime.values import Card, Seating

    game = check_dsl(_game(), "t")
    zones = ZoneStore(game.zones, (0,), positions={"column": (1, 2, 3)})
    rs = RuntimeState(Seating(1), zones, random.Random(0))
    rs.position_domains = {"column": (1, 2, 3)}
    pile = zones.instance("pile", 1)
    pile.add(Card("2", "spades"))
    pile.add(Card("A", "spades"))
    ctx = Ctx(rs=rs, chooser=lambda p, c, k: c[:k])

    assert stdlib.call("top_of", [pile], ctx) == Card("A", "spades")
    assert stdlib.call("bottom_of", [pile], ctx) == Card("2", "spades")
    with pytest.raises(RuntimeError, match="the collection is empty"):
        stdlib.call("top_of", [zones.single("deck")], ctx)
    with pytest.raises(RuntimeError, match="expects a collection of cards"):
        stdlib.call("top_of", [[1, 2]], ctx)
