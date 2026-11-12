## The climbing form of `round`

Combination-climbing games (Big Two, President, Tichu) run on a third
configuration of the kernel `round`. A climbing trick plays like a trick, but each
play is a *combination* (a set of cards laid down together), not a single card:

```text
round climb <move_type> from <leader> over <participants>
      source <zone> into <zone>
      combinations <catalogue> follows <function>
      until <predicate>
      [before asking <binder> { <statement>* }]
```

The two slots name the round's engine: the game's own Combination Catalogue
and follows function ("Combination Catalogues"), or a registered engine's
lead and follows queries. The leader leads a play the engine admits; each
participant in turn beats the standing play with one the engine admits over it
or passes — a pass does **not** drop a player. The
trick ends when action returns to the last player who played (everyone else passed
one full lap), when `until` holds (a player has shed out — Big Two; the third
player out or a completed double victory — Tichu, whose `until` reads the
round's own `state.shed_first` / `state.shed_second` beside the game's
finishing order), or the instant the lead itself is a trick-ending play:
the engine may mark a play `ends_trick` (Tichu's Dog), and the form then closes
the trick with **zero follower draws**. The last player to play is
the `outcome`; the surrounding body routes the pile and the next lead, exactly as
for a trick.

A play the engine returns conforms to a declared protocol
(`primitives.ClimbPlay`), and three of its members open the form's two
further regimes beside the ring, never two at one step:

- **The Play Announcement.** A play whose `announce` names tokens is
  followed by exactly one further decision of the same seat over those
  tokens before the ring advances; the token is announced publicly and
  recorded beside every play in the trick's own event record, which a
  game-local query reads through `EngineFacts.round_state` to enforce a
  rule that spans plays. A play the standing rule compels is marked
  `compelled` by the query, and a candidate list holding one offers the
  compelled plays alone and no pass — the query marks, the form narrows.
  Tichu's Mahjong wish is the witness; the tokens are the engine's,
  docked by `primitives.climb_announcements`. A pending announcement is
  void once the round has terminated, since the hand is over.
- **The Interrupt Window.** For an engine whose registry row declares a
  decline token (`primitives.climb_interrupt_decline`): after every
  ordinary turn — a play but a trick-ending one, or a pass — every
  participant still holding cards is asked in turn order from the seat
  after the one who acted round to that seat itself, asked last, offered
  its `interrupt` plays that beat the standing play beside the decline —
  so a seat with nothing to play submits the same public decline a seat
  declining by choice does, and who is asked is a function of public
  state alone. The window after the pass that returns the ring to the
  last player is the trick's last. A taken interrupt stands, the ring
  resumes after the interrupter, and the window reopens; a compulsion
  binds on turn only. Tichu's bombs out of turn are the witness; Big Two
  and President declare no decline and open no window. This is the
  off-the-clock idiom ("Off-the-clock windows") applied inside a form,
  where a poll cannot sit; the surface options once sketched for it — a
  move-type property, a permitting rule, a phase-level list — are all
  refused by the same law that decided the poll: a permission that varies
  by seat and moment is a decision the kernel asks, never a rule that
  widens a legal set.

Every ask the three regimes make is one of a closed set of kinds — the
ring's lead and follow, the window's ask after an ordinary turn, and the
Play Announcement (`mechanics.CLIMB_ASK_KINDS`). The optional trailing
clause is the round's **Hosted Poll**: a body of the game's own
statements that the shared decision loop runs before every ask of the
first three kinds, its
binder bound to the seat about to be asked, so a game can poll its own
off-the-clock moves between the form's asks — Tichu's small tichu call,
open to a seat until it first plays. What the body may hold, and why the
round rather than the form runs it, is in "Off-the-clock windows".

Rejected for both: folding the announcement into the play (one action per
play-and-token pair multiplies the action space by the token count and still
needs the announce, since a play's movement carries its cards and nothing
else); asking only the seats that hold an interrupting play (who is asked
becomes a function of hidden holdings — the swap proof's "same seat asked"
fails on the first pair that differs in a bomb).

**The named leader need not be a participant.** `from` and `over` are
independent expressions, so in a game where going out does not end the hand
(President, Tichu) the trick winner can shed their last card on the winning
play and still be named as the next leader. That is a normal state: the ring
starts at the first participant at or after them in turn order, exactly as the
trick, auction, and `turns` forms treat the same clause pair. A game therefore
writes the natural `leader := winner` and needs no hand-authored "skip to the
next player still holding cards" fallback. Only an **empty** `over` set is an
error — there is then no one to lead and no one to follow. Like the trick form, the climbing form exposes its terminal state to
the body (`mech_state` → `last_round_state`, read as `state.x`):
`state.lead_ended_trick`, and `state.shed_first` / `state.shed_second` — the
first two players who played their last cards this trick, in play order, from
which a finishing-order game (Tichu: double victory, first-out routing, call
payouts) folds its global out-order without any extra chooser draw.

Two decisions distinguish it from the trick form and the `turns` ring:

- **The engine is a declaration the round names, and the form moves the cards.**
  A combination play moves a *specific set of cards* — the cards of the chosen
  combination — and the transfer vocabulary moves cards *by count* (`all` / `one`
  / `N cards`), never a named set. So a combination play is not a DSL `move_type`
  effect the way a bet is: the round names its engine, and the climb form performs
  the card transfer itself. A game declares its plays in a Combination Catalogue
  and says which follow in a follows function ("Combination Catalogues"); a game
  whose plays no catalogue declares yet names a **registered engine**, two
  game-local Primitive queries (`combinations`, the lead options; `follows`, the
  legal follows), Tichu's (issue #989). Resolve stamps which on the round
  (`ClimbRound.engine`). The construct depends only on the engine's interface: a
  sequence of plays conforming to `primitives.ClimbPlay` — the cards a play
  moves, and the behaviours the form acts on (`ends_trick`, `wild`, `compelled`,
  `announce`, `interrupt`), each answered by its default in an engine that has
  none of them, as a Declared Engine's plays do.

- **The winner is the loop's last player, not an outcome function.** Unlike the
  trick form, which selects the winner from the played cards, the climbing winner is
  whoever played the standing combination when everyone else passed — returned
  directly. There is no `outcome` callback.

As with a `turns` ring, the round's only decision points are the per-turn
candidate draws (the lead query, then `[follows…, pass]`); the scoring and routing
in the surrounding body consume no randomness — where a game's *rules* are random
(Tichu's Dragon trick going to a random opponent, its random-rate call gates at
the migrated scope), that randomness is a game-local Primitive drawing on
the shared `rng`, not a chooser decision. So a climbing hand re-expressed on
this form reproduces a hand-written engine's behaviour byte-for-byte when it
presents the same per-turn candidate lists — the property the climbing games
([games/big-two.cardlang](../games/big-two.cardlang),
[games/president.cardlang](../games/president.cardlang),
[games/tichu.cardlang](../games/tichu.cardlang)) are verified against
([kernel-migration.md](../kernel-migration.md), Workstream 3).

For the OpenSpiel action space, a climb play's id comes from the engine's play
universe — a Combination Catalogue's, numbered from its rows and golden-pinned
(Big Two, President), or a registered engine's, **computed by an arithmetic
codec** (pure play-identity ↔ index functions over a fixed per-kind block
layout) where enumeration is infeasible (Tichu, whose codec's `size` states the
universe — Phoenix straights under free suit assignment dominate). A play's
identity is its card multiset plus the rank value a wildcard among those cards
stands for: a card-set holding a wildcard can be
two plays (Tichu's {Phoenix,3,4,5,6} is 2-6 or 3-7), and the climb form
announces the value publicly so every follower's legal set derives from what
it has seen. Either way the id is a stable function of that identity, which
is what determinized replay needs; the codec route is the designed answer
for any future engine whose combination space explodes
([kernel-migration.md](../kernel-migration.md), Workstream 3). A catalogue's
plays are numbered by card count and then by their sorted card ids, so an id
is a function of the cards alone and no shape's label takes part; a Declared
Engine offers its candidates in that order (`primitives.action_order`), so a
per-turn candidate list is a function of the plays it holds and never of how
they were generated.
