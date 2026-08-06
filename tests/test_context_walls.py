"""Statement-context totality (Task 3: `Movement`/`EpistemicOp` filters bind
`card`) and IsCheck totality (Task 4: `is empty`/`is not empty`/`is none`/
`is not none`), typecheck + runtime.

Completeness ledger — statement-context totality
--------------------------------------------------
property:  every `_stmt_exprs` position that the runtime evaluates with an
           implicit binder in scope is checked with that same binder in
           scope at typecheck time — no expression position where a Card
           wall (or any binder-typed wall) is silently dark because the
           statement walk left it unbound.
domain:    every branch of `_stmt_exprs` (`cardlang/typecheck.py`) — the
           registry of "which expressions does a statement hold directly":
           AssignStmt, LetStmt, Movement, EpistemicOp, Offer, Round,
           IfStmt/RepeatUntil, Produce (ForEach/EachSimultaneous/RotateStmt
           hold none).
registry:  `_stmt_exprs`'s own branches (read exhaustively — every one is
           named in `_check_stmt_exprs`'s docstring) cross-checked against
           resolve.py's independent registry of the same fact,
           `_BINDER_SCOPE_FIELDS` (`cardlang/resolve.py`), which lists which
           *fields* of a binder-introducing node see the binder: `Movement:
           ("filter",)`, `EpistemicOp: ("filter",)` — confirming `filter` is
           the only `_stmt_exprs`-held field either registry scopes to an
           implicit binder. The two registries are independent (typecheck's
           governs *typing* the binder, resolve's governs *resolving* the
           bare name at all) and agree by construction on which field is
           special, which is what makes "the whole class is exactly these
           two members" a checked claim, not an assumption.
covered:   Movement.filter and EpistemicOp.filter, each: rejects an unknown
           Card field inside the filter (the closed CARD_FIELDS wall, now
           reachable — THE PROBE); rejects a non-Boolean filter; accepts the
           real corpus shape (`card.suit is hearts`/`card.rank is Q`).
           Movement.source is confirmed to still run its own (unrelated,
           pre-existing) zone-family-index wall in the SAME statement a
           filter is present on — proof the two checks don't interfere.
sampled:   none — the domain is small (8 `_stmt_exprs` branches) and every
           branch is either exhaustively argued (the 6 non-Movement/
           EpistemicOp branches hold no predicate, confirmed by reading
           `_stmt_exprs`'s source directly, restated in
           `_check_stmt_exprs`'s docstring) or probed above.
residual:  none for this property. (The general let-bound-locals residual
           from test_operator_walls.py applies here too — a filter that
           only references a `let`-bound name stays `TAny` — but that is
           the same pre-existing, module-spanning gap, not specific to this
           wall; not re-recorded.)

Completeness ledger — IsCheck totality
-----------------------------------------
property:  `is empty`/`is not empty` reject a concrete non-collection
           operand; `is none`/`is not none` reject a concrete non-optional
           operand (both checks would otherwise have a fixed, state-
           independent truth value — dead code that reads as a live
           condition). The runtime `_is_check` never bare-asserts a shape:
           emptiness folds `len()` over any sized value, and a genuinely
           non-collection value at that call site raises a typed
           `RuntimeError`, not an `AssertionError`.
domain:    `IsCheck.kind`'s closed 4-value domain (`none`/`not_none`/
           `empty`/`not_empty` — `cardlang/ast/nodes.py`) crossed with the
           operand-type registry (`cardlang/types.py`'s `Type` union) at
           both typecheck (`_check_is_check`) and runtime (`_is_check`).
registry:  `n.IsCheck.kind`'s docstring-declared 4-value set; `types.Type`.
covered:   empty/not_empty x {TCollection (accept), TAny (accept, gradual),
           TInteger (reject)}; none/not_none x {TOptional (accept — the
           corpus shape, probed on a declared `Player?`), TNull (accept —
           `none` itself), TAny (accept, gradual), TInteger (reject, with
           the always-false/always-true framing for each of `none`/
           `not_none`)}. Runtime: `_is_check`'s empty/not_empty arm over a
           `Zone` (regression), a plain `list` (a CardQuery `set` result —
           the shape a bare `assert isinstance(value, Zone)` used to
           reject outright), and a non-sized value (the typed
           `RuntimeError`, executed both ways — `empty` and `not_empty`).
sampled:   none/not_none's reject branch is probed once (TInteger); every
           other concrete non-optional type (TBoolean, TCard, TPlayer,
           TCollection, TString, TStruct) shares the identical `isinstance
           (t, (TAny, TOptional, TNull))` branch — one `isinstance` check,
           not a per-type dispatch — so probing one member of the reject
           set exercises the whole branch. Corpus sweep (all `is none`/`is
           not none`/`is empty`/`is not empty` sites in `docs/games/*.
           cardlang`) confirmed every real usage is on a declared `T?`
           state var, a zone/zone-family, or a `TAny` pronoun member —
           zero corpus trips from either wall.
residual:  none.
"""

from __future__ import annotations

import random

import pytest

from cardlang.ast import nodes as n
from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl
from cardlang.runtime.errors import OwnerGuardError
from cardlang.runtime.evaluate import evaluate
from cardlang.runtime.state import Ctx, RuntimeState, ZoneStore
from cardlang.runtime.values import Card, Seating

# --- shared minimal-game builder ---


def _game(body: str, extra_zones: str = "", extra_state: str = "") -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  pile : TrickPile {extra_zones} }}
  state {{ score[player] : Integer = 0 {extra_state} }}
  phase p {{
    {body}
  }}
  winner: highest score
}}
"""


def _accepts(src: str) -> None:
    check_dsl(src, "mini.cardlang")


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as ei:
        check_dsl(src, "mini.cardlang")
    assert needle in str(ei.value), str(ei.value)


# =============================================================================
# Task 3 — Movement/EpistemicOp filter binds `card`
# =============================================================================


def test_movement_filter_rejects_an_unknown_card_field() -> None:
    # The headline probe. Were `_stmt_exprs` to run the filter
    # through the flat, unbound `env`, `card` would type `TAny` (an unbound
    # local) and the closed CARD_FIELDS wall would never fire.
    _rejects(
        _game("deal 5 cards from deck where card.colour is 3 to each hand"),
        "Card has no field 'colour'",
    )


def test_reveal_filter_rejects_an_unknown_card_field() -> None:
    _rejects(
        _game("reveal one card from hand[0] where card.colour is 3"),
        "Card has no field 'colour'",
    )


def test_movement_filter_must_be_boolean() -> None:
    _rejects(
        _game("deal 5 cards from deck where card.rank to each hand"),
        "'deal' filter must be Boolean, got Rank",
    )


def test_reveal_filter_must_be_boolean() -> None:
    _rejects(
        _game("reveal one card from hand[0] where card.rank"),
        "'reveal' filter must be Boolean, got Rank",
    )


def test_movement_filter_real_corpus_shape_is_accepted() -> None:
    _accepts(_game("move chosen 2 cards from hand[0] where card.suit is hearts to pile"))


def test_reveal_filter_real_corpus_shape_is_accepted() -> None:
    _accepts(_game("reveal one card from hand[0] where card.rank is Q"))


def test_movement_source_is_still_checked_unbound_alongside_a_filter() -> None:
    # The OTHER Movement expressions (source/dest/amount/visibility) carry no
    # `card` binder and are checked in the ambient environment — proven by a
    # statement that has BOTH a real filter AND a source-side error, so the
    # source's own (unrelated) zone-family-index wall must still fire.
    _rejects(
        _game("move all cards from hand[hearts] where card.suit is hearts to pile"),
        "`hand` is keyed by Player — got Suit",
    )


# =============================================================================
# Task 4 — IsCheck totality (typecheck)
# =============================================================================


def test_is_empty_rejects_a_non_collection() -> None:
    _rejects(
        _game("let probe = (score[0] is empty)"),
        "`is empty` asks a zone or collection — got Integer",
    )


def test_is_not_empty_rejects_a_non_collection() -> None:
    _rejects(
        _game("let probe = (score[0] is not empty)"),
        "`is not empty` asks a zone or collection — got Integer",
    )


def test_is_empty_accepts_a_zone() -> None:
    _accepts(_game("let probe = (hand[0] is empty)"))


def test_is_empty_accepts_gradual_any() -> None:
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    mode m { transition_to: p when play_to_trick where action.card_count is empty }\n"
            "    mode p { }"
        )
    )


def test_is_none_rejects_a_non_optional_naming_always_false() -> None:
    _rejects(
        _game("let probe = (score[0] is none)"),
        "`is none` on a non-optional Integer is always false",
    )


def test_is_not_none_rejects_a_non_optional_naming_always_true() -> None:
    _rejects(
        _game("let probe = (score[0] is not none)"),
        "`is not none` on a non-optional Integer is always true",
    )


def test_is_none_accepts_a_declared_optional() -> None:
    # doppelkopf.cardlang/skat.cardlang's real shape: `fox1_victim is none`,
    # `passer is none` — a declared `Player?` state var.
    _accepts(
        _game(
            "let probe = (dealer is none)",
            extra_state="dealer : Player? = none",
        )
    )


def test_is_not_none_accepts_a_declared_optional() -> None:
    _accepts(
        _game(
            "let probe = (dealer is not none)",
            extra_state="dealer : Player? = none",
        )
    )


def test_is_none_accepts_gradual_any() -> None:
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    mode m { transition_to: p when play_to_trick where action.card_count is none }\n"
            "    mode p { }"
        )
    )


# =============================================================================
# Task 4 — IsCheck totality (runtime: evaluate._is_check)
# =============================================================================


def _ctx(players: tuple[int, ...] = (0, 1)) -> Ctx:
    game = check_dsl(_game("let probe = 0"), "mini.cardlang")
    rs = RuntimeState(Seating(len(players)), ZoneStore(game.zones, players), random.Random(0))
    return Ctx(rs=rs, chooser=lambda p, c, k: list(c[:k])).acting_as(0)


def test_runtime_is_empty_over_a_zone_still_works() -> None:
    # Regression: a Zone (a singleton/family instance) is one shape
    # `_is_check` must handle; the `len()`-based fold must still answer it
    # correctly.
    ctx = _ctx()
    ctx.rs.zones.instance("hand", 0).add_all([Card("Q", "spades")])
    zone_ref = n.NameRef("hand", ref_kind="zone")
    empty_check = n.IsCheck(operand=zone_ref, kind="empty")
    not_empty_check = n.IsCheck(operand=zone_ref, kind="not_empty")
    assert evaluate(empty_check, ctx) is False
    assert evaluate(not_empty_check, ctx) is True
    ctx.rs.zones.instance("hand", 0).cards.clear()
    assert evaluate(empty_check, ctx) is True
    assert evaluate(not_empty_check, ctx) is False


def test_runtime_is_empty_over_a_card_query_set_result() -> None:
    # A CardQuery "set" result evaluates to a plain `list`
    # (evaluate._card_query's "set" arm), not a `Zone` — without the
    # `len()`-based fold, a bare `assert isinstance(value, Zone)` in
    # `_is_check` would crash on this with an AssertionError instead of
    # answering the question.
    ctx = _ctx()
    ctx.rs.zones.instance("hand", 0).add_all([Card("Q", "hearts"), Card("2", "clubs")])
    query = n.CardQuery(
        kind="set",
        source=n.NameRef("hand", ref_kind="zone"),
        pred=n.BinOp(
            "==",
            n.Member(n.NameRef("card", ref_kind="local"), "suit"),
            n.NameRef("hearts", ref_kind="enum_value"),
        ),
    )
    empty_check = n.IsCheck(operand=query, kind="empty")
    assert evaluate(empty_check, ctx) is False  # one heart present: not empty

    query_no_match = n.CardQuery(
        kind="set",
        source=n.NameRef("hand", ref_kind="zone"),
        pred=n.BinOp(
            "==",
            n.Member(n.NameRef("card", ref_kind="local"), "suit"),
            n.NameRef("spades", ref_kind="enum_value"),
        ),
    )
    empty_check_2 = n.IsCheck(operand=query_no_match, kind="empty")
    assert evaluate(empty_check_2, ctx) is True  # no spades: empty


def test_runtime_is_empty_over_a_non_collection_is_a_typed_runtime_error() -> None:
    # Simulates a checker gap (or a future caller of `evaluate` that skips
    # typecheck): a non-collection value must fail with a typed
    # `RuntimeError`, never a bare `assert`.
    ctx = _ctx()
    empty_check = n.IsCheck(operand=n.IntLit(3), kind="empty")
    with pytest.raises(OwnerGuardError, match="is empty"):
        evaluate(empty_check, ctx)
    not_empty_check = n.IsCheck(operand=n.IntLit(3), kind="not_empty")
    with pytest.raises(OwnerGuardError, match="is not empty"):
        evaluate(not_empty_check, ctx)
