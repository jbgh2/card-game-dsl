"""Type signatures for the stdlib functions and value-callbacks.

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
    TBoolean,
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


CALL_SIGS: dict[str, Sig] = {
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
    "bring_in_seat": Sig((), TPlayer()),  # Stud: lowest-door seat (no args; reads upcards)
    "first_to_act_seat": Sig((), TPlayer()),  # Stud: highest-upcards live seat
    "pot_share": Sig((TPlayer(),), TInteger()),  # Stud: showdown chips for a player
    "bigtwo_first_leader": Sig((), TPlayer()),  # Big Two: the 3♦ holder (leads hand 1)
    "rank_value": Sig((TCard(),), TInteger()),  # a card's rank strength (higher = stronger)
    "card_value": Sig((TCard(),), TInteger()),  # a card's deck-declared card-point value
    "pinochle_meld_value": Sig((TPlayer(),), TInteger()),  # Pinochle: a hand's meld under trump
    "tarot_led_suit": Sig((), TEnum("Suit")),  # French Tarot: the effective led suit
    "tarot_trump_height": Sig((TCard(),), TInteger()),  # French Tarot: an atout's rank strength
    "tarot_excuse_player": Sig((), TOptional(TPlayer())),  # French Tarot: who played the Excuse
    "tarot_per_opp": Sig((TInteger(),), TInteger()),  # French Tarot: the per-opponent settlement
    "tarot_card_points": Sig((TCard(),), TInteger()),  # French Tarot: doubled card-point value
    "schnapsen_trick_winner": Sig(
        (TPlayer(), TOptional(TEnum("Suit"))), TPlayer()
    ),  # Schnapsen: the completed two-card trick's winner
    "skat_next_bid": Sig((TInteger(),), TInteger()),  # Skat: the next Reizen ladder value
    "skat_follow_ok": Sig((TPlayer(), TCard()), TBoolean()),  # Skat: follow-class legality
    "skat_trick_winner": Sig((TPlayer(),), TPlayer()),  # Skat: the three-card trick's winner
    "skat_matadors": Sig((TPlayer(),), TInteger()),  # Skat: with/without matador count
    "skat_effective_loss": Sig(
        (TInteger(), TInteger(), TInteger()), TInteger()
    ),  # Skat: the overbid-aware loss base
    "doko_trick_winner": Sig((TPlayer(),), TPlayer()),  # Doppelkopf: the trick's winner
    "tichu_mahjong_holder": Sig((), TPlayer()),  # Tichu: leads the first trick
    "tichu_players_holding": Sig((), TInteger()),  # Tichu: players still holding cards
    "tichu_double_victory": Sig((), TBoolean()),  # Tichu: first two finishers teammates?
    "tichu_partner": Sig((TPlayer(),), TPlayer()),  # Tichu: the teammate
    "tichu_next_holder": Sig((TPlayer(),), TPlayer()),  # Tichu: next holder ccw (or arg)
    "tichu_dragon_won": Sig((), TBoolean()),  # Tichu: Dragon captured the last trick?
    "tichu_opponent_team": Sig((TPlayer(),), TTeam()),  # Tichu: the other team
    "tichu_first_out": Sig((), TPlayer()),  # Tichu: the first finisher (default 0)
    "tichu_card_points": Sig((TCard(),), TInteger()),  # Tichu: the card-point table
    "tichu_hand_summary": Sig((), TInteger()),  # Tichu: emit tichu_hand; captured points
    "president_next_holder": Sig((TPlayer(),), TPlayer()),  # President: next holder cw (or arg)
    "president_is_top_rank": Sig(
        (TPlayer(), TCard()), TBoolean()
    ),  # President: is the card the player's highest rank?
    "coup_players_in": Sig((), TInteger()),  # Coup: players still holding influence
    "coup_next_in_game": Sig((TPlayer(),), TPlayer()),  # Coup: next in-game clockwise
    "coup_has_char": Sig(
        (TPlayer(), TOptional(TEnum("Rank"))), TBoolean()
    ),  # Coup: proof lookup (an unset claim matches no card)
    "coup_note_reveal": Sig((TPlayer(),), TInteger()),  # Coup: trace the flip
    "coup_game_summary": Sig((), TInteger()),  # Coup: conservation/finals trace
    "peg_value": Sig((TCard(),), TInteger()),  # Cribbage: pegging/fifteens value
    "peg_pair_points": Sig((), TInteger()),  # Cribbage: live pegging-count pair points
    "peg_run_points": Sig((), TInteger()),  # Cribbage: live pegging-count run points
    "peg_origin_of": Sig((TCard(),), TPlayer()),  # Cribbage: who played a pegging-pile card
    "cribbage_show_value": Sig((TPlayer(),), TInteger()),  # Cribbage: a hand's show score
    "cribbage_crib_value": Sig((), TInteger()),  # Cribbage: the crib's show score
    "gin_card_points": Sig((TCard(),), TInteger()),  # Gin: A=1, pips, face=10
    "gin_deadwood": Sig((TPlayer(),), TInteger()),  # Gin: optimal-partition deadwood of the hand
    "gin_can_knock": Sig((TPlayer(),), TBoolean()),  # Gin: some discard leaves <= 10 (the announce guard)
    "gin_knock_ok": Sig((TPlayer(), TCard()), TBoolean()),  # Gin: knock legality after this discard
    "gin_valid_meld": Sig(
        (TCollection(TCard()),), TBoolean()
    ),  # Gin: joint meld validity (the defender's arrangement guard)
    "gin_arrange_ok": Sig(
        (TPlayer(), TCollection(TCard())), TBoolean()
    ),  # Gin: valid meld AND the rest still arranges to <= 10 (the knocker's guard)
    "gin_can_declare": Sig((TPlayer(),), TBoolean()),  # Gin: some declarable meld exists
    "gin_can_declare_free": Sig(
        (TPlayer(),), TBoolean()
    ),  # Gin: some valid meld exists (defender — no knock budget)
    "gin_flat_points": Sig((TPlayer(),), TInteger()),  # Gin: the hand counted as all-deadwood
    "gin_shown_points": Sig((TPlayer(),), TInteger()),  # Gin: shown_deadwood[p]'s point count
    "gin_lay_ok_a": Sig((TCard(), TPlayer()), TBoolean()),  # Gin: card extends knocker's meld A
    "gin_lay_ok_b": Sig((TCard(), TPlayer()), TBoolean()),  # Gin: card extends knocker's meld B
    "gin_lay_ok_c": Sig((TCard(), TPlayer()), TBoolean()),  # Gin: card extends knocker's meld C
}

# Outcome / value callbacks passed by bare name — result type is mechanic-driven.
VALUE_SIGS: dict[str, Type] = {
    "highest_of_led_suit": TAny(),
    "highest_trump_or_led_suit": TAny(),
    "tarot_trick_winner": TAny(),  # trick winner; the Excuse never wins
    "bridge_auction_outcome": TAny(),  # auction form: produces the typed variant
    "pinochle_auction_outcome": TAny(),  # auction form: produces bid_won
    "tarot_auction_outcome": TAny(),  # auction form: produces taken | thrown_in
}

# Early-termination predicates named by a `round`'s `early` clause. Signature is
# (card, led_suit) -> Boolean; the table is loose (TAny) like the value callbacks.
EARLY_SIGS: dict[str, Type] = {
    "on_play_of_tochoo": TAny(),
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
