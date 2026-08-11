---
term: Shadow Guard
definition: A deliberately redundant guard standing behind an Owner Guard it names; unreachable if that Owner Guard is correct. Its firing is always an engine gap: it addresses the engine maintainer, and its message leads with the Owner Guard that leaked, game context second. Code artifact: runtime Owner Guards raise `OwnerGuardError`, Shadow Guards raise `ShadowGuardError`, both subtypes of `GameDescriptionError` (`cardlang/runtime/errors.py`) — the base names what's wrong (catch it in harnesses), the subtype names the role that caught it, and any `ShadowGuardError` raised anywhere in the suite is a failure (Pinned in `tests/conftest.py`). Where each class sits is itself Pinned, in `tests/test_failure_taxonomy.py`. Retired as names for this role: `backstop`, `twin` (→ F-19, F-21) — F-19's "no marker distinguishes a live check from a backstop" is what puts backstop here rather than with the Owner Guard.
layer: check
status: canonical
reserved: false
home:
see: []
retired_spellings: [backstop, twin]
findings: []
---
