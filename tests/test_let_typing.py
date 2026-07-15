"""Lets are typed at declaration — the sequential fold that closed the
let-TAny gap (`typecheck._seq_tree_scoped` + `_scoped_env`).

A `let`-bound name used to infer `TAny` in every later statement, and `TAny`
passes `assignable` in both directions — so EVERY wall went dark one binding
away: `hearts is 3` was rejected while `let z = hearts` / `z is 3` was
accepted, and the same laundering defeated the ordering, arithmetic,
offset_by, run-argument, assignment and endpoint walls. This was the widest
recorded hole in the checker (three separate ledgers carried "bounded by the
let-TAny gap" residuals). The fix is one fold: every statement-tuple walk
routes through `_seq_tree_scoped`, which binds a `let` for the REST of its
tuple — the same fold resolve applies for scoping and the runtime applies for
values — and `_scoped_env` types the binder by inferring its initializer in
the environment at that point.

property:   a `let`-bound name carries its initializer's inferred type into
            every later statement of its scope, so each wall answers the same
            for the laundered spelling as for the inline one
domain:     statement context {phase body, nested phase via items fold, hook
            body, if/repeat body, move effect, define body, produces arm,
            procedure body} × representative wall (the walls themselves are
            matrix-tested in test_operator_walls.py / test_procedures.py /
            test_movement_endpoints.py; this module pins the THREADING) —
            plus the form axis {plain let, chained let-of-let, indexed let}
covered:    every context below with an executed laundering probe; the
            chained and indexed forms; the scope boundary (a nested body's
            let does not leak — enforced by resolve, exercised here); the
            positions the runtime evaluates with a DIFFERENT context (a
            nested phase's qualifier and a transition predicate see preceding
            lets — typed with them; same-phase hooks and state defaults run
            at entry and are REJECTED at resolve if they read a body let);
            the element axis (a non-card collection is not a zone) and the
            key axis (keyed maps check their key domain on read and write);
            the gradual case (a TAny initializer stays permissive, by rule)
sampled:    each context is probed with ONE wall (cross-enum equality),
            because `_scoped_env` is the single resolution point every wall
            reads — per-wall coverage lives in each wall's own matrix, which
            now includes laundered rows
residual:   a `let` whose initializer itself types `TAny` (`outcome`, an
            unregistered `action.<field>`) carries `TAny` forward — gradual
            typing's ordinary rule, pinned below, with the runtime's typed
            backstops (test_fail_loud.py) behind it
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

_LAUNDER = "comparing Suit with Integer can never be equal"


def _game(phase_items: str, tail: str = "") -> str:
    return f"""game G {{
  players: 4
  max_length: 100
  direction: clockwise
  cards: standard52
  zones {{ deck : Deck  hand[player] : Hand<player> }}
  state {{ n[player] : Integer = 0 }}
  phase p {{
    {phase_items}
  }}
  winner: highest n
}}
{tail}"""


def _rejects(src: str, needle: str) -> None:
    with pytest.raises(DiagnosticError) as excinfo:
        check_dsl(src, "probe.cardlang")
    assert needle in str(excinfo.value), str(excinfo.value)


# --- the threading, one context at a time -------------------------------------


def test_a_let_types_across_phase_body_statements() -> None:
    _rejects(_game("let z = hearts\n    if z is 3 { n[0] := 1 }"), _LAUNDER)


def test_a_let_types_into_a_nested_if_body() -> None:
    _rejects(
        _game("let z = hearts\n    if n[0] is 0 { if z is 3 { n[0] := 1 } }"),
        _LAUNDER,
    )


def test_a_let_types_within_a_repeat_body() -> None:
    _rejects(
        _game(
            "repeat until n[0] > 0 { let z = hearts\n"
            "      if z is 3 { n[0] := 1 } }"
        ),
        _LAUNDER,
    )


def test_a_let_types_into_a_later_nested_phase() -> None:
    # The phase-ITEMS fold: a phase-body let is visible inside a nested phase
    # that follows it, mirroring resolve's generic tuple fold.
    _rejects(
        _game("let z = hearts\n    phase inner { if z is 3 { n[0] := 1 } }"),
        _LAUNDER,
    )


def test_a_let_types_within_a_hook_body() -> None:
    _rejects(
        _game(
            "phase loop repeat until n[0] > 0 {\n"
            "      before_each { let z = hearts\n"
            "        if z is 3 { n[0] := 1 } }\n"
            "      deal 1 cards from deck to each hand\n"
            "    }"
        ),
        _LAUNDER,
    )


def test_a_let_types_within_a_move_effect() -> None:
    _rejects(
        _game(
            "for each player q: offer to q one of [m]",
            tail=(
                "move_type m { effect { let z = hearts\n"
                "  if z is 3 { n[actor] := 1 } } }"
            ),
        ),
        _LAUNDER,
    )


def test_a_let_types_within_a_define_body_and_produces_arm() -> None:
    _rejects(
        _game(
            "d produces:\n      Won { let z = hearts\n"
            "        if z is 3 { n[0] := 1 } }",
            tail="define d -> { Won } { produce Won }",
        ),
        _LAUNDER,
    )
    _rejects(
        _game(
            "d produces:\n      Won { n[0] := 1 }",
            tail=(
                "define d -> { Won } { let z = hearts\n"
                "  if z is 3 { produce Won }\n  produce Won }"
            ),
        ),
        _LAUNDER,
    )


def test_a_let_types_within_a_procedure_body() -> None:
    _rejects(
        _game(
            "run f(0)",
            tail=(
                "procedure f(who : Player) { let z = hearts\n"
                "  if z is 3 { n[who] := 1 } }"
            ),
        ),
        _LAUNDER,
    )


# --- the form axis -------------------------------------------------------------


def test_a_chained_let_infers_through_the_chain() -> None:
    # `b`'s type comes from `a`, whose type comes from its initializer — the
    # fold resolves earlier lets before later ones, in scope order.
    _rejects(
        _game("let a = hearts\n    let b = a\n    if b is 3 { n[0] := 1 }"),
        _LAUNDER,
    )


def test_an_indexed_let_types_as_a_collection_of_its_element() -> None:
    # `let base[p] = <Suit>` is a per-player map of suits: a subscript read
    # yields the element type, and the key binder types as Player inside the
    # initializer only.
    _rejects(
        _game(
            "let base[p] = if p is 0 then hearts else spades\n"
            "    if base[0] is 3 { n[0] := 1 }"
        ),
        _LAUNDER,
    )


def test_the_indexed_lets_key_binder_is_a_player_inside_the_value() -> None:
    # `p offset_by left` demands a Player receiver — legal exactly because the
    # key binder is typed, not TAny.
    check_dsl(
        _game(
            "let base[p] = p offset_by left\n"
            "    for each player q: n[base[q]] += 1"
        ),
        "probe.cardlang",
    )


# --- positions the runtime evaluates with a DIFFERENT context ------------------
#
# Found by adversarial probing: the fold must match what the driver actually
# does, position by position. A nested phase's qualifier and a transition
# predicate run MID-BODY with the threaded context (a preceding let is bound,
# so they are typed with it); this phase's own hooks and state defaults run at
# ENTRY, before any body let has executed (so resolve rejects the read — the
# binding cannot exist yet, and it used to die as a raw KeyError mid-playout).


def test_a_nested_phase_qualifier_is_typed_with_preceding_lets() -> None:
    # This exact expression gets ONE verdict everywhere now; the qualifier
    # position used to be checked with the bare env, so `when z is 3` was
    # accepted while the same expression in the body was rejected — and the
    # phase silently never fired.
    _rejects(
        _game("let z = hearts\n    phase inner when z is 3 { n[0] := 1 }"),
        _LAUNDER,
    )


def test_a_same_phase_hook_cannot_read_a_body_let() -> None:
    # `before_each` runs at iteration entry, BEFORE the body's `let` executes —
    # the binding cannot exist, so the read is an unresolved name at compile
    # time, not a raw runtime KeyError.
    _rejects(
        _game(
            "phase loop repeat until n[0] > 0 {\n"
            "      let z = 5\n"
            "      before_each { n[1] := z }\n"
            "      n[0] += 1\n"
            "    }"
        ),
        "unresolved name 'z'",
    )


def test_a_same_phase_state_default_cannot_read_a_body_let() -> None:
    # State declares at phase entry, same timing argument as the hooks.
    _rejects(
        _game(
            "phase inner {\n"
            "      let z = 5\n"
            "      state { q : Integer = z }\n"
            "      n[0] := q\n"
            "    }"
        ),
        "unresolved name 'z'",
    )


def test_an_enclosing_let_is_visible_to_a_nested_phases_hook() -> None:
    # The contrast that keeps the rule honest: a nested phase receives the
    # THREADED context, so an enclosing-body let is genuinely bound when its
    # hooks run — accepted, and it runs.
    check_dsl(
        _game(
            "let z = 5\n"
            "    phase loop repeat until n[0] > 0 { "
            "before_each { n[1] := z } n[0] += 1 }"
        ),
        "probe.cardlang",
    )


# --- the element and key axes (what the type now says, the walls now use) ------


def test_a_non_card_collection_is_not_a_zone() -> None:
    # A collection SHAPE is not enough: `all players` is a collection too, and
    # it used to reach the runtime's backstop with a message claiming the
    # checker couldn't know — it knew Collection<Player> exactly.
    _rejects(
        _game("let z = all players\n    move all cards from z to deck"),
        "movement source must be a zone, got Collection<Player>",
    )


def test_a_keyed_map_rejects_a_wrong_domain_key() -> None:
    # Keyed collections carry their key domain: an indexed let is
    # player-keyed, and a per-player state var is keyed by its declared index
    # role — reads and writes both check, where a raw KeyError used to be the
    # first sign.
    _rejects(_game("let m[q] = q\n    n[m[hearts]] := 1"), "`m` is keyed by Player")
    _rejects(
        _game("let k = hearts\n    if n[k] > 0 { n[0] := 1 }"),
        "`n` is keyed by Player — got Suit",
    )
    _rejects(_game("n[hearts] := 1"), "'n' is keyed by Player — got Suit")


def test_a_zone_valued_let_map_still_works() -> None:
    # The legitimate shape on the same axes: a per-player map of zones, read
    # back with a Player key and used as a movement source.
    check_dsl(
        _game(
            "let m[q] = hand[q]\n"
            "    for each player w: move all cards from m[w] to deck"
        ),
        "probe.cardlang",
    )


# --- the recorded residual: TAny initializers stay gradual ---------------------


def test_a_tany_initializer_carries_tany_forward() -> None:
    # `outcome` is deliberately loose (`TAny`) — a let bound to it stays
    # permissive, which is gradual typing's ordinary rule, not a hole in the
    # fold. The runtime's typed backstops stand behind this path
    # (tests/test_fail_loud.py).
    check_dsl(
        _game(
            "d produces:\n      Won(w) { let z = w\n        n[0] := 1 }",
            tail="define d -> { Won(Integer) } { produce Won(3) }",
        ),
        "probe.cardlang",
    )
