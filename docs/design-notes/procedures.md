# Named procedures: nameable, parameterized statement blocks

*Status: design analysis / proposal — not a settled decision, and not yet
implemented. Called for by
[lexical-cleanup.md](lexical-cleanup.md) §6 (the one definition-form gap with
a forcing corpus case); this note is the design conversation that must settle
before any grammar lands. The committed spec is [../decisions.md](../decisions.md).*

## 1. The forcing evidence

The corpus cannot name a statement block, so repeated *procedures* are pasted:

- **Coup** (`games/coup.cardlang`, ~520 lines) pastes three unnamed blocks:
  influence loss ×14, the challenge window ×8, the proven-claim swap ×7 —
  most of the file is paste. This is the forcing case.
- Tichu's grand-call poll ×3, go-fish's book-completion ×2, Skat's Reizen
  round shape ×2.

Rules, move types, functions (expressions), defines (variant producers), and
types are all nameable; statement sequences are not. The corpus-first gate is
cleared many times over in one file.

## 2. The load-bearing constraint: pure reuse, never an escape hatch

A procedure must be **textual-equivalent reuse**: calling one behaves exactly
as if its body were written inline at the call site, after parameter
substitution. Concretely:

- **Expansion before execution.** The resolver (or a dedicated expansion
  pass) splices the body in at compile time — the same mechanism library
  rules use (`resolve._instantiate_rules`). The runtime never sees a
  "procedure call"; it sees the statements.
- **Observation-event identity.** Because the body is the inline statements,
  the observation events it emits — and therefore the derived information
  sets — are exactly what inline text would emit. A procedure can never
  create an info-set gap, because it does not exist at the layer where
  observations are emitted. This is what keeps the construct on the right
  side of the `instantiate` lesson ([../principles.md](../principles.md)):
  the retired escape hatch injected *Python* behavior the kernel could not
  see; a procedure injects only DSL the kernel already interprets.
- **No recursion, no dynamic dispatch.** Like functions: the call graph is
  acyclic (checked at resolve), and a call names its procedure statically.

## 3. Proposed surface

```
procedure lose_influence(victim: Player) {
  // ... statements, exactly the phase-body vocabulary ...
}

phase challenge_window {
  run lose_influence(challenger)
}
```

- `procedure NAME(params) { statements }` as a top-level item (sibling of
  `rule` / `move_type` / `function`).
- Invocation is a statement. The keyword spelling (`run` above) is open;
  candidates: `run X(a)`, `do X(a)`, or bare `X(a)` (bare risks ambiguity
  with expression-statements, which the grammar does not have today — that
  absence is worth preserving; a keyword keeps statement-hood visible).
  One spelling per concept: pick exactly one.

## 4. Parameters and scoping

- **Parameter kinds, corpus-first:** `Player` and `Zone` cover the forcing
  cases (Coup's blocks parameterize over the victim/claimant and their
  influence zone). `Suit`/`Rank`/`Integer` join when a case needs them.
  Same closed-domain treatment as rule templates: unsupported kinds are
  rejected loudly ([../roadmap.md](../roadmap.md)).
- **Substitution, not environment capture.** Arguments substitute into the
  body at expansion (hygiene checks as in rule templates: a body binder may
  not shadow a parameter). The body reads game/phase state lexically as
  inline text would; it does NOT capture caller locals — a caller local must
  be passed as an argument. This mirrors function hermeticity and keeps
  expansion order-independent.
- **State declarations inside bodies:** disallowed in v1. A `let` is fine
  (block-scoped, as inline); a `state { }` block is not (two expansions
  would collide or silently shadow — the duplicate-declaration defect
  class). Loud rejection.
- **`produce` / `continue to` / `skip to next hand` inside bodies:**
  disallowed in v1 — control flow that unwinds past the expansion site
  makes the "reads as inline text" story subtle (an inline block's
  `produce` targets the enclosing define/phase; a procedure used in two
  contexts could target different variants). Reject until a corpus case
  forces a design.

## 5. Open questions before implementation

1. The invocation keyword (one spelling).
2. Whether expansion happens in `resolve` (like library rules — favored:
   one mechanism, one place where `game` is rewritten) or a separate pass.
3. Whether a procedure may invoke another (acyclic) — Coup does not need
   it; simplest v1: reject nested invocation, lift with evidence.
4. Per-expansion `let` names: two expansions in one body scope introduce
   the same `let` names — the existing scoping rules treat inline repeats
   fine (each `let` rebinding shadows forward), so likely a non-issue;
   verify with the Coup rewrite.

## 6. Acceptance

- Coup's three pasted blocks become three procedures; the file shrinks by
  roughly half; trace goldens stay **byte-identical** (expansion is textual
  equivalence, so this is a hard check, not an aspiration).
- Surface totality: every parameter-kind/arity/control-flow mismatch above
  is a rejection with a test.
- The lockstep rule: Tichu / go-fish / Skat adopt in the same change if
  their shapes fit the v1 parameter kinds; otherwise their deferral is
  recorded here.
