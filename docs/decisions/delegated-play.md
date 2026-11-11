## Delegated play

A move is normally chosen by the player it's attributed to: the
active player picks from their own hand, submits a bid on their own
behalf. Some games separate these — a move comes from one player's
zone, attribution stays with that player, but the *choice* is made
by a different player.

The canonical case is Bridge's dummy. Once revealed, dummy's cards
play from `dummy_hand[dummy]` (the move belongs to dummy, the
information-state attributes the play to dummy), but declarer is
the one who picks which card. Defenders play their own cards
normally.

The language handles this with per-game helper functions, not new
zone-level or move-level constructs:

```text
play_source_for(actor) =                // which zone the move comes from
  if actor is declarer.partner and dummy_revealed:
    dummy_hand[actor]
  else:
    private_hand[actor]

chooser_for(actor) =                    // who decides what move it is
  if actor is declarer.partner and dummy_revealed:
    declarer
  else:
    actor
```

The mechanism: the kernel round loop consults an optional `chooser_for`
helper that defaults to the identity function (the actor chooses for
themselves), and a parallel `play_source_for` helper routes the actor's
move-source zone. Both live as ordinary per-game functions; the seat a
helper yields is the [[decider]] — the `chose` observation and the
OpenSpiel decision node are the Decider's, while the trace, the movement,
the Arrival Record, and the trick stay the actor's: the record never
stores the Decider, whose provenance no observer's stream entails ("The
Arrival Record").
The trick form is the routed form; the other decision points refuse the
helpers by name rather than ignore them (`runtime/delegation.py` classifies
every chooser call site, and issue #458 records what lifting a refusal
takes). Three Owner Guards ride the helpers: at resolve, a helper takes
exactly one Player, and a game defining helpers must hold a trick round
for them to reach; at the draw, a delegated decision's pool must project
full identity to its Decider — legal actions must be a function of the
Decider's own information state, and whether a seat's pool is delegated
depends on both helpers' values at that seat, which is not statically
decidable over two opaque expression bodies. A routing condition read
from a hidden zone is issue #458's recorded deferral.

The default — actor is chooser, hand is source — is implicit.
Games without delegated play declare neither helper and the
defaults apply.

**A rule reads the routed pool.** Every rule is asked at the trick round's
card decision, the one decision the helpers route, so a rule clause's bare
`hand` — the Play Source ("Rule demand forms") — is the zone
`play_source_for` yields, and so is the round's `source` family named bare
in a clause. Bridge's `MustFollowSuit` therefore binds declarer to dummy's
exposed cards on dummy's turn, not to dummy's emptied hand. A function the
clauses call sees no Play Source, and reading one there is refused.

**Why per-game helpers, not a zone-level construct.** A
`choices_made_by:` declaration on the zone type was considered.
The case against: delegated play is a niche pattern (Bridge dummy
and its near-variants — Honeymoon Bridge, Solo Whist with a
dummy). Lifting it to the zone type would add language surface
that every reader has to understand for a feature most games
never use. Per-game helpers stay local to the game that needs
them and integrate with the existing convention for routing
helpers (Bridge already had `play_source_for` before this
resolution; `chooser_for` is the symmetric counterpart).

Apparent second data points like Sheepshead's partner-by-card and
Doppelkopf's Re/Kontra announcements turn out *not* to be
actor-vs-chooser cases on close reading — they are
hidden-information / team-formation patterns where each player
still chooses their own moves. The Bridge family is the only
known case of true delegated play in the standard-deck corpus.
