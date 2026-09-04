# Oh Hell

The companion formal file is [oh-hell.cardlang](oh-hell.cardlang); this is the
readable twin. Four-player Oh Hell (also Blackout, Up and Down the River,
Contract Whist). Each hand turns up a card to fix trump, every player bids the
*exact* number of tricks they expect, and the hand scores +1 per trick won plus
a +10 bonus for hitting the bid exactly (missing — over or under — costs only
the bonus, never goes negative). The hand-size sequence runs 10 down to 1, then
back up to 10 (sizes 2–10): 19 hands, after which the highest score wins. Source:
[Pagat](https://www.pagat.com/exact/ohhell.html).

Tricks are played via the kernel `round` construct. The trump suit changes every
hand, so it is passed as a `trump` argument (the per-hand `trump_suit` state
var) rather than the fixed game-level `trump:` declaration that Spades uses.

**The hook rule** — the total of all bids may not equal the hand size, so
somebody must miss. Bidding starts left of the dealer and goes round, so the
dealer bids last with every other bid already heard, and that is what makes the
constraint land on them: the rulebook forbids the dealer, at the moment they
choose, the one number that would make the bids total the hand size. The
dealer's bid says exactly that — `excluding hand_size - total_bid` removes the
forbidden number from the dealer's range as the bid is chosen — so the bid
every player hears is the bid the game scores. When the other three have
already bid past the hand size, no number is forbidden and the dealer bids
freely, as at the table.
