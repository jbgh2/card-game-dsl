# Cheat

The companion formal file is [cheat.cardlang](cheat.cardlang); this is the
readable twin. Cheat — also known as I Doubt It, Bullshit, or Bluff — is a
shedding game where every play is a possible lie: cards go down **face
down**, called out as a rank the player may or may not actually be holding,
and the only way to find out is to accuse them. This corpus entry fixes the
**basic game** described on Pagat, at **four players** on a standard 52-card
deck, with a play capped at **four cards**. Source:
[Pagat](https://www.pagat.com/beating/cheat.html).

Setup and play:

- **Deal.** Shuffle and deal the whole deck out — 13 cards to each of the
  four hands. There is no stock; every card is in someone's hand.
- **The claim cycle.** Plays are called as ranks in a fixed ascending cycle
  that belongs to the table, not to any player: the first play is called
  "Aces", the second "Twos", the third "Threes", … then Jacks, Queens,
  Kings, and back to Aces. The cycle advances by exactly one step per play
  and never resets — a challenge does not restart it.
- **A turn.** Play goes clockwise from seat 0. On your turn you discard
  **one to four cards face down** onto the pile and call them as the
  cycle's current rank — "two Sevens". The count you announce is the count
  you played (miscounting is not part of this variant); the *ranks* are
  your own business. You do not need to hold the called rank at all: with
  the wrong hand at the wrong point of the cycle, lying is not just
  allowed, it is forced.
- **The challenge window.** After each play, every other player — clockwise
  from the player's left — may call "Cheat!" or let it go; the first call
  closes the window. (Pagat's rule is a real-time race — whoever calls
  first; serializing it into a clockwise window is this corpus's standard
  faithful rendering of such races, the same one Coup uses. Seat order
  decides first refusal on a catch; nothing else changes.)
  - **A call.** The played cards — just this play, not the pile beneath —
    are turned **face up** for the whole table. If **every** one is the
    called rank, the claim was honest: the embarrassed challenger picks up
    those cards *and the entire pile* into their hand. If **any** card is
    not the called rank, the liar is caught and picks it all up instead.
  - **No call.** The cards join the pile face down, unseen, and stay
    unseen — a lie that draws no call is never found out.
- **After a play.** Challenged or not, the cycle advances one rank and the
  turn passes to the next player clockwise.
- **Winning.** The first player to empty their hand *and survive the
  challenge window on that final play* wins immediately. A caught lie on
  the final play refills the liar's hand from the pile; a final play that
  is called honestly, or not called at all, ends the game on the spot.

The turn structure runs on the kernel's `turns` form (decisions.md "The
`turns` form"): the form owns rotation, and each turn is one `offer` over
the four count announces `play_one` … `play_four` — the announce is the
public claim of *count*, the `move chosen` inside it is the hidden card
decision, and the claimed *rank* is not a decision at all, because the cycle
forces it: it is the public `claim_rank` state everyone already reads. The
whole adjudication — window, flip, verdict, pickup, cycle step — is one
named procedure run from every play's effect, Coup's challenge-window shape
with an **open** claim vocabulary (all 13 ranks, where Coup's is five
characters). `play_one` is unguarded, so the turn-holder always has a legal
move: an empty hand ends the game before its owner is ever offered a turn.

Zones and visibility: `hand[player]` is a private `Hand<player>` — owner
sees all, others see a count. `played` (this play's face-down cards) and
`pile` (the accumulated unchallenged discards) are `FaceDownPile`s — bare
counts to everyone, *including* the player who played them, whose knowledge
of what they really played comes from their own choice events, not from the
zone. `flipped` is a `Discard` — identity to all — and is empty except for
the instant a challenge exposes a play: routing the played cards through it
IS the reveal, exactly what a reveal builtin would do under the projection
model. The claim itself — `claim_rank`, `claim_count`, `claimant`, and the
window state — is ordinary public state: decisions.md's modeling rule ("a
public assertion is a state variable *because* it is public, while the
concealed truth it may misrepresent sits in a face-down zone") in its purest
corpus form. Every field of that claim belongs to ONE play and is cleared
where the play resolves, so a seat asked to announce reads no claimant, no
count and no verdict: the settled play's record is in each observer's event
log, which is where a fact about the past belongs. `claim_rank` alone belongs
to the table rather than to a play, and steps once per play.

**The information-set point.** Cheat is the corpus's **compound
hidden-function probe** for
[structural-infoset-proofs](../open-questions/structural-infoset-proofs.md):
the challenge verdict is a public Boolean function of hidden content — *do
all the face-down cards match the public claim?* — followed by a reveal of
exactly the cards the function read. Everything an observer knows falls out
of the declared projections and the emitted events, with no per-game
observation rule anywhere: before any call, a bystander's information state
is provably identical whether the play was honest or a lie (the proof
module pins this — the call/allow decision is made under genuine
uncertainty); the instant the flip fires, every player's information state
gains the flipped identities and the verdict's public routing (whose hand
ate the pile); and a play nobody calls leaks nothing, ever. A pile pickup
lands in the loser's `Hand`, so the loser learns exactly what they
collected (owner-identity projection) while everyone else sees the count —
which is why a player who has eaten the pile can bluff *better* afterwards,
and why their opponents' models of the pile differ from each other's. This
line-dependence — whether a hidden card may vary depends on whether it was
played, flipped, or picked up, not on any fixed attribute — is what defeats
the readiness harness's per-card swap axes, and Cheat therefore anchors the
**constructive world generator** (`tests/openspiel_ready/worlds.py`): the
proof derives the pinned cards from the line itself and permutes the entire
remaining hidden set, certifying indistinguishability by construction for
every observer.

```
game Cheat {

  players: 4
  direction: clockwise
  // Measured over seeded random playouts (tests/test_playout_cheat.py):
  // 200 seeds: p50 849, p95 2454, max 3942 decisions.
  max_length: 20000

  cards: standard52
  // Cheat never compares rank strength; the convention only fixes the Rank
  // enumeration order. Aces low matches the claim cycle's A -> K reading.
  ranking: aces low

  zones {
    deck         : Deck             // used once, for the deal
    hand[player] : Hand<player>     // private hands: identity to owner, count to others
    played       : FaceDownPile     // this play's face-down cards, pre-adjudication
    pile         : FaceDownPile     // the accumulated, unchallenged, never-revealed discards
    flipped      : Discard          // challenge exposure: identity to all, empty between challenges
  }

  state {
    // `claim_rank` belongs to the TABLE: it is the cycle's position, so it
    // names what a standing play is called as while one stands and what the
    // next play must call between plays. Every other field below belongs to
    // one PLAY, and holds its idle value whenever no play stands — the
    // announce sets them, `resolve_play` clears them, and a seat asked for
    // its turn therefore reads nothing about the play that just resolved.
    claim_rank  : Rank?   = none    // the cycle's position; the table's, not a play's
    claim_count : Integer = 0       // cards the standing play claims (0: none stands)
    claimant    : Player? = none    // whose play stands, announce to resolution
    challenged  : Boolean = false   // did anyone call "Cheat!" on it?
    challenger  : Player? = none    // who called
    responder   : Player? = none    // the open window's rotation cursor
    window_open : Boolean = false
    won[player] : Boolean = false   // set for the survivor of the winning play
  }

  phase play {
    shuffle deck
    deal 13 cards from deck to each hand
    claim_rank := A                  // the first player must call Aces

    turns t from 0 over all players
          until any player where won[player] {
      offer to t one of [play_one, play_two, play_three, play_four]
    }
  }

  winner: highest won
}

move_type play_one {
  effect {
    claimant := actor
    claim_count := 1
    move chosen one card from hand[actor] to played
    run resolve_play(actor)
  }
}

move_type play_two {
  when: (number of cards in hand[actor]) >= 2
  effect {
    claimant := actor
    claim_count := 2
    move chosen 2 cards from hand[actor] to played
    run resolve_play(actor)
  }
}

move_type play_three {
  when: (number of cards in hand[actor]) >= 3
  effect {
    claimant := actor
    claim_count := 3
    move chosen 3 cards from hand[actor] to played
    run resolve_play(actor)
  }
}

move_type play_four {
  when: (number of cards in hand[actor]) >= 4
  effect {
    claimant := actor
    claim_count := 4
    move chosen 4 cards from hand[actor] to played
    run resolve_play(actor)
  }
}

move_type call_cheat {
  effect {
    challenged := true
    challenger := actor
  }
}

move_type allow {
  effect {
  }
}

// The whole adjudication, run from every play_N effect: the clockwise
// window (first call closes it), then flip-judge-collect or a quiet merge,
// the shed-out check, and the cycle step.
procedure resolve_play(who : Player) {
  challenged := false
  window_open := true
  responder := who
  repeat until not window_open {
    responder := responder offset_by left
    if responder is who { window_open := false }
    if window_open {
      offer to responder one of [call_cheat, allow]
      if challenged { window_open := false }
    }
  }
  if challenged {
    move all cards from played to flipped
    if all cards in flipped where card.rank is claim_rank {
      move all cards from flipped to hand[challenger]
      move all cards from pile to hand[challenger]
    } else {
      move all cards from flipped to hand[who]
      move all cards from pile to hand[who]
    }
  } else {
    move all cards from played to pile
  }
  if hand[who] is empty { won[who] := true }
  claim_rank := next_rank(claim_rank)
  // The play stops standing here, so its fields stop describing anything.
  claimant := none
  claim_count := 0
  challenged := false
  challenger := none
  responder := none
}

// The fixed claim cycle: A, 2, ... 10, J, Q, K, back to A.
function next_rank(r : Rank?) =
  if r is A then "2"
  elif r is "2" then "3"
  elif r is "3" then "4"
  elif r is "4" then "5"
  elif r is "5" then "6"
  elif r is "6" then "7"
  elif r is "7" then "8"
  elif r is "8" then "9"
  elif r is "9" then "10"
  elif r is "10" then J
  elif r is J then Q
  elif r is Q then K
  else A
```
