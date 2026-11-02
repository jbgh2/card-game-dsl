"""Standard-library [[move-type]]s, as data.

The named card-movement patterns from library.md "Move types". The resolver
checks every `constrains:`, `legal_moves:`, and transition move-event
reference against this set. Seeded with what the formalized corpus uses;
extended corpus-first as games introduce new move types.
"""

from __future__ import annotations

from typing import Literal, get_args

# The construct that makes a kernel move: where a constraint on it is stated,
# which is what a rule naming it is told (decisions.md "Rule demand forms").
KernelMoveForm = Literal["trick_round", "offer", "chosen_movement", "number_choice", "climb_round"]
KERNEL_MOVE_FORM_NAMES: tuple[KernelMoveForm, ...] = get_args(KernelMoveForm)

# Every kernel move type, with the construct that makes it. The one table
# both the set below and the rule refusal read, so a kernel move type cannot
# exist without saying how it is made.
KERNEL_MOVE_FORMS: dict[str, KernelMoveForm] = {
    "play_to_trick": "trick_round",
    # Hearts' pass: `move chosen 3 cards ...`, its count and filter the law.
    "transfer_between_hands": "chosen_movement",
    # a player names a number (Spades/Oh Hell bidding): `choose integer in ...`,
    # or a game's own `submit_bid` move type offered (Bridge, Five Hundred).
    "submit_bid": "number_choice",
    # Schnapsen's lead moves (play_card / declare_marriage / exchange_trump_jack /
    # close_talon) are game-defined `move_type`s in schnapsen.cardlang, not
    # library moves — like Seven-Card Stud's betting moves below.
    # Bidding moves a game may define under the kernel's spelling.
    "pass": "offer",
    "declare_trump_suit": "offer",
    "double": "offer",
    "redouble": "offer",
    # Skat's Reizen/declaration moves (bid / yes / pass / play_at_eighteen /
    # throw_in / pick_up_skat / declare_hand / choose_suit_game /
    # declare_grand / declare_null / declare_suit) are game-defined
    # `move_type`s in skat.cardlang, not library moves.
    # Seven-Card Stud's betting moves (check/bet/call/raise/fold) are
    # game-defined `move_type`s in seven-card-stud.cardlang, not library moves.
    # The climbing games' shared play (Big Two, Tichu): one combination per
    # `round climb` step. Tichu's push is a chosen movement and its calls
    # are rng-gated primitives, so neither carries a move type.
    "play_combination": "climb_round",
    # Coup's seven actions (income / foreign_aid / coup / tax / assassinate /
    # steal / exchange) are game-defined `move_type`s in coup.cardlang, not
    # library moves; challenging and blocking are rng-gated windows at the
    # migrated scope, not moves.
}

LIBRARY_MOVE_TYPES: frozenset[str] = frozenset(KERNEL_MOVE_FORMS)

# The ONE move type rule enforcement runs for. `rules.legal_cards` has a single
# caller (the trick form's card decision), which passes this; every other
# decision site computes its candidates without consulting rules at all
# (decisions.md "Rule demand forms"). Named here, and read by BOTH the caller
# and the resolver's reachability Owner Guard, so the Owner Guard cannot drift
# from the consumer it describes (tests/test_rule_sites.py pins the two
# readers).
RULE_ENFORCED_MOVE_TYPE: str = "play_to_trick"

# The ONE move type the climbing form's decision site runs. Named here for the
# same reason as its neighbour above, but note the difference in strength: that
# one has two readers and so cannot drift from its consumer, while NOTHING in
# `ClimbForm` reads a climb round's `move_type` at all. The form runs the
# combination engine named by its `combinations`/`follows` queries regardless.
# So this constant has one reader — the resolver's Owner Guard — and its job is
# to keep the two forms' facts in one place rather than to track a consumer.
# Until that Owner Guard landed, every other spelling was accepted and meant nothing.
CLIMB_DECISION_MOVE_TYPE: str = "play_combination"
