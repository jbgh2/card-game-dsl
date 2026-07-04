# A card-group (meld) construct

**Tier 2 — high impact, blocked on a corpus-quality anchor game.** Three
data points now exist on the same missing shape — the corpus-first threshold
for a mechanic:

- **Pinochle** (corpus): melds as *scoring* over a static hand — expressed
  today with four near-identical rule bodies whose repetition
  [library.md](../library.md) already flags.
- **Gin Rummy** (stress branch): melds as *live, owned structures* — the
  encoding models three meld slots as separate zones with per-slot validity
  helpers written three times, because functions cannot take a zone
  parameter and nothing represents "a group of cards with a joint
  predicate."
- **Canasta** (stress branch): melds as *shared, growing, team-owned piles
  keyed by rank* — wanting a `(team, rank)`-indexed zone family (zone
  families take exactly one index) plus wild-card composition rules per
  group.

(Stress-branch evidence: `stress-test/broad-sweep`,
`stress-test/FINDINGS.md`.) The common shape: a **named group of cards with
a joint validity predicate** (same-rank set / consecutive run / wild-card
limits), an owner, visibility, and per-group scoring. Today each game
re-derives it from zones + triplicated helpers, and the *joint* part — "these
K cards together form a valid run" — is genuinely inexpressible, because
`chosen K cards where <pred>` filters each card independently.

## Why it matters for the stated goals

The rummy family (Gin, Canasta, Rummy 500, Contract Rummy…) is one of the
largest game families outside trick-taking; today every member pays the same
tax. A meld construct would also subsume two gaps the sweep filed
separately: joint-predicate selection (for forming the group) and
multi-index zone families (for holding them). And melds are public knowledge
structures — first-class groups give the projection model a natural unit
("the meld's identity is public, the hand it came from stays hidden") that
zones currently approximate.

## The options

- **A `meld` zone-like declaration.** Groups as first-class zone contents:
  declared validity predicate (checked at formation and extension), owner,
  projection, and comprehension access for scoring. Largest design; covers
  all three data points.
- **Joint-predicate selection only.** Add "choose a *set* of K cards
  satisfying `<joint pred>`" and keep representing melds as zones. Cheaper;
  fixes formation but leaves the (team, rank) indexing and the triplicated
  validators untouched.
- **Defer until a rummy-family game enters the corpus properly.** The
  stress-branch encodings are breadth probes, not spec-grade anchors; the
  design wants a real game file to be written against.

**Current recommendation: defer, with Gin Rummy as the named forcing
function.** Gin is already in [games/_candidates.md](../games/_candidates.md)
and is the smallest rummy-family game; promoting it to the corpus is the
natural trigger to design the construct, starting from the joint-predicate
selection primitive (which Casino's sum-capture also wants) and growing to
first-class groups only if Gin still needs them.

Related: [library.md](../library.md) (Pinochle's flagged meld repetition —
the corpus-side data point); [decisions.md](../decisions.md) "The operation
vocabulary" (where a joint-selection mode would live);
[games/_candidates.md](../games/_candidates.md) (gin-rummy, canasta).
