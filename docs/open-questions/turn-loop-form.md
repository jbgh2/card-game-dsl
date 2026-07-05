# A `turns` form: the loop beneath the three round forms

**Tier 2 — high impact, blocked on a corpus-quality anchor game.** Surfaced
by the broad-sweep stress test (branch `stress-test/broad-sweep`,
`stress-test/FINDINGS.md`): seven of fourteen games — Palace, Durak, Cheat,
Ninety-Nine, Go Fish, Canasta, Gin Rummy — fit none of the trick / climb /
auction `round` forms and each hand-rolled the same turn scaffolding from
`repeat until` + `offer` + a current-player state variable. Counting rotation
operations (`offset_by`, `rotate`, manual cursor assignments) per file:
Ninety-Nine 10, Cheat 8, Palace 8, Durak 7, Go Fish 7. Every one of those is
a re-implementation of: advance to the next player, skip the
eliminated/empty-handed, decide where the termination check sits, and reset
the cursor at trick/pile boundaries.

That scaffolding is exactly where the sweep's runtime failures clustered
(the `repeat until` iteration-cap crash, off-by-one leader hand-offs), and it
is invisible to anything that wants to reason about the game statically: a
hand-rolled loop gives the kernel no uniform decision/observation site, where
the three `round` forms give it one per form.

By the corpus-first standard — a third data point forces a mechanic — a
*seventh* data point in a single sweep is the strongest forcing evidence any
library addition has had. What's missing is not evidence of need but a
corpus-quality anchor: the stress-branch files are breadth probes (several
audited `rules-faked` or `broken`), not spec-grade examples to design
against.

## The shape being asked for

Not a fourth trick variant — a *lighter* primitive the three round forms
could themselves be seen as configuring:

```
turns from <leader> over players where <participant-pred> [direction <dir>]
      until <termination> {
  ... body with the current player bound, e.g. as `actor` ...
}
```

with the rotation, participant filtering (re-evaluated per step, so
elimination falls out), and termination placement owned by the form — and
one uniform decision/observation site for the kernel, which is what the
OpenSpiel adapter and the info-set derivation actually consume.

## The options

- **Add the `turns` form to the library.** Direct; retires the scaffolding
  class of bugs; gives non-trick games the same derivation surface trick
  games already have. Design cost: the knob set (direction changes
  mid-loop, re-entry after interruption, nested turn structures like
  Durak's bout-within-hand) needs one real game to pin down.
- **Reframe the three round forms as configurations of `turns`.** Same
  construct, more ambitious: trick/climb/auction become library
  instantiations. Attractive long-term (one decision-site mechanism), but a
  refactor of working, byte-identical machinery — not to be done
  speculatively.
- **Defer.** Rejected as a long-term posture by the evidence volume, but
  acceptable until an anchor game exists in the corpus.

**Current recommendation: add `turns` when the first non-round corpus game
lands, and design it against that game.** President is the natural anchor
(cleanest stress-branch audit, exercises climb + roles + a manual outer
loop); Gin Rummy or Ninety-Nine would anchor the pure draw-play-discard
shape. Do not refactor the existing round forms onto it until it has two
corpus users of its own.

Related: [decisions.md](../decisions.md) "Round configuration vs rules" (the
existing forms' knob philosophy this form should follow);
[single-actor-binding](single-actor-binding.md) (the companion binder for
one-player decisions inside and outside loops);
[games/_candidates.md](../games/_candidates.md) (president, gin-rummy — the
anchor candidates).
