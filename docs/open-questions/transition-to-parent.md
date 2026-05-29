# Transition to parent

**Tier 3 — medium impact, narrow scope.**

A sub-phase that ends and returns control to its parent's enclosing
loop has no syntax in the corpus. The provisional form used in Tichu:

```
phase play {
  ...
  phase wish_active when active_wish != none {
    active_rules: [+ MustPlayWishedRankIfAble]
    transition_to: parent when active_wish becomes none
  }
}
```

Existing `transition_to:` triggers in the corpus go sibling →
sibling: Hearts' `hearts_not_broken → hearts_broken`, Spades'
`spades_not_broken → spades_broken`. The pattern is "switch to a
named peer." Tichu's wish sub-phase needs "fall out, resume the
parent's body where it left off" — a structurally different shape.

Design choices:

- **`transition_to: parent`** — explicit keyword. Reads naturally
  at the call site; matches the lexical-scoping framing in
  [decisions.md](../decisions.md) (the parent is the unambiguous
  enclosing scope).
- **`when active_wish becomes none` as an implicit exit
  condition** on the sub-phase, with no `transition_to` clause —
  the sub-phase ends when its `when:` predicate becomes false.
  Symmetric with `phase wish_active when ...` (the entry guard) and
  pulls the exit out of the body.
- **Make the sub-phase a `with` block** — `phase play { ... with
  wish_active: ... }` — explicitly scoping the modified rule set to
  a sub-region of the parent body. More invasive; the rest of the
  corpus uses `transition_to:` style.

Tichu is the only game in the corpus that needs this. A second game
with a temporary rule-set extension that ends mid-flow (some Skat
declaration phases come close) would clarify which form to commit.

Related: [per-player-sub-phases](per-player-sub-phases.md) — also
about a sub-phase whose lifetime is shorter than the parent's, but
the *closing condition* there is per-player rather than per-state.
