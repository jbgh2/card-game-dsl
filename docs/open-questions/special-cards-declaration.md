# Special cards declaration (residual: contextual rank)

**Tier 4 — low impact, defer until forced.**

The declaration-mechanism half of this question was answered when the
card model adopted the per-suit form with `specials:` for non-(suit,
rank) singletons (see decisions.md "Deck declaration"). Tichu's deck
now reads `standard52 + { specials: [Mahjong, Dog, Phoenix, Dragon] }`
— the singletons sit alongside the standard grid via the same
composition syntax. French Tarot's Excuse uses the same mechanism.

What remains open is the *contextual-rank* problem for Phoenix.
Phoenix's rank when played as a single card is *half a rank above
the last play* — 1.5 if led, 8.5 when played over an 8. The rank
isn't intrinsic to the card; it's resolved at play time against
trick context. The provisional encoding `PhoenixRank(base_rank: Rank?)`
captures this but is awkward (it carries the surrounding context
inside the card identity).

Possible cleaner shapes:

- **Per-play `computed_rank` callback** on the move type — when the
  move plays Phoenix as a single, the move's computed rank is
  `state.trick.last_play.rank + 0.5`. The card's intrinsic rank
  becomes irrelevant for comparison; the move carries its own
  rank.

- **Stdlib `JumpUp` rank operator** — a unary modifier that adds
  half a rank to whatever the base is. Phoenix's `effective_rank`
  in single play is `JumpUp(state.trick.last_play.rank)`.

- **Inline case in `MustBeatPreviousCombination`** — handle
  Phoenix as a special case in the rule itself; the card's rank
  stays nominal. Most explicit but couples the trick rule to a
  card identity.

**Tier 4 because** Tichu is currently the only game with contextual-
rank cards. A second game with the same shape (Munchkin's "level"
modifications, certain Tarot variants) would help pin down which
encoding generalizes.
