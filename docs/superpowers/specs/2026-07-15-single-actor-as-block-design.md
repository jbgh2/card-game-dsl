# The `as <player> { … }` block — design

**Settles the single-actor-binding question (formerly Tier 1) and roadmap
"next steps" item #1.** Adds the first-class binder for a single named player's
decision, and rewrites the corpus idiom it replaces. On sign-off the open
question was promoted into [decisions.md](../../decisions.md) "Single-actor
decisions: the `as` block" (maintaining.md rule 3) and its file deleted.

## The problem this fixes

The only way the language can direct a `chosen` movement at one named player is a
`for each player p: if p is <who> { … }` loop — `chosen` needs an actor binding,
and `for each player` (via `ctx.acting_as(p)`) is one of the only statement
constructs that supplies one. Two defects follow:

1. **It silently breaks `actor`.** `for each player p:` rebinds the acting player
   for its body, and `actor` *reads* the acting player, so `if p is actor { … }`
   is true for **every** `p`. There is no wall; it type-checks and runs.
2. **The guarded-loop shape re-reads its guard mid-pass.** When the body mutates
   the guard variable, a *later* player in the same pass can re-match. Cribbage's
   pegging (`for each player p: if p is active`, whose body reassigns `active` on
   every path) hits this: the loop runs a second player's turn inside one pass.

An `as` block fixes both at the root: it evaluates its player expression in the
**outer** context and *then* rebinds, and runs its body **once**. So
`as actor { … }` is idempotent, `as challenger { … }` reads the state var, and
neither can be captured or re-matched.

## The construct

```
as <player-expr> { <statement>* }
```

- **Grammar** (`cardlang/grammar/cardlang.lark`): `as_block: _AS_KW expr "{" statement* "}"`
  with an anchored keyword terminal `_AS_KW: "as" /(?![A-Za-z0-9_-])/`, mirroring
  the existing `_IS_KW`/`_NOT_KW`. The `-` in the lookahead is load-bearing: it
  keeps `as` from lexing as a prefix of `as-equally-as-possible` (Getaway) or of a
  statement-leading identifier (`assets := …`). `as` is statement-leading, so it
  does **not** join the `NAME` value-keyword exclusion.
- **AST**: `AsBlock(player: Expr, body: tuple[Stmt, ...], span)`, added to the
  `Stmt` and `AstNode` unions.
- **Semantics** (`runtime/execute.py`): evaluate `player` in the outer ctx → a
  `Player`; `ctx.acting_as(player)`; run the body as a **block scope** (bindings
  do not escape, like `Block`; state writes and card moves persist); return the
  original ctx. Identical `acting_as` code path to the loop idiom — **it emits no
  new observations.** Its only effect on the OpenSpiel target is a strict
  improvement: the decision-node chooser is statically readable instead of
  predicate-derived. Derived information sets are unchanged.

## Totality (surface-totality-audit)

- **Exhaustive dispatch.** Every `match` over statements ending in `assert_never`
  (resolve, typecheck ×4, ir, deckcheck, execute) gains an `AsBlock` arm —
  mypy-forced, so no site is silently missed.
- **Non-Player player-expr → static reject** in typecheck (`assignable(t, Player)`,
  keeping the Integer-stands-for-player leniency of `dealer : Player = 0` and
  zone-family indices, for consistency).
- **Body** = plain block; admissibility identical to an `if` body — no bespoke
  restriction. Non-local control flow (`produce` / `continue to` /
  `skip to next hand`) propagates through `as` to the enclosing construct, exactly
  as through `if` / `for each`.
- **Procedure interaction: no new wall.** Procedure hygiene is by-value in
  `expand.py` (arguments become caller-context `let`s), so `as <param> { … }`
  reading the parameter is already safe — this is what makes Coup's rewrite clean.
- **Rejection tests**: non-Player expr; unknown name; `as-equally-as-possible`
  still parses (parse test); nested `as`; empty body.

## Corpus migration (lockstep)

Rewrite every single-actor identity-guard site to `as`. All are byte-identical
except Cribbage (below).

| Game | Sites | Rewrite |
|---|---|---|
| French Tarot | chien discard | `as taker { … }` |
| Doppelkopf | 4 trick plays | `as leader / s2 / s3 / s4 { … }` |
| Schnapsen | follower answer ×2 | `as fol { … }` |
| President | card return | `as president { … }` |
| Skat | 3 trick plays | `as leader / second / third { … }` |
| Coup | `lose_influence` procedure | `as victim { if alive[victim] and influence[victim] is not empty { … } }` |

**Cribbage** (pegging, line 82) is also byte-identical, and instructively so. Its
body reassigns the guard variable `active` on every path, so the old loop
double-executed — a `for each` pass starting at `active = 0` ran *both* players'
turns (measured: 2494 of 4159 passes ran two decisions). But because `active`
alternates identically either way, the loop's two-turns-per-pass and `as active`'s
one-turn-per-pass produce the **same flat decision-and-score sequence** — verified
0 diffs over 300 seeds. So the rewrite is a pure clarity win: it removes a
confusing benign double-execution without changing observable play.

**Left alone** (genuine iteration, not single-actor): French Tarot's scoring loop
(`if p is taker { + } else { − }`), Cribbage's all-players crib discard,
Tichu's `if q is not p`.

## Gates

`mypy` (bare) + full `pytest -q` green; goldens and `tests/openspiel_ready/`
byte-identical **except** Cribbage's justified golden update; surface-totality
audit artifacts (rejection tests + completeness ledger) shipped with the change.
