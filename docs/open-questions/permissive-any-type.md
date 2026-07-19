# Permissive `TAny` — split ⊤ from "unresolved"

`TAny` is the type checker's top type: [types.py](../../cardlang/types.py)'s
`assignable` returns true whenever either side is `TAny`, and ~20 sites in
[typecheck.py](../../cardlang/typecheck.py) short-circuit their check on
`isinstance(x, TAny)`. So a value typed `TAny` satisfies *every* constraint —
correct for a genuine top type, wrong for a value the checker merely failed to
resolve. Those two meanings live in one type, and the second is a standing
source of the repo's worst defect class (accepted-but-ignored): a lookup that
should have hit but didn't falls to a permissive `TAny` and silently accepts
whatever follows.

**Two populations of `TAny`, one type.** Among the ~60 production sites:

- *Legitimate ⊤* — no better type exists. `error()`'s return (it diverges, so
  it must type in any context); context-dependent stdlib returns whose real
  type the `Sig` system can't express (`tarot_trick_winner`,
  `belote_trick_winner`, the auction outcomes, `highest_of_led_suit`);
  collections of unknown element type; deferred pronoun member access.
- *Lookup-miss backstops* — the bug source. `type_from_name` falling to `TAny`
  for an unknown name; `env.locals`/`state_vars`/`zones`/`value_enums`
  `.get(name, TAny())`; `role_type`'s "backstop for the permissive walks that
  run before that rejection" ([domains.py](../../cardlang/domains.py)). These
  are meant never to fire (resolve rejects bad names first) — but they do when
  a type environment is built incompletely, and then they accept silently.

**Evidence it's a class, not incidents.** Two PR-review findings within one
review cycle were the same shape: a move parameter whose position domain was
not threaded into the binder env typed `TAny`, so `src is hearts` passed
([typecheck.py](../../cardlang/typecheck.py) `_move_param_binders`); the
owner-argument-vs-index gap was adjacent. Each was fixed by populating the env
so the miss did not happen — whack-a-mole against the amplifier, not the class.

**The proposed design.** Split the two roles:

- A **non-permissive `TUnresolved`** sentinel for the lookup-miss sites, which
  the compat/assignable layer treats as satisfying *nothing* — a comparison or
  operation involving it is a loud diagnostic at the use site. This converts
  the whole accepted-but-ignored class into loud errors, and would have caught
  both recent bugs *at the use* — including the incomplete-env case, where the
  name was valid but the env was not built with it.
- A **small, named, audited set** of legitimate `TAny` (⊤) uses that stay
  permissive — `error()`, the dynamic stdlib returns, unknown-element
  collections — so ⊤ is auditable rather than a catch-all.

**Why it is not just "delete `TAny`".** Full removal needs a type-system
investment the corpus does not yet force: a divergence/never type for
`error()`, polymorphic signatures for the context-dependent stdlib returns,
and element-type inference for every collection. The permissiveness is the
harm; the type itself is partly load-bearing.

**Cost and risk — why it is its own change, not a rider.** ~11 producer sites
to reclassify (⊤ vs unresolved; the docstrings already hint which), and the
~20 consumer short-circuits to audit — each `isinstance(x, TAny)` that means
"permit" must decide whether `TUnresolved` permits (almost always: no). The
risk is a test or game that leans on `TAny`'s permissiveness to mask something
that is *not* a bug (the deferred pronoun access); those must stay ⊤. Because
it touches the layer every comparison consults, it ships with the
producer-classification and consumer-audit as surface-totality artifacts
(decisions.md "Closed-domain completeness"), not an ad-hoc edit.

Resolution promotes the split into [decisions.md](../decisions.md)'s type
model and removes this file.
