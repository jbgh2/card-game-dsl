# Appendix

Background research synthesis and corpus state catalogue. Both are stable
references rather than living spec material.

## Background research findings (high-level)

Two extended surveys were conducted earlier in the design process. Verbatim
text is preserved under [research/](research/); summaries follow.

### Game description languages for card games

Surveyed: GDL, GDL-II, Regular Boardgames, Ludii, Zillions, CardStock,
OpenSpiel, RLCard, PokerKit, Forge, CARDSTOCK.

Key conclusion: no off-the-shelf DSL cleanly covers the 52-card family.
Ludii's ludemic class-grammar is the closest architectural inspiration;
GDL-II's `sees`/`random` is the cleanest formal model for hidden information;
OpenSpiel is the de facto AI substrate. There's a real gap to fill.

Pinochle-relevant: most existing systems require AI authors to write
per-game code. A DSL that auto-derives information sets from zone visibility
is the prize.

See [research/game-description-languages.md](research/game-description-languages.md)
for the full survey.

### Composition and interaction of behavioral units

Surveyed: AOP, algebraic effects, FOP/SPL, traits, multimethods, object
algebras, ECS, hooks, language workbenches, FRP, process calculi, plus the
game-studies side (MDA, Björk & Holopainen, Machinations, Ludii, VGDL,
PuzzleScript, Juul's emergence/progression).

Key conclusion: PL has mature mechanisms but rarely makes "interaction"
first-class. Game studies has rich vocabulary for interactions but few
operational frameworks. CLOS method combinations and algebraic effect
handlers are the PL constructs closest to "interactions as first-class
units." We're effectively designing in this gap.

The implication for our design: composition by intersection (rule
composition), explicit named interactions (move types as named patterns),
and event-driven sub-phase transitions all live in this gap and are why this
project is worth doing.

See [research/composing-behavioral-units.md](research/composing-behavioral-units.md)
for the full survey.

## Corpus state catalogue

A reference catalogue of every state variable across the first five
games at the time the state-and-mutation question was settled. The
catalogue is documented here because it is concrete evidence for the
state-scoping and mutation decisions in [decisions.md](decisions.md) —
readers verifying those design choices against real game requirements
can cross-check against this table.

"Lifetime" is the phase instance whose entry/exit boundary the
variable resets at, derived from how it is used.

| Variable | Game(s) | Lifetime | Mutability | Source of mutation | Notes |
|---|---|---|---|---|---|
| `led_suit` | All 5 | per-trick | replaced | move event (first play sets it) | Derivable from `trick_pile[0].suit`. Lives inside the Trick mechanic. |
| `pass_direction` | Hearts | per-hand | rotated | setup phase | Cycles through `[left, right, across, none]`. |
| `cumulative_score[player]` | Hearts | game-level | accumulating | scoring phase | One of two game-level accumulators in Hearts. |
| `trick_terminated_early` | Getaway | per-trick | replaced (default false) | move event (tochoo play) | Read post-trick by `GetawayRouting` to choose waste vs hand. |
| `eliminated[player]` | Getaway | game-level | set-once (per player) | post-trick check | Derivable from `hand[player].is_empty`. Monotonic. |
| `bid[player]` | Spades, Pinochle (via auction outcome) | per-hand | set-once (per player) | bidding phase | Once set, read-only for the rest of the hand. |
| `tricks_won[team]` | Spades | per-hand | accumulating | post-trick | Derivable from `captured[team].size / participants`. |
| `tricks_won[player]` | Spades | per-hand | accumulating | post-trick | Needed for Nil scoring. Not derivable from zones (captured is per-team). |
| `bags[team]` | Spades | game-level | accumulating (with modulus reset) | scoring phase | `bags >= 10 → score -= 100; bags -= 10`. Unusual reset. |
| `score[team]` | Spades, Pinochle | game-level | accumulating | scoring phase | Plain accumulator. |
| `trump` | Pinochle | per-hand | set-once | `declare_trump` phase outcome | One per hand. Not derivable. |
| `current_bid` | Pinochle | per-hand | replaced (monotonic during auction, frozen after) | Auction mechanic | Reset by setup, set during auction, read-only thereafter. |
| `high_bidder` | Pinochle | per-hand | set-once | Auction mechanic outcome | Set when auction ends; read by scoring. |
| `passed[player]` | Pinochle | **per-auction** | set-once per player (false → true) | auction in-progress | Lives inside the Auction mechanic. |
| `meld_score[team]` | Pinochle | per-hand | accumulating (within melding) then frozen | MeldingPhase mechanic | Reset at setup, frozen after melding. |
| `trick_score[team]` | Pinochle | per-hand | accumulating (within scoring) | scoring phase | Reset at setup, computed in scoring. |
| `contract` | Bridge | per-hand | set-once | `bidding` phase outcome | Destructured from `contract_made(c, d)`. |
| `declarer` | Bridge | per-hand | set-once | `bidding` phase outcome | Set with `contract`. |
| `dummy` | Bridge | per-hand | set-once | `bidding` phase outcome (derived from declarer) | Always `declarer.partner`. Genuinely derivable; stored for read convenience. |
| `tricks_taken[partnership]` | Bridge | per-hand | accumulating | post-trick | Derivable from `captured[partnership].size / 4`. |
| `dummy_revealed` | Bridge | per-hand | set-once (false → true) | `reveal_dummy` phase | Derivable from `dummy_hand[dummy].non_empty`. Used only by `play_source_for`. |
| `games_won[partnership]` | Bridge | per-rubber | accumulating | scoring (game-won branch) | Threshold-checked: `>= 2` ends rubber. |
| `above_line[partnership]` | Bridge | per-rubber | accumulating | scoring (component sum) | Never resets within rubber. |
| `below_line_current_game[partnership]` | Bridge | per-rubber-with-reset | accumulating then reset | scoring (component sum + game-won reset) | Resets for *both* partnerships when *either* crosses 100. Coupled reset. |
| `leader` / `current_leader` | All 5 | per-trick-loop (e.g., `play` phase) | replaced | Trick outcome | Lives in the phase that loops over tricks. Not derivable. |
| `dealer` | Spades, Pinochle, Bridge | per-hand or per-rubber | rotated | setup phase | Referenced as `dealer.left`. Rotates per hand. |

Stud (see [games/seven-card-stud.md](games/seven-card-stud.md)) added
significant additional state — per-betting-round tracking, side-pot
eligibility, per-player chip and commitment state. Its variables are
described inline in the game file rather than catalogued here.
