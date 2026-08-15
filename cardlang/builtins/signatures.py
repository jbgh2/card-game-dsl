"""Type signatures for the stdlib functions and value-callbacks.

Companion to :mod:`cardlang.builtins.functions` (which holds the *names*); these
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
    "bring_in_seat": Sig((), TPlayer()),  # Stud: lowest-door seat (no args; reads upcards)
    "first_to_act_seat": Sig((), TPlayer()),  # Stud: highest-upcards live seat
    "pot_share": Sig((TPlayer(),), TInteger()),  # Stud: showdown chips for a player
    # Hold'em: the seat-ring skip past busted seats (button/blind resolution) and
    # the showdown side-pot share. `holdem_next_entrant` reads only `in_hand` and
    # the seating ring — no card content — which is why it classifies GENERIC
    # where `holdem_pot_share`, which ranks cards, is deck-only.
    "holdem_next_entrant": Sig((TPlayer(),), TPlayer()),
    "holdem_pot_share": Sig((TPlayer(),), TInteger()),
    # Heads-up Hold'em's showdown share. Same shape and same maths as
    # `holdem_pot_share` — a separate name because a primitive module binds one
    # declared-reads row (issue #232), not because the query differs.
    "holdem_heads_up_pot_share": Sig((TPlayer(),), TInteger()),
    "rank_value": Sig((TCard(),), TInteger()),  # a card's rank strength (higher = stronger)
    "card_value": Sig((TCard(),), TInteger()),  # a card's deck-declared card-point value
    # Positional order reads (decisions.md "Position domains and positional
    # zones", sequence orientation): top = the sequence end (most recent
    # arrival), bottom = the front. Loud runtime error on an empty collection.
    "top_of": Sig((TCollection(TCard()),), TCard()),
    "bottom_of": Sig((TCollection(TCard()),), TCard()),
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
    "tichu_next_holder": Sig((TPlayer(),), TPlayer()),  # Tichu: next holder ccw (or arg)
    "tichu_dragon_won": Sig((), TBoolean()),  # Tichu: Dragon captured the last trick?
    "tichu_card_points": Sig((TCard(),), TInteger()),  # Tichu: the card-point table
    "coup_next_in_game": Sig((TPlayer(),), TPlayer()),  # Coup: next in-game clockwise
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
    "five_hundred_next_bid": Sig(
        (TInteger(), TOptional(TEnum("Suit"))), TInteger()
    ),  # 500: cheapest bid ordinal in a strain beating the standing bid (0 = none)
    "five_hundred_bid_value": Sig((TInteger(),), TInteger()),  # 500: contract ordinal -> score value
    "five_hundred_bid_level": Sig((TInteger(),), TInteger()),  # 500: contract ordinal -> trick target
    "five_hundred_follow_ok": Sig((TPlayer(), TCard()), TBoolean()),  # 500: follow legality
    "five_hundred_lead_ok": Sig((TPlayer(), TCard()), TBoolean()),  # 500: lead legality
    "five_hundred_trick_winner": Sig((TPlayer(),), TPlayer()),  # 500: the trick's winner
    "belote_trump_height": Sig((TCard(),), TInteger()),  # Belote: trump-suit rank strength
    "belote_opp_winning": Sig((), TBoolean()),  # Belote: live trick's winner is an opponent?
    "belote_royal_player": Sig((), TOptional(TPlayer())),  # Belote: who played a trump K/Q
    "belote_best_is": Sig(
        (TPlayer(), TInteger(), TEnum("Rank"), TBoolean()), TBoolean()
    ),  # Belote: the declaration guard — stated combination is the best exactly
    "belote_decl_points": Sig((TPlayer(),), TInteger()),  # Belote: best combination's points
    "belote_decl_class": Sig((TPlayer(),), TInteger()),  # Belote: best combination's class
    "belote_decl_height": Sig((TPlayer(),), TInteger()),  # Belote: best combination's height
    "belote_decl_trump": Sig((TPlayer(),), TBoolean()),  # Belote: best combination in trump?
    "belote_decl_size": Sig((TPlayer(),), TInteger()),  # Belote: declared-card count
    "belote_decl_slot": Sig((TPlayer(), TInteger(), TCard()), TBoolean()),  # Belote: k-th declared card?
    "canasta_can_take_pile": Sig((TPlayer(),), TBoolean()),  # Canasta: legal pile take exists
    "canasta_must_take_pile": Sig((TPlayer(),), TBoolean()),  # Canasta: no-stock forced take
    "canasta_can_start": Sig(
        (TPlayer(), TEnum("Rank")), TBoolean()
    ),  # Canasta: a new meld of the rank is completable
    "canasta_stage_ok": Sig(
        (TPlayer(), TCard()), TBoolean()
    ),  # Canasta: card joins the open attempt, close stays reachable
    "canasta_close_ok": Sig((TPlayer(),), TBoolean()),  # Canasta: attempt closes as it stands
    "canasta_meld_points": Sig((TTeam(),), TInteger()),  # Canasta: melded card points
    "canasta_canasta_bonus": Sig((TTeam(),), TInteger()),  # Canasta: canasta bonuses
    "canasta_hand_points": Sig((TTeam(),), TInteger()),  # Canasta: points left in hands
}

# Outcome / value callbacks passed by bare name — result type is mechanic-driven.
VALUE_SIGS: dict[str, Type] = {
    "highest_of_led_suit": TAny(),
    "highest_trump_or_led_suit": TAny(),
    "tarot_trick_winner": TAny(),  # trick winner; the Excuse never wins
    "belote_trick_winner": TAny(),  # trick winner under Belote's J-9 trump order
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
