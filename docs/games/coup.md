# Coup

Coup (Tchanturia, 2012), base game, 3–6 players. A bluff-and-challenge
game with a 15-card custom deck (five characters × three copies) and a
coin economy. Each player holds two face-down *influence* cards and a
visible pile of coins; on a turn the active player takes one action,
other players get windows to challenge or block it, and influence is
lost by flipping a card permanently face-up. Last player with influence
wins.

Out of scope: the two-player variant (different setup and starting
coins), and the Reformation / Rebellion / Anarchy expansions (extra
characters, factions, and team play). Negotiation between players is
allowed at the table but is never binding and carries no game state, so
it isn't modelled.

```
game Coup {

  players: 3..6
  direction: clockwise

  // One classifying dimension — the character — modelled as the rank,
  // with a singleton suit `court`. No suit comparison is ever made; a
  // card's identity for every rule is its character (its rank). The
  // five ranks, three copies each, give the 15-card deck.
  cards: {
    suits: { [court]: [Duke, Assassin, Captain, Ambassador, Contessa] }
    copies_per_card: 3
  }

  resources {
    coin : Resource
  }

  zones {
    court_deck        : Deck                    // face-down draw/return pile; count_only to all, shuffled
    influence[player] : Hand<player>            // face-down influence; identity to owner, count_only to others
    revealed[player]  : PlayerPile<player>      // lost influence, face-up; identity to all
    treasury          : Zone<Resource<coin>> { composition: count_only to all }   // the bank (starts with all 50 coins)
    coins[player]     : ChipStack<player>       // each player's coins; count public per stdlib
  }

  // No persistent game-level or per-hand state. A single game runs to a
  // sole survivor; everything that varies lives in zone contents. The
  // active player is driven by turn order, skipping eliminated players.

  // === Helpers (per-game functions) ===

  in_game(p)          = influence[p].non_empty
  has_character(p, c) = influence[p] contains a card where card.rank == c
  next_in_game_player(p) = next player clockwise from p with in_game(p)
    // analogous to Stud's next_active_player; skips the exiled.

  phase setup {
    shuffle court_deck                          // all 15 character cards begin here
    for each player p:
      deal 2 cards from court_deck to influence[p]   // identity to p, count_only to others
      transfer 2 coins from treasury to coins[p]
    // Starting player is the winner of the previous game; for a single
    // game the runtime supplies the opener.
  }

  // Turn order advances clockwise, skipping exiled players.
  phase play repeats until (count of p in players where in_game(p)) == 1 {
    let actor = current player        // the opener on the first turn, then next_in_game_player each iteration

    phase turn {
      active_rules: [ForcedCoupAtTenPlus,
                     CoupLegalIfAffordable,
                     AssassinateLegalIfAffordable]
      legal_moves:  [income, foreign_aid, coup, tax, assassinate, steal, exchange]

      offer action to actor:

        // --- General actions: no character claim ---

        income:
          transfer 1 coin from treasury to coins[actor]

        foreign_aid:
          // Not a character action, so it can't be challenged — but any
          // player may block it by claiming the Duke.
          instantiate BlockWindow (
            blockers            = players where in_game(p) and p != actor,
            blocking_characters = { Duke }
          ) produces:
            blocked:
              // foreign aid blocked: no coins this turn
            not_blocked:
              transfer 2 coins from treasury to coins[actor]

        coup:
          let target = actor chooses one player in (players where in_game(p) and p != actor)
          transfer 7 coins from coins[actor] to treasury         // always affordable here (rule gates < 7)
          lose_influence(target)                                 // a Coup cannot be challenged or blocked

        // --- Character actions: the claim can be challenged ---

        tax:
          instantiate ChallengeWindow (claimant = actor, claimed = Duke) produces:
            claim_stands:
              transfer 3 coins from treasury to coins[actor]
            claim_refuted:
              // actor lost influence in the window; the action fails

        assassinate:
          let target = actor chooses one player in (players where in_game(p) and p != actor)
          transfer 3 coins from coins[actor] to treasury         // fee paid up front
          instantiate ChallengeWindow (claimant = actor, claimed = Assassin) produces:
            claim_refuted:
              transfer 3 coins from treasury to coins[actor]     // action challenged out: fee returned
            claim_stands:
              instantiate BlockWindow (
                blockers            = [target],
                blocking_characters = { Contessa }
              ) produces:
                blocked:
                  // assassination blocked by Contessa: fee stays spent, no influence lost
                not_blocked:
                  lose_influence(target)

        steal:
          let target = actor chooses one player in (players where in_game(p) and p != actor)
          instantiate ChallengeWindow (claimant = actor, claimed = Captain) produces:
            claim_refuted:
              // action fails
            claim_stands:
              instantiate BlockWindow (
                blockers            = [target],
                blocking_characters = { Captain, Ambassador }
              ) produces:
                blocked:
                  // steal blocked by Captain or Ambassador: no coins move
                not_blocked:
                  let amount = min(2, coins[target].amount_of(coin))   // take 2, or 1 if that's all they have
                  transfer amount coins from coins[target] to coins[actor]

        exchange:
          instantiate ChallengeWindow (claimant = actor, claimed = Ambassador) produces:
            claim_refuted:
              // action fails
            claim_stands:
              deal 2 cards from court_deck to influence[actor]   // drawn privately: identity to actor only
              let returned = actor chooses 2 cards in influence[actor]   // keep any, return two to restore the original count
              transfer returned from influence[actor] to court_deck
              shuffle court_deck                                 // returned cards reabsorbed anonymously
    }
  }

  winner: the sole player with in_game(p).
}

// === Operations ===

// Losing an influence: the player chooses which of their own face-down
// cards to flip permanently face-up. Reaching zero influence exiles the
// player — the `play` loop's termination predicate observes it the
// moment influence[p] empties (continuous evaluation; see decisions.md
// "Loop termination semantics") — and their coins return to the bank.
operation lose_influence(p) {
  if not in_game(p): return                     // already exiled: nothing to lose (e.g. double-hit)
  let card = p chooses one card in influence[p]
  reveal(card, observers = all)                 // the lost influence becomes common knowledge
  transfer card from influence[p] to revealed[p]
  if influence[p].empty:
    transfer all coins from coins[p] to treasury
}

// === Mechanics ===

// A challenge window. The claimant has asserted they hold `claimed`.
// Each other in-game player, in clockwise priority from the claimant's
// left, is offered the chance to challenge; the first to do so becomes
// the challenger and the claim is adjudicated. (Real play is a
// simultaneous "anyone may challenge"; offering in priority order is the
// standard deterministic resolution — the first challenge is the only
// one that can bind.) The outcome is common knowledge to all observers;
// the only private residue is the replacement card, carried by the deal.
mechanic ChallengeWindow (
  claimant : Player
  claimed  : Character            // i.e. a rank
) → outcome { claim_stands | claim_refuted } {
  legal_moves: [challenge, pass]

  for each c in (players where in_game(p) and p != claimant), in turn order from claimant.left:
    offer action to c:
      challenge:
        if has_character(claimant, claimed):
          // Claim proven. The challenger loses an influence; the claimant
          // proves the card, returns it, and draws a fresh replacement so
          // the proof costs no information going forward.
          let proof = the card in influence[claimant] where card.rank == claimed
          reveal(proof, observers = all)
          transfer proof from influence[claimant] to court_deck
          shuffle court_deck
          deal 1 card from court_deck to influence[claimant]    // replacement: identity to claimant only
          lose_influence(c)
          produce claim_stands
        else:
          // Bluff caught.
          lose_influence(claimant)
          produce claim_refuted
      pass:
        continue                  // this player declines; offer the next
  produce claim_stands            // nobody challenged
}

// A counteraction (block) window. One of `blockers` may claim one of
// `blocking_characters` to block the action in progress. A declared
// block is itself a character claim, so it opens a nested
// ChallengeWindow (anyone in-game may challenge the blocker). The first
// block attempt resolves the window: if its claim survives challenge (or
// goes unchallenged) the action is blocked; if the block is refuted the
// action proceeds.
mechanic BlockWindow (
  blockers            : List<Player>
  blocking_characters : Set<Character>
) → outcome { blocked | not_blocked } {
  legal_moves: [block, pass]

  for each b in blockers where in_game(b), in turn order:    // a blocker exiled by an earlier window can't act
    offer action to b:
      block:
        let claimed = b chooses one character in blocking_characters
        instantiate ChallengeWindow (claimant = b, claimed = claimed) produces:
          claim_stands:  produce blocked         // block holds (challenger, if any, lost influence)
          claim_refuted: produce not_blocked     // block was a bluff and failed; action proceeds
      pass:
        continue
  produce not_blocked             // nobody blocked
}

// === Rules ===

// At 10+ coins the only legal action is Coup: every other action is
// gated off. (Coup is itself always affordable at 10+, so the action set
// never empties.)
rule ForcedCoupAtTenPlus {
  constrains: income, foreign_aid, tax, assassinate, steal, exchange
  applies_when: coins[active_player].amount_of(coin) < 10
}

// Affordability gates. A Coup costs 7, an Assassinate costs 3; the action
// isn't offered unless the actor can pay.
rule CoupLegalIfAffordable {
  constrains: coup
  applies_when: coins[active_player].amount_of(coin) >= 7
}

rule AssassinateLegalIfAffordable {
  constrains: assassinate
  applies_when: coins[active_player].amount_of(coin) >= 3
}

// `income`, `foreign_aid`, `tax`, `steal`, `exchange` carry no cost and
// no extra precondition beyond ForcedCoupAtTenPlus, so they need no rule
// of their own.

// === Types ===

// Character is the deck's rank enumeration — the five court roles.
type Character = Duke | Assassin | Captain | Ambassador | Contessa

// === Notes ===

// Coins as fungible tokens. Coins are a Resource; every gain, payment,
// and refund is a `transfer` of a `count type` amount (`1 coin`,
// `2 coins`, `7 coins`, `amount coins`, `all coins`) between count-only
// zones. See decisions.md "Resource amount syntax". Two distinct failure
// shapes appear and are both handled at the game level (no partial-
// fulfillment primitive — see decisions.md "Resource transfer failure"):
//   - Fees (Coup 7, Assassinate 3) cannot underflow: the affordability
//     rules gate the action, so the fee transfer always succeeds.
//   - Steal is a genuine partial take: `min(2, coins[target])` is written
//     explicitly, exactly as Stud writes all-in calls with `min`.

// The challenge-defense memory event is a composition of stdlib
// operations, not a custom event: `reveal` (prove the card to all) →
// `transfer` to court_deck → `shuffle` (anonymise it back into the deck)
// → `deal` a replacement (private to the claimant). Under perfect recall
// observers remember the claimant *held* that character at that instant,
// but the reshuffle plus the deck's count_only projection means the
// returned card and the new one are unknown going forward. No `forget`
// is used, so the game stays perfect-recall.

// Challenge and block windows are decision phases with typed outcomes,
// dispatched with `produces:` — not `simultaneously:` blocks. "Any player
// may challenge" sounds simultaneous, but the step that matters is a
// conditional commit ("challenge, or not") with a branching result, which
// belongs to the phase/typed-outcome machinery, not the atomic-effect
// block. See decisions.md "Simultaneous moves and atomic effect".

// The "double danger" of assassination falls out for free: a target who
// challenges the Assassin and loses takes one hit in the ChallengeWindow,
// then — having not blocked — a second from `lose_influence(target)`; a
// target who bluffs a Contessa block and is challenged out loses one hit
// in the block's nested ChallengeWindow and a second when the
// assassination resolves not_blocked.
```
