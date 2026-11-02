# ADR-0010: Every guarantee names its Enforcement Ladder rung, and the top rung is the default

- **Status:** Accepted
- **Date:** 2026-10-25
- **Ruled by:** the operator, on the Architect's counsel (option b of three)
- **Record:** PR #956 (merged 2026-10-25), the counsel in its body
- **Governs:** decisions.md, "Prefer the guard you cannot need"; decisions.md, "Closed-domain completeness" (the `held by:` ledger row); the `cardlang-planning` and `surface-totality-audit` skills' rung-first gates

## Context

The law already ranked the four rungs — Unrepresentable, Derived and
Pinned, Born-Green Pin, review-enforced prose — and preferred a type over
a pin and a pin over prose, but nothing asked for the rung until a pin was
proposed, so a pin or a prose rule was the default even where a type could
hold the fact. The Observation findings of 2026-10-24 were its cost:
emission open at five sites, four builders of one log, a renderer that
refuses nothing, each a guarantee held by a sweep where a type or an owner
could hold it. Backfilled on 2026-11-01 from the PR.

## Decision

Every guarantee states its rung where it is written: a Contract Block's
Establishes clauses carry a held-by line, the completeness ledger carries a
`held by:` row, the planning and audit gates ask "rung first" before a
guard is named, the review files a wrong-rung finding, and a rung promotion
on shipping surface or rigor-critical machinery is not scaffolding at Gate
3.5. The top rung is the default; a lower one is a recorded decision.
Convergence is when-touched: an existing Contract Block gains its lines
when its module is next edited, and the scrape that mechanizes the held-by
rule is written against the first Contract Block in the new form, not
against the template.

## Alternatives

- **(a) Leave the ladder available and asked only at pin time.** Lost: no
  edit, and the Observation findings are what it costs.
- **(c) The rule plus the scrape plus a one-PR migration of every Contract
  Block.** Lost: a change across every module docstring before the first
  worked example exists, calibrating the scrape on a template rather than
  an instance.

## Consequences

A new Contract Block without held-by lines is a review finding until the
scrape lands; the ledger row axis grows by exactly `held by`, in both
templates, pinned in `tests/test_ledger_referents.py`; the four rungs and
the ladder are glossary terms. Information sets do not move.
