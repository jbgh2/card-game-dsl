# Tichu

The companion formal file is [tichu.cardlang](tichu.cardlang); this is the
readable twin. A four-player team **climbing** game on a 56-card deck (the
standard 52 plus four special cards: Mahjong, Dog, Phoenix, Dragon). First
team to **1000** wins. Rules: Fata Morgana English edition.

Each hand:

1. Deal 8 cards each; each player may call **Grand Tichu** (±200) before
   the last six cards are dealt. The deal completes to 14 and every player
   **pushes** one card to each other player. Any player who has not called
   may call **Tichu** (±100) at any time before playing their first card —
   including before or during the push.
2. The Mahjong holder leads. Players **climb**: each play must be a combination
   of the led *type and length* and **beat** the previous play in rank, or be a
   **bomb** (four of a kind, which beats any non-bomb), or **pass**. Three passes
   end the trick and the last player to play wins it and leads next.
   Combinations: singles, pairs, triples, full houses, straights (≥5),
   consecutive pairs (≥2), and bombs.
3. The special cards: the **Mahjong** is rank 1 (lowest) and leads first; the
   **Dog** is led alone and hands the lead to your partner (no capture); the
   **Phoenix** is a wildcard / a single worth half a rank above the last play
   (and −25 points); the **Dragon** is the highest single, worth +25, and its
   trick is given to an opponent of the winner's choice.
4. As players empty their hands they go out in order. If both partners of a team
   go out first and second — a **double victory** — the hand ends for 200 points
   with no card counting. Otherwise the last player's remaining hand goes to the
   opponents and their captured tricks to the first player out, and each team
   scores its captured card points (K and 10 = 10, 5 = 5, Dragon +25, Phoenix
   −25; 100 in all). Finally, **Tichu** (±100) and **Grand Tichu** (±200) calls
   pay out by whether the caller went out first.

The hand runs fully on the kernel. Each climbing trick is one `round climb`
over the game-local combination engine (`tichu_lead_options` /
`tichu_follows` — the enumeration itself is not DSL-expressible: a play moves
a specific computed card-set, where the movement vocabulary moves cards by
count). The Dog is a *trick-ending lead*: the engine marks the play
`ends_trick`, the climb form closes the trick with no follower draws, and the
body routes it off the round's terminal state (`state.lead_ended_trick` —
pile to the discard, lead to the partner). Finishing order likewise comes
from terminal round-state (`state.shed_first` / `state.shed_second`, the
first two players to play out their cards each trick, in play order). The
push is one chosen 3-card movement per player into a per-player `gift` pile
— simultaneous, since gifts land only after every pick — distributed
giver-major and draw-free (pick *i* to the *i*-th other seat), so each
receiver learns exactly what landed and from whom, and nobody else learns
anything but counts. The calls and the Dragon are real decisions. Grand
tichu is a discrete window in the deal (eight cards, each player accepts or
declines in seat order, then the last six). Small tichu is off-the-clock —
any time before the caller's first play — encoded as the quiescence-lap poll
([decisions.md](../decisions.md) "Off-the-clock windows"): before the push,
after it, and before each climbing trick, an offering round walks the ring
while the public gate holds (`no_call` laps close it). Eligibility is public
with no dedicated tracking: before the push nobody has played; after it,
exactly the players still holding 14 cards haven't. Because the climb round
owns the decisions inside a trick, within-trick call timing coarsens to
trick boundaries — no call becomes unreachable, only its fine timing
relative to plays inside the caller's first trick. A Dragon-won trick is
given away by a real announced choice (`dragon_to_left` / `dragon_to_right`);
both opponents bank into the same team pile, so the choice moves no points,
but the decision itself is public history, as at the table. One honest
consequence of real calls: under *indiscriminate* calling the 1000-point
race diverges (a random call is worth about −50 in expectation), so a table
of maniacs never finishes — the corpus's second legally-unbounded line
([open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md));
the playout tests drive the windows through a reference policy instead.
Scope reductions (unchanged): the Mahjong wish, the Phoenix as a wildcard
inside straights/consecutive-pairs, straight-flush bombs, and out-of-turn
bombs are omitted.

```
game Tichu {

  players: 4
  teams: [[0, 2], [1, 3]]   // partners sit across
  direction: counterclockwise
  max_length: 20000

  cards: tichu56
  // The sparse point table: K and 10 score 10, 5 scores 5, the Dragon 25,
  // the Phoenix -25; every other card 0 (100 points per hand).
  card_points { 5: 5  10: 10  K: 10  Dragon: 25  Phoenix: -25 }

  zones {
    deck           : Deck
    hand[player]   : Hand<player>
    gift[player]   : Hand<player>     // the push: three picks, in pick order
    trick_pile     : TrickPile
    captured[team] : TeamPile<team>
    discard        : Discard          // the Dog goes here (no capture)
  }

  state {
    // Game-level: persists across hands.
    score[team] : Integer = 0
  }

  phase hand_sequence repeat until (any team where score[team] >= 1000) {
    before_each {
      move all cards to deck
      shuffle deck
      deal 8 cards from deck to each hand
    }

    phase play {
      state {
        called[player] : Integer = 0   // 0 / 100 / 200; calls are announced (public)
        out_first  : Player? = none    // finishing order (public), first two only —
        out_second : Player? = none    //   all the scoring ever reads
        leader     : Player? = none
        poll_anchor : Player = 0       // fixed, public ring anchor for pre-lead polls
        quiet      : Integer = 0       // consecutive no_call count (poll bookkeeping)
        push_done  : Boolean = false   // public flip: post-push, hand size 14 = unplayed
      }

      legal_moves: [play_combination]

      // Grand tichu: on the first eight cards, each player in seat order
      // accepts or declines the 200-point call, then the deal completes.
      for each player p: offer to p one of [call_grand_tichu, decline_grand]
      deal 6 cards from deck to each hand

      // Small tichu before the push ("a call before the cards are pushed can
      // be useful as a request for partner to hand over his best card").
      if tichu_window_open() {
        quiet := 0
        round offering [call_tichu, no_call] from poll_anchor over all players
              until quiet >= 4
      }

      // The push: one draw of three from the live hand per player; gifts land
      // only after every pick (simultaneous). Distribution is draw-free and
      // giver-major: pick i goes to the i-th other player in seat order.
      for each player p: move chosen 3 cards from hand[p] to gift[p]
      for each player p: for each player q: if q is not p { deal one card from gift[p] to hand[q] }
      push_done := true

      // Small tichu between the push and the first lead.
      if tichu_window_open() {
        quiet := 0
        round offering [call_tichu, no_call] from poll_anchor over all players
              until quiet >= 4
      }

      // The Mahjong holder (post-push) leads the first trick.
      leader := player_holding(Mahjong of special)

      // Climbing tricks until at most one player holds cards, or the first two
      // finishers are teammates (double victory ends the hand early). A Tichu
      // trick never ends early on a shed (`until false`) — the others must
      // still beat or pass; the DOG ends it via the engine's `ends_trick`.
      repeat until (number of players where hand[player] is not empty) <= 1 or tichu_double_victory() {
        // Small tichu before each trick (the poll cannot interleave with the
        // plays inside the climb round; see the header note).
        if tichu_window_open() {
          quiet := 0
          round offering [call_tichu, no_call] from leader over all players
                until quiet >= 4
        }
        round climb play_combination from leader
              over players where hand[player] is not empty
              source hand into trick_pile
              combinations tichu_lead_options follows tichu_follows
              until false
        if state.lead_ended_trick {
          // The Dog: no capture, the lead passes to the partner. The reference
          // records no shed on this path (its finishing order skips a player
          // who sheds by playing the Dog), so shed processing is skipped too.
          move all cards from trick_pile to discard
          leader := the player where player is not winner and team_of(player) is team_of(winner)
        } else {
          // Fold this trick's sheds (play order) into the finishing order.
          if state.shed_first is not none {
            if out_first is none { out_first := state.shed_first }
            else { if out_second is none { out_second := state.shed_first } }
          }
          if state.shed_second is not none {
            if out_first is none { out_first := state.shed_second }
            else { if out_second is none { out_second := state.shed_second } }
          }
          // A Dragon-won trick is given to an opponent of the winner's
          // choice. Both opponents bank into the same team pile, so the
          // choice moves no points — but the announced decision is public
          // history, exactly as at the table. Otherwise the winner's team
          // captures the pile.
          if tichu_dragon_won() {
            offer to winner one of [dragon_to_left, dragon_to_right]
            move all cards from trick_pile to captured[tichu_opponent_team(winner)]
          } else {
            move all cards from trick_pile to captured[team_of(winner)]
          }
          leader := winner
        }
        leader := tichu_next_holder(leader)
      }

      // --- Scoring: double victory is a flat +200 (no card points); otherwise
      // the lone remaining player's hand goes to the opponents and their
      // captured tricks to the first player out, then each team scores its
      // captured card points (100 in play every hand).
      if tichu_double_victory() {
        score[team_of(out_first)] += 200
      } else {
        if (any player where hand[player] is not empty) {
          let last = the player where hand[player] is not empty
          move all cards from hand[last] to captured[tichu_opponent_team(last)]
          move all cards from captured[team_of(last)] to captured[team_of(out_first)]
        }
        for each team t: score[t] += (sum of card_points(card) over cards in captured[t])
      }
      // Tichu / Grand Tichu settle against going out first.
      for each player p:
        if called[p] > 0 {
          if out_first is not none and p is out_first { score[team_of(p)] += called[p] }
          else { score[team_of(p)] -= called[p] }
        }
    }
  }

  winner: highest score
}

// === Call and Dragon vocabulary ===
//
// Game-defined move_types (the Skat/Doppelkopf shape). Guards read only the
// actor's public standing (their call flag and hand count); effects write
// only public state. `no_call` is unguarded, so a poll never offers an empty
// candidate set, and a forced decline emits the same public event as a
// chosen one.

move_type call_grand_tichu {
  when: called[actor] is 0
  effect { called[actor] := 200 }
}

move_type decline_grand {
  effect { }
}

move_type call_tichu {
  when: called[actor] is 0 and (not push_done or (number of cards in hand[actor]) is 14)
  effect {
    called[actor] := 100
    quiet := 0
  }
}

move_type no_call {
  effect { quiet += 1 }
}

// The Dragon's gift: which opponent physically takes the trick. Both bank
// into the same team pile, so neither move needs an effect — the announced
// choice is the whole content.
move_type dragon_to_left {
  effect { }
}

move_type dragon_to_right {
  effect { }
}

// The public small-tichu gate: someone may still call iff they have not
// called and have not played (pre-push: nobody has played; post-push: a
// full 14-card hand is exactly "unplayed", since only plays shrink it).
function tichu_window_open() =
  any player where called[player] is 0 and (not push_done or (number of cards in hand[player]) is 14)

// Double victory: both recorded finishers are teammates (ends the hand
// early; a flat +200 with no card points).
function tichu_double_victory() =
  out_first is not none and out_second is not none and team_of(out_first) is team_of(out_second)

// The team a player does not belong to (two-team game).
function tichu_opponent_team(p : Player) = if team_of(p) is 0 then 1 else 0
```
