---
term: Subset
definition: A set of cards drawn from one zone, enumerated as a domain rather than named. The binder of the subset forms (`any subset of 2 or more cards in table where …`) and the candidate of a joint selection are both Subsets; the two differ in what enumerates them, not in what they are.
layer: kernel
status: canonical
reserved: true
home: `ast/nodes.py` (`SubsetQuery`), `runtime/subsets.py`
see: [Candidate]
retired_spellings: []
findings: []
---

**Reserved word.** Approved compounds: Subset binder (the pronoun the subset forms bind), Subset query (either register of the construct), subset codec (the action-space encoding of a joint selection's candidates).

**Surface.** `subset` and `subsets` are keywords, and `subset` is the binder the
subset forms bind per candidate set — the domain noun's singular, as `card` is
the card queries'. Reserved here is a rule about PROSE, not about the parser: a
game may name a zone or a state variable `subset`, exactly as it may name one
`card` or `player`, and inside a subset query the binder shadows it by the
ordinary lexical rule. What the reservation binds is our own writing — never the
bare word where the sense is not obvious.

**Not the joint selection's `cards`.** `where jointly` binds `cards` to the
candidate set of a DECISION; a Subset binder ranges over an enumerated domain
inside an expression. The values are the same shape — a card collection that is
not a zone — so neither may stand where a zone is demanded; what differs is
that one is chosen by a player and the other is folded over.

**Bounded.** Every enumeration of a zone's Subsets goes through
`runtime/subsets.py`, which refuses a pool past its bound rather than walking
it. The bound is a fixed engine limit, shared by both constructs that
enumerate, so the number and the refusal cannot drift apart.
