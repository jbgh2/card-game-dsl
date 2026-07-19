"""The type foundations under `Subscript`, `Member` and `Call`, where a
mistyped receiver silently disarms every wall downstream of it.

Four areas, one section below each: a zone-family subscript types as the
family's content (not as a single Card, which would degrade an aggregation
source to `TAny` and take every wall in the body dark with it); the Card
field pair lives in one `CARD_FIELDS` registry rather than at two sites that
can drift; `action.card.*` and the bare `actor` pronoun are typed from
`ACTION_FIELDS` rather than left as `TAny` and silently `False`; and
`rank_value` is gated on a declared `ranking:` by `RANKING_GATED_FUNCS`,
mirroring resolve.py's `Rank`-move-param gate on the same condition.

Completeness ledger
--------------------
property:  a zone-family subscript (`hand[p]`, `captured[t]`) types as the
           zone's content collection, its index is checked against the
           zone's declared index role, and every operation that consumes a
           collection (aggregation source, membership, dot-access) sees that
           type consistently — no operation silently degrades to `TAny` or a
           spurious rejection because of the family/singleton distinction.
domain:    every `ZoneDecl` (index role) x every operation that can consume
           a `Subscript` expression.
registry:  `ZoneDecl.index` over `game.zones` (resolve.py's `_KNOWN_ROLES =
           {"player", "team"}` is the closed index-role domain).
covered:   both index roles (`player`, `team`) x both accept/reject index-
           type shapes (Player/Team-typed accept via exact match or the
           existing Integer->Player/Team coercion in `types.assignable`;
           every other type — String, Card, a foreign enum — rejects) x
           singleton-zone subscript (rejected, "not indexed") x the
           consuming operations reachable in the corpus (aggregation
           source, membership right-hand side, dot-access) x the predicate
           contexts `_check_expr` is invoked from that carry a zone-family
           subscript in the corpus (movement source/dest/filter, `reveal
           … from`, `let`/aggregation bodies) — each exercised below with an
           executed probe, not by "same code path" assumption.
sampled:   the cross-product of "every CALL_SIGS function" x "has_ranking"
           is sampled at one representative gated function (`rank_value`,
           the only member of `RANKING_GATED_FUNCS` today) x the two
           predicate contexts actually reachable in the corpus (a `let`
           aggregation body, a movement filter) — not every predicate
           position enumerated in `typecheck()`'s "remaining expression
           positions" block is separately probed for the ranking gate,
           since the gate lives inside `_check_expr`'s Call handling and
           every one of those positions is that same recursion's entry
           point (structural coverage, not per-site duplication).
residual:  (a) `action`'s move-type-specific fields (`action.amount`,
           `action.card_count` — named in the grammar comment at
           cardlang/grammar/cardlang.lark:320, used in
           tests/test_construct_combination_validity.py) stay `TAny` —
           full move-type-aware typing of `action` is out of scope
           (roadmap.md, "Action-field typing beyond the universal
           card/actor pair"). (b) The zone-family index check uses
           `assignable`, which (by an existing, pre-dating-this-change rule
           in `types.assignable`) lets a literal Integer stand for a
           Player/Team identity — so `hand[0]` is ACCEPTED, not rejected.
           This is a deliberate deviation from a stricter "index must be
           exactly Player-typed" reading: gops.md's setup phase
           (`move ... to hand[0]` / `hand[1]`, `reveal one card from
           bid[0]`, `captured[0] +=`-style routing) has no symbolic
           alternative for its asymmetric two-hand deal and relies on this
           coercion — a stricter rule would make that corpus file
           inexpressible. Flagged here for a human to overrule if a
           stricter rule (and a gops.md rewrite) is actually wanted; see
           roadmap.md, "Zone-family index strictness (deferred re-audit)".
"""

from __future__ import annotations

import pytest

from cardlang.diagnostics import DiagnosticError
from cardlang.pipeline import check_dsl

# --- shared minimal-game builders (mirrors tests/test_domain_completion.py) ---


def _game(
    body: str,
    ranking: str = "ranking: A K Q J 10 9 8 7 6 5 4 3 2",
    extra_zones: str = "",
    extra_state: str = "",
) -> str:
    return f"""
game Mini {{
  players: 2
  max_length: 1000
  cards: standard52
  {ranking}
  zones {{ deck : Deck  hand[player] : Hand<player>  bid[player] : HiddenPile<player>  pile : TrickPile {extra_zones} }}
  state {{ score[player] : Integer = 0 {extra_state} }}
  phase p {{
    {body}
  }}
  winner: highest score
}}
"""


def _team_game(body: str) -> str:
    return f"""
game Mini {{
  players: 4
  partnerships: [[0, 2], [1, 3]]
  max_length: 1000
  cards: standard52
  ranking: A K Q J 10 9 8 7 6 5 4 3 2
  zones {{ deck : Deck  hand[player] : Hand<player>  captured[team] : TeamPile<team> }}
  state {{ score[team] : Integer = 0 }}
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
# Zone-family subscript typing
# =============================================================================

# --- Symptom A: aggregation source degraded to TAny ---


def test_aggregation_over_a_zone_family_binds_card_not_any() -> None:
    # Without the subscript typing this would pass too (a TAny source is
    # permissive), but for the wrong reason — proven by the next test, which
    # shows the wall firing *inside* the same shape.
    _accepts(_game("let probe = sum of rank_value(card) over cards in hand[0]"))


def test_aggregation_body_over_a_zone_family_is_walled() -> None:
    # Without this, `hand[0]` would infer as a single Card, so the
    # comprehension source would not be a TCollection, so `card` would bind
    # TAny inside the body and a bad field would silently pass. With the
    # subscript typing, `card : Card` and the Card-field wall fires.
    _rejects(
        _game(
            "let probe = sum of rank_value(card) over cards in hand[0] "
            "where card.colour is hearts"
        ),
        "Card has no field 'colour'",
    )


# --- Symptom B: membership rejected outright ---


def test_card_membership_in_a_zone_family_is_accepted() -> None:
    # Without this, `hand[0]` would infer as Card, so the `in` right-hand-side
    # wall would reject this with "must be a collection... got Card".
    _accepts(_game("let probe = (Q of spades) in hand[0]"))


# --- the new dot-access wall (a zone family is a collection, not a Card) ---


def test_rejects_dot_access_on_a_zone_family_subscript() -> None:
    # Without this, `hand[0]` would infer as Card, so `.rank` would type-check
    # clean as `Rank` and only fail at play time, where a field read is served
    # only for the value shapes that HAVE fields and a zone is not one of them.
    # With the subscript typing, `hand[0] : Collection<Card>` and the
    # collection-has-no-fields wall catches it statically.
    _rejects(_game("let probe = hand[0].rank"), "a collection has no fields")


# --- index-type checking ---


def test_rejects_a_zone_family_index_of_the_wrong_type() -> None:
    _rejects(
        _game("let probe = number of cards in hand[hearts]"),
        "`hand` is keyed by Player — got Suit",
    )


def test_rejects_subscripting_a_non_family_zone() -> None:
    _rejects(
        _game("let probe = number of cards in pile[0]"),
        "zone 'pile' is not indexed",
    )


def test_accepts_an_integer_literal_zone_family_index() -> None:
    # Documented residual: `types.assignable` lets an Integer stand for a
    # Player identity (pre-existing, not introduced by this change) and
    # gops.md's asymmetric two-hand setup relies on it (`hand[0]`/`hand[1]`,
    # `bid[0]`/`bid[1]`, `captured[0]`/`captured[1]`) — see the module
    # docstring's residual (b).
    _accepts(_game("let probe = number of cards in hand[0]"))


def test_zone_family_index_wall_fires_in_a_movement_source() -> None:
    # A different predicate/expression context than the `let` probes above —
    # movements carry their own zone-family subscripts (gops.md's own
    # `move ... from hand[player] to bid[player]`), and `_check_expr` walks
    # `Movement.source`/`.dest` too.
    _rejects(
        _game("move all cards from hand[hearts] to pile"),
        "`hand` is keyed by Player — got Suit",
    )


def test_zone_family_index_wall_fires_in_a_reveal_target() -> None:
    # gops.md: `reveal one card from bid[0]` / `bid[1]` — EpistemicOp.target
    # is a Subscript too.
    _rejects(
        _game("reveal one card from bid[hearts]"),
        "`bid` is keyed by Player — got Suit",
    )


# --- the team index role (the other member of the closed role domain) ---


def test_team_family_subscript_by_a_team_binder() -> None:
    _accepts(
        _team_game("for each team t: score[t] := (number of cards in captured[t])")
    )


def test_team_family_subscript_by_an_integer_literal() -> None:
    # Same Integer->identity coercion as the player case, sampled once for
    # the Team role (the code path is shared, not re-enumerated per role).
    _accepts(_team_game("let probe = number of cards in captured[0]"))


def test_rejects_a_player_index_on_a_team_family() -> None:
    # The wrong-role cross-check: a Player-typed value doesn't stand for a
    # Team identity (`assignable(TPlayer, TTeam)` is False — only Integer
    # coerces to either), so this is a genuinely wrong sentence, not a
    # narrower case of the accepted Integer-literal shape above.
    _rejects(
        _team_game(
            "for each player q: score[0] := (number of cards in captured[q])"
        ),
        "`captured` is keyed by Team — got Player",
    )


# =============================================================================
# The Card field pair, one registry (CARD_FIELDS)
# =============================================================================


def test_card_fields_still_accepted_after_the_registry_merge() -> None:
    _accepts(_game("let probe = if (Q of spades).suit is spades then 1 else 0"))
    _accepts(_game("let probe = if (Q of spades).rank is Q then 1 else 0"))


def test_unknown_card_field_message_lists_both_registry_fields() -> None:
    _rejects(
        _game("let probe = (Q of spades).colour"),
        "Card has no field 'colour' (its fields are `rank` and `suit`)",
    )


# =============================================================================
# action.card / action.actor / bare actor typing
# =============================================================================


def test_action_card_suit_flows_through_to_the_enum_wall() -> None:
    # Without this typing, `action` would be TAny, so `action.card` and
    # `action.card.suit` would both be TAny too, and `action.card.suit is 3`
    # would typecheck clean — silently False at runtime (hearts.md/spades.md's
    # real shape, just with a bug: an Integer instead of a Suit).
    _rejects(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card.suit is 3"
        ),
        "comparing Suit with Integer",
    )


def test_action_card_suit_against_a_suit_still_accepted() -> None:
    # The real corpus shape (hearts.md/spades.md) must keep working.
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card.suit is hearts"
        )
    )


def test_unknown_action_field_stays_permissive() -> None:
    # Residual by design: `action.card_count` is not in ACTION_FIELDS (move
    # params are per-move-type), so it stays TAny — matches
    # tests/test_construct_combination_validity.py's existing acceptance of
    # this exact shape.
    _accepts(
        _game(
            "for each player q: score[q] := 1\n"
            "    transition_to: p when play_to_trick where action.card_count is 3"
        )
    )


def test_bare_actor_pronoun_types_as_player() -> None:
    _accepts(
        _team_game(
            "state { last_actor : Player = 0 }\n"
            "    for each player q: last_actor := actor"
        )
    )


def test_actor_dot_access_is_rejected_by_the_object_model_wall() -> None:
    # Without this typing `actor` would be TAny (permissive); it is Player,
    # and Player is in the closed dot-form-rejection set (decisions.md "Typed
    # object model") — `actor.foo` must reject the same way `p.foo` already
    # does for any other Player-typed value.
    _rejects(
        _team_game("for each player q: score[0] := (if actor.foo is 1 then 1 else 0)"),
        "the dot form is object-member access only",
    )


def test_actor_indexes_a_player_family_zone() -> None:
    # coup.md's real shape (`influence[actor]`, `coins[actor]`): actor's new
    # Player typing must still satisfy the zone-family subscript typing's
    # index check.
    _accepts(
        _team_game("for each player q: score[0] := (number of cards in hand[actor])")
    )


# =============================================================================
# rank_value gated on a declared ranking:
# =============================================================================


def test_rejects_rank_value_with_no_declared_ranking() -> None:
    _rejects(
        _game(
            "let probe = sum of rank_value(card) over cards in hand[0]", ranking=""
        ),
        "rank_value() reads a card's rank strength from ranking:",
    )


def test_accepts_rank_value_with_a_declared_ranking() -> None:
    _accepts(_game("let probe = sum of rank_value(card) over cards in hand[0]"))


def test_ranking_gate_fires_in_a_movement_filter_too() -> None:
    # A second predicate context (not the `let` aggregation body above) —
    # the gate lives in `_check_expr`'s shared Call handling, so every
    # position `_check_expr` is invoked from inherits it structurally.
    _rejects(
        _game(
            "move all cards from hand[0] where rank_value(card) > 5 to pile",
            ranking="",
        ),
        "rank_value() reads a card's rank strength from ranking:",
    )


def test_ranking_gate_does_not_touch_other_stdlib_calls() -> None:
    # A no-ranking game (Coup's shape) still calls other stdlib functions
    # freely — only the registered ranking-dependent ones are gated.
    _accepts(
        _game(
            "let probe = sum of (if suit_of(card) is hearts then 1 else 0) "
            "over cards in hand[0]",
            ranking="",
        )
    )
