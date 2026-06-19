"""Type signatures for the stdlib functions, value-callbacks, and zone methods.

Companion to :mod:`cardlang.stdlib.functions` (which holds the *names*); these
tables hold the *types*, consumed by the type checker. The keys reconcile with
the name sets (asserted in tests), keeping "stdlib is data" single-sourced.

Looseness is deliberate where the corpus forces it: `suit_of` accepts a card or a
single-card zone, so its argument is `TAny`; outcome value-callbacks return
`TAny`; the `Resource` zone (`ChipStack`) holds `TAny`. These track the deferred
parts of the typed object model.
"""

from __future__ import annotations

from dataclasses import dataclass

from cardlang.stdlib.zones import LIBRARY_ZONE_TYPES
from cardlang.types import (
    TAny,
    TCard,
    TCollection,
    TEnum,
    TInteger,
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


@dataclass(frozen=True)
class MethodSig:
    """A zone-query method. ``lambda_arg`` marks a first argument that is a
    predicate over the receiver's element type (bound by the checker).
    ``returns_receiver`` means the method yields the same collection type as its
    receiver; otherwise ``ret`` is the result type."""

    lambda_arg: bool
    params: tuple[Type, ...]
    returns_receiver: bool
    ret: Type | None = None


CALL_SIGS: dict[str, Sig] = {
    "player_holding": Sig((TCard(),), TPlayer()),
    "team_of": Sig((TPlayer(),), TTeam()),
    "suit_of": Sig((TAny(),), TOptional(TEnum("Suit"))),  # card or single-card zone
    "strain_index": Sig((TOptional(TEnum("Suit")),), TInteger()),  # strain bidding rank
    "error": Sig((TString(),), TAny()),  # the if_impossible fallback
}

# Outcome / value callbacks passed by bare name — result type is mechanic-driven.
VALUE_SIGS: dict[str, Type] = {
    "highest_of_led_suit": TAny(),
    "highest_trump_or_led_suit": TAny(),
    "bridge_auction_outcome": TAny(),  # auction form: produces the typed variant
}

# Early-termination predicates named by a `round`'s `early` clause. Signature is
# (card, led_suit) -> Boolean; the table is loose (TAny) like the value callbacks.
EARLY_SIGS: dict[str, Type] = {
    "on_play_of_tochoo": TAny(),
}

METHOD_SIGS: dict[str, MethodSig] = {
    "where": MethodSig(lambda_arg=True, params=(), returns_receiver=True),
    "cards_of_suit": MethodSig(
        lambda_arg=False,
        params=(TEnum("Suit"),),
        returns_receiver=False,
        ret=TCollection(TCard()),
    ),
}

# Zone type name -> contents. Card containers hold cards; the resource zone holds
# the permissive top (Resource generics deferred).
ZONE_CONTENT: dict[str, Type] = {
    name: (TCollection(TAny()) if name == "ChipStack" else TCollection(TCard()))
    for name in LIBRARY_ZONE_TYPES
}
