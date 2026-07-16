# Scope once: one binding walk for resolve and typecheck

**Status: proposal.** This is the implementation plan for the widest hole left
in the checker — roadmap.md, "A `let`-bound name has no static type, so any
wall reading it is blind" — reframed as what it structurally is: the engine
computes lexical scope twice, and the second computation is a partial copy of
the first.

## The two machineries

Resolve's `_rewrite` implements the language's *complete* scoping semantics:

- all binder-introducing node kinds, from the one registry
  (`_introduced_binders`, exhaustive over `Node`);
- per-field scoping (`_BINDER_SCOPE_FIELDS`: a comprehension's binder scopes
  over `body`/`filter` but not `source`);
- the sequential `let` fold (`_rewrite_value`: a `let` binds for the rest of
  its statement tuple, and an indexed `let`'s key binder only over its own
  value);
- per-declaration parameter isolation (move types, functions, procedures);
- produce-arm and derived-field scoping.

Its output records only the *classification* (`NameRef.ref_kind = "local"`).
Which binder a name resolved to — and therefore what type it carries — is
computed, used to classify, and thrown away.

Typecheck then re-derives scope, partially. `_stmt_tree_scoped` threads
exactly two binder kinds (`ForEach`, `EachSimultaneous`); procedure and
function parameters are bound at their declaration sites
(`_all_statements_scoped`, `_function_sigs`); produce arms get a scoped
sub-walk (`_check_produces`); the movement/reveal filter's `card` is bound at
its consumption site (`_check_stmt_exprs`); expression-level binders are
bound inside `infer`/`_check_expr`. Everything that walk misses — above all
the sequential `let` — types as `TAny`.

## Why it matters: TAny is contagious silence

`TAny` passes `assignable` in both directions, so *every* wall goes dark
behind a `let`:

    if hearts is 3 { … }          rejected (the equality wall fires)
    let z = hearts
    if z is 3 { … }               accepted — the same comparison, one let away

This one gap is the recorded bound on several otherwise-closed ledgers: the
equality/ordering/membership matrices (`tests/test_operator_walls.py`), the
`run`-argument wall (`tests/test_procedures.py`), and the movement-endpoint
wall's `local` residual (`tests/test_movement_endpoints.py`). Each of those
walls is total over its own domain *except* where a `let` launders the type.

## The fix, in one move

**Thread `let` bindings through the statement walk, typed at declaration.**
The walk already yields statements in source order within each tuple (that is
what makes the sequential fold well-defined at resolve and at runtime); the
consumption loop in `typecheck()` maintains the environment, so the change is
localized:

1. `_stmt_tree_scoped` grows the same sequential fold `_rewrite_value` has:
   walking a statement tuple, after yielding a `LetStmt` it extends the binder
   list for the *remaining* statements of that tuple with `(name, <deferred>)`.
   Scope boundaries it already gets right (a nested body's lets do not leak
   out; `Block` exists precisely to pop them).
2. The type itself cannot be computed inside the walk (typing needs the
   environment; the walk is env-free), so the binder entry carries the
   `LetStmt` node and `typecheck()`'s loop resolves it: on reaching the let,
   `env.with_local(name, infer(stmt.value, senv))`. An indexed `let` binds its
   key binder only over its own value expression — same rule as resolve.
3. `role_type`'s `TAny` fallback and the `ACTION_FIELDS` boundary stay as they
   are; this plan types *lets*, not the action payload (that residual has its
   own roadmap entry and its own design question).

This is deliberately the narrow form. Two deeper forms were considered and
parked:

- **Resolve annotates bindings onto the `NameRef`** (a `binding` field:
  which binder, declared where). Structurally the cleanest — scope would be
  computed exactly once — but it grows the AST for every consumer and its one
  extra payoff (substitution knowing binder identity) is already solved for
  procedures by unspellable temporaries. Revisit if a third pass ever needs
  binding identity.
- **A shared scope-walk module** consumed by both resolve and typecheck.
  Right if the two walks keep growing in parallel; today typecheck's walk
  *after step 1* is no longer a partial copy but a typed view over the same
  fold, and the duplication left is one function each. A third consumer of
  scoped traversal (deckcheck and observe do not need scope) is the trigger.

## Acceptance criteria

This lands as one change with its own surface-totality ledger, and it is done
when the residuals it exists to close actually close:

- `tests/test_operator_walls.py::test_offset_by_accepts_gradual_any_on_either_side`
  flips from pinning the gap to pinning the wall (a `let`-derived operand is
  typed, so the ordering wall fires through it);
- the `run`-argument ledger row "bounded by the let-TAny gap" is deleted and
  `let z = hearts / run f(z)` (Player parameter) gets a rejection test;
- the movement-endpoint wall's `local` residual row narrows to "a local whose
  initializer types `TAny`" or closes outright, and
  `let h = 3 / move all cards from h to deck` is rejected at check time;
- the equality matrix gains `let`-laundered rows for the cells that were
  previously untestable;
- roadmap.md's "A `let`-bound name has no static type" entry and the
  "Let-bound local typing across statements" residual block are removed
  (spec, not history: no tombstones).

Corpus impact must be zero by construction: every corpus game already
type-checks with lets at `TAny`, and typing them can only *reject more*, so
the gate is "the corpus still checks and every new rejection has a named
test". If a corpus game turns out to rely on a laundered type, that is a bug
in the game file, fixed in the same change (operating rule 2).
