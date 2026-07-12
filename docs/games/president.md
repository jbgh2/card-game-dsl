# President

The companion formal file is [president.cardlang](president.cardlang); this is
the readable twin. A **five-player climbing / shedding** game on the standard
52-card deck (no jokers) — the **basic multi-round game** plus one variant:
**transparent threes** (Pagat's "Transparent cards"). The aim is to shed your
whole hand first: the first player out each hand is the **President**, the
second the **Vice-President**, and the last player left holding cards is the
**Scum**. Points accumulate across hands; the first game-ending hand crowns the
highest total. Rules:
[Pagat](https://www.pagat.com/climbing/president.html) (Basic Game +
"Transparent cards").

**Card order.** Ranks run, high to low: **2 A K Q J 10 9 8 7 6 5 4 3**. Suits
are entirely irrelevant — no tie-breaks, no flushes, no follow-suit. Play is
clockwise.

## Each hand

1. **Deal.** The whole deck is dealt out as equally as possible — 52 over five
   players, so two players hold 11 cards and three hold 10.
2. **The exchange** (every hand after the first): the **Scum gives their
   single highest-ranked card to the President** — this is forced, not a
   choice (when several cards tie at the top rank, any one of them is the same
   give, since suits carry no strength) — and the **President returns any one
   card** they do not want. The two transfers are private to the pair:
   everyone else sees only that one card moved each way.
3. **Lead.** On the **first hand** seat 0 leads. On **every later hand the
   President leads**.
4. **Play.** The leader plays any **set of 1–4 cards of equal rank** (a
   single, pair, triple, or four of a kind). In turn order, each other player
   must either **pass** or **beat the standing set**: the **same number of
   cards** of a **strictly higher rank** (a single beats a single, a pair a
   pair — never across sizes, never equal rank, no bombs). Passing does not
   lock you out — you may play again when the turn comes back around. When
   everyone else has passed, the trick is spent: the cards are turned face
   down and put aside, and the **last (highest) player leads** the next trick
   with anything. A player who runs out of cards mid-hand is simply skipped;
   if the leader-to-be is out, the lead passes clockwise to the next player
   still holding cards.
5. **Transparent threes** (the one variant carried): a set made **entirely of
   threes** beats an equal-sized set of **any** rank — even 2s, even a
   standing threes-play — and **takes on the rank of the cards it beat**.
   If a pair of kings stands and you play a pair of threes, your threes now
   count as kings: the next player must beat a pair of kings or pass. If all
   pass, your threes have won and you lead. A set of threes **led** naturally
   is just the lowest rank (anything beats it — including, transparently,
   another set of threes). Threes have no special power as singles-in-mixed
   company: a set is equal-ranked by definition, so "transparent" only ever
   means a pure-threes set.
6. **End of the hand.** The hand ends **the instant only one player still
   holds cards** — that player is the Scum (the fourth player's last play is
   never answered; there is nobody left to beat it against). The first player
   who shed all their cards is the President, the second the Vice-President.
7. **Scoring.** President **+2**, Vice-President **+1**, everyone else 0.
   The game ends when a hand completes with **any player at 11 points or
   more**; the **highest score wins**.

## Scoped rulings (recorded conventions, not from the Pagat text)

- **The deal's extra cards.** Pagat deals from the dealer's left with the
  President's seat rotating; here the deal is a fixed round-robin from seat 0,
  so **seats 0 and 1 always hold the eleventh card**. Suits and seat labels
  carry no strength, so this changes nothing a player could act on.
- **The first lead.** Pagat has the player to the dealer's left start; the
  deal here has no explicit dealer, so **seat 0 leads hand 1** (the implicit
  dealer sits at the last seat). From hand 2 on, the **President leads** —
  Pagat's social-rank seating (the President leads off from the top seat)
  reduced to the lead alone, since seats never move here.
- **No seat rotation.** Players keep their seats between hands; the social
  hierarchy is carried entirely by the exchange and the lead. (Pagat's
  physical re-seating is ceremony — it affects nothing but who sits where.)
- **The scoring scheme** (President +2, Vice-President +1, play to 11,
  highest total wins) is one of the simple cumulative schemes Pagat describes
  informally ("the players simply keep a running total"); the exact numbers
  are this corpus's fixed choice.
- **Totality of the offices.** With five players, four shed before the hand
  ends, so President and Vice-President always exist; the `is not none`
  guards around the score updates are a totality backstop, never taken.

## How the description maps to the DSL

- **The hand runs fully on the kernel.** Each climbing trick is one
  `round climb` over the game-local combination engine
  (`president_lead_options` / `president_follows` in
  `cardlang/runtime/president.py` — game-local like Big Two's and Tichu's,
  because a play moves a specific computed card-set where the movement
  vocabulary moves cards by count). The trick loop, the pile routing, the
  finishing order, the exchange, and the scoring are DSL.
- **The hand ends mid-trick by the round's `until` predicate** — the instant
  one player remains with cards — so the last holder never plays into a
  finished hand (Pagat: the hand is over when one player remains). Finishing
  order comes from the round's terminal state (`state.shed_first` /
  `state.shed_second`), folded into `out_first` / `out_second` exactly as in
  Tichu.
- **Transparent threes live entirely in the follows query.** The climb form
  threads the standing play but never compares plays itself, so a pure-threes
  follow is constructed with the *standing* play's key: when it becomes the
  standing play, the next follower's legality is computed against the rank it
  absorbed. Its action id is just its card-set's (the same id as leading those
  threes naturally) — what the play *means* is carried by the public trick
  context, exactly as at a real table.
- **The exchange derives its information sets from the zone projections.**
  The Scum's give is a draw-free filtered movement (`where
  president_is_top_rank(scum, card)` — forced by rule, so it is no decision and
  consumes no chooser draw); the President's return is a chosen one-card
  movement. Both are hand-to-hand transfers, so each participant sees the
  identity of the card on their own side and every bystander sees a one-card
  count — nobody learns the exchanged cards but the pair, and nobody authors
  an observation rule to make it so.
- **Suits never matter**, so the engine offers each (rank, size) as one
  representative set (the group's highest suits — the Big Two representative
  convention) without changing any legality, and the OpenSpiel
  indistinguishability class for hidden hands is exactly "same rank, any
  suit" (`swap_axis="rank"` in `tests/openspiel_ready/test_president.py`).
- **State is public throughout:** scores, the finishing order, and the
  standing offices (President / Scum) are all public facts; hidden
  information lives only in the hand zones.
