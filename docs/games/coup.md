# Coup

The companion formal file is [coup.cardlang](coup.cardlang); this is the
readable twin. Coup (base game, 3-6 players; the executable fixes four) — a
bluff-and-challenge game with a 15-card deck (five characters, three copies
each) and a coin economy. Each player holds two face-down *influence* cards and
some coins; on a turn the active player takes one action, others may challenge
or block it, and influence is lost by flipping a card permanently face-up. The
last player with influence wins. Rules: Tchanturia, 2012.

A turn's actions:

- **Income** — take 1 coin (uncontestable).
- **Foreign aid** — take 2 coins, unless someone claims the Duke to block it.
- **Coup** — pay 7, force a player to lose influence (uncontestable). Forced once
  you reach 10 coins.
- **Tax** (claim Duke) — take 3 coins.
- **Assassinate** (claim Assassin) — pay 3, a target loses influence unless they
  claim the Contessa to block.
- **Steal** (claim Captain) — take 2 coins from a target unless they claim
  Captain or Ambassador to block.
- **Exchange** (claim Ambassador) — draw 2 from the deck and return 2.

Any character claim (an action or a block) can be **challenged**: if the claimant
holds the character, the challenger loses influence and the claimant swaps the
proven card for a fresh one; if it was a bluff, the claimant loses influence and
the action fails. A player who loses their last influence is exiled and their
coins return to the bank.

The game runs fully on the kernel, at real interactive scope. Each turn is
one `offer` over the seven coin-guarded actions (the forced Coup at ten
coins falls out of the `when:` guards); `steal`, `assassinate`, and `coup`
carry a declared `target : Player` parameter, so naming the victim is the
actor's own announced choice. A claimed action opens a challenge window —
each other in-game player, clockwise from the claimant's left, is offered
`[challenge, allow]`, and the first challenge closes the window. Blocks are
decisions too: foreign aid polls every opponent with
`[block_claiming_duke, allow]`, while a steal or assassination offers its
target the block vocabulary — so *which* character the blocker claims, the
bluff itself, is the decision. A block claim is challengeable by everyone
else, including the original actor, through the same window. A proven
challenge `reveal`s the shown card publicly, returns it to the deck,
reshuffles, and redraws; every influence loss is a chosen movement by the
loser, flipped publicly into `revealed` (everyone sees the lost card — real
Coup); the exchange draws off the top, returns two chosen cards, and
reshuffles. Window results (`challenge_stands` / `block_stands`) are public
phase state, and every window field is cleared where the action that opened
it resolves, so the seat asked for its turn reads no verdict and no claimant
from the action just settled. Coins are integers (always 50 in total, the treasury clamping
every gain) and influence cards conserve to 15. `alive[p]` is a Boolean —
true while a player is in, false once exiled — so `winner: highest alive`
names the survivor. The three blocks the game repeats — the challenge window
(×8), the influence loss (×14) and the proven-claim swap (×7) — are named
`procedure`s, written once and `run` at each site, with each argument bound once
at the call ([decisions.md](../decisions.md) "Named procedures"). The forced Coup at 10 coins drives every aggressive line to an
end; a table that only ever exchanges makes no coin progress, so the
declared `max_length` backstop is Coup's real termination bound on
maximally passive lines
([open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md)).
