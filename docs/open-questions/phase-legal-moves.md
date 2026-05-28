# Phase legal_moves

**Tier 5 — cosmetic, no design risk.**

A phase declares `active_rules`. The legal move types are derivable
(each rule constrains a move type). Should `legal_moves` be:

(a) Derived automatically from `active_rules`
(b) Stated explicitly for readability
(c) Stated explicitly for *additional* legal moves not constrained
    (moves with no rule constraints that are still legal)

Most likely (c) — derived by default, explicit only for
unconstrained legal moves.
