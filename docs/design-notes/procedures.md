# Named procedures: nameable, parameterized statement blocks

*Status: settled and implemented — kept for the forcing evidence and for the
questions §5 left open, each of which is answered below with what decided it. The
ruling itself is spec: [../decisions.md](../decisions.md) "Named procedures"
(the surface, the textual-reuse guarantee, hermeticity, the three hygiene Owner Guards,
the closed parameter domain). The deferred cells are in
issue #134; the completeness ledger is
`tests/test_procedures.py`.*

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
  rejected loudly (issue #134).
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

## 5. The open questions, and what answered them

1. **The invocation keyword** — `run X(a)`. A keyword, not a bare call: the
   statement layer has no expression-statement form, and that absence is worth
   preserving.
2. **Where expansion happens** — a separate pass, AFTER typecheck; *not* in
   `resolve` beside `_instantiate_rules`, which this note favored. The note's
   argument was "one mechanism, one place where `game` is rewritten", and it did
   not work out the consequence for §4's parameter types: a `victim : Player`
   can only bite while the `run` site still exists to check its arguments
   against. Expanding in resolve would leave every annotation parsed and ignored
   — the accepted-but-ignored class the whole surface-totality rule exists to
   prevent. The substitution *mechanism* is still shared with rule templates
   (`resolve.substitute`); only the timing differs, and it differs for a reason.
3. **Nested invocation** — rejected, as proposed. Coup does not need it.
4. **Per-expansion `let` names** — a non-issue, as suspected: two expansions in
   one block rebind the same `let` name and each shadows forward, exactly as two
   inline pastes would. The Coup rewrite confirms it.

## 5a. What this note got wrong: substitution is not the primitive

§2's "textual-equivalent reuse — calling one behaves exactly as if its body were
written inline, after parameter substitution" reads like a definition. It is
actually a *choice*, and it is the wrong one, because a procedure takes
**unevaluated expressions** where a function takes **values**. Substituting an
expression into every place the body reads its parameter is silently wrong in ways
this note never considered, and all of them are reachable:

- **One written decision becomes N.** `run bump(choose integer in 0 .. 1)` is one
  decision in the text. By name it is copied to every read, polled independently,
  and two reads can return two different answers — crediting two different players
  from a single written choice. This is the serious one: it changes the game's
  decision count relative to what the designer wrote, on the exact path CLAUDE.md
  says bounds every design choice.
- **Zero reads drop the decision entirely.**
- **An argument naming state the body mutates** denotes a different value on its
  second read than its first.
- **A body binder captures a caller's local**, inbound (through an argument) or
  outbound (a body `let` leaking forward into the caller's sequence).

The first implementation guarded the capture cases and shipped the rest. That was
wrong twice over: it left the decision-duplication defects live, and the Owner Guards it
did build were the kind that teach an author to work around a bug rather than fix
it. Coup's `lose_influence` carried a `let loser = victim` line whose only job was
to defeat by-name substitution.

The fix is to stop treating substitution as the primitive. Expansion binds each
argument to a `let` in the caller's context — once, by value — and wraps the body
in a block. Every defect above becomes impossible instead of guarded, the two
capture Owner Guards become vacuous and are deleted, and Coup's workaround line goes with
them. The one Owner Guard that survives is the one expansion cannot fix: a body binder
sharing a *parameter's* name is ambiguous at classification time.

The lesson generalizes past this construct: "behaves as if pasted" is not a safety
property. What a paste does is not the acceptance criterion — what the author wrote
is.

## 6. Acceptance — what landed

- Coup's three pasted blocks are three procedures. **521 -> 375 lines**; 29
  pasted blocks -> 3 named ones. (Not "roughly half": the remaining bulk is the
  seven action bodies and the two block windows, which are genuinely distinct.)
  The trace golden was **byte-identical** across the procedure rewrite — the hard
  check, and it held. It moved only later, and deliberately, when `alive` became
  a Boolean, with the diff proven representation-only.
- Surface totality: every rejection cell has a test, and the parameter-domain
  sweep is derived from `KNOWN_TYPE_NAMES x {plain, optional}` rather than
  hand-listed. Ledger: `tests/test_procedures.py`.
- **Parameter kinds: `Player`, `Rank`, `Rank?` — not `Zone`.** §4 guessed the
  corpus would need a `Zone` parameter; it does not. A `Player` parameter already
  carries its zone (`influence[victim]`), which is a small instance of the same
  finding the auction promotion produced (lexical-cleanup.md §3): the shared
  thing was not what the note predicted.
- **The lockstep adopters are deferred, and here is why.** Tichu's grand-call
  poll, go-fish's book completion and Skat's Reizen shape all sit around a
  `round`, and a `round` may not appear in a procedure body: it binds its own
  `outcome`, which the body's pronoun Owner Guard cannot yet distinguish from the
  caller's. Rejected whole rather than shipped half-usable. Recorded in
  issue #134; lifting it is what those three games need.
