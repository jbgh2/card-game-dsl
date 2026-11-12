## `Any` means the top, never a failed lookup

`Any` is the type checker's top: it is compatible with every type in
both directions, and every operand guard short-circuits on it. That is
correct for a value whose type genuinely cannot be narrowed, and it is
the mechanism that keeps typing *gradual* — an unrefined corner of the
object model must not manufacture errors in expressions that touch it.

The same permissiveness is a defect when it stands for "the checker
failed to look this up". A value that satisfies every constraint
silently exempts everything below it from every guard, so a single
missed lookup turns a whole subtree's type checking off and the checker
still reports success. This is the "accepted-but-ignored" class
(see "Surface totality") in its most damaging form, because it is
invisible: nothing in the program looks wrong. ADR-0001 records the
ruling and the sentinel type that lost.

**The two roles are separated at the producers, not in the type.** There
is one `Any`, and it means the top. A lookup whose domain is closed does not
fall back to it:

- **A closed-registry lookup raises.** Binder roles, native call
  signatures, zone content types, operator result types,
  and `ref_kind` dispatch each have a registry that an earlier pass
  validates against. A miss is a divergence between two registries —
  a compiler bug, not a program error — so it fails in the compiler's
  failure channel (an `AssertionError` naming the guard or builder that
  guarantees it), exactly as the runtime's `role_members` and
  `zone_observer_key` already did.
- **An environment lookup raises.** A name resolve classified but the
  type environment does not bind means the environment was built
  incompletely — most often a binder a statement walk failed to
  thread. The fix is always to thread the binding in the pass that owns
  the scope; binding `Any` at the failing site to quiet it restores the
  hole.
- **A declared type name is validated where it is declared.** Every
  position that declares a type is checked by the resolver, at the
  declaration rather than at some use. The positions are derived from
  the grammar rather than listed by hand — the productions referencing
  `type_name` or `payload_type` — because a hand-listed enumeration of
  them was found incomplete: state variables, move parameters, procedure
  parameters, rule-template parameters, function parameters, and
  phase-outcome payloads. The grid that
  crosses them against every source a name can come from is
  `tests/test_type_name_positions.py`. Otherwise a mere typo maps to the top and *widens* what
  the checker accepts: the misspelled program passes where the
  correctly-spelled one is rejected. Exactly one Owner Guard owns each
  position, and it is the tightest one that applies — a move parameter
  answers to the enumerable-domain gate (which subsumes name validity,
  since an unknown name is not an enumerable domain), a procedure
  parameter to its own domain set, and the remaining positions to a
  plain name check. Each position's allowed set mirrors exactly what
  its type builder can resolve, so a name the guard admits is never one
  the builder still maps to the top, and no defect is reported twice in
  two channels.

  A gate belongs to the DECLARATION, not to the uses that reach it: a
  gate run from the vocabulary sites that name a move would leave a move
  type nothing offers ungated entirely, and would report one named twice
  as two defects. Declaring a construct is what makes its parts real.

**What stays permissive is a small audited set**, enumerated and pinned by a
test so a new permissive site must be classified rather than added:
values with no better type (a diverging `error()`, context-dependent
native returns the signature model cannot express, deferred pronoun
shapes), and propagation downstream of a
guard that already fired. Gradual typing is preserved — the top still flows
and still suppresses errors where it is deliberate.

The general rule this instantiates: **a fallback is only legitimate
when no better answer exists.** A fallback standing in for an answer
the program *does* have is a silent wrong answer, and belongs upstream
as an Owner Guard (see "Closed-domain completeness", write-time triage).
