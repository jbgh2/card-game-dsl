# Spades

The companion formal file is [spades.cardlang](spades.cardlang); this is the
readable twin. Spades is a four-player team trick-taking game (partners
sit across) with spades always trump. Each player bids the number of tricks
they expect to take (a bid of zero is *nil*); the team's contract is the
sum of its non-nil bids. After thirteen tricks the hand is scored and the deal
rotates. The game runs until a team reaches +500 (a win) or −200 (a loss).
**Deck:** standard 52.

Scoring (the variant formalized here — Spades has several; this one is kept
internally consistent so each hand's score reconciles):

- **Contract.** Make the contract (team tricks ≥ contract): +10 per bid trick,
  plus one *bag* per overtrick. Miss it: −10 per bid trick, no bags.
- **Nil.** A nil bidder who takes no tricks scores +100; one who takes any
  scores −100. Nil is scored per player, independently of the contract.
- **Bag overflow.** Every 10 accumulated bags costs 100 points and drops the
  bag counter by 10.

The game file folds scoring into the `scoring` phase (as Hearts does) rather than
using separate `scoring_component` blocks; the first-trick "no spades" ban from
some rulebooks is omitted because "no leading spades until broken" already
forbids leading a spade on the first trick.
