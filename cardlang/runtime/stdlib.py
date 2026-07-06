"""Runtime implementations of the stdlib functions Hearts names.

These are the deferred runtime-primitives the front end only signatured
(library.md "Stdlib functions" / "Outcome functions"). Zone-query methods
(`where`, `cards_of_suit`) live in the evaluator; this module holds the bare
`f(...)` calls and the value-callbacks.
"""

from __future__ import annotations

from typing import Any, Callable

from cardlang.runtime.state import Ctx, IllegalMove
from cardlang.runtime.values import SUITS, Card, Player


def call(name: str, args: list[Any], ctx: Ctx) -> Any:
    match name:
        case "player_holding":
            return _player_holding(args[0], ctx)
        case "team_of":
            return ctx.rs.team_of[args[0]]
        case "suit_of":
            return _suit_of(args[0])
        case "strain_index":
            return _strain_index(args[0])
        case "error":
            raise IllegalMove(args[0] if args else "illegal move")
        case "bring_in_seat":
            from cardlang.runtime.stud import bring_in_seat

            return bring_in_seat(ctx)
        case "first_to_act_seat":
            from cardlang.runtime.stud import first_to_act_seat

            return first_to_act_seat(ctx)
        case "pot_share":
            from cardlang.runtime.stud import pot_share

            return pot_share(ctx, args[0])
        case "bigtwo_first_leader":
            from cardlang.runtime.bigtwo import first_leader_seat

            return first_leader_seat(ctx)
        case "rank_value":
            return ctx.rs.rank_index[args[0].rank]
        case "card_value":
            return ctx.rs.card_values.get(args[0].rank, 0)
        case "pinochle_meld_value":
            from cardlang.runtime.pinochle import pinochle_meld_value

            return pinochle_meld_value(ctx, args[0])
        case "tarot_led_suit":
            from cardlang.runtime.tarot import tarot_led_suit

            return tarot_led_suit(ctx)
        case "tarot_trump_height":
            from cardlang.runtime.tarot import tarot_trump_height

            return tarot_trump_height(args[0])
        case "tarot_excuse_player":
            from cardlang.runtime.tarot import tarot_excuse_player

            return tarot_excuse_player(ctx)
        case "tarot_per_opp":
            from cardlang.runtime.tarot import tarot_per_opp

            return tarot_per_opp(ctx, args[0])
        case "tarot_card_points":
            from cardlang.runtime.tarot import tarot_card_points

            return tarot_card_points(args[0])
        case "schnapsen_trick_winner":
            from cardlang.runtime.schnapsen import schnapsen_trick_winner

            return schnapsen_trick_winner(ctx, args[0], args[1])
        case "skat_next_bid":
            from cardlang.runtime.skat import skat_next_bid

            return skat_next_bid(args[0])
        case "skat_follow_ok":
            from cardlang.runtime.skat import skat_follow_ok

            return skat_follow_ok(ctx, args[0], args[1])
        case "skat_trick_winner":
            from cardlang.runtime.skat import skat_trick_winner

            return skat_trick_winner(ctx, args[0])
        case "skat_matadors":
            from cardlang.runtime.skat import skat_matadors

            return skat_matadors(ctx, args[0])
        case "skat_effective_loss":
            from cardlang.runtime.skat import skat_effective_loss

            return skat_effective_loss(args[0], args[1], args[2])
        case "tichu_call_roll":
            from cardlang.runtime.tichu import tichu_call_roll

            return tichu_call_roll(ctx)
        case "tichu_mahjong_holder":
            from cardlang.runtime.tichu import tichu_mahjong_holder

            return tichu_mahjong_holder(ctx)
        case "tichu_players_holding":
            from cardlang.runtime.tichu import tichu_players_holding

            return tichu_players_holding(ctx)
        case "tichu_double_victory":
            from cardlang.runtime.tichu import tichu_double_victory

            return tichu_double_victory(ctx)
        case "tichu_partner":
            from cardlang.runtime.tichu import tichu_partner

            return tichu_partner(ctx, args[0])
        case "tichu_next_holder":
            from cardlang.runtime.tichu import tichu_next_holder

            return tichu_next_holder(ctx, args[0])
        case "tichu_dragon_won":
            from cardlang.runtime.tichu import tichu_dragon_won

            return tichu_dragon_won(ctx)
        case "tichu_dragon_recipient":
            from cardlang.runtime.tichu import tichu_dragon_recipient

            return tichu_dragon_recipient(ctx, args[0])
        case "tichu_opponent_team":
            from cardlang.runtime.tichu import tichu_opponent_team

            return tichu_opponent_team(ctx, args[0])
        case "tichu_first_out":
            from cardlang.runtime.tichu import tichu_first_out

            return tichu_first_out(ctx)
        case "tichu_card_points":
            from cardlang.runtime.tichu import tichu_card_points

            return tichu_card_points(ctx, args[0])
        case "tichu_hand_summary":
            from cardlang.runtime.tichu import tichu_hand_summary

            return tichu_hand_summary(ctx)
        case "peg_value":
            from cardlang.runtime.cribbage import value

            return value(args[0])
        case "peg_pair_points":
            from cardlang.runtime.cribbage import peg_pair_points

            return peg_pair_points(ctx.rs.zones.single("play_pile").cards)
        case "peg_run_points":
            from cardlang.runtime.cribbage import peg_run_points

            return peg_run_points(ctx.rs.zones.single("play_pile").cards)
        case "peg_origin_of":
            from cardlang.runtime.cribbage import peg_origin_of

            return peg_origin_of(ctx, args[0])
        case "cribbage_show_value":
            from cardlang.runtime.cribbage import cribbage_show_value

            return cribbage_show_value(ctx, args[0])
        case "cribbage_crib_value":
            from cardlang.runtime.cribbage import cribbage_crib_value

            return cribbage_crib_value(ctx)
        case _:
            raise AssertionError(f"unknown stdlib function '{name}'")


def _strain_index(strain: str | None) -> int:
    """The bidding rank of a strain: clubs<diamonds<hearts<spades<no-trump. A
    suit's ordinal in the deck's suit order; `none` (no-trump) ranks above every
    suit. Used by an ascending contract auction to compare bid strains."""
    return len(SUITS) if strain is None else SUITS.index(strain)


def _suit_of(value: Any) -> str:
    """The suit of a card, or of the single card in a zone (a face-up trump
    indicator)."""
    from cardlang.runtime.state import Zone

    if isinstance(value, Zone):
        return value.cards[0].suit
    assert isinstance(value, Card)
    return value.suit


def _player_holding(card: Card, ctx: Ctx) -> Player | None:
    """The player whose hand contains `card`, or None."""
    for player, zone in ctx.rs.zones.families["hand"].items():
        if card in zone.cards:
            return player
    return None


# --- value-callbacks (mechanic functions passed by name) ---

# An outcome function picks the trick winner from the plays, the led suit, the
# trump suit (None when no trump), and the game's rank-strength map.
RankIndex = dict[str, int]
OutcomeFn = Callable[[list[tuple[Player, Card]], str, "str | None", RankIndex], Player]
# An early-termination predicate: does this play end the trick? (card, led_suit)
EarlyTermFn = Callable[[Card, str], bool]


def value_function(name: str) -> Callable[..., Any]:
    match name:
        case "highest_of_led_suit":
            return highest_of_led_suit
        case "highest_trump_or_led_suit":
            return highest_trump_or_led_suit
        case "on_play_of_tochoo":
            return on_play_of_tochoo
        case "tarot_trick_winner":
            from cardlang.runtime.tarot import tarot_trick_winner

            return tarot_trick_winner
        case _:
            raise AssertionError(f"unknown stdlib value '{name}'")


# --- climbing-form combination-engine queries (named on a `round climb`) ---
#
# A *lead* query returns every combination a hand may lead; a *follows* query
# returns those that beat the standing play. Both take the runtime ctx (a lead
# query may read game state, e.g. Big Two's opening 3♦ filter). The engines are
# game-local, so these dispatch to per-game modules.


def climb_lead_function(name: str) -> Callable[[list[Card], Ctx], list[Any]]:
    match name:
        case "bigtwo_lead_options":
            from cardlang.runtime.bigtwo import bigtwo_lead_options

            return bigtwo_lead_options
        case "tichu_lead_options":
            from cardlang.runtime.tichu import tichu_lead_options

            return tichu_lead_options
        case _:
            raise AssertionError(f"unknown climb lead query '{name}'")


def climb_follow_function(name: str) -> Callable[[list[Card], Any, Ctx], list[Any]]:
    match name:
        case "bigtwo_follows":
            from cardlang.runtime.bigtwo import bigtwo_follows

            return bigtwo_follows
        case "tichu_follows":
            from cardlang.runtime.tichu import tichu_follows

            return tichu_follows
        case _:
            raise AssertionError(f"unknown climb follows query '{name}'")


def climb_universe_function(name: str) -> Callable[[], list[Any]]:
    """The engine's full play universe — every combination it can ever emit —
    keyed by the SAME name as its `combinations` lead query. The OpenSpiel
    adapter derives the climb action space from this; the lead query itself
    cannot serve (its representatives depend on the live hand and game state)."""
    match name:
        case "bigtwo_lead_options":
            from cardlang.runtime.bigtwo import bigtwo_universe

            return bigtwo_universe
        case _:
            raise AssertionError(f"no combination universe for climb engine '{name}'")


def highest_of_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The player who played the highest-ranked card of the led suit."""
    of_suit = [(p, c) for (p, c) in played if c.suit == led_suit]
    return max(of_suit, key=lambda pc: rank_index[pc[1].rank])[0]


def highest_trump_or_led_suit(
    played: list[tuple[Player, Card]],
    led_suit: str,
    trump: str | None,
    rank_index: RankIndex,
) -> Player:
    """The highest trump if any trump was played, else the highest card of the
    led suit (the standard trick winner for a trump game)."""
    trumps = [(p, c) for (p, c) in played if c.suit == trump]
    if trumps:
        return max(trumps, key=lambda pc: rank_index[pc[1].rank])[0]
    return highest_of_led_suit(played, led_suit, trump, rank_index)


def on_play_of_tochoo(card: Card, led_suit: str) -> bool:
    """A tochoo is a card that fails to follow the led suit; playing one (only
    possible when void) ends the trick early (Getaway: the highest led-suit
    card then picks up the pile)."""
    return card.suit != led_suit


# --- auction outcome callbacks (the auction form of `round`) -----------------
#
# An auction outcome receives the bid history (`(player, move_type, param)` per
# accepted move) and the live `Ctx` (the auction's terminal phase state and
# `team_of`), and returns the typed `(tag, payloads)` the phase's `produces:`
# consumes. It consumes no RNG — it is a pure read of the threaded state/history.

AuctionHistory = list[tuple[Player, str, Any]]
AuctionOutcomeFn = Callable[[AuctionHistory, Ctx], "tuple[str, list[Any]]"]


def auction_outcome_function(name: str) -> AuctionOutcomeFn:
    match name:
        case "bridge_auction_outcome":
            return bridge_auction_outcome
        case "pinochle_auction_outcome":
            return pinochle_auction_outcome
        case "tarot_auction_outcome":
            return tarot_auction_outcome
        case _:
            raise AssertionError(f"unknown auction outcome '{name}'")


def bridge_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """Bridge's auction result: a pass-out, or the final contract with its
    declarer — the first player of the high-bidding side to have named the final
    strain (their left-hand opponent leads, so the exact seat matters)."""
    rs = ctx.rs
    if not rs.get("made_bid"):
        ctx.trace("bridge_contract", {"all_pass": True})
        return ("all_pass", [])
    high_team = rs.team_of[rs.get("high_bidder")]
    strain = rs.get("cur_strain")
    level = rs.get("cur_level")
    doubled = rs.get("doubled")
    declarer = next(
        (
            p
            for (p, move, param) in history
            if move == "submit_bid" and param == strain and rs.team_of[p] == high_team
        ),
        None,
    )
    assert declarer is not None, (
        f"bridge auction: made_bid is set but no submit_bid in the history names "
        f"the final strain {strain!r} for the high team {high_team} "
        f"(high_bidder={rs.get('high_bidder')})"
    )
    ctx.trace(
        "bridge_contract",
        {
            "all_pass": False,
            "declarer_team": high_team,
            "level": level,
            "strain": strain,
            "doubled_mult": doubled,
        },
    )
    return ("contract_finalized", [declarer, level, strain, doubled])


def pinochle_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """Pinochle's ascending auction always settles on a declarer: the standing
    high bidder at the bid he reached, or — if every seat passed without a bid —
    the opener at the minimum 50. (The bidding side must reach this in meld +
    tricks or be set back; see `pinochle.cardlang`.)"""
    rs = ctx.rs
    lead_bidder = rs.get("lead_bidder")
    if lead_bidder is None:
        declarer, bid = rs.get("opener"), 50
        assert declarer is not None, (
            "pinochle auction: all-pass fallback has no opener — the `auction` "
            "phase must set `opener := dealer offset_by left` before the round"
        )
        ctx.trace("pinochle_contract", {"all_pass": True, "declarer": declarer, "bid": bid})
        return ("bid_won", [declarer, bid])
    bid = rs.get("working_bid")
    ctx.trace(
        "pinochle_contract", {"all_pass": False, "declarer": lead_bidder, "bid": bid}
    )
    return ("bid_won", [lead_bidder, bid])


def tarot_auction_outcome(
    history: AuctionHistory, ctx: Ctx
) -> tuple[str, list[Any]]:
    """French Tarot's four-level bid: the high bidder becomes the taker at the
    level he reached, or — if every seat passed — the hand is thrown in (re-dealt,
    no score). `current_level` is 1..4 (petite..garde_contre; 0 = no bid)."""
    rs = ctx.rs
    taker = rs.get("lead_taker")
    if taker is None:
        ctx.trace("tarot_contract", {"thrown_in": True})
        return ("thrown_in", [])
    level = rs.get("current_level")
    ctx.trace("tarot_contract", {"thrown_in": False, "taker": taker, "level": level})
    return ("taken", [taker, level])
