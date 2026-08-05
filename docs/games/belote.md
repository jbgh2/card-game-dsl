# Belote

**Variant:** plain four-player team Belote (not Coinche; Klaverjas is
a separate, later delta), simple two-round trump-making, first team to 1000.
**Players:** 4, in fixed teams sitting across (0+2 vs 1+3).
**Deck:** 32 cards (A K Q J 10 9 8 7 in each suit — the skat32 pack).
**Executable spec:** [belote.cardlang](belote.cardlang). **Rules source:**
https://www.pagat.com/jass/belote.html (fetched live). Deliberate departures
from that page are listed at the end under "Scope and departures".

Play is counterclockwise. The player to the dealer's right is eldest: she
bids first and leads the first trick. The deal rotates to the right each
hand, including thrown-in hands.

## Rank orders and card points

Belote uses three orders, and they are different:

- **Plain suits (play):** A > 10 > K > Q > J > 9 > 8 > 7, worth
  11 / 10 / 4 / 3 / 2 / 0 / 0 / 0.
- **Trump suit (play):** J > 9 > A > 10 > K > Q > 8 > 7, worth
  20 / 14 / 11 / 10 / 4 / 3 / 0 / 0.
- **Sequences (declarations only):** the natural order
  A K Q J 10 9 8 7 — so K-Q-J is a sequence but A-K-Q-J-10-9 style "wrap"
  never is, and 10 sits in its natural place, not next to the ace.

The card points sum to 152; with the 10 for the last trick a hand's trick
points total 162.

## The deal and the trump-making

The dealer gives each player a packet of three, then a packet of two, and
turns the next card face up (the turn-up). Bidding starts at eldest and goes
around once: each player either **takes** — accepting the turn-up's suit as
trump — or passes. If all four pass, a second round from eldest lets each
player name any **other** suit as trump, or pass. If all four pass again,
the hand is thrown in and the next dealer deals.

As soon as someone takes, the bidding ends: the taker adds the turn-up card
to his hand, the deal completes with three more cards to every other player
and two more to the taker (so everyone holds eight), and the taker's team
becomes the **taking side** — it must win at least half the points (see
Scoring) or lose everything.

## Play

Eldest leads the first trick; each trick's winner leads the next. A trick is
won by the highest trump in it, else the highest card of the led suit. The
follow obligations are strict:

- **Follow suit if you can.** This always applies.
- **Trump led:** you must not only follow with a trump, but play a trump
  that **beats the best trump so far** if you can — whoever is winning the
  trick, partner included. Unable to beat it, you still play a trump (any);
  void in trumps, you may discard anything.
- **Plain suit led, and you are void:**
  - If an **opponent** is currently winning the trick, you must trump if
    you can. If the trick already holds a trump (the opponent's winning
    one), you must **over-trump** if able; unable, you must still play a
    trump ("under-trumping" — it does not help, but it is compulsory).
    Without a trump you may discard anything.
  - If your **partner** is currently winning, you are free: trump or
    discard as you please — with one exception. If your partner is winning
    the trick **with a trump**, you may discard or over-trump, but you may
    not under-trump (unless under-trumps are the only cards you hold).

## Declarations

Combinations held in hand score for one side only, and are announced during
the first trick:

- **Tierce** — three-card sequence in one suit (natural order): 20.
- **Quarte** — four-card sequence: 50.
- **Quinte** — five-card sequence: 100.
- **Carré** — four of a kind: Jacks 200, Nines 150, Aces / Tens / Kings /
  Queens 100. Carrés of 8s or 7s score nothing and are not declarable.

At the close of the first trick, each player in play order (from the trick's
leader) either **declares** — announcing her hand's best combination: its
kind, its top card, and whether it is in trump ("tierce to the king",
"four jacks", "quarte in trumps to the ace") — or stays silent. A
declaration is verified by the rules: you can only announce the best
combination you actually hold at that moment, exactly. The same card never
counts in two combinations; when a hand decomposes several ways, the
canonical reading applies — carrés first, then in each suit the longest run
declarable from the remaining cards (a six- or seven-card run declares one
quinte from its top; the short remainder declares nothing) — and the best
of those combinations (kind, then height, then trump) is the declarable
one.

**Comparison.** A carré beats any sequence (carrés rank J > 9 > A > 10 >
K > Q); a quinte beats a quarte beats a tierce; equal-length sequences
compare by their top card; an equal-height trump sequence beats a plain
one; and a tie between equal plain sequences goes to the **earlier
announcer in rotation**. Apart from Belote-Rebelote, **only the team
holding the single best declaration counts its declarations** (both
partners'); the other team's count for nothing.

**Showing.** Before the second trick, the entitled side shows its declared
combinations, card by card — those cards become public. The losing side
never shows: its concealed cards stay concealed; all anyone learns of them
is what was announced.

## Belote-Rebelote

A player holding **both the King and Queen of trumps** may announce them for
20 points, saying "belote" as she plays the first of the pair. Announcing
shows everyone the partner card still in her hand (that is the announcement's
whole content: she holds both). The completion on the second card
("rebelote") follows automatically. Staying silent forfeits the 20 — and
reveals nothing. The 20 always counts for the announcing team, in every
outcome of the hand, and is separate from (and unaffected by) the
declaration comparison above.

The window opens exactly once, at the close of the trick where the first
trump King-or-Queen is played, for the player who played it. A player who
does not hold the partner card declines with the same visible "no" as a
player declining by choice, so silence never betrays a holding.

## Scoring

Each side totals: card points in its captured tricks, plus 10 for winning
the **last trick** (dix de der), plus its entitled declarations, plus its
Belote-Rebelote 20 if announced. A side that took **no trick** counts none
of its declarations (the Belote-Rebelote 20 survives even that).

- **Contract made** — the taking side's total is **at least** the
  defenders' (ties go to the takers): both sides add their totals to their
  game score.
- **Dedans** — the taking side falls short: it scores nothing (bar a
  Belote-Rebelote 20), and the defenders score **162 plus every announced
  declaration of both sides** (plus their own Belote-Rebelote 20 if any).
- **Capot** — the taking side wins all eight tricks: it scores 100 instead
  of the dix de der, i.e. 252 plus its declarations (and its 20). Only the
  taking side earns the capot bonus; defenders who sweep the takers simply
  collect the dedans award.

First team to reach 1000 game points wins.

## Scope and departures from the reference

The executable spec makes these deliberate, visible simplifications of the
Pagat page; everything else above is the reference rule.

1. **Announcement timing is batched to the trick boundary.** The reference
   interleaves declarations with the first trick's card plays (each player
   speaks as she plays) and the Belote announcement with the royal's play
   itself; the trick form of `round` admits no foreign decision mid-pass, so
   both land at the close of the same trick. What is announced is
   unchanged; players later in the first trick just no longer hear the
   earlier announcements before choosing their first card.
2. **Announcements are unconditional, not negotiated.** The reference's
   comparison dialogue reveals a sequence's height only when the other side
   holds an equal-length one ("how high?" — "good!"), and trump status only
   when heights tie; here a declaration always announces kind, height, and
   trump flag. The dialogue is expressible as more decision vocabulary but
   is scoped out; the composed variant over-announces exactly those two
   facts. (Recorded as the Belote data point in
   [open-questions/knowledge-events.md](../open-questions/knowledge-events.md).)
3. **One declaration per player: the best combination.** The reference lets
   a player announce every combination she holds ("tierce, tierce"), and
   the entitled side scores them all; here each player announces her best
   combination or nothing, and only announced combinations score. The
   constraint is structural: an announcement's content must ride the
   announcement itself (the move name and its parameter — that is what an
   observer's information set derives from), and the closed move-parameter
   domains carry one (kind, height, trump) triple per decision. Hands with
   two or more combinations are uncommon; their extra combinations neither
   score nor show. Combinations are evaluated on the hand as it stands at
   the close of trick one, so a combination broken by the player's own
   first-trick card is not declarable — the reference evaluates on the hand
   as dealt. A rational declarer keeps a declared combination intact
   through trick one, so the reachable difference is small.
4. **Showing is unconditional.** The reference shows the entitled side's
   cards on the opponents' request; here they are always shown (the
   deterministic reading of a request that costs nothing and is near-always
   made). The losing side's cards stay hidden either way.
5. **Rebelote is automatic.** Once belote is said (and the partner card
   publicly revealed), the completion on the second card carries no
   information and no rational player forfeits it, so it is not a second
   decision. Declining the first announcement forfeits the pair — the
   reference's late or split announcements are out of scope.
6. **No rounding, no litige.** Raw points are banked (the page's base text;
   rounding to tens is a table convention), and the page's tie rule — the
   taking side makes its contract on equality — is implemented as written,
   so there is no held-over "litige" score.
