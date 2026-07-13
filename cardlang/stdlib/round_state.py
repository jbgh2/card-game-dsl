"""What a `round` publishes to `state.` — the one registry, two consumers.

The `state.` pronoun reads the live round's accumulator (`runtime/state.py`'s
`mech_state`). That accumulator is also the form's *working memory*: `TrickForm`
drives `next_actor` off a ring cursor `idx` and a materialized `order`, and both
sat in the same dict as `led_suit`. Nothing distinguished them, and nothing
checked the field name — so `state.idx` type-checked, ran, and silently changed
the game (in Hearts it moved the winner from player 2 to player 0), while a typo
like `state.lead_suit` reached the runtime as a bare `KeyError`. A round's private
cursor was part of the language's surface by accident.

This module is the line between the two. A form's PUBLISHED fields are the closed,
typed set the DSL may name; its INTERNALS are working memory the surface cannot
reach. `typecheck` types `state.<field>` from this registry and rejects anything
else; `runtime/mechanics.py` is pinned against it, so a form that starts
publishing (or hiding) a field without saying so here fails a test rather than
quietly widening the language.

Typing the fields is the second half of the win. `state.led_suit` used to infer
`TAny`, which is contagious: `card.suit is state.idx` compared a Suit to an
Integer and slipped past the enum-comparison wall because the right-hand side was
untyped. With a declared type, every existing wall starts working there.
"""

from __future__ import annotations

from cardlang.types import TBoolean, TEnum, TOptional, TPlayer, Type

# `round <move> from <leader> over <players> source <zone> into <zone> outcome <fn>`
TRICK_PUBLISHED: dict[str, Type] = {
    "led_suit": TOptional(TEnum("Suit")),  # none while leading
    "trick_terminated_early": TBoolean(),
}
TRICK_INTERNAL: frozenset[str] = frozenset({"trump", "played", "order", "idx"})

# `round climb …` — one combination-climbing trick.
CLIMB_PUBLISHED: dict[str, Type] = {
    "lead_ended_trick": TBoolean(),  # a Dog-style lead closed the trick
    "shed_first": TOptional(TPlayer()),  # first two players to shed out, in play order
    "shed_second": TOptional(TPlayer()),
}
CLIMB_INTERNAL: frozenset[str] = frozenset({"current", "last", "idx", "guard"})

# `round offering […] … until …` — the auction and betting forms. They publish
# NOTHING: the auction's result is routed by its own outcome mechanism, and the
# betting form is outcome-less. This empty row is deliberate and load-bearing, not
# an omission — it is what makes "the auction form has no `state.`" a checkable
# fact rather than a thing you learn from a stale read.
AUCTION_PUBLISHED: dict[str, Type] = {}
AUCTION_INTERNAL: frozenset[str] = frozenset({"i", "guard", "history"})

# The union the checker validates against. It is a union, not a per-form lookup,
# because a reference is not statically attached to a form: `MustFollowSuit` lives
# once in stdlib/rules.cardlang and is activated by games in context, so the
# checker cannot know which `round` will be running when its `state.led_suit`
# evaluates. Narrowing that — "this rule reads trick state, so it may only be
# active in a trick phase" — is the standing residual (roadmap.md).
ROUND_STATE_FIELDS: dict[str, Type] = {
    **TRICK_PUBLISHED,
    **CLIMB_PUBLISHED,
    **AUCTION_PUBLISHED,
}
