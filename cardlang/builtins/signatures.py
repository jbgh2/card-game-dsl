"""Type signatures for the native functions and value-callbacks.

Companion to :mod:`cardlang.builtins.functions` (which holds the *names*); these
tables hold the *types*, consumed by the type checker. The keys reconcile with
the name sets (asserted in tests), keeping "the native surface is data" single-sourced.

Looseness is deliberate where the corpus forces it: `suit_of` accepts a card or a
single-card zone, so its argument is the [[permissive-top]] `TAny`; outcome
value-callbacks return `TAny`; the `Resource` zone (`ChipStack`) holds `TAny`.
These track the deferred parts of the typed object model.
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
    # Hold'em: the showdown side-pot share (ranks cards, so deck-only).
    "holdem_pot_share": Sig((TPlayer(),), TInteger()),
    # Heads-up Hold'em's showdown share. Same shape and same maths as
    # `holdem_pot_share` — a separate name because a primitive module binds one
    # declared-reads row (issue #232), not because the query differs.
    "holdem_heads_up_pot_share": Sig((TPlayer(),), TInteger()),
    "rank_value": Sig((TCard(),), TInteger()),  # a card's rank strength (higher = stronger)
    "card_points": Sig((TCard(),), TInteger()),  # a card's points under `card_points { }`
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
    "skat_next_bid": Sig((TInteger(),), TInteger()),  # Skat: the next Reizen ladder value
    "skat_follow_ok": Sig((TPlayer(), TCard()), TBoolean()),  # Skat: follow-class legality
    # The three trick winners read the trick pile's Arrival Record (issue
    # #256): attribution is the kernel's, so no argument remains — the old
    # `leader` parameter existed only for the retired seat-order zip.
    "skat_trick_winner": Sig((), TPlayer()),  # Skat: the three-card trick's winner
    "skat_matadors": Sig((TPlayer(),), TInteger()),  # Skat: with/without matador count
    "tichu_dragon_won": Sig((), TBoolean()),  # Tichu: Dragon captured the last trick?
    "coup_game_summary": Sig((), TInteger()),  # Coup: conservation/finals trace
    "peg_pair_points": Sig((), TInteger()),  # Cribbage: live pegging-count pair points
    "peg_run_points": Sig((), TInteger()),  # Cribbage: live pegging-count run points
    "peg_origin_of": Sig((TCard(),), TPlayer()),  # Cribbage: who played a pegging-pile card
    "cribbage_show_value": Sig((TPlayer(),), TInteger()),  # Cribbage: a hand's show score
    "cribbage_crib_value": Sig((), TInteger()),  # Cribbage: the crib's show score
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
    "five_hundred_trick_winner": Sig((), TPlayer()),  # 500: the trick's winner
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
    "canasta_canasta_bonus": Sig((TTeam(),), TInteger()),  # Canasta: canasta bonuses
}

# Outcome / value callbacks passed by bare name — result type is mechanic-driven.
VALUE_SIGS: dict[str, Type] = {
    "highest_of_led_suit": TAny(),
    "highest_trump_or_led_suit": TAny(),
    "highest_by_trick_order": TAny(),  # trick winner under the game's `trick_order { }`
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
