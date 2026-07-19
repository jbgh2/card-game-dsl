# Knowledge events

**Tier 4 — low impact, defer until forced.**

What happens to knowledge when a phase produces multiple possible
outcomes that observers do not observe identically? Probably
reduces to the existing observation-event story but worth
confirming when a concrete case arises.

**Coup (examined, did not force it).** Coup's challenge resolution was
the expected canonical case — but its outcomes turn out to be *common
knowledge*: every observer sees who challenged, who lost influence, and
the revealed card. The only private residue, the claimant's replacement
card, rides the ordinary `deal` projection, not the phase outcome. So
Coup reduces to the existing observation story trivially and does *not*
exhibit a genuinely unequally-observed phase outcome.

**500 (in corpus, examined — did not force it).** Open misère's
mid-play reveal — after the first trick the declarer's whole hand
becomes public for the rest of the play phase
([games/five-hundred.md](../games/five-hundred.md)) — composes entirely
from existing machinery: the reveal is a plain movement into a
`PublicHand` zone (`exposed[declarer]`), so the visibility flip is
carried by the standing zone projections plus the movement observation,
and every opposing information set contains the revealed cards with no
new epistemic construct (proven, including the no-over-reveal converse
for non-open contracts, in `tests/openspiel_ready/test_five_hundred.py`).
What the data point establishes: a mid-phase visibility flip of a
private zone, observed *equally* by all, is zone relocation — not a
knowledge event needing surface. Like Coup, it is common knowledge, so
the question narrows rather than closes: the genuinely
unequally-observed resolution still awaits a dedicated-deck game
(Mascarade, Love Letter — out of scope).

**Belote (implemented — corroborates the reduction, with one sharp
lesson).** Belote's mid-play declarations and Belote-Rebelote
([games/belote.md](../games/belote.md)) are the richest in-play
knowledge events in the corpus, and they compose from existing ops with
NO new observation surface: the announcement is a decision whose
**content rides the move name and Rank parameter**
(`declare_tierce_trump(A)` — the Doppelkopf announcement-vocabulary
shape), the comparison runs over those public claims, the entitled
side's showing is a loop of guarded one-card `reveal`s over the
combination's cards, Belote-Rebelote is an `offer` on a public gate
whose acceptance `reveal`s the partner card still in hand, and the
losing side's unshown cards are the private residue riding the standing
`hand` projection. Every emission is to all observers identically —
the "unequal" part is only *which hidden cards stay hidden*, exactly
the reduction this question was waiting to see in play. Two findings
for whoever closes the question:

1. **Announced content must live in the announce event, not in state.**
   Phase state does not reach a paused information state (frames
   unwind), and the announce event carries only the move's rendering —
   so a nullary "declare" whose effect writes hand-computed values to
   public state runs fine but leaves observers' derived info sets
   without the announced facts. The composition rule is: fold the
   content into the move vocabulary (name + closed parameter domains).
   That is composable, but it bounds the *payload*: one
   (kind, height, trump) triple per decision fits the closed
   `Rank`-parameter domain; Belote's multi-combination announcements
   ("tierce, tierce") do not fit one decision and are scoped to the
   best combination per player (belote.md, "Scope and departures").
   A first-class `announce <fact>` op (catalogued in library.md,
   unbuilt) with a typed computed payload is what would lift that
   bound.
2. **Conditional-reveal dialogues stay out of reach of pure
   composition.** The reference's minimal-information comparison
   ("how high?" asked only on equal lengths, "good!" conceding —
   height surfacing only when forced, trump status only on a height
   tie) is a *negotiation* whose reveals are gated on another player's
   private response. It is expressible as more decision vocabulary,
   but only by over-announcing (Belote announces height and trump
   flag unconditionally) or by building the dialogue's decision tree
   out longhand. No existing op expresses "reveal the minimum that
   settles the comparison".
