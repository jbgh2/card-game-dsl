# 500 (Five Hundred)

**Variant:** four-player team Australian 500 — the canonical game:
43-card pack, 27-rung bid ladder with misère and open misère, kitty of
three, play to +500 / out backwards at −500.
**Players:** 4, partners sitting across. **Deck:** 43 cards — `A K Q J 10 9
8 7 6 5` in the black suits, the same plus the `4` in the red suits, and one
joker. **Executable spec:** [five-hundred.cardlang](five-hundred.cardlang).
**Rules source:** https://www.pagat.com/euchre/500.html (fetched live).

## The deal

The dealer gives everyone ten cards and the **kitty** three, in batches: 3
to each player, 1 to the kitty, 4 to each, 1 to the kitty, 3 to each, 1 to
the kitty. The deal rotates clockwise each hand.

## The auction

Bidding starts with the player to the dealer's left and runs clockwise. A
bid names a number of tricks (six to ten) and a suit or no-trumps; each bid
must be higher on the ladder than the standing bid, and a player who passes
is out of the auction for good. The auction ends when a bid stands and
everyone else has passed; if all four pass, the cards are thrown in and the
next dealer deals.

| Tricks | ♠ | ♣ | ♦ | ♥ | No-trumps |
|---|---|---|---|---|---|
| Six | 40 | 60 | 80 | 100 | 120 |
| Seven | 140 | 160 | 180 | 200 | 220 |
| Eight | 240 | 260 | 280 | 300 | 320 |
| Nine | 340 | 360 | 380 | 400 | 420 |
| Ten | 440 | 460 | 480 | 500 | 520 |

Two contracts sit between the rungs:

- **Misère** (250): no trumps, and the bidder undertakes to win *no* tricks.
  It ranks above every seven bid and below every eight bid, and may only be
  bid after someone has bid seven.
- **Open misère** (500): the same contract with the bidder's hand exposed
  (below), ranking between ten diamonds and ten hearts. It may be bid over
  any lower bid, or even as the first bid.

Note the ranking is by ladder position, not points: misère (250 points)
still loses the auction to eight spades (240 points).

## The kitty and the joker nomination

The auction winner — the **declarer** — picks up the three kitty cards
without showing them and discards any three face down in their place.

In the no-trump family (no-trumps, misère, open misère) the declarer, if
holding the joker, may then **nominate the suit the joker belongs to**,
announced to the table before the first lead; the joker then counts as the
highest card of that suit — it must follow when that suit is led, wins any
trick where that suit is led, and *loses* when discarded on another suit.

## Play

The declarer leads the first trick; the winner of each trick leads the
next. Players must follow suit if able; a player void in the suit led may
play anything — there is no obligation to trump. The trick is won by the
highest trump in it, or by the highest card of the suit led if no trump was
played.

**Trumps.** Under a suit contract the top trumps are the **joker**, then
the **right bower** (jack of trumps), then the **left bower** (the other
jack of the same colour), then A K Q 10 9 … The joker and left bower are
members of the trump suit in all respects — for following, beating, and
leading — so the left bower's printed suit plays a jack short.

**The joker in the no-trump family.** Un-nominated, the joker belongs to no
suit and is the highest card in the pack — it wins any trick it is played
to, but it may only be played when its holder is void in the suit led. In a
misère the void holder *must* play it; in plain no-trumps playing it stays
optional. (Lead restriction: see "Chosen ruleset" below.)

**Misère is played three-handed.** In a misère or open misère the
declarer's partner takes no part: his cards lie face down and unseen for
the whole hand, and each trick has three cards. Play stops the moment the
declarer wins a trick — the contract is already lost.

**The open-misère reveal.** In an open misère, after the first trick has
been played the declarer arranges his cards face up on the table for all to
see, and plays the rest of the hand exposed.

## Scoring

- **Suit and no-trump contracts.** Making the contract (the declarer's side
  takes at least the bid number of tricks) scores the table value; failing
  scores minus the value. A **slam** — all ten tricks — on a contract worth
  less than 250 scores 250 instead. The opponents score 10 per trick they
  take, whether the contract makes or fails.
- **Misère and open misère.** The declarer's side scores the value (250 or
  500) for taking no trick, minus the value for taking any. The opponents
  score nothing either way.

The game ends when a side reaches **+500 by winning a contract** — crossing
500 on opponents' 10-per-trick points alone does not win — or when a side
sinks to **−500** and goes "out the back door", losing the game.

## Chosen ruleset (modelling notes)

Two auction/joker conveniences follow corpus precedent (Bridge derives its
bid levels and omits the dummy; the file documents the chosen ruleset):

- **Bids climb rung by rung.** A bid names a strain and takes the cheapest
  rung in it that beats the standing bid (the Bridge precedent). A jump bid
  (6♠ straight to 9♥) is folded into successive raises; every contract on
  the ladder remains reachable, and misère/open misère are bid directly at
  their insertion points.
- **An un-nominated joker is not led early.** Pagat lets an un-nominated
  joker be *led* with a lead-time suit nomination, provided that suit has
  not previously been led, and forbids the lead once all four suits have
  been led except to the last trick. The model keeps the restriction and
  drops the lead-time nomination: an un-nominated joker may be led only as
  its holder's last card (where it simply wins). The declarer's start-of-play
  nomination — the strategically load-bearing form, and the one a misère
  declarer cannot survive without — is modelled in full.

## Notes for the executable spec

- The whole contract ladder is one integer ordinal (`bid_rank`, a public
  state variable); the game-local primitives map ordinals to values and
  trick targets, so the ordering (misère above the sevens, open misère
  between 10♦ and 10♥) and the value table never share a scale.
- The bowers and the joker are a follow-*class* remap in the game-local
  `five_hundred_follow_ok` / `five_hundred_trick_winner` primitives — the
  Skat precedent (jacks + trump suit as one class), extended with the left
  bower's effective-suit change. The declarative `ranking:` stays a plain
  strongest-first enumeration; suit-contextual orders are out of its scope
  ([decisions.md](../decisions.md), "The `ranking:` declaration: enumeration or convention").
- The open-misère reveal is a plain movement into `exposed[declarer]`, a
  `PublicHand` zone: the mid-phase visibility flip is carried entirely by
  the standing zone projections and the movement observation — no new
  epistemic construct
  ([open-questions/knowledge-events.md](../open-questions/knowledge-events.md)).
- The sat-out partner's hand simply never moves or emits: it stays at the
  `Hand` zone's count-only projection for the whole misère, which is
  exactly "face down on the table".
- The joker nomination is offered to the declarer in every no-trump-family
  contract, whether or not he holds the joker (declining is always legal,
  so the offer's occurrence reveals nothing); actually nominating is
  guarded on holding it. The deck-derived `Suit` domain carries the
  joker's own "joker" suit as a fifth value — it is never a biddable
  strain nor a nominable suit, and both guards mask it permanently.
