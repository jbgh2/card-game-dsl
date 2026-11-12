## Joint-predicate selection

A transfer's per-card `where` filter tests each candidate alone —
`chosen K cards where <pred>` can never say "these K cards *together* form a
valid group," which is the load-bearing test of every meld-family game. The
joint form binds **`cards`** — the candidate *set*, a card collection — and
the selection becomes ONE decision over the source's satisfying subsets.

The predicate ROOTS IN A CALL, and that root is what lets the form reach
OpenSpiel: joint candidates are card subsets — what the combo block deals in,
exactly like climb combination plays — and their universe is not derivable
from the predicate's text, so it comes from a **registered per-predicate
codec** (`cardlang/runtime/primitives.py`, `joint_codec_function`, the
climb-engine codec pattern). That codec is engine Python, keyed by the root
call's name: Gin's `gin_valid_meld` and `gin_arrange_ok` both name the
329-meld universe of standard52. The front end accepts an inline predicate;
the refusal comes at action-space construction — loudly, never as a silent
absence from the space — and a root call no codec is registered under is
refused in the same place. Where the subsets cannot be encoded at all,
because the deck holds duplicate identical cards and the combo block's
frozenset canonicalization collapses copies, the shape is the
announce-then-stage decomposition instead
("Meld groups: flattened zone families" below, Canasta's
`stage_card`/`close_meld`). That wall and the remaining codec walls — a game
mixing climb and joint selections, two joint predicates wanting different
codecs — are recorded in [roadmap.md](../roadmap.md), "Grammar surface deferred
by the checker".

```cardlang-fragment jointly_selection
as arranger {
  move chosen some cards from hand[arranger]
       where jointly gin_valid_meld(cards) to waste
}
```

The amount picks the subset sizes: `some` (any non-empty size — the joint
predicate owns the size constraint), an expression (exactly that size), or
the degenerate `one`/`all` (size 1 / the whole source). Subset sizes are
always at least one — a zero-card "choice" is not a decision — so a
non-positive count, and `all` over an empty source, fall to the same loud
no-satisfying-subset error `some` gives. (Transfer amounts generally are
guarded at evaluation: a negative amount is a typed runtime error everywhere
— a Python slice would otherwise silently move the rest — and a zero
`chosen` amount is a vacuous decision node, also refused.) `jointly`
requires `chosen` — the selection is a player decision over subsets; a
dealt joint selection has no decider and a `random` one has no corpus user
(both rejected loudly, recorded in
[roadmap.md](../roadmap.md), "Grammar surface deferred by the checker") — `some`
requires `jointly`, and `to each` is rejected under `jointly` (it would
silently make every destination seat its own subset decider; recorded).
Enumeration is deterministic (sizes ascending, combinations in source
order) and bounded: a source pool past 16 cards is a loud runtime refusal,
not a hang. No satisfying subset is the no-implicit-actions error: guard
the transfer so it is only reached when one exists.

Gin Rummy's showdown arrangements are the anchor: the knocker declares
melds one joint selection at a time, each guarded so the remaining hand
still arranges to a legal knock — every reachable arrangement stays legal,
random play included, while equal-deadwood arrangement *choices* (which
change what the defender can lay off) remain real decisions. Persistent
meld *objects* (shared growing team piles, per-group scoring) are not a
construct at all — see "Meld groups: flattened zone families" below.
