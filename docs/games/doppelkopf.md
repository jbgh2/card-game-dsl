# Doppelkopf

The formal, machine-checkable description is
[doppelkopf.cardlang](doppelkopf.cardlang); this file is the readable twin.

**Variant:** four players, 48-card double pack, DDV-aligned base **normal
game** — no Vorbehalt round (marriage, poverty, and bid solos are out of
scope; a *silent solo*, both ♣Q dealt to one player, arises naturally and is
scored as a normal game with the lone player's score tripled). One session =
one round of deals: four hands, each player dealing once. Cumulative
zero-sum score; highest total wins. **Rules source:** Pagat,
<https://www.pagat.com/schafkopf/doko.html> (base text; the "second ♥10
wins" and Schweinchen/Genscher house variants are excluded).

## The pack

Two copies each of A 10 K Q J 9 in all four suits (the Pinochle
composition), with the Skat card points — the game's `card_points` table:
A=11, 10=10, K=4, Q=3, J=2, 9=0 — 240 card points in play.

**Trumps (26 cards), high to low:**
♥10 ♥10 · ♣Q ♣Q ♠Q ♠Q ♥Q ♥Q ♦Q ♦Q · ♣J ♣J ♠J ♠J ♥J ♥J ♦J ♦J ·
♦A ♦A ♦10 ♦10 ♦K ♦K ♦9 ♦9

The plain suits rank A 10 K 9 (clubs, spades) and A K 9 (hearts — both ♥10
are trumps). Every queen and jack is a trump, so plain suits have no Q or J.

## Each hand

1. **Deal.** Dealer shuffles; 12 cards to each player. The deal rotates one
   seat left each hand; the player left of the dealer leads the first trick.

2. **Teams.** The two players dealt the queens of clubs are the **Re** team;
   the other two are **Kontra**. Nobody says who they are — team membership
   is private until a ♣Q is played or an announcement reveals it. If one
   player was dealt both ♣Q, that player is Re alone against three (the
   silent solo).

3. **Play.** Twelve tricks. The leader plays any card; the others must
   follow the *class* of the led card — trumps are one suit for following
   purposes (a ♠Q lead is a trump lead, not a spade lead; a spade lead
   obliges a plain spade). Void in the led class, any card may be played.
   The highest trump wins the trick, else the highest card of the led suit;
   **of two identical cards, the first played wins**. The trick's winner
   leads next.

4. **Announcements** may be made *at any time* during the play — not just on
   the announcer's turn — bounded by the announcer's own hand size:

   | Announcement | Meaning | Requires holding at least |
   |---|---|---|
   | Re / Kontra | "my side wins" (+2 to the hand's value each) | 11 cards |
   | No 90 | opponents stay under 90 | 10 cards |
   | No 60 | under 60 | 9 cards |
   | No 30 | under 30 | 8 cards |
   | Schwarz | opponents take no trick | 7 cards |

   A side's announcements ladder: no 90 requires that side to have said
   Re/Kontra first, no 60 requires no 90, and so on. Saying "no 90" (or
   deeper) publicly states which side the announcer is on. **Reply rule:**
   after the other side announces, your side may still say Re/Kontra while
   holding one card fewer than that announcement required (e.g. after a
   no 60, a reply is legal while holding 8).

5. **Scoring.** Card points are tallied per team from the tricks won.
   - **Targets.** Re wins with 121; Kontra wins with 120. If Kontra was
     announced and Re was not, Re needs only 120 (and Kontra 121). A side
     that announced no 90 / no 60 / no 30 needs 151 / 181 / 211; an
     announced schwarz needs every trick.
   - **Winner.** A side that fails any level it announced loses the hand to
     the other side — even if the other side is under its base target
     (Pagat's worked example: Re announces "Re, no 90, no 60" and takes 172;
     Kontra wins with 68). If **both** sides fail their announcements,
     nobody wins the game (see the scoped ruling below). Otherwise the base
     targets decide.
   - **Hand value** (to the winning side): 1 for game, +1 if Kontra won
     ("gegen die Alten"), +2 for each said Re / Kontra, +1 for each level
     the losers were actually held under (90/60/30/schwarz), +1 for each
     level the winners announced, +2 for each level the losers announced
     and failed. This reproduces Pagat's two worked examples exactly (8 and
     9 points).
   - **Extras**, independent of who won the game, netted into the value:
     **Fox** — capturing an opponent's ♦A, +1 per copy; **Charlie** —
     winning the last trick with a ♣J, +1 (playing a ♣J into an
     opponent-won last trick concedes the point; partner-won is silent);
     **Doppelkopf** — a trick whose four cards are all aces and tens, +1.
   - **Settlement.** The hand's net value `d` is scored zero-sum: each
     winner +d, each loser −d; a lone (silent-solo) player settles with all
     three opponents, so their score is ±3d.

## Scoped rulings (recorded, not from the Pagat base text)

- **Both sides fail their announcements** (possible only when both
  announced): no game / gegen-die-Alten / Re / Kontra points are scored;
  each side still scores +1 per level it actually achieved against the
  other, +2 per level the other side announced and failed, and the
  difference settles zero-sum. Extras apply unchanged. This follows the
  DDV's "neither won" treatment (Turnierspielregeln 7.1.4); the Pagat base
  text does not cover the case.
- **Extras in the silent solo** apply as in any normal game — Pagat's "Fox
  and Charlie cannot be scored in a solo" reads on *bid* solos, which are
  out of scope here.

## How the description maps to the DSL

- **Teams are hidden information, so they are never state.** `is_re(p)`
  reads p's own hand (only in move guards — the actor's private legality)
  or the public record `re_known[p]`, written only on public events:
  playing a ♣Q, or making a Re-side announcement. By scoring time every
  card has been played, so the public record is the complete partition —
  the rulebook's own deferred evaluation ("the ♦A is left face up and
  turned over when the team becomes clear") made operational.
- **The "at any time" window is the quiescence-lap poll** settled in
  [decisions.md](../decisions.md) "Off-the-clock windows": before every
  card decision, while the public gate `window_open()` holds (hand counts
  and the ladder — public information only), an offering round walks the
  ring from the player about to act; each player submits an announcement or
  `no_announcement`, and four consecutive declines close the poll. A player
  with no legal announcement submits the same public `no_announcement` as a
  player declining by choice, so silence never reveals *why* — private
  ineligibility is indistinguishable from patience. Because hand sizes
  change only when their owner plays, a poll before each play offers every
  announcement at exactly the hand sizes the paper rules allow.
- **Tricks are hand-rolled** (the Skat shape) because announcements land
  between any two card plays — a foreign decision inside the trick, which
  the trick form of `round` cannot host. No game-local runtime primitive
  remains: the trump group (both hearts 10, the queens, the jacks, the
  diamonds) is the game's **Trick Order** (decisions.md "Trick Order"), so
  `highest_by_trick_order(trick_pile)` names the winner — first of equals
  over the trump class, the plays read off the trick pile's Arrival Record,
  who played each card the kernel's fact and never seat arithmetic — and
  `follows_lead` gives follow legality from the SAME declaration, so the led
  class has one definition rather than two. The window gate and all
  bookkeeping remain in-DSL functions.
- **Deferred bonus events** (Fox, Charlie, the last trick's winner) are
  recorded as `Player?` slots during play — public facts about public
  plays — and team-resolved at scoring, when the partition is complete.
