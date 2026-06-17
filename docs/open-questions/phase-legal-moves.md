# Phase legal_moves

**Tier 4 — low impact, defer until forced.**

A phase declares `active_rules`, and its body offers moves through the kernel
`round` (`play_to_trick`), `offer to … one of [...]`, and the auction form `round
offering [...]`. The legal move types are largely derivable from these. So what is
the `legal_moves:` clause *for*, and how does it relate to the body? Two coupled
sub-questions:

**1. Source of truth.** Should `legal_moves` be:

(a) derived automatically from `active_rules` plus the body's offers/rounds;
(b) stated explicitly for readability;
(c) stated explicitly only for *additional* legal moves not otherwise constrained
    (most likely — derived by default, explicit for the rest).

**2. Consistency check (a parked static check).** Whatever the source of truth,
should resolve/typecheck verify that `legal_moves:` matches what the phase body
actually offers — flagging a move type listed in `legal_moves` that the body never
offers, or a move the body offers that `legal_moves` omits?

This sharpened when the auction form introduced `offering [...]`, which *also*
declares a move vocabulary: Bridge's auction phase lists its bid moves in
`offering` and dropped `legal_moves:` entirely, so the two clauses now overlap with
no defined relationship. The static check is only meaningful once (1) settles which
clause is authoritative: if `legal_moves` is derived, there is nothing to
cross-check; if it is explicit, a body-consistency check is worth having (it would
catch a `legal_moves`/`offering` drift, or a phase that declares a move it never
offers). It is the compile-time counterpart to the runtime "no implicit actions"
guarantees (decisions.md "No implicit actions").

Resolve (1) first; (2) follows from it. Until then `legal_moves:` is honoured as a
human-readable declaration that nothing validates against the body.
