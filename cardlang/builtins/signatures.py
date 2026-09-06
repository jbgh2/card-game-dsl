"""Type signatures for the native functions and value-callbacks.

Companion to :mod:`cardlang.builtins.functions` (which holds the *names*); these
tables hold the *types*, consumed by the type checker. The keys reconcile with
the name sets (asserted in tests), keeping "the native surface is data" single-sourced.

Looseness is deliberate where the corpus forces it: `suit_of` accepts a card or a
single-card zone, so its argument is the [[permissive-top]] `TAny`; outcome
value-callbacks return `TAny`; the `Resource` zone (`ChipStack`) holds `TAny`.
These track the deferred parts of the typed object model.

`CALL_SIGS` keys the [[builtins]] — the generic native functions the language
ships — and nothing else. A [[primitive]]'s signature is the `sig` column of
its row in the implementation index (`cardlang/primitives_block.py`,
`PRIMITIVE_IMPLEMENTATIONS`), read through `implementation_sig`, beside the
module and attribute that find its Python: one table per half, so a Primitive
key here is a signature no declaration reconciles.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import (
    TAny,
    TBoolean,
    TCard,
    TCell,
    TCollection,
    TDir,
    TEnum,
    TInteger,
    TLine,
    TOptional,
    TPlayer,
    TString,
    TTeam,
    Type,
)


@dataclass(frozen=True)
class Sig:
    """A plain function signature: positional param types and a return type."""

    params: tuple[Type, ...]
    ret: Type


CALL_SIGS: dict[str, Sig] = {
    # The board's length-k lines (decisions.md "Boards and cells"): each a
    # `TLine` (a cell tuple), for the `any line in lines(k) where …` register.
    "lines": Sig((TInteger(),), TCollection(TLine())),
    # The class-1 movement/region verbs (decisions.md "Boards and cells", rung-2
    # movement): `neighbor` the destination cell one step along a direction in a
    # player's frame, `has_step` the guard that gates it, `is_diagonal` whether
    # the step captures, `home`/`far_row` the setup and reach-goal cell regions.
    # Each reads the `board:` entry (the `lines` twin, BOARD_ONLY). `home`/
    # `far_row` return `Collection<Cell>` -- the shape the `cell in <cellset>`
    # membership consumes.
    "neighbor": Sig((TCell(), TDir(), TPlayer()), TCell()),
    "has_step": Sig((TCell(), TDir(), TPlayer()), TBoolean()),
    "is_diagonal": Sig((TDir(),), TBoolean()),
    "home": Sig((TPlayer(),), TCollection(TCell())),
    "far_row": Sig((TPlayer(),), TCollection(TCell())),
    "player_holding": Sig((TCard(),), TPlayer()),
    "team_of": Sig((TPlayer(),), TTeam()),
    # `suit_of` accepts a card or a single-card zone (polymorphic arg -> TAny)
    # and always yields a suit: an empty zone is a loud runtime error at the
    # cause, never a silent `none` (the return was once `Suit?`, which promised
    # an absence the runtime never produced). Plain `Suit` still assigns into
    # every corpus target (`trump_suit : Suit? = none`).
    "suit_of": Sig((TAny(),), TEnum("Suit")),
    "strain_index": Sig((TOptional(TEnum("Suit")),), TInteger()),  # strain bidding rank
    "error": Sig((TString(),), TAny()),  # the if_impossible fallback
    "rank_value": Sig((TCard(),), TInteger()),  # a card's rank strength (higher = stronger)
    "card_points": Sig((TCard(),), TInteger()),  # a card's points under `card_points { }`
    # Positional order reads (decisions.md "Position domains and positional
    # zones", sequence orientation): top = the sequence end (most recent
    # arrival), bottom = the front. Loud runtime error on an empty collection.
    "top_of": Sig((TCollection(TCard()),), TCard()),
    "bottom_of": Sig((TCollection(TCard()),), TCard()),
    # The standard trump-game trick winner over a fully public pile's Arrival
    # Record (issue #256). The zone argument is polymorphic like `suit_of`'s
    # (TAny: the runtime needs the Zone handle, not coerced elements — the
    # record rides the zone); the trump is a suit or none.
    "highest_trump_or_led_suit": Sig((TAny(), TOptional(TEnum("Suit"))), TPlayer()),
    # The Trick Order's five (decisions.md "Trick Order"; issue #250). The
    # three READERS the language mints from the block's rows: each takes the
    # card and returns exactly what its row must type — these return types
    # ARE the required row types, read back by typecheck's `_check_trick_order`
    # so the demand is stated once. `follow_class` is `Suit?` because `none`
    # means class-less (a card that neither sets the lead nor wins).
    "is_trump": Sig((TCard(),), TBoolean()),
    "follow_class": Sig((TCard(),), TOptional(TEnum("Suit"))),
    "card_strength": Sig((TCard(),), TInteger()),
    # The two Builtins over the whole declaration. Both take the pile
    # polymorphically (`TAny`, the `highest_trump_or_led_suit` precedent: the
    # runtime needs the Zone handle, not coerced elements, because the
    # [[arrival-record]] rides the zone); which argument is the pile is
    # `ARRIVAL_RECORD_CALLS`.
    "follows_lead": Sig((TCard(), TAny()), TBoolean()),
    "highest_by_trick_order": Sig((TAny(),), TPlayer()),
}

# Outcome / value callbacks passed by bare name — result type is mechanic-driven.
VALUE_SIGS: dict[str, Type] = {
    "highest_of_led_suit": TAny(),
    "highest_trump_or_led_suit": TAny(),
    "highest_by_trick_order": TAny(),  # trick winner under the game's `trick_order { }`
    "bridge_auction_outcome": TAny(),  # auction form: produces the typed outcome
    "pinochle_auction_outcome": TAny(),  # auction form: produces bid_won
    "tarot_auction_outcome": TAny(),  # auction form: produces taken | thrown_in
}

# Early-termination predicates named by a `round`'s `early` clause. Signature is
# (card, led_suit) -> Boolean; the table is loose (TAny) like the value callbacks.
EARLY_SIGS: dict[str, Type] = {
    "on_play_off_led_suit": TAny(),
}

# Zone type name -> contents. Card containers hold cards; the resource zone holds
# the permissive top (Resource generics deferred).
# `zone=True`: these types describe values that ARE zones at runtime, which is
# what the movement/epistemic zone-position checks require — a card QUERY also
# types Collection<Card> but evaluates to a plain list, not a Zone.
ZONE_CONTENT: dict[str, Type] = {
    name: (
        TCollection(TAny(), zone=True)
        if name == "ChipStack"
        else TCollection(TCard(), zone=True)
    )
    for name in LIBRARY_ZONE_TYPES
}
