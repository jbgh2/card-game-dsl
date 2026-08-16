# 500 vs Belote as the next corpus game — a decision brief

*Dated record. This decision brief argues about a roadmap line as it stood when the
decision brief was written, so its quotations stay verbatim. That line has since moved
to the tracker — the ordering it belonged to is now
[issue #143](https://github.com/jbgh2/card-game-dsl/issues/143), and both games
are in the corpus. Read the roadmap citations below as historical.*

A decision-grade comparison of the two candidates
[roadmap.md](../roadmap.md) "Suggested next steps" item 1 offers as the
"one game, two unblocks" pick: 500 and Belote. The two questions at stake are
[knowledge-events](../open-questions/knowledge-events.md) (Tier 4, low impact —
awaiting a phase outcome observed *unequally*) and
[structural-infoset-proofs](../open-questions/structural-infoset-proofs.md)
(Tier 2, high impact, *actually blocked* — its constructive world generator
awaits a *compound hidden-function probe*). This decision brief informs a human
decision; it does not make it, and it does not touch
[_candidates.md](../games/_candidates.md) or any settled doc.

**Sources (fetched 2026-07-16):** 500 —
<https://www.pagat.com/euchre/500.html> (four-player partnership Australian
rules); Belote — <https://www.pagat.com/jass/belote.html> (plain four-player
partnership, i.e. *not* Coinche). Pagat is the authoritative reference per
CLAUDE.md; rules below are quoted from those two pages.

## Verdict up front (the "two unblocks" framing is optimistic)

Neither game is the clean double-unblock the roadmap line reads as. On the
verified rules:

- **The high-impact unblock (structural-infoset-proofs, Tier 2) is delivered
  by NEITHER game.** 500's open misère is a *total* reveal of the declarer's
  hand — not a function of hidden state. Belote's declaration contest is
  resolved by *public verbal announcement* (type, then top card spoken aloud),
  so its public outcome is a function of *public claims*, not hidden cards.
  Neither defeats a swap axis. **[Cheat](../games/_candidates.md#cheat) remains
  the sole clean witness** — its challenge outcome is a public boolean function
  of face-down cards. The roadmap's "plausibly also the compound hidden-function
  probe" is, on the fetched rules, **false for both**.
- **The low-impact unblock (knowledge-events, Tier 4) is genuinely served — and
  can be *closed* — by Belote**, weakly by 500. This is a real deliverable: a
  Tier-4 "confirm the reduction when a case arises" question is *resolved* by a
  concrete in-play case demonstrating that an unequally-*revealed* phase outcome
  reduces to `announce` + conditional all-observer `reveal`, with the private
  residue riding ordinary zone projection. Belote's in-play declarations are
  that case in full; 500's open misère is the weakest possible witness (a full
  common-knowledge reveal, the same category as Coup, which was already examined
  and did *not* force the question — [knowledge-events.md](../open-questions/knowledge-events.md)).

**Recommendation: Belote (plain, four-player partnership, no Coinche)** is the
better of the two, on three independent tiebreakers below. But if the *driving*
goal is the Tier-2 structural-infoset unblock, **neither 500 nor Belote belongs
next — Cheat does**, and 500 in particular should wait until Euchre has settled
the effective-suit-remap bower axis it prematurely drags in.

---

## Game 1 — Five Hundred

### Variant to formalize, and why

**Four-player partnership Australian 500, 43-card deck, play to 500.** This is
the canonical, best-documented 500 and sits squarely in the corpus's partnership
trick-taking family (Spades, Pinochle, Doppelkopf). The 6-player/45-card and
3-player solo variants are less standard and add players/deck surface without
new *mechanism*; the partnership 4-player game isolates the target mechanics
(the misère/open-misère contracts) cleanly.

Deck (43 cards): `A K Q J 10 9 8 7 6 5 4` in the red suits, `A K Q J 10 9 8 7 6
5` in the black suits, plus one joker (11+11+10+10+1).

### Deal, kitty, bidding

- **Deal** 10 each + a 3-card **kitty** face down (batches of 3 / kitty 1 / 4 /
  kitty 1 / 3 / kitty 1).
- **Bidding ladder** (lowest→highest), each bid a contract of *tricks × suit*:

  | Tricks | ♠ | ♣ | ♦ | ♥ | No-trump |
  |---|---|---|---|---|---|
  | Six | 40 | 60 | 80 | 100 | 120 |
  | Seven | 140 | 160 | 180 | 200 | 220 |
  | Eight | 240 | 260 | 280 | 300 | 320 |
  | Nine | 340 | 360 | 380 | 400 | 420 |
  | Ten | 440 | 460 | 480 | 500 | 520 |

  **Misère** = 250 (legal only after someone has bid seven; ranks above 7-bids,
  below 8-bids). **Open misère** = 500 (ranks between 10♦ and 10♥). Ties at equal
  value break No-trump > ♥ > ♦ > ♣ > ♠.
- **Kitty pickup:** the contractor picks up the 3 kitty cards *without showing
  them* and discards any 3 face down — Skat's `pick_up_skat` shape exactly.

### Trump / card ranking — the bowers (and the joker)

With a trump suit: **joker (top) > right bower (jack of trump) > left bower
(other jack of same colour) > A > K > Q > 10 > 9 > …**. The left bower "behave[s]
in all respects as [a] member of the trump suit" — it changes **effective suit**
for following, beating, and leading. The trump's same-colour off-suit therefore
"has no jack".

**The joker in No-trump (and misère / open misère) is not simply a lone top
trump** — it belongs to no suit and carries its own decision and legality
surface:

- "A contractor who holds the joker can nominate which suit it belongs to. The
  nomination must be made at the start of play, before the lead to the first
  trick. The joker then counts as the highest card of that suit" — a
  **pre-play suit-nomination decision node** for the contractor.
- A non-nominated joker may be *led* with a lead-time suit nomination "which
  the others must play if they can, provided that this suit has not previously
  been led"; "once all four suits have been led, it is illegal to lead the
  joker, except to the last trick."
- Played to someone else's lead, "you can only play the joker if you have no
  cards of the suit led" — and in misère "you **must** play the joker if you
  have no cards of the suit led."

### The hidden-information moments — misère is played three-handed, then (if open) revealed

In **any** misère contract, the contractor plays **alone**:

> "If the contract is Misere or Open Misere, the contractor's partner does not
> take part in the play, but puts his cards face down on the table."

So tricks are played three-handed for the whole contract, and the partner's
ten cards sit face down on the table — an **inactive, still-hidden hand** that
is itself information-set-relevant: every observer's candidate set over the
live hands must exclude those ten unknown cards without ever learning them.

Then, for open misère only:

> "If the contract is Open Misère, after the first trick has been played, the
> contractor arranges his cards face up on the table for all to see, and plays
> the rest of the hand with his cards exposed."

The reveal is a **full common-knowledge reveal** to every observer identically,
after trick 1. It is *not* unequally observed. See the analysis section.

### Scoring / game end

Contractors making their bid score the table value; opponents score 10 per trick
they take. Failing scores *minus* the contract value (opponents still score 10
per trick). Misère/open-misère: the table value (250/500) for taking *no* trick,
minus it for taking any; opponents score nothing either way. Slam under 250 →
250. Game ends at **+500** (win) or **−500** ("out the back door", loss).

---

## Game 2 — Belote

### Variant to formalize, and why

**Plain four-player partnership Belote, 32-card deck** (from `jass/belote.html`).
**Not Coinche.** Coinche (Belote Coinchée) adds a doubling/redoubling contract
auction — a layer already fully covered by Bridge's `double`/`redouble` auction
surface, and orthogonal to the mechanics that make Belote interesting here
(constrained follow, in-play declarations, belote/rebelote). Implementing plain
Belote first isolates those; Klaverjas (Dutch near-twin) is then a delta, exactly
as [_candidates.md](../games/_candidates.md#belote) recommends.

Deck: `A K Q J 10 9 8 7` per suit.

### Two rank orders and their point values

- **Trump:** `J(20) > 9(14) > A(11) > 10(10) > K(4) > Q(3) > 8(0) > 7(0)`.
- **Plain:** `A(11) > 10(10) > K(4) > Q(3) > J(2) > 9(0) > 8(0) > 7(0)`.

Note this is a **within-trump rank *reorder*** (J and 9 promoted) — *not* an
effective-suit remap. The trump jack stays a trump of its own suit; nothing
changes colour. This is strictly *less* demanding than Skat, which lifts all four
jacks out of their suits into a trump class — a shape the corpus already handles.

### Deal and the two-phase bid

Deal 3 then 2 to each; turn one card face up. Player to dealer's right bids
first: **take** (accept the turned suit as trump) or pass. If all pass, a second
round lets a player **name any other suit**. The taker gets the turned card + 2
more; each other player gets 3 more. A compact Euchre-shaped auction, simpler
than 500's ladder.

### Follow / overtrump obligations (the constrained-follow family, in a new shape)

Quoted:

> "If a player is unable to follow to a non-trump suit, and an opponent is
> currently winning the trick, he must trump if he can, otherwise he may discard
> any card. If his partner is currently winning the trick he is free to either
> trump, or discard any card."
>
> When a later player cannot follow and an opponent has trumped, they "must
> overtrump if possible. If holding trumps but unable to overtrump, they must
> still play a trump" (undertrump / "pisser").
>
> Exception: "If the fourth player is unable to follow suit to a plain suit lead
> which his partner has already trumped … the fourth player may either discard
> (even if he holds trump) or overtrump."

This is a follow-legality predicate that reads **the current trick's winning card
*and* the acting player's partnership** — richer than any corpus follow predicate,
but the same *shape* as Pinochle's "follow, trump and over-trump if able" (which
already reads trick state). See new-surface analysis.

### The declarations — what is spoken vs shown (verified)

> "Each player makes his declaration(s) at the moment he plays his card during
> the first trick, saying '4 kings', 'sequence of 4', etc. After the first
> trick, only the team holding the highest declaration scores any declarations."

Sequences (same suit, descending): 3→20, 4→50, 5→100. Carré (four of a kind):
Jacks 200, Nines 150, A/10/K/Q 100.

**The comparison protocol is fully verbal** (this is the load-bearing fact for
structural-infoset-proofs):

> "If the highest sequence announced by each side is equal, the first announcer
> in rotation specifies the highest card of the sequence, and the next announcer
> either specifies his highest card if it beats the opponent's, or says 'good!'
> if it does not."

The cards "remain in hand unless challenged." Losers **do not reveal**. The
winning team must show **only if asked**, as truthful verification — the outcome
is already decided by the spoken comparison. Order: longest sequence > highest
top card > trump status > rotation.

### Belote / Rebelote

Holder of trump K+Q says **"Belote"** on playing the first and **"Rebelote"** on
the second — two announcements across two separate tricks, worth 20 regardless of
other declarations. The K and Q are ordinary trick plays (already `identity` to
all in `trick_pile`); the announcements are pure public facts riding those plays.

### Scoring

Card points in tricks + declarations, per team. **Dix de der** (last trick) = 10
(hand totals 162). **Capot** (all tricks) = 100 instead of the 10 (total 252 +
declarations). Contract: the taking team makes it if its points ≥ the opponents';
if *dedans* (fewer), opponents score 162 + all declarations.

---

## Analysis — mapping onto the kernel

### (1) Which construct carries the unequally-observed outcome, and what it emits

The decisive finding for **knowledge-events**: in *both* games the "unequal"
resolution decomposes into **all-observer** observation events. Nothing needs a
per-observer-differentiated phase-outcome emission. The only asymmetry is *which
hidden cards remain hidden*, and that is the standing zone projection, not a
phase outcome.

**500 open misère** → after trick 1, `reveal(hand[declarer], observers = all)`
inside the play `round`, then exposed play as ordinary movements. Every observer
gets `identity` simultaneously. This is the *Coup category* — a common-knowledge
reveal — which [knowledge-events.md](../open-questions/knowledge-events.md)
already records as *not* forcing the question. The three-handed play is the
existing participants axis (the ring predicate excludes the contractor's
partner), and the partner's face-down hand never emits at all — it stays at the
hand zone's default others-projection for the rest of the contract. Sketch:

```text
round offering [play_card] from leader
      over players where not (is_misere and player is partner_of_declarer)
      until <hands empty>
      // ... after the first trick resolves:
if is_open_misere and tricks_played is 1 {
  reveal hand[declarer] to all        // identity to every observer, equally
}
```

**Belote declarations** → each play in the trick-1 `round` optionally carries
`announce(<declaration_type_and_top_card>, all)` — a public *claim* (a state
variable, per decisions.md "a public assertion is a state variable *because* it
is public"). The winner-take-declarations resolution reads those public claims;
belote/rebelote are `announce(..., all)` on the trump K/Q plays; the losing
team's cards are simply never revealed and stay at `hand`'s owner projection.

Per-observer emission in both cases: **to every observer, the same announces and
the same (conditional) reveal**. The unequal *residue* (500's pre-reveal hidden
hand; Belote's unshown losing melds) is carried by the standing `hand` zone
projection, exactly as CLAUDE.md's model predicts. **This closes
knowledge-events** — the reduction the Tier-4 question was waiting to confirm,
now exhibited by a real in-play case (Belote) rather than argued.

### (2) Does either supply the compound hidden-function probe? — No.

structural-infoset-proofs needs a *public outcome that is a non-trivial function
of still-hidden state*, defeating any simple swap axis (its own examples: "how
many red cards do you hold", a sum-capture reveal, a partial-information bid
comparison).

- **500: no.** [_candidates.md](../games/_candidates.md#500) already calls it —
  "full reveal, not a function". Open misère reveals the *entire* hand; before
  the reveal it is an ordinary hidden hand; the misère win/loss reads only public
  trick captures. No public outcome reads still-hidden content. A swap of the
  pre-reveal hand replays to an indistinguishable world (nothing public depends
  on it yet), so it defeats no axis.
- **Belote: no (verified).** The tempting probe is "highest declaration scores,
  losers never show" — a partial-information comparison. But the fetched protocol
  resolves the comparison **by spoken announcement of type and top card**, so the
  public outcome (who scores) is a function of the *announcements*, not the hidden
  cards. Swapping a loser's concealed cards does not move the public outcome,
  because the outcome was computed from what was said. There is no legally-
  replayable-but-distinguishable world here. Belote thus gives **nothing beyond
  Pinochle's melds** for this question.

Consequently the constructive world generator's blocking data point is **not**
supplied by either candidate. **Cheat** — where the challenge outcome is a public
boolean function of genuinely face-down cards, then a reveal, and claims may be
*false* — remains the only clean witness in the pipeline
([_candidates.md](../games/_candidates.md#cheat)).

### (3) Mechanics with no existing kernel/grammar fit — the new-surface cost

**500 (heavier, and mostly *not* one of its advertised unblocks):**

| Mechanic | Fit | New-surface cost |
|---|---|---|
| Bidding ladder (25 suit/level bids + misère + open-misère + no-trump, strictly ordered) | Auction `round`, Bridge/Skat shape | Moderate: a large ordered bid vocabulary + a game-local ladder-ordering primitive (Skat's `skat_next_bid` precedent) |
| Kitty pickup + 3-card discard | `pick_up_skat` verbatim | None |
| Misère inverse scoring (declarer wants 0 tricks) | Scoring expression `if declarer_tricks is 0` | None — Hearts' shoot-the-moon precedent |
| No-trump contract | Follow-class variant (Skat's Null template) | Low |
| Open-misère exposed play | `reveal(..., all)` + ordinary movement | Low |
| Misère played three-handed (partner sits out, hand face down) | Participants predicate on the play ring (Getaway/Stud shape) | Low-moderate: the shrunk ring is an existing axis, but the sat-out hand is a **mid-contract inactive face-down hand** — a zone that stays at its hidden projection while its owner takes no turns. Modelable as-is (`hand[partner]` simply never moves or emits), but it is an information-set-relevant object the readiness proofs must cover: every observer's partition must keep those ten cards hidden-but-excluded for the rest of the hand, and trick-winner/lead logic must skip the seat. A new proof wrinkle, not new grammar. |
| **Bowers: left bower changes effective suit** | **No fit** | **High — and it is Euchre's job.** Contextual rank *and* effective-suit remap keyed to runtime-chosen trump is the unsolved hard axis of [special-cards-declaration](../open-questions/special-cards-declaration.md); Euchre is its designated witness. 500 inherits it in the base rules. |
| Joker in No-trump / misère: pre-play suit nomination + lead-time nomination + no-suit legality | Nomination ≈ Skat's `declare_suit` one-draw round; the rest has **no clean fit** | **Moderate-high, previously undercounted.** Three pieces: (i) a contractor-only pre-play decision node ("nominate which suit it belongs to… before the lead to the first trick"); (ii) a *lead-time* nomination when the joker is led un-nominated ("a suit which the others must play if they can, provided that this suit has not previously been led") — a card play carrying a suit parameter, plus led-suit history as state; (iii) follow/lead legality for a card of **no suit** ("only… if you have no cards of the suit led"; *must* play it in misère; illegal to lead once all four suits have been led, except the last trick). (ii)+(iii) are the effective-suit problem again in a second costume — the joker's follow-class is contract- and nomination-dependent — compounding the bower work. |

**Belote (lighter, mostly *precedented*):**

| Mechanic | Fit | New-surface cost |
|---|---|---|
| Two-phase take/name auction + turned card + asymmetric redeal | Compact auction `round` (Euchre shape) | Low |
| Trump rank *reorder* (J,9 promoted within trump) | Game-local trick-winner primitive | Low — *less* than Skat's jacks-out-of-suit, already in corpus |
| Constrained follow: must-trump / must-overtrump / undertrump / 4th-player-partner-trumped exception | Movement `where` predicate reading trick winner + partnership | **Moderate — the genuine new shape.** Same *form* as Pinochle's follow-and-overtrump predicate, but the richest instance in the corpus (reads who is currently winning *and* partnership). Expressible within existing grammar. |
| Sequence / carré recognition | Game-local scoring primitive | Low — **precedented by Pinochle's `pinochle_meld_value` / `has_marriage`** runtime primitives; not new grammar |
| Declaration timing + highest-scores comparison | trick-1 `announce` per play + a comparison over public claims | Moderate: fiddly but pure public-claim bookkeeping |
| Belote/Rebelote | `announce(..., all)` on trump K/Q plays | None |
| Partnerships, team piles, team scoring | `partnerships:`, `team_of`, `TeamPile` | None — Spades/Doppelkopf/Pinochle precedent |

Belote's new surface reuses existing corpus machinery almost throughout; its one
genuinely-new demand (the constrained-follow predicate) is a harder instance of a
*shape the corpus already has*. 500's new surface includes the **unsolved**
effective-suit-remap axis, which is not one of its two advertised unblocks and
which belongs to Euchre.

### (4) Recommendation and runner-up disqualifiers

**Recommend Belote (plain, four-player partnership, no Coinche)** between the
two. Three independent tiebreakers, each supported above:

1. **knowledge-events:** Belote's in-play declarations + belote/rebelote are the
   *rich* witness that closes the Tier-4 question by exhibiting the reduction to
   `announce` + conditional all-observer `reveal`. 500's open misère is the
   *weakest* witness — a full common-knowledge reveal, the Coup category that
   already failed to force the question.
2. **structural-infoset-proofs:** a wash at *nil* — neither supplies the probe —
   so this does not favour 500, and Belote at least exercises a partial-
   information comparison shape (even though, verified, it resolves publicly).
3. **New surface:** Belote reuses precedented patterns (Pinochle melds &
   overtrump, Skat trump-rank primitive, partnership machinery); 500 drags in
   Euchre's unsolved bower/effective-suit-remap axis in its base rules.

**500's disqualifiers as the "two-unblock" pick:**

- Its knowledge moment (open misère) is a **full common-knowledge reveal, not
  unequally observed** — [_candidates.md](../games/_candidates.md#500) itself
  flags "full reveal, not a function," and Coup already showed this category does
  not force knowledge-events.
- It contributes **nothing** to the high-impact structural-infoset question (a
  total reveal is not a hidden function).
- It forces the **effective-suit-remap bower axis** — the hardest open item in
  [special-cards-declaration](../open-questions/special-cards-declaration.md) —
  which is Euchre's designated witness. Tackling it first inside 500, wrapped in
  a large bid ladder, is the wrong place to solve it. **500 is Euchre's sequel,
  not its predecessor**; it should wait until Euchre settles the bower design.
- The joker's No-trump/misère behaviour (pre-play nomination decision,
  lead-time nomination against led-suit history, no-suit follow legality) is
  the effective-suit problem in a second costume, and misère's three-handed
  play adds a mid-contract sat-out face-down hand the readiness proofs must
  cover — both raise 500's cost beyond the first draft of this decision brief, and
  neither serves either advertised unblock. The recommendation is unchanged;
  these corrections only widen Belote's margin.

### Honest caveat on the whole framing

The roadmap's "one game, two unblocks" oversells both candidates. Verified:

- The **high-impact** unblock (structural-infoset-proofs, Tier 2, *actually
  blocked*) is served by **neither** — **Cheat** is the game for it, and if that
  question is the priority, Cheat should be sequenced ahead of both 500 and
  Belote.
- The **low-impact** unblock (knowledge-events, Tier 4) is *corroborated and
  closable*, most convincingly by Belote — a real but modest deliverable.

So the strongest case for Belote is **corpus value** — it adds the major
Jass/Belote family, the continental melding tradition, and the richest
constrained-follow instance in the corpus — *while also* closing knowledge-events
and exercising (harmlessly) the partial-information-comparison shape. It is a
good next game. It is not a shortcut to the Tier-2 unblock, and the decision
should not be made on the belief that it is.

### Where Pagat contradicted the open-question files' assumptions

1. **knowledge-events.md (lines 15–19)** lists "500 (open misère reveals the
   declarer's hand mid-phase)" among games that exhibit "the resolution *itself*
   … seen differently by different observers." Pagat: the open-misère reveal is
   to **all observers identically** (a common-knowledge lay-down after trick 1).
   It is *not* seen differently by different observers — it is the same category
   as Coup, which the same file already records as *not* forcing the question.
2. **roadmap.md item 1** ("plausibly also the compound hidden-function probe …
   one game, two unblocks") and **_candidates.md** (Belote "plausibly" for
   structural-infoset). Verified Pagat: Belote's declaration comparison is
   resolved by **spoken announcement** of type and top card; the public outcome
   reads public claims, not hidden cards. Belote supplies **no** hidden-function
   probe. The "two unblocks" claim does not survive the fetched rules for either
   candidate on the high-impact question.
3. Minor: **_candidates.md #500** flags misère inverse scoring as a "second data
   point beyond Hearts' shoot-the-moon." Accurate — no contradiction, noted for
   completeness. Two 500 mechanics the candidate entry does not mention at all:
   the joker's No-trump/misère nomination-and-legality surface, and misère being
   played three-handed with the partner's hand face down on the table (both
   quoted in the 500 section above).
