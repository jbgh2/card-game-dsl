## Rule exemption (`exempts:`)

A rule may declare `exempts: <card-set expr>` alongside (or instead of)
`demands:`. When the rule's `applies_when` holds, the cards it selects sit
**outside the demand cascade entirely**: no other rule's `demands` can narrow
them away, they never count toward satisfying an obligation, and — when the
rule `constrains` a move — they are legal candidates offered **after every
other legal card**, in hand order, regardless of where they sit in the hand.

This is a distinct axis from `demands:`, not a special case of it. A card-set
`demands` can only *narrow* the running candidate set (`rules.legal_cards`'s
per-rule intersection); it has no way to *reorder* a card to the end of the
result regardless of hand position. French Tarot's Excuse needs exactly that:
it is never subject to follow-suit/trump/over-trump, never able to satisfy
one, and must be offered last — reproducing the reference implementation's
`base + excuse` candidate order, which the RNG stream depends on (a
determinized replay must draw the same candidate at the same list index).
Folding this into `demands:` (e.g. a "the demands union" trick, or
re-ordering the whole cascade's output) cannot express "exempt AND always
last" without special-casing the exempt cards somewhere — which is exactly
what a dedicated clause makes explicit instead of implicit.

Semantics (`cardlang/runtime/rules.py::legal_cards`): a pre-pass collects the
exempt set from every rule that `constrains` the move type in question and
whose `applies_when` holds; `working` is the hand minus that set; the demand
cascade runs over `working` exactly as before (unchanged code path); the
result is `working`'s narrowed survivors, in hand order, followed by the hand's
exempt cards, in hand order. A rule with no `exempts:` clause contributes
nothing to the exempt set, so a game that never uses this clause sees a
byte-for-byte identical result to before the axis existed (verified: every
pre-existing game's golden IR and characterization tests are untouched by its
introduction). `applies_when` gates exemption exactly as it gates a demand —
French Tarot's `ExcuseIsExempt` only exempts the Excuse once a suit has been
led (`state.led_suit is not none`), so the leader (who faces no obligations at
all) still sees their whole hand in its ordinary, unreordered position.
