# French Tarot

Four-player French Tarot, FFT rules. 78-card Tarot deck (4 standard
suits × 14 + 21 atouts + Excuse). One player (the *taker*) plays
alone against three opponents, aiming to take enough card points
in tricks to make the bid. Source:
[Pagat](https://www.pagat.com/tarot/frtarot.html).

French Tarot adds to the corpus:

- The first **non-uniform deck** — exercises the per-suit form of
  the cards model committed in decisions.md "Deck declaration"
  (here used via the `tarot78` stdlib constant).
- A **fourth bidding pattern** beyond decisions.md "Bidding
  patterns": one-shot ascending bid per player in turn, with four
  named levels (Petite, Garde, Garde sans le chien, Garde contre
  le chien). Each level both ranks the bid AND specifies the
  downstream chien-handling behaviour.
- **Chien handling dispatched by bid level** — the bidding phase
  resolves to a typed outcome whose value determines whether the
  chien sub-phase runs at all. See decisions.md "Typed phase outcomes".
- A **bouts-conditional win threshold** (36/41/51/56 card points
  depending on how many bouts the taker captured). Per-game
  scoring shape.
- The **Excuse** — a singleton special card whose play has unusual
  routing semantics: the team that plays it keeps it in their
  tricks regardless of who wins the trick, transferring a
  0.5-point card to the trick winner in compensation.

In scope: 4-player FFT rules; all four bid levels; chien handling;
Excuse routing; poignée and petit-au-bout bonuses; standard
multiplier-based scoring.
Out of scope: 3-/5-player variants; chelem and petit chelem;
misère; petit imprenable; the "mouches" pool-based historical
scoring; variant scoring systems.

```
game FrenchTarot {

  players: 4
  direction: counterclockwise         // canonical for French Tarot

  cards: tarot78                      // see library.md "Stdlib decks"
  // Card-point values are doubled here to keep all arithmetic in
  // integers — Pagat lists them as 4.5, 3.5, 2.5, 1.5, 0.5, summing
  // to 91 across the 78 cards. The doubled values sum to 182.
  //   Bouts (1 of atouts, 21 of atouts, Excuse) — 9
  //   Kings                                       — 9
  //   Queens                                      — 7
  //   Knights (Cavalier)                          — 5
  //   Jacks                                       — 3
  //   All other cards                             — 1
  // The scoring component halves the totals at the end.

  zones {
    deck              : Deck
    hand[player]      : Hand<player>
    chien             : FaceDownPile              // the six-card kitty
    trick_pile        : TrickPile
    captured[player]  : PlayerPile<player>
    excuse_repay_pile : Discard                   // see TarotTrickRouting below
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
      taker         : Player?    = none
      bid_level     : BidLevel?  = none
      poignee[player] : PoignéeSize = none      // declared at start of play
    }

    phase setup {
      shuffle deck
      // 78 cards: 4×18 to players + 6 to chien. Packets of three; chien
      // cards interspersed during the deal (first 3 and last 3 may not
      // go to chien). The exact pacing is dealer's choice and doesn't
      // affect downstream play.
      deal 18 cards to each hand, with 6 cards routed to chien
        (constraint: chien cards aren't from the first or last 3 of deck)
      dealer := dealer.right                     // counter-clockwise rotation
    }

    phase bidding {
      instantiate TarotBidding (
        starting_player = dealer.right,
        outcome = (winner, level) ⇒ {
          taker     := winner
          bid_level := level
        }
      )
    }

    bidding produces:
      all_pass:
        // Hand is thrown in. No scoring; advance.
        hands_played += 1
        skip to next hand
      taker_chosen(_, level):
        if level == Petite or level == Garde:
          continue to chien_visible
        else:
          // Garde sans / Garde contre: chien not handled by taker
          continue to play

    phase chien_visible {
      // Taker turns chien face up, takes into hand, discards six.
      reveal all cards in chien to all players
      move all cards from chien to hand[taker]
      active_rules: [DiscardRestrictions]
      legal_moves:  [discard_to_chien]
      offer action to taker:
        choose 6 cards from hand[taker]
        move chosen cards from hand[taker] to captured[taker]
        // Discards count to taker's tricks at scoring time.
    }

    phase play {
      state {
        leader : Player = dealer.right           // player to dealer's right leads
      }

      // Window for declaring poignée — each player may show 10+ trumps
      // before playing their first card. See call_poignee precondition.
      legal_moves:  [play_to_trick, call_poignee]
      active_rules: [MustFollowSuit, MustTrumpIfVoid, MustOvertrumpIfPossible]

      repeat 18 times {
        instantiate Trick (
          participants = all players,
          leader       = leader,
          source_zone  = hand,
          play_zone    = trick_pile,
          play_rules   = active_rules,
          outcome      = TrumpedHighestOfLedSuit(trump = atouts),
          routing      = TarotTrickRouting
        )
        leader := outcome
      }
    }

    phase scoring {
      let result = TarotHandResult(
        taker          = taker,
        bid_level      = bid_level,
        opponents      = all players except taker,
        captured       = captured,
        chien_contents = chien,                  // empty for Petite/Garde, full otherwise
        poignee        = poignee
      )
      apply_components: [TarotScoring]
      hands_played += 1

      // Reset for next hand.
      move all cards from captured[player]   to deck for each player
      move all cards from hand[player]       to deck for each player
      move all cards from chien              to deck
      move all cards from excuse_repay_pile  to deck
    }
  }

  winner: player with highest score
}

// =====================================================================
// Bidding — one shot per player, ascending
// =====================================================================

mechanic TarotBidding (
  starting_player: Player,
  outcome: (winner: Player, level: BidLevel) → effect | all_pass → effect
) {
  state {
    current_level   : BidLevel? = none
    current_bidder  : Player?   = none
    speakers_left   : Integer   = 4
  }

  active_rules: [BidExceedsCurrent]
  legal_moves:  [submit_bid, pass]

  let active = starting_player
  repeat until speakers_left == 0 {
    offer action to active: one of
      pass:
        speakers_left -= 1
      submit_bid:
        choose BidLevel L where L > current_level (or current_level == none)
        current_level  := L
        current_bidder := active
        speakers_left  -= 1
    active := active.right
  }

  if current_bidder == none:
    outcome(all_pass)
  else:
    outcome(current_bidder, current_level)
}

// =====================================================================
// Move types
// =====================================================================

move_type submit_bid     { carries: level : BidLevel }
move_type pass           { }
move_type discard_to_chien {
  source: hand[active_player]
  destination: captured[active_player]   // discards count to taker's tricks
}
move_type call_poignee {
  preconditions: poignee[active_player] == none
              and active_player has played zero cards this hand
              and active_player's hand contains at least 10 trumps
  effect:
    let trump_count = number of atouts cards in hand[active_player]
    let size = if trump_count >= 15 then Triple
              elif trump_count >= 13 then Double
              else                       Single
    poignee[active_player] := size
    reveal trump cards in hand[active_player] to all players
}

// play_to_trick: standard.

// =====================================================================
// Types
// =====================================================================

// Bid levels in ascending order. The bid both ranks (each bid must
// exceed the prior) AND specifies downstream chien handling and the
// scoring multiplier.
type BidLevel = Petite | Garde | GardeSansLeChien | GardeContreLeChien
  ordered: Petite < Garde < GardeSansLeChien < GardeContreLeChien

type PoignéeSize = Single | Double | Triple | none

type TarotHandResult = {
  taker          : Player
  bid_level      : BidLevel
  opponents      : Set<Player>
  captured       : Map<Player, Zone<Card>>
  chien_contents : Zone<Card>
  poignee        : Map<Player, PoignéeSize>
}

// =====================================================================
// Routing — the Excuse gets special handling
// =====================================================================

// When the Excuse is played to a trick:
//   - If the team that played Excuse wins the trick: routing is normal.
//   - Otherwise: Excuse stays with its playing team; the playing team
//     transfers a 0.5-point card (=1 doubled point) from their captured
//     pile to the winner. If they don't yet have such a card, the
//     transfer is deferred (`excuse_repay_pile` tracks the debt).
// In the last trick the FFT rule reverses this — for scope, we use the
// standard pre-1990 rule (excuse stays with playing team).
routing TarotTrickRouting = (played_cards, trick_state, winner) ⇒
  if not any played card is Excuse:
    all cards from trick_pile to captured[winner]
  else:
    let excuse_player = player_who_played(Excuse, trick_state)
    if excuse_player == winner:
      all cards from trick_pile to captured[winner]
    else:
      // Excuse stays with its playing team; one 0.5-pt card transferred.
      move Excuse                            from trick_pile to captured[excuse_player]
      move all remaining cards from trick_pile to captured[winner]
      if captured[excuse_player] has any non-bout 0.5-point card:
        move one such card from captured[excuse_player] to captured[winner]
      else:
        // Defer the transfer; remember the debt.
        move one half-point IOU from excuse_repay_pile to captured[winner]
        // The next 0.5-point card excuse_player captures will be
        // transferred to settle the debt. (Sketch — kept abstract.)

// =====================================================================
// Rules
// =====================================================================

rule BidExceedsCurrent {
  constrains: submit_bid
  applies_when: state.current_level != none
  demands: BidLevel L where L > state.current_level
}

// Standard MustFollowSuit (see library.md). Default same_suit_class
// (printed-suit equality) applies — atouts are a real suit here.

rule MustTrumpIfVoid {
  constrains: play_to_trick
  applies_when: state.trick.led_card is not none
                and not hand[active_player] has card of led suit
  demands: hand[active_player].cards_of_suit(atouts)
}

rule MustOvertrumpIfPossible {
  // Whenever you have to play a trump — either because trump was led
  // or because you're void in led suit — you must play a higher trump
  // than any trump already in the trick, if you have one. If you can't,
  // you may play any trump.
  constrains: play_to_trick
  applies_when: playing a trump (either led suit is atouts,
                                  or void in led suit forcing a trump)
                and any trump already in trick_pile
  demands:
    let highest_trump_played = trick_pile.highest_of_suit(atouts).rank
    hand[active_player].cards_of_suit(atouts)
                       .where(c ⇒ c.rank > highest_trump_played)
  if_impossible: hand[active_player].cards_of_suit(atouts)
}

rule DiscardRestrictions {
  // Taker may not discard trumps, kings, or the Excuse. Exception:
  // if the taker's hand is so trump-heavy that they cannot otherwise
  // discard 6 non-trumps, they may discard trumps (but never bouts);
  // those trump discards must be shown to all players.
  constrains: discard_to_chien
  demands: 6 cards from hand[taker], none of which are
           trumps, kings, or Excuse
  if_impossible: 6 cards where bouts are still excluded and any
                 trump discards are revealed to all players
}

// =====================================================================
// Scoring
// =====================================================================

scoring_component TarotScoring (result) {
  // Card points captured by the taker (doubled units for integer arithmetic).
  let taker_doubled = sum of card_value(c) for c in result.captured[result.taker]
                    + (match result.bid_level:
                         Petite | Garde       → 0    // chien already in captured
                         GardeSansLeChien     → sum of card_value(c) for c in result.chien_contents
                         GardeContreLeChien   → 0)
  let opp_doubled =
        sum of card_value(c) for opp in result.opponents, c in result.captured[opp]
      + (if result.bid_level == GardeContreLeChien:
           sum of card_value(c) for c in result.chien_contents
         else: 0)
  let taker_points = taker_doubled / 2
  // (taker_doubled + opp_doubled = 182 = 91 × 2 invariant)

  // Bouts captured by taker.
  let bouts = number of bouts in (result.captured[result.taker]
                                 + (chien if bid_level in {Petite, Garde, GardeSansLeChien}))
  let threshold = match bouts:
    3 → 36
    2 → 41
    1 → 51
    0 → 56

  let pt = taker_points - threshold     // signed: positive if made, negative if down

  // Petit au bout: 10 points if the 1 of atouts is in the last trick.
  // Sign depends on who took the last trick.
  let pb = match (1_of_atouts_in_last_trick, taker_took_last_trick):
    (true,  true)  → +10
    (true,  false) → -10
    _              → 0

  // Multiplier from bid level.
  let mu = match result.bid_level:
    Petite              → 1
    Garde               → 2
    GardeSansLeChien    → 4
    GardeContreLeChien  → 6

  // Poignée bonus: applied to the winning team's score.
  // Single 20, Double 30, Triple 40.
  let pg = sum over player p of:
    let size_pts = match result.poignee[p]:
      Single → 20
      Double → 30
      Triple → 40
      none   → 0
    // The bonus goes to the winning team. Taker wins if pt >= 0.
    let p_on_winning_team = (p == result.taker) == (pt >= 0)
    if p_on_winning_team then +size_pts else -size_pts

  // Per-opponent transfer. The formula is:
  //   per-opponent = ((25 + pt + pb) × mu) + pg
  // The taker collects 3× this from the three opponents.
  let per_opp = ((25 + pt + pb) * mu) + pg

  let delta[player] = 0 for each player
  delta[result.taker] += 3 * per_opp
  for each opp in result.opponents:
    delta[opp] -= per_opp

  ScoreDelta { score[p] += delta[p] for each player p }
}

// Card values, doubled to keep all arithmetic integer.
card_value(c) =
  if c == Excuse:                                                9
  elif c.suit == atouts and (c.rank == 1 or c.rank == 21):       9    // petit, 21
  elif c.rank == K:                                              9
  elif c.rank == Q:                                              7
  elif c.rank == Cavalier:                                       5
  elif c.rank == J:                                              3
  else:                                                          1

bouts = { 1 of atouts, 21 of atouts, Excuse }
```
