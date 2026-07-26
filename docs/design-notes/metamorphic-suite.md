# The metamorphic suite: transformations the spec says are meaningless

**Status: implemented (T1/T2/T3/T5); T4 deferred.** This was the
implementation plan for the metamorphic testing work; the suite now lives
at `tests/metamorphic/` — see issue #127 for T4's deferral, the two real
findings the suite surfaced (both real `cardlang/` behaviors, not fixed by
this suite), and the reasoning for deferring T4 (suit relabeling cannot be a
pure `Game -> Game` AST transform — a suit's card membership lives in a
Python registry the parsed tree never carries). This file stays as the
original design record below: it described the goal correctly for the three
transforms that landed as designed (T1, T2, T5) and the one that landed with
a narrower domain than proposed (T3, single-witness — decisions.md "Named
procedures" is itself corpus-first, single-witness) — checking the runtime
against itself by pinning equivalences the spec already asserts implicitly.
A metamorphic check needs no second implementation: transform a game in a
way the spec says cannot change its meaning, replay both variants under the
same seed and the same scripted decisions, and require the traces to agree.
A failure is almost always a real bug — a meaning the pipeline attached to
something the spec says is meaningless: a name's spelling, declaration
order, a suit's identity, the `run`/inline distinction.

## Why this, and why before fuzzing

The differential harness covers one game (GOPS) against one hand-coded
oracle; the goldens pin byte-stability of specific traces, not *invariance*
under change. Between those two sits a class of bug neither catches: the
engine silently depending on something semantically inert. The by-value
expansion defect was exactly this class — `run f(x)` and its hand-inlined
body diverged — and it is pinned today only by its own regression test, not
by the general equivalence it violated. Metamorphic failures are near-always
real; a grammar fuzzer (see [grammar-fuzzing.md](grammar-fuzzing.md)) needs a
triage round to burn off uninteresting findings first. Hence the sequencing:
this suite first.

## Shape

Transforms are pure `Game -> Game` functions over the *parsed* AST (the
`dataclasses.replace` walk idiom of `cardlang/resolve.py` and
`cardlang/expand.py`), applied before resolve; each variant then runs the
ordinary pipeline once (parse → resolve → typecheck → expand →
deck-capacity). Re-running the checkers on an already-checked tree is not an
option — `resolve._instantiate_rules` splices stdlib rules into `game.rules`
and is not idempotent (a second pass treats the spliced rules as local
definitions shadowing the stdlib) — and single-passing each variant is also
the stronger test: the transform exercises the full pipeline, not just the
runtime. A transform whose output fails the pipeline is a harness bug and
fails loudly rather than corrupting the comparison. Playout runs through the
existing seams:
`runtime/driver.play_game` with a fixed seed and the deterministic
greedy-first chooser the readiness harness already uses, captured through the
one `Ctx.observer`/tracer choke point. Comparison is trace-level — the
sequence of decisions, movements, and the final `GameResult` — with a
per-transform `rename: dict[str, str]` hook applied to one side before
comparing (identity for transforms that rename nothing). A new
`tests/metamorphic/` package holds the pairing harness and one module per
transform, parametrized over the corpus glob; each module carries its
completeness ledger (domain: corpus games × seeds; registry: the corpus
glob). `PYTHONHASHSEED` is pinned in every paired playout — `legal_cards`
returns a set, and unpinned hash randomization makes trace comparison flaky.
The suite is additive proof machinery: no runtime changes, no golden churn.

## The four transforms

1. **α-rename.** Rename every zone, state variable, and (where a game names
   them) player/team identifier through a generated map; traces must be
   identical after applying the map to names embedded in events. Catches any
   site that switches on a name's spelling rather than its declaration.
2. **Inline-vs-`run`.** For every game and fixture with procedures: the game
   as written, against a variant whose `run` sites are replaced at *source*
   level by the procedure body with `let`-bound arguments — the expansion
   decisions.md "Named procedures" defines, performed textually. Identical
   traces required. The source-level splice is preferred over comparing
   against `expand`'s own output, which would share code with the thing under
   test; the choice is confirmed at implementation time.
3. **Suit relabeling.** Apply a suit permutation to the deck, every suit
   literal, and the initial conditions; the result must be the same game
   under the permutation (traces agree after mapping suits). This is the
   runtime-level cousin of the readiness proofs' suit-axis swap classes, and
   the admissible permutations are derived the same way: a game whose rules
   name a suit (Hearts) admits only permutations fixing it — computed from
   the game's suit literals, never hand-listed.
4. **Declaration reorder.** Permute declaration order where the spec says
   order is irrelevant (zones, state variables, move types, rules — each
   confirmed against decisions.md before inclusion; anything order-sensitive
   is excluded with a comment citing the spec section). Identical traces, and
   identical diagnostics over the rejection corpus (`tests/rejections/`).

## Acceptance

The suite runs in ordinary CI (a small fixed seed set per game, tens of
seconds), with an env-var knob for a longer local run. Done means: all four
transforms live over the whole corpus, each with its ledger; the
inline-vs-`run` regression test's invariant is subsumed by transform 2's
general form (the specific test stays — it is a rejection-shaped witness);
and any divergence found on the way is triaged wall/backstop/missing-wall
per decisions.md "Closed-domain completeness" before being fixed.
