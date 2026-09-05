# Tichu

The companion formal file is [tichu.cardlang](tichu.cardlang); this is the
readable twin. A four-player team **climbing** game on a 56-card deck (the
standard 52 plus four special cards: Mahjong, Dog, Phoenix, Dragon). First
team to **1000** wins. Rules: Fata Morgana English edition.

Each hand:

1. Deal 8 cards each; each player may call **Grand Tichu** (±200) before
   the last six cards are dealt. The deal completes to 14 and every player
   **pushes** one card to each other player. Any player who has not called
   may call **Tichu** (±100) at any time before playing their first card —
   including before or during the push.
2. The Mahjong holder leads. Players **climb**: each play must be a combination
   of the led *type and length* and **beat** the previous play in rank, or be a
   **bomb** (four of a kind, which beats any non-bomb), or **pass**. Three passes
   end the trick and the last player to play wins it and leads next.
   Combinations: singles, pairs, triples, full houses, straights (≥5),
   consecutive pairs (≥2), and bombs.
3. The special cards: the **Mahjong** is rank 1 (lowest) and leads first; the
   **Dog** is led alone and hands the lead to your partner (no capture); the
   **Phoenix** is a wildcard / a single worth half a rank above the last play
   (and −25 points); the **Dragon** is the highest single, worth +25, and its
   trick is given to an opponent of the winner's choice.
4. As players empty their hands they go out in order. If both partners of a team
   go out first and second — a **double victory** — the hand ends for 200 points
   with no card counting. Otherwise the last player's remaining hand goes to the
   opponents and their captured tricks to the first player out, and each team
   scores its captured card points (K and 10 = 10, 5 = 5, Dragon +25, Phoenix
   −25; 100 in all). Finally, **Tichu** (±100) and **Grand Tichu** (±200) calls
   pay out by whether the caller went out first.

The hand runs fully on the kernel. Each climbing trick is one `round climb`
over the game-local combination engine (`tichu_lead_options` /
`tichu_follows` — the enumeration itself is not DSL-expressible: a play moves
a specific computed card-set, where the movement vocabulary moves cards by
count). The Dog is a *trick-ending lead*: the engine marks the play
`ends_trick`, the climb form closes the trick with no follower draws, and the
body routes it off the round's terminal state (`state.lead_ended_trick` —
pile to the discard, lead to the partner). Finishing order likewise comes
from terminal round-state (`state.shed_first` / `state.shed_second`, the
first two players to play out their cards each trick, in play order). The
push is one chosen 3-card movement per player into a per-player `gift` pile
— simultaneous, since gifts land only after every pick — distributed
giver-major and draw-free (pick *i* to the *i*-th other seat), so each
receiver learns exactly what landed and from whom, and nobody else learns
anything but counts. The calls and the Dragon are real decisions. Grand
tichu is a discrete window in the deal (eight cards, each player accepts or
declines in seat order, then the last six). Small tichu is off-the-clock —
any time before the caller's first play — encoded as the quiescence-lap poll
([decisions.md](../decisions.md) "Off-the-clock windows"): before the push,
after it, and before each climbing trick, an offering round walks the ring
while the public gate holds (`no_call` laps close it). Eligibility is public
with no dedicated tracking: before the push nobody has played; after it,
exactly the players still holding 14 cards haven't. Because the climb round
owns the decisions inside a trick, within-trick call timing coarsens to
trick boundaries — no call becomes unreachable, only its fine timing
relative to plays inside the caller's first trick. A Dragon-won trick is
given away by a real announced choice (`dragon_to_left` / `dragon_to_right`);
both opponents bank into the same team pile, so the choice moves no points,
but the decision itself is public history, as at the table. One honest
consequence of real calls: under *indiscriminate* calling the 1000-point
race diverges (a random call is worth about −50 in expectation), so a table
of maniacs never finishes — the corpus's second legally-unbounded line
([open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md));
the playout tests drive the windows through a reference policy instead.
Scope reductions (unchanged): the Mahjong wish, the Phoenix as a wildcard
inside straights/consecutive-pairs, straight-flush bombs, and out-of-turn
bombs are omitted.
