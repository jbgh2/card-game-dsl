# Tichu

The companion formal file is [tichu.cardlang](tichu.cardlang); this is the
readable twin. A four-player team **climbing** game on a 56-card deck (the
standard 52 plus four special cards: Mahjong, Dog, Phoenix, Dragon). First
team to **1000** wins. Rules: Fata Morgana English edition, the source
Pagat's Commercial Card Games index names for Tichu.

Each hand:

1. Every player takes eight cards, one at a time; any time before taking
   the ninth, a player may call **Grand Tichu** (±200) — on one card or on
   eight, and having seen whether the others called. The deal completes to
   14 and every player **pushes** one card to each other player. Any player
   who has not called may call **Tichu** (±100) at any time before playing
   their first card — including before or during the push.
2. The Mahjong holder leads. Players **climb**: each play must be a
   combination of the led *type and length* and **beat** the previous play
   in rank, or be a **bomb** that outranks whatever stands, or **pass**.
   Three passes end the trick and the last player to play wins it and leads
   next. Combinations: singles, pairs, triples, full houses, straights (≥5),
   consecutive pairs (≥2), and bombs — four of a kind, or five or more
   consecutive cards of one suit; bombs rank first by number of cards, then
   by rank, so any straight flush beats any four of a kind.
3. **Bombs play out of turn.** After every play but the Dog, and once more
   when the trick would otherwise be gathered, every other player still
   holding cards is asked in turn whether they bomb; a bomb played there
   stands, and play resumes after the bomber.
4. The special cards: the **Mahjong** is rank 1 (lowest), leads first, and
   goes only into a straight from the one; whoever plays it may **wish** for
   a rank, and from then on every player asked in turn must play a
   combination holding a natural card of that rank whenever they lawfully
   can (a bomb holding one counts; a bomb played out of turn need not),
   until a play holding it clears the wish. The **Dog** is led alone and
   hands the lead to your partner (no capture). The **Phoenix** stands for
   any one card from 2 to Ace in any combination but a bomb, and as a single
   is worth half a rank above the last play (and −25 points); the rank it
   stands for is announced with the play. The **Dragon** is the highest
   single, joins no combination, is worth +25, and its trick is given to an
   opponent of the winner's choice.
5. As players empty their hands they go out in order, however the last
   card leaves — the Dog included. The hand ends the instant only one player
   still holds cards, or the instant both partners of a team have gone out
   first and second — a **double victory**, worth 200 points with no card
   counting; the trick in progress ends there too, still taken (or given
   away by the Dragon) by the last player to play. Otherwise the last
   player's remaining hand goes to the opponents and their own captured
   tricks to the first player out, and each team scores the card points its
   players captured (K and 10 = 10, 5 = 5, Dragon +25, Phoenix −25; 100 in
   all). Finally, **Tichu** (±100) and **Grand Tichu** (±200) calls pay out
   by whether the caller went out first.

The hand runs fully on the kernel. Each climbing trick is one `round climb`
over the game-local combination engine (`tichu_lead_options` /
`tichu_follows` — the enumeration itself is not DSL-expressible: a play moves
a specific computed card-set, where the movement vocabulary moves cards by
count). The engine enumerates every combination at every suit choice and
is held to the rules by an independent validator over every subset of
sampled hands (`tests/test_tichu_combinations.py`). The Dog is a
*trick-ending lead*: the engine marks the play `ends_trick`, the climb form
closes the trick with no follower draws, and the body routes it off the
round's terminal state (`state.lead_ended_trick` — pile to the discard, lead
to the partner). The trick's `until` ends it the instant the third player
goes out or a double victory is complete. Finishing order comes from
terminal round-state (`state.shed_first` / `state.shed_second`, the first two
players to play out their cards each trick, in play order), folded in
however the trick closed. Each player banks their own tricks
(`captured[player]`), so the Dragon's gift (`dragon_to_left` /
`dragon_to_right`) names the opponent whose pile the trick lands in, and
the tailender rule moves the last player's own pile alone.

The wish is the climb form's announcement regime: the play holding the
Mahjong is followed by one more decision of the same seat over the wish
tokens (a rank, or no wish), announced publicly; the engine marks the plays
a standing wish compels and the form offers those alone, with no pass; the
wish outlives the trick in `wish`, written after each round from the
round's own record. Bombs out of turn are the form's interrupt window: the
engine names which plays interrupt (bombs) and what a decline is called
(`no_bomb`), and the form asks every other seat in turn after each play and
at the close, so a seat with no bomb says the same thing as one who
declines. The Phoenix's rank in a play is announced beside the play's
movement, because the movement shows the cards alone and every follower's
legal set depends on that rank.

The push is one chosen 3-card movement per player into a per-player `gift`
pile — simultaneous, since gifts land only after every pick — distributed
giver-major and draw-free (pick *i* to the *i*-th other seat), so each
receiver learns exactly what landed and from whom, and nobody else learns
anything but counts. The calls are real decisions. Grand tichu is polled
after each of the first eight cards — the off-the-clock quiescence-lap poll
([decisions.md](../decisions.md) "Off-the-clock windows"), so a call on any
card count is a decision the game offers, and a seat that sees another
decline may still call before the next card. Small tichu is off-the-clock —
any time before the caller's first play — encoded as the same poll: before
the push, after it, and before each climbing trick, an offering round walks
the ring while the public gate holds (`no_call` laps close it). Eligibility
is public with no dedicated tracking: before the push nobody has played;
after it, exactly the players still holding 14 cards haven't. Because the
climb round owns the decisions inside a trick, within-trick small-tichu
timing coarsens to trick boundaries — no call becomes unreachable, only its
fine timing relative to plays inside the caller's first trick. One honest
consequence of real calls: under *indiscriminate* calling the 1000-point
race diverges (a random call is worth about −50 in expectation), so a table
of maniacs never finishes — the corpus's second legally-unbounded line
([open-questions/unbounded-lines-and-max-length.md](../open-questions/unbounded-lines-and-max-length.md));
the playout tests drive the call windows through a reference policy
instead, whose grand-tichu gate is derived per hand from the number of
polls.
