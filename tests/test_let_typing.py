"""Lets are typed at declaration — the sequential fold that closed the
let-TAny gap (`typecheck._seq_tree_scoped` + `_scoped_env`).

Without this fold, a `let`-bound name would infer `TAny` in every later
statement, and `TAny` passes `assignable` in both directions — so EVERY wall
would go dark one binding away: `hearts is 3` would be rejected while
`let z = hearts` / `z is 3` sailed through, and the same laundering would
defeat the ordering, arithmetic, offset_by, run-argument, assignment and
endpoint walls — the widest recorded hole in the checker. The fold: every
statement-tuple walk routes through `_seq_tree_scoped`, which binds a `let`
for the REST of its tuple — the same fold resolve applies for scoping and the
runtime applies for values — and `_scoped_env` types the binder by inferring
its initializer in the environment at that point.

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
            let does not leak — pinned below); the positions the runtime
            evaluates with a DIFFERENT context (a nested phase's qualifier
            sees preceding lets — typed with them; same-phase hooks and state
            defaults get ENTRY scope; a transition predicate reads NO let at
            all, enclosing or not — it is fired by whichever round matches
            its event, so no lexical position makes a binding reliably live —
            all pinned below with contrast pairs); the facet axes (a non-card
            collection is not a zone; unify merges each facet in its wall's
            polarity — `zone` PERMITS so it ANDs, a maybe-zone is not an
            endpoint; `key` PROHIBITS so it is STICKY, a maybe-map still
            rejects `in`; keyed maps check their key domain on read and
            write; `to each` consumes the family NAME, so even a zone-valued
            binder is rejected there); the gradual case (a TAny initializer
            stays permissive, by rule)
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
# binding cannot exist yet, and without that rejection it would die as a raw
# KeyError mid-playout).


def test_a_nested_phase_qualifier_is_typed_with_preceding_lets() -> None:
    # This exact expression gets ONE verdict everywhere. Were the qualifier
    # position checked with the bare env, `when z is 3` would be accepted
    # while the same expression in the body was rejected — and the phase
    # would silently never fire.
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


def test_a_transition_predicate_cannot_read_a_same_phase_body_let() -> None:
    # A transition is CONFIGURATION: collected position-independently and
    # evaluated with the context captured at whichever round fires it — which
    # may run before the `let`. Entry scope, like hooks and state defaults.
    # Without this wall the earlier passes are no help: resolve scopes the let
    # over it and typecheck types it, so the mismatch survives to a round that
    # may run before the binding exists.
    _rejects(
        _game(
            "legal_moves: [play_to_trick]\n"
            "    let z = hearts\n"
            "    mode gate {\n"
            "      transition_to: opened when play_to_trick where "
            "action.card.suit is z\n"
            "    }\n"
            "    mode opened { }"
        ),
        "unresolved name 'z'",
    )


def test_a_transition_predicate_reads_no_let_even_an_enclosing_one() -> None:
    # Stricter than the hooks: an ENCLOSING let is rejected too, because the
    # firing round is chosen by the event, not by lexical position — a round
    # lexically before the let can fire a transition declared after it, and
    # the binding is not live in that round's captured context. The
    # well-typed no-let spelling stays accepted.
    src = _game(
        "let z = hearts\n"
        "    phase inner {\n"
        "      legal_moves: [play_to_trick]\n"
        "      mode gate {\n"
        "        transition_to: opened when play_to_trick where "
        "action.card.suit is z\n"
        "      }\n"
        "      mode opened { }\n"
        "    }"
    )
    _rejects(src, "unresolved name 'z'")
    check_dsl(
        src.replace("action.card.suit is z", "action.card.suit is hearts"),
        "probe.cardlang",
    )


def test_a_let_does_not_leak_out_of_a_nested_body() -> None:
    # The scope boundary the module ledger claimed without a pin: a let inside
    # an if-body binds for the REST OF THAT TUPLE only.
    _rejects(
        _game("if n[0] is 0 { let z = 5 }\n    n[0] := z"),
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
    # without this wall it would reach the runtime's backstop with a message
    # claiming the checker couldn't know — it knows Collection<Player> exactly.
    _rejects(
        _game("let z = all players\n    move all cards from z to deck"),
        "movement source must be a zone, got Collection<Player>",
    )


def test_a_computed_card_collection_is_not_a_zone() -> None:
    # The RIGHT element is not enough either: a card
    # query and a list literal both type Collection<Card> but evaluate to
    # plain lists, not zones — only ZONE_CONTENT's `zone` marker separates
    # `hand[0]` from `cards in hand[0] where …`. The message says why the
    # rejection isn't a contradiction.
    _rejects(
        _game(
            "let cs = cards in deck where card.suit is hearts\n"
            "    move all cards from cs to hand[0]"
        ),
        "a computed card collection",
    )
    _rejects(
        _game("let cs = [2 of clubs]\n    shuffle cs"),
        "a computed card collection",
    )


def test_a_produce_payload_is_typed_through_a_let() -> None:
    # The payload-vs-variant check runs in its own pass (`_check_define_
    # outcomes` / `_check_phase_produces`). Were those to read the bare env,
    # `produce Won(z)` with `let z = hearts` would pass a Player payload the
    # inline spelling had just been rejected for. Both owners fold binders
    # like the main walk.
    _rejects(
        _game(
            "d produces:\n      Won(w) { n[w] := 1 }",
            tail=(
                "define d -> { Won(Player) } { let z = hearts\n  produce Won(z) }"
            ),
        ),
        "outcome case 'Won' expects Player, got Suit",
    )
    _rejects(
        _game(
            "phase q -> outcome { Won(Player) } {\n"
            "      let z = hearts\n"
            "      produce Won(z)\n"
            "    }\n"
            "    q produces:\n      Won(w) { n[w] := 1 }"
        ),
        "outcome case 'Won' expects Player, got Suit",
    )


def test_a_keyed_map_rejects_a_wrong_domain_key() -> None:
    # Keyed collections carry their key domain: an indexed let is
    # player-keyed, and a per-player state var is keyed by its declared index
    # role — reads and writes both check, where without them the first sign
    # would come at play time.
    _rejects(_game("let m[q] = q\n    n[m[hearts]] := 1"), "`m` is keyed by Player")
    _rejects(
        _game("let k = hearts\n    if n[k] > 0 { n[0] := 1 }"),
        "`n` is keyed by Player — got Suit",
    )
    _rejects(_game("n[hearts] := 1"), "`n` is keyed by Player — got Suit")


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


# --- facets through unify, and the walls that guard them -----------------------


def test_a_conditional_choice_of_zones_is_still_a_zone() -> None:
    # Were unify() to rebuild TCollection(element) BARE, it would strip
    # zone=True even from unify(zone, zone) — falsely rejecting this legal
    # program with a hint calling two named zones 'a query result or list'.
    # Facets the branches agree on survive.
    check_dsl(
        _game(
            "let h = if n[0] is 0 then hand[0] else hand[1]\n"
            "    move all cards from h to deck\n"
            "    shuffle h"
        ),
        "probe.cardlang",
    )


def test_a_conditional_choice_of_keyed_maps_keeps_the_key() -> None:
    # The key facet's twin: two same-keyed maps unify to a keyed map, so the
    # key wall fires through the conditional instead of the runtime KeyError.
    _rejects(
        _game(
            "let m = if n[0] is 0 then n else n\n"
            "    if m[hearts] > 0 { n[0] := 1 }"
        ),
        "keyed by Player — got Suit",
    )


def test_a_map_merged_with_a_non_map_stays_keyed() -> None:
    # The key facet is STICKY through unify: `if c then n else [99]` may be a
    # dict at runtime, so `2 in m` is exactly as ambiguous as on the map
    # itself — without stickiness it would run the keys-vs-values misread on
    # the map branch while typing as a plain list. The domain becomes
    # unknowable (TAny), so a subscript read stays permissive.
    _rejects(
        _game(
            "let m = if n[0] is 0 then n else [99]\n"
            "    if 2 in m { n[0] := 1 }"
        ),
        "may be a keyed map",
    )
    check_dsl(  # the permissive contrast: reading the merge by index is fine
        _game(
            "let m = if n[0] is 0 then n else [99]\n"
            "    n[0] := m[0]"
        ),
        "probe.cardlang",
    )


def test_a_zone_merged_with_a_non_zone_is_not_a_zone() -> None:
    # The zone facet merges the OPPOSITE way (AND): an endpoint requires a
    # DEFINITE zone, because the list branch would crash the executor. The
    # facets' merge directions follow their walls' polarities — zone permits,
    # key prohibits.
    _rejects(
        _game(
            "let h = if n[0] is 0 then hand[0] else [2 of clubs]\n"
            "    move all cards from h to deck"
        ),
        "movement source must be a zone",
    )


def test_to_each_requires_the_family_name_not_a_zone_value() -> None:
    # `to each X` deals into X[player] BY NAME — the executor never evaluates
    # the destination — so a binder can never stand there even when it holds
    # a zone: without this wall `let h = hand[0]` / `to each h` would type
    # clean (h IS a zone) and reach the executor, which requires a declared
    # player-indexed zone FAMILY under that name and refuses any other name at
    # deal time. The generic endpoint rule admits zone-valued binders; this
    # position is stricter because it consumes the name, not the value.
    _rejects(
        _game("let h = hand[0]\n    deal 1 cards from deck to each h"),
        "BY NAME, so it must name a player-indexed zone family",
    )


def test_membership_on_a_keyed_map_is_rejected_as_ambiguous() -> None:
    # `2 in m` reads as a VALUE test and typechecked as one, but the runtime
    # store is a dict whose `in` asks about KEYS: with every value 99, `2 in
    # m` answered True because seat 2 exists — a silent misreading. Both
    # meanings have direct spellings; `in` on a keyed map is walled.
    _rejects(
        _game("let m[q] = 99\n    if 2 in m { n[0] := 1 }"),
        "keys or values?",
    )
    _rejects(  # the indexed-state-var twin, same seam
        _game("if 2 in n { n[0] := 1 }"),
        "keys or values?",
    )


def test_move_type_params_are_typed_in_guard_and_effect() -> None:
    # The let-laundering shape, one binder kind over: move params were scoped
    # by resolve and never typed, so both positions passed what the inline
    # spelling rejects. Function and procedure params were already typed;
    # this was the one _PARAM_BEARING row without teeth.
    _rejects(
        _game(
            "for each player q: offer to q one of [m]",
            tail="move_type m(s : Suit) { effect { if s is 3 { n[actor] := 1 } } }",
        ),
        _LAUNDER,
    )
    _rejects(
        _game(
            "for each player q: offer to q one of [m]",
            tail="move_type m(s : Suit) { when: s is 3  effect { n[actor] := 1 } }",
        ),
        _LAUNDER,
    )


def test_derived_fields_type_their_siblings() -> None:
    # A derived body reads sibling fields by bare name; their declared types
    # are in the struct registry and are bound — without that binding,
    # `seat is hearts` on a Player field would be accepted as TAny.
    _rejects(
        _game("n[0] := 1").replace(
            "game G {",
            "type T = {\n  seat : Player\n} derived {\n  bad = seat is hearts\n}\ngame G {",
        ),
        "comparing Suit with Player can never be equal",
    )


def test_the_zone_hint_names_the_filter_only_where_one_can_be_written() -> None:
    # Unqualified, the hint would suggest `where` filters on destinations,
    # gathers and shuffle targets — positions whose grammar has no filter
    # slot, sending the designer to a syntax error.
    _rejects(
        _game("let cs = [2 of clubs]\n    shuffle cs"),
        "name the zone itself)",
    )
    _rejects(
        _game(
            "let cs = [2 of clubs]\n    move 1 cards from deck to cs"
        ),
        "name the zone itself)",
    )
    _rejects(
        _game(
            "let cs = [2 of clubs]\n    move all cards from cs to deck"
        ),
        "narrow the movement with a `where` filter)",
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
