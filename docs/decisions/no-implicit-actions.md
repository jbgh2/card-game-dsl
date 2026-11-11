## No implicit actions

Every decision point has at least one legal move, and the engine neither invents
one nor silently skips the decision. Where a player would have nothing legal to
do, that is a **malformed game** — reported as an error, not absorbed. This keeps
the action space honest (the OpenSpiel finite-enumerable invariant) and makes a
missing rule, an unguarded choice, or a too-wide participant set *loud* instead of
hidden. The fix is always something the game states explicitly; the reusable forms
live in the standard library so a game opts into a behaviour by name:

- **An `offer` (or any ring of decisions) with no legal move** → add an
  always-legal move to the vocabulary (an unguarded `pass`/`decline`), or guard the
  decision (`if <able> { offer … }`). For a ring that shrinks as players drop out,
  narrow the participants clause (`over <players> where <still-in>`) so a player
  with nothing to do is never offered a turn.
- **A rule that can filter every candidate** → declare its `if_impossible`:
  `error(...)` to reject the move, or an explicit fallback card-set. A trick play
  with no legal card (a rule emptied the set with no fallback, or the hand is
  exhausted) is an error, not an implicit pass.
- **A `choose` over an empty domain** (e.g. an inverted range) → an error; a choice
  must offer at least one candidate.
- **The acting player is never defaulted.** A choice or chosen transfer made with
  no acting player is an error ("who is choosing?"), not a silent attribution to
  player 0 — wrap it in a per-player context (`as <player>` for one named decider,
  `for each player p` or the simultaneous pass for everyone) so the chooser knows
  who decides. The checker refuses it, and a read of `actor`, wherever no
  player is acting: a phase's own statements, its `before_each`/`after_each`,
  a phase's `when` or `repeat until`, `loser:`, a state default, and a trick
  round's mode triggers and Delegated Play helpers where the round stands
  outside any per-player context — a function or procedure reached from one
  included. A chosen deal `to each` is decided by each receiver and needs no
  acting player. A gate or `loser:` cannot hold a per-player context, so the
  fix there is to decide during play, before the gate is read, into a state
  variable and read it.
