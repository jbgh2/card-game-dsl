# Plan — the completeness-ledger batch migration (issue #392)

Dated 2026-09-06. Operator ruling in the direction-review conversation of
the same day, recorded on #392: **batch** — every legacy-format
completeness ledger converts in one change, and the same change adds the
scrape that refuses a retired row, so the population cannot rise again.
The alternative (attrition) was measured backwards: three modules were
born legacy-format in the window after PR #468 while zero migrated.

## Gate 1 — owners

- The format and the routing table: `docs/decisions.md`, "Closed-domain
  completeness" (the four rows; `registry:` the locator row; the six-kind
  table; "a history is none of the six").
- The ruling and its reasoning: #392's ruling comment (2026-08-20) and
  `docs/design-notes/documentation-fixed-points.md`.
- The calibration: PR #404 — five modules migrated so the routing judgment
  could be checked against a human. Its two findings bind here: deferred
  work needs no new writing (the issue is already cited at the guard or
  fixture), and designed constraints are already at the construct.
- Not Merge Lane A (no grammar). Not engine-structural: the change is
  docstring prose in `tests/` plus one scrape over prose. The operator's
  standing instruction not to build enforcement machinery for the NEW
  rows stands; the scrape here refuses the RETIRED rows, which the
  2026-09-06 ruling asked for by name.

## Gate 2 — classification

tests/goldens (docstring prose, no behaviour), plus one closed-domain
scrape (`tests/test_ledger_rows_retired.py`). The scrape triggers the
surface-totality audit: its grid is the parametrized refused-label cells
and the tree sweep, its misuse probes are the four-rows-clean control and
the mid-line-word control, its ledger is the module docstring.

## Gate 3 — acceptance

1. Runs: not applicable — no executable line outside the scrape changes.
2. Regression-clean: bare `mypy`; the prose-scraper set
   (`test_ledger_referents`, `test_ledger_rows_retired`,
   `test_assert_triage`, `test_glossary`, `test_doc_references`,
   `test_doc_snippets`); full `pytest` on CI. Goldens are untouched by
   construction: no file under `cardlang/` or `docs/games/` changes.
3. Info sets derive: untouched — no observation, projection, or adapter
   line changes; stated so the criterion is answered, not forgotten.

Corpus lockstep: none. Witness: the scrape's own red run on the tree
(87 modules at authoring, derived by `_ledger_docstrings`) is the witness
that the work list is real, and its green is the proof the list drained.

## Gate 3.5 — reach

R3 (#392's tag): every author and reviewer of a closed-domain mechanism
meets it. The operator ruled the batch on 2026-09-06 with the attrition
measurement in front of him; that ruling is the authority for the cost.

## Gate 4 — the audit's Step 1, run at planning

Axes derived in code: `REFUSED_LABELS` = the class template's rows less
the completeness template's rows, plus `sampled`. Framing check against
the definition sources (the two template fences and `_rows`'s parse)
found two things the author's derivation had not: `sampled` is outside
EVERY template and so invisible to the row parse by design, which is why
it is hand-named with that reason in the ledger; and a continuation line
that begins with a label IS a row head to the parse, which the first
negative control got wrong and execution caught. Expected column
authored, grid run red before any ledger moved.

## Gate 5 — steps, each with its artifact

1. **The scrape, red.** `tests/test_ledger_rows_retired.py`; the
   population walk factored to `_ledger_docstrings` in
   `tests/test_ledger_referents.py` so both sweeps read one population.
   Artifact: the sweep failing on the derived list.
2. **Route the 87.** Per module: delete `covered:` and `sampled:`; route
   every `residual:` item by the six-kind table; keep only instrument
   limits, under `does not prove:`; move cross-module maps to
   `registry:` in locator register; fold a genuine domain boundary into
   `domain:` positively; delete history; reword any in-module sentence
   that points at a deleted row ("see residual"). Then read the whole
   ledger as one thing. Artifact: the sweep green, and
   `test_ledger_referents` green (every locator resolves).
3. **The cross-module pointer sweep.** Prose in another module or doc
   naming a deleted row is invisible to both scrapes. Artifact: the
   query, recorded in the PR body, returning no live pointer.
4. **Close-out.** #392 closes on merge; #143's item 7 loses its stalled
   paragraph at merge per the ordering issue's maintenance contract.
   Artifact: CI green on the Lease branch `claude/issue-392`.
