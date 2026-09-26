# Tichu plays its rulebook — the plan record

Milestone 6 (epic #762; parts #703, #721–#727). Gate order per the
`cardlang-planning` skill; the probe first, per the epic.

## Acceptance criteria

1. Runs: `docs/games/tichu.cardlang` checks and plays 300 of 300 games to
   completion under the reference policy.
2. Regression-clean: bare `mypy`, full `pytest`, the experiment rigs; the
   per-seed goldens regenerated at full width (a game change moves them by
   design — every hand's score changes).
3. Info sets derive: every new decision (the wish, the interrupt window's
   asks, the Phoenix's rank) is an ordinary kernel decision emitting an
   ordinary public announce; the readiness proofs (`tests/openspiel_ready/
   test_tichu.py`) hold on the new tree, and the swap proof now proves three
   pairs at every manifest seed.

Corpus lockstep: `docs/games/tichu.cardlang` and `docs/games/tichu.md`;
Big Two and President conform to the play protocol with the default
behaviours and their goldens gate the no-change.

## The probe (epic step 1)

Recorded on #703 (2026-09-26). Baseline, the game-file parts, the parts
with engine prototypes, and the landed file, 300 games each under the
reference policy, every hand scored a second time by an independent scorer
over observer 0's stream. What the read's list did not say: the per-card
grand-tichu window multiplied the policy's per-offer 4% gate eightfold and
45 of 300 games hit `max_length` (the instrument, re-derived per hand);
`TichuHands` skipped a Dog shed on purpose (the instrument, fixed); a
Phoenix play's rank was in no observation event (announced now); the
enumerator under-built the Phoenix-completes-the-triple full house (found
by the validator differential, in no issue); the old card-set codec refused
6,209 of the new enumerator's plays over 300 hands (a crash at the replay
seam, not a silent collapse — the injectivity refusal at `_legal` guards
the collapse for every engine).

## Classification and lanes

| Part | Class | Lane |
|---|---|---|
| #721 #722 #723 #727 | corpus game | C |
| #724 #725 #726 (Phoenix, straight flushes) | runtime (engine + codec) | B |
| #726 wish | runtime (kernel: the climb form's announcement regime) | B |
| #726 bombs out of turn | runtime (kernel: the climb form's interrupt window) | B — the axis WS3 reserves sign-off for; the Architect's counsel attaches to the change |
| #703 | grammar | A — leaves the epic; Hoyle's counsel attached to the issue |

The whole change is Merge Lane B by supremum.

## Reachability

R1 throughout: a player at the table meets every part in an ordinary hand.

## The audit's artifacts

- The grid: `tests/test_tichu_combinations.py` — `KINDS` × Phoenix ×
  Mahjong, outcomes authored from the rules, each cell a witness hand;
  the completeness ledger in its docstring.
- The oracle: the validator differential (sound and complete over every
  subset of sampled hands), the follows-against-beats relation, the codec's
  two-way bijection with the universe count derived a second time.
- Misuse probes: the Mahjong pair and full house, a lower bomb on a
  higher, a suited run as a straight, the Phoenix in a bomb, the wish
  offered to the wrong seat, a window asked out of order.
- Driven witnesses (aimed generation): `tests/test_tichu_wish.py`,
  `tests/test_tichu_bombs.py` — each audits every climb decision against the
  test's own reading of the rule and asserts the rare branches were reached.

## The counsel

The Architect's counsel (three blocks: the announcement regime, the
interrupt window, play identity with a wildcard) is in the PR body; Hoyle's
counsel on #703's surface is on the issue. Both consulted at planning time.

## What the operator decides

- The interrupt window is the axis-level change WS3 reserved sign-off
  for; it lands as its own commit so it can be dropped without touching the
  rest.
- #703 (a `wager` / `concession` row on a move type) is Merge Lane A and
  leaves the epic, per the epic's own rule.
