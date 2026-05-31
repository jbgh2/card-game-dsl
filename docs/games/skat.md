# Skat

Three-player Skat (DSkV / International rules, post-1999). 32-card
deck. Players bid (Reizen) for the right to play alone against the
other two. Declarer picks a game type (Suit / Grand / Null), takes
or skips the two-card skat, and tries to win the contract for a
calculated game value. Source:
[Pagat](https://www.pagat.com/schafkopf/skat.html).

Skat is the corpus's tenth game and adds:

- A fourth bidding pattern beyond decisions.md "Bidding patterns" —
  call-and-response **Reizen** between forehand/middlehand and then
  rearhand/survivor, with bids drawn from a fixed legal sequence.
- A seventh typed-outcome phase (`declare_contract`) richer than
  Pinochle's `declare_trump` — outcome carries game type, hand mode,
  and trump suit. Adds a data point for
  [open-questions/mechanic-phase-unification.md](../open-questions/mechanic-phase-unification.md).
- A scoring shape where the *final score per player* is a single
  integer but its *computation* is structured: `base × multiplier`
  with multipliers from matadors, game, Hand, Schneider, Schwarz.
  Confirms the existing-language pattern that "structured score" in
  the channels-with-eligibility sense (Bridge, Stud) is a special
  case, not a generalized concept.
- The **overbid** rule: if declarer's actual game value is less than
  their bid, they automatically lose 2× the smallest multiple of the
  base value that is ≥ the bid. Distinctive Skat penalty.

In scope: Suit / Grand / Null contracts; Hand vs Skat games;
matadors; earned Schneider and Schwarz; standard overbid.
Out of scope: announced Schneider/Schwarz/Ouvert (Hand-only edge);
Null Ouvert; Ramsch / forced-round variants; 4-player dealer-sits-out
rotation; tournament point conversions; pre-1999 single-penalty losses.

```
game Skat {

  players: 3
  direction: clockwise

  // 32-card deck, ace-ten order (10 above K). See library.md "Stdlib decks".
  cards: skat32
  // Trick rules differ per contract: Suit and Grand games have all
  // four Jacks as trumps (C > S > H > D), ranking above other trumps.
  // Null games have no trumps and rerank A > K > Q > J > 10 > 9 > 8 > 7.
  // See SuitTrickWinner / GrandTrickWinner / NullTrickWinner below.

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    skat             : FaceDownPile        // the two-card widow
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }

  state {
    // Game-level: persists across hands.
    score[player] : Integer = 0
    hands_played  : Integer = 0
  }

  // === Top-level phase sequence ===

  phase hand_sequence repeats until hands_played >= 36 {
    state {
      // Per-hand: reset each hand.
      forehand    : Player = dealer.left
      middlehand  : Player = forehand.left
      rearhand    : Player = middlehand.left

      declarer    : Player? = none
      bid         : Integer = 0

      game_type   : GameType?  = none
      trump_suit  : Suit?      = none           // only set for Suit games
      hand_mode   : Boolean    = false          // true if declarer didn't pick up skat
    }

    phase setup {
      shuffle deck
      // 3-3-skat-4-3 deal: 3 each, 2 to skat, 4 each, 3 each.
      deal 3 cards from deck to each hand
      deal 2 cards from deck to skat
      deal 4 cards from deck to each hand
      deal 3 cards from deck to each hand
      dealer := dealer.left
    }

    phase bidding {
      instantiate Reizen (
        forehand   = forehand,
        middlehand = middlehand,
        rearhand   = rearhand,
        outcome    = (winner, value) ⇒ {
          declarer := winner
          bid      := value
        }
      )
    }

    bidding produces:
      declarer_chosen(_, _):
        continue to declare_contract
      all_pass:
        // Hand is thrown in: no score, just advance.
        hands_played += 1
        skip to next hand

    phase declare_contract → outcome {
      suit_declared(Suit, hand: Boolean) |
      grand_declared(hand: Boolean) |
      null_declared(hand: Boolean)
    } {
      legal_moves: [pick_up_skat, declare]

      offer action to declarer: one of
        pick_up_skat:
          move all cards from skat to hand[declarer]
          choose 2 cards from hand[declarer]
          move chosen cards from hand[declarer] to skat
          // declarer keeps card points of discarded cards (skat counts
          // to declarer's captured at scoring time)
          // hand_mode remains false
        declare_hand:
          hand_mode := true
          // skat untouched; counts to declarer at scoring time

      offer action to declarer: one of
        declare_suit_diamonds: trump_suit := D; resolve suit_declared(D, hand_mode)
        declare_suit_hearts:   trump_suit := H; resolve suit_declared(H, hand_mode)
        declare_suit_spades:   trump_suit := S; resolve suit_declared(S, hand_mode)
        declare_suit_clubs:    trump_suit := C; resolve suit_declared(C, hand_mode)
        declare_grand:         resolve grand_declared(hand_mode)
        declare_null:          resolve null_declared(hand_mode)
    }

    declare_contract produces:
      suit_declared(s, h):
        game_type  := Suit
        // trump_suit and hand_mode already set above
        continue to play
      grand_declared(h):
        game_type := Grand
        continue to play
      null_declared(h):
        game_type := Null
        continue to play

    phase play {
      state {
        leader : Player = forehand        // forehand always leads trick 1
      }

      // The trick-resolution function depends on the contract. All three
      // share the trick loop; only `outcome` varies.
      let trick_outcome = match game_type:
        Suit  → SuitTrickWinner(trump_suit)
        Grand → GrandTrickWinner
        Null  → NullTrickWinner

      active_rules: [MustFollowSuit]
      legal_moves:  [play_to_trick]

      repeat 10 times {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = trick_outcome,
          routing      = all cards from trick_pile to captured[outcome]
        )
        leader := outcome
      }
    }

    phase scoring {
      let result = SkatHandResult(
        declarer    = declarer,
        bid         = bid,
        game_type   = game_type,
        trump_suit  = trump_suit,
        hand_mode   = hand_mode,
        defenders   = all players except declarer
      )

      apply_components: [SkatScoring]
      hands_played += 1
    }
  }

  winner: player with highest score
}

// =====================================================================
// Reizen — Skat's call-and-response bidding mechanic
// =====================================================================

// The legal bid sequence (game values that can actually be reached
// in valid Skat games). The bidder doesn't need to mean a specific
// game type by the bid — just that they intend to play a game worth
// at least this much.
let legal_bid_sequence = [
  18, 20, 22, 23, 24, 27, 30, 33, 35, 36, 40, 44, 45, 46, 48, 50,
  54, 55, 59, 60, 63, 66, 70, 72, 77, 80, 81, 84, 88, 90, 96, 99,
  100, 108, 110, 117, 120, 121, 126, 130, 132, 135, 140, 143, 144,
  150, 153, 156, 160, 162, 165, 168, 170, 176, 180, 187, 192, 198,
  204, 216, 240, 264
]

mechanic Reizen (
  forehand: Player, middlehand: Player, rearhand: Player,
  outcome: (winner: Player, value: Integer | all_pass) → effect
) {
  state {
    // Per-Reizen: lives for one instance.
    current_bid : Integer = 0
  }

  // Part 1: middlehand speaks, forehand responds.
  let part1_winner = reizen_exchange(speaker = middlehand, responder = forehand)

  // Part 2: rearhand speaks, part1_winner responds.
  let final_winner = reizen_exchange(speaker = rearhand, responder = part1_winner)

  if current_bid == 0:
    // Both M and R passed without a bid. Forehand may play at 18 or throw in.
    offer action to forehand: one of
      play_at_eighteen:
        current_bid := 18
        outcome(forehand, 18)
      throw_in:
        outcome(all_pass)
  else:
    outcome(final_winner, current_bid)

  // ---- inner exchange ----
  let reizen_exchange = (speaker, responder) ⇒ {
    repeat until decided {
      offer action to speaker: one of
        pass:
          return responder
        bid:
          choose Integer b from legal_bid_sequence where b > current_bid
          current_bid := b
          offer action to responder: one of
            yes:
              // responder matches; loop continues — speaker may raise or pass
              continue
            pass:
              return speaker
    }
  }
}

// =====================================================================
// Move types
// =====================================================================

// Bidding moves (used inside Reizen).
move_type pass   { }
move_type bid    { carries: value : Integer }
move_type yes    { }

// Contract declaration moves.
move_type pick_up_skat {
  preconditions: not hand_mode
                 and skat.size == 2
}
move_type declare_hand {
  preconditions: skat.size == 2          // hasn't been picked up
}
move_type declare_suit_diamonds  { }
move_type declare_suit_hearts    { }
move_type declare_suit_spades    { }
move_type declare_suit_clubs     { }
move_type declare_grand          { }
move_type declare_null           { }

// Plus the special forehand-fallback moves.
move_type play_at_eighteen { }
move_type throw_in         { }

// play_to_trick: standard.

// =====================================================================
// Types
// =====================================================================

type GameType = Suit | Grand | Null

type SkatHandResult = {
  declarer   : Player
  bid        : Integer
  game_type  : GameType
  trump_suit : Suit?
  hand_mode  : Boolean
  defenders  : Set<Player>
}

// =====================================================================
// Rules
// =====================================================================

rule MustFollowSuit {
  // Skat reuses the standard MustFollowSuit shape but consults the
  // per-game `same_suit_class` predicate rather than comparing printed
  // suits directly. In Suit/Grand games, the four jacks form a
  // "trump class" along with the trump-suit cards (Suit) or by
  // themselves (Grand). In Null games, the predicate collapses to
  // printed-suit equality.
  constrains: play_to_trick
  applies_when: state.trick.led_card is not none
  demands: hand.where(c ⇒ same_suit_class(c, state.trick.led_card))
}

// =====================================================================
// Per-game helpers
// =====================================================================

// What follow-suit class does this card belong to? The return value is
// an opaque tag used only for equality comparison — `"trump"` is not a
// real Suit value, just a sentinel that all trump cards share.
same_suit_class(c1, c2) = follow_class(c1) == follow_class(c2)

follow_class(c) =
  if game_type == Null:               c.suit
  elif c.rank == J:                   "trump"
  elif game_type == Suit and c.suit == trump_suit:  "trump"
  else:                               c.suit

// =====================================================================
// Trick-winner outcomes (one per game type, dispatched at phase entry)
// =====================================================================

// Suit game: trumps are the four jacks (C > S > H > D) plus the seven
// other cards of the trump suit (A > 10 > K > Q > 9 > 8 > 7 within the
// non-jack trumps; jacks rank above all non-jack trumps).
outcome SuitTrickWinner (trump_suit) = (played_cards, trick_state) ⇒
  let trumps = played_cards.filter(c ⇒ c.rank == J or c.suit == trump_suit)
  if trumps.non_empty:
    player_of(argmax trumps by suit_game_trump_order(trump_suit))
  else:
    player_of(argmax played_cards.filter(c ⇒ c.suit == trick_state.led_suit)
                                  by skat_rank)

// Grand game: only the four jacks are trumps. Otherwise highest of led suit.
outcome GrandTrickWinner = (played_cards, trick_state) ⇒
  let jacks = played_cards.filter(c ⇒ c.rank == J)
  if jacks.non_empty:
    player_of(argmax jacks by jack_suit_order)                  // C > S > H > D
  else:
    player_of(argmax played_cards.filter(c ⇒ c.suit == trick_state.led_suit)
                                  by skat_rank)

// Null game: no trumps. Ranking is A > K > Q > J > 10 > 9 > 8 > 7.
outcome NullTrickWinner = (played_cards, trick_state) ⇒
  player_of(argmax played_cards.filter(c ⇒ c.suit == trick_state.led_suit)
                                by null_rank)

// Ranking orders used above:
//   skat_rank: A > 10 > K > Q > 9 > 8 > 7 (used for non-jack cards in Suit/Grand)
//   null_rank: A > K > Q > J > 10 > 9 > 8 > 7 (Null game, all cards)
//   jack_suit_order: C > S > H > D (jack ordering in Suit/Grand)
//   suit_game_trump_order(s): jacks (C > S > H > D) above non-jack trumps of suit s
//                             (A > 10 > K > Q > 9 > 8 > 7)

// =====================================================================
// Scoring
// =====================================================================

scoring_component SkatScoring (result) {
  let delta[player] = 0 for each player

  if result.game_type == Null:
    let declarer_won = captured[result.declarer].is_empty
    let game_value = null_game_value(result.hand_mode)
    if declarer_won and game_value >= result.bid:
      delta[result.declarer] += game_value
    else:
      // Null contract failed (declarer took a trick) OR overbid.
      delta[result.declarer] -= 2 * effective_loss_value(game_value, result.bid,
                                                        null_base = game_value)
  else:
    // Suit or Grand: card-point threshold game.
    let declarer_points = sum of card_value(c) for c in captured[result.declarer]
                            + sum of card_value(c) for c in skat   // skat goes to declarer
    let defender_points = 120 - declarer_points
    let base = base_value(result.game_type, result.trump_suit)
    let matadors = matadors_count(result.declarer, result.trump_suit, result.game_type)

    let threshold =
      if declarer_points >= 90 or defender_points == 0: 1   // Schneider/Schwarz earned
      else: 0
    let schwarz = if (declarer's tricks_won == 10 or defender's tricks_won == 10): 1 else: 0

    let multiplier = matadors + 1          // matadors + 1 for game
                   + (if result.hand_mode then 1 else 0)
                   + (if declarer_points >= 90 then 1 else 0)
                   + (if declarer_points <= 30 then 1 else 0)   // declarer Schneider
                   + schwarz

    let game_value = base * multiplier
    let declarer_made = declarer_points >= 61

    if declarer_made and game_value >= result.bid:
      delta[result.declarer] += game_value
    else:
      delta[result.declarer] -= 2 * effective_loss_value(game_value, result.bid,
                                                        suit_base = base)

  ScoreDelta { score[p] += delta[p] for each player p }
}

// Game value for null contracts.
null_game_value(hand_mode) =
  if hand_mode then 35 else 23

// Effective loss value handles the overbid rule.
// If game_value >= bid: lose 2 * game_value (declarer simply lost a
// contract they could have made).
// If game_value < bid: lose 2 * (smallest multiple of base ≥ bid)
// — the overbid penalty.
effective_loss_value(game_value, bid, base) =
  if game_value >= bid:
    game_value
  else:
    smallest multiple of base ≥ bid

base_value(game_type, trump_suit) =
  match game_type:
    Suit  → match trump_suit: D→9, H→10, S→11, C→12
    Grand → 24
    Null  → 23   // unused — Null uses fixed game values directly

// Matadors: the CJ and any top trumps in unbroken sequence with it,
// in declarer's hand+skat. If declarer doesn't hold the CJ, count the
// unbroken top trumps the opponents hold instead ("without N").
matadors_count(declarer, trump_suit, game_type) =
  let top_trumps_order = trump_order(game_type, trump_suit)
  let declarer_cards = hand[declarer] ∪ skat
  let declarer_holds_top(n) = declarer_cards contains top_trumps_order[n]
  if declarer_holds_top(0):
    // "with N" — count consecutive top trumps declarer holds
    largest N such that declarer_holds_top(0..N-1) all true
  else:
    // "without N" — count consecutive top trumps declarer is missing
    largest N such that declarer_holds_top(0..N-1) all false

trump_order(game_type, trump_suit) =
  match game_type:
    Grand → [CJ, SJ, HJ, DJ]
    Suit  → [CJ, SJ, HJ, DJ, A_of_trump, 10_of_trump, K_of_trump,
             Q_of_trump, 9_of_trump, 8_of_trump, 7_of_trump]

card_value(card) =
  match card.rank:
    A → 11, 10 → 10, K → 4, Q → 3, J → 2,
    _ → 0
```
