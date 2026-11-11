# Pre-registration: the authoring benchmark, first run

**Dated 2026-11-11, and committed before any model was called for this
benchmark.** No model has been called by this rig at the time of writing:
the rig was built and tested against a scripted fake provider only. The
commit that adds this file is checkable, and the first run directory's
`run.json` carries the commit it ran at:

```bash
git log --diff-filter=A --format='%h %aI' -1 -- experiments/llm_eval/PREREGISTRATION_AUTHORING.md
```

## The question

Epic #1043's goal: *a model given a game's rules source and
`docs/authoring.md` writes a checker-green `.cardlang` for it, and every
refusal it meets on the way names the fix in the designer's words.* This run
measures the first half directly and lists the counter-examples to the
second: every refusal after which the model's next edit left the refusal
standing.

This run is the **before** measurement. The epic's diagnostic parts (#1045,
#1046 and the rest) change what the checker says; the same config, re-run
after they land, is the after. The comparison between the two is the
benchmark's purpose, and neither run alone is a verdict on the epic.

## Design

| | |
|---|---|
| models | `frontier` = `claude-opus-5`, `mid` = `claude-sonnet-5` (the newest ids the playing rigs' configs carry) |
| request | `max_tokens: 16000`, `thinking: {type: disabled}`, `output_config: {effort: high}` |
| games | 3 corpus games withheld, 2 candidates (below) |
| attempts | 2 per (game, model), each a fresh conversation |
| round limit | 8 drafts per attempt, the first included; the model is told the limit |
| checker | `python -m cardlang check game.cardlang`, text form, this checkout |
| real-game check | 100 uniform-random playouts per file (`author_facts.py`) |
| ceiling | `max_cost_usd: 40` over the results tree's whole spend log (`window: all`), with token backstops |

**Games.** The set is derived from the tree, never labelled
(`author_run.held_out_set`):

| slug | set | what it is checked against |
|---|---|---|
| `hearts` | corpus withheld | the differential against `docs/games/hearts.cardlang` |
| `go-fish` | corpus withheld | the differential against `docs/games/go-fish.cardlang` |
| `oh-hell` | corpus withheld | the differential against `docs/games/oh-hell.cardlang` |
| `crazy-eights` | candidate | a rules read |
| `euchre` | candidate | a rules read |

Each corpus game's variant line in the config names the variant its corpus
file plays, so the differential compares one game with itself.

**What the model is shown.** One prompt, cache-shaped (`author_prompt.py`):
the task text; `docs/authoring.md`; the three family libraries
(`docs/libraries/*.cardlang`); four corpus games as worked examples
(`spades`, `gops`, `cheat`, `five-card-draw`), none of them a held-out game;
the game's name, variant line, source URL and rules text; then each earlier
round's file and the checker's words verbatim.

**What the model is never shown.** A held-out game's corpus file or its
rulebook twin (`docs/games/<slug>.cardlang`, `docs/games/<slug>.md`). The
runner refuses a config whose references name either, for any game in the
run, before any model is called; the rules directory may not lie inside
`docs/games/`; and the prompt builder takes strings only. Pinned by
`tests/test_author_run.py`: `test_a_withheld_file_is_refused_as_a_reference`,
and `test_no_shipped_prompt_shows_a_held_out_games_withheld_files`, which
drives this config through the runner with a fake provider and finds no
three-line window of a withheld file in any prompt that no allowed reference
also holds. Measured 2026-11-11 at this commit's parent, with the reference
set above, of the three-line windows of each corpus file the references
also hold (shared idioms, not leaks): `hearts` 4 of 121, `go-fish` 2 of 84,
`oh-hell` 14 of 104, most of them shared with `spades`. The static part of
the prompt is 93,863 characters before the game's rules text.

**Rules sources.** The operator saves each game's rules text from its
source URL (the config's `source_url`, a Pagat page) into one directory at
run time; nothing from the source is kept in the repo. `run.json` records
each file's SHA-256 beside its URL.

## Metrics, defined

Every figure is derived from the recorded rounds by `author_run` and
`author_report`, and can be re-derived from `attempts.jsonl` alone.

- **Outcome** of an attempt, one of: `green`; `round_limit`; `gave_up` (the
  model replied `CANNOT EXPRESS: ...`, naming the rule); `checker_failed` (the
  checker crashed, hung, or exited 1 with nothing readable: a crash is never
  read as a refusal); `provider_error`; `stopped_by_ceiling`;
  `harness_error` (the checker exited 2, the rig's fault).
- **First draft green**: the attempt's first draft checks green.
- **Fix rounds to green**: the number of drafts after the first up to and
  including the green one; absent when no draft is green. A reply holding no
  draft (no fenced block, two of them, or cut off at the output limit) is a
  round and is not a draft.
- **A refusal the model could not act on** (`stands`): an error the checker
  printed for draft *k* such that the next draft checked, draft *j*, is
  different from draft *k*, and draft *j*'s check prints an error with the
  same key at a line whose stripped text equals the stripped text of the
  line the draft-*k* error stood at. The key is the diagnostic's code once
  the checker reports one (#1046), and until then its message with the
  `did you mean` offers removed. The definition is conservative on purpose:
  it counts only a refusal that stood still while the model edited
  something. Recorded and not counted: `persists` (the same key in draft
  *j*, at another line or an edited one), `gone`, `masked` (draft *j*'s
  errors are all syntax errors and this one is not, so the stage that would
  report it did not run), `not_edited` (draft *j* is byte-identical: a model
  non-edit, not a diagnostic failure), `no_next_edit`. The checker's text
  form prints the first of several diagnostics twice (#606); the reader
  counts it once.
- **Real game**, for a green file, one of: `agrees_on_facts_compared`,
  `diverges`, `does_not_play`, `rules_read_pending`, `not_comparable`.
  A corpus game's green file is compared with its corpus file on facts that
  survive relabelling (`author_facts.py`): the seat count and Component Set
  exactly, and, as distributions over 100 seeded uniform-random playouts
  each, the choices made (decisions offering two or more candidates), hands
  played, Length Stops, the number of seats sharing the win, and the mean
  number of card identities the deciding seat has been shown at each of its
  choices. Two-sample Kolmogorov-Smirnov per playout fact, family-wise level
  0.001 split evenly across the five. A candidate's green file is played and
  left to a rules read. **`diverges` and `does_not_play` are failures of the
  attempt**, whatever the checker said: a green file that is a reduced game
  is not a pass. A `diverges` that a rules read finds to be an encoding
  difference (a choice offered as two decisions where the corpus file offers
  one) is overturned only by an amendment that names the attempt and the
  fact, never silently. Calibration, measured 2026-11-11: each corpus file
  against itself under disjoint seed ranges, 100 playouts a side:
  all three agree on every fact, the smallest p-value 0.34 (`go-fish`,
  `oh-hell`) against a per-fact level of 0.0002; `hearts`' 100 playouts take
  under a minute.

## What counts as a finding to file against epic #1043

- Each `stands` refusal, after the filer reads its two rounds and confirms
  the message does not name a fix the model could have made. Filed as a
  sub-issue of #1043 (a diagnostic part), in milestone 27, with a kind and a
  reachability label; the report prints each one as an issue draft. One
  issue per refusal key and position in the language, not per occurrence;
  every attempt that met it is listed on it.
- Each `gave_up` whose named rule the language truly cannot express: a
  language-gap witness issue (`CLAUDE.md`, "The game does not bend to the
  harness"), filed loose unless its rule bears on the epic's goal.
- Each `checker_failed`: a bug, with the draft as its witness.
- A `diverges` confirmed by a rules read: recorded in the report; filed only
  if the divergence traces to something the checker accepted and should
  have refused.

## Stopping rule

Two attempts per (game, model), fixed here before the first call. No
re-run of an attempt for its result; no extension of the round limit on a
near-miss. The ceiling stops the run between calls, records the attempt it
stopped as `stopped_by_ceiling`, and the report states the partial N. Cost,
estimated from the prompt sizes measured above at about 4 characters per
token and an 8-round worst case per attempt: under $1.50 an attempt on
`claude-opus-5` and under $1 on `claude-sonnet-5`, so under $25 for the 20
attempts. The ceiling sits above that estimate so an underestimate shows as
a partial N rather than an overrun.

## What would make the result unusable

- More than a quarter of rounds holding no draft (no block, or truncated):
  the run measures the reply format, not the language.
- Any `harness_error`, or a `checker_failed` the rig caused.
- A corpus reference whose calibration above diverges from itself.
- A provider error rate above 10% of calls.

## What this run cannot settle

- **Two models, five games, two attempts.** A stand rate is a sample of the
  refusals these attempts reached; a refusal no attempt reached is not
  measured.
- **No thinking.** The request disables extended thinking so the output
  budget is the file; a thinking arm is a separate run.
- **What the real-game check cannot see.** A rule uniform play rarely
  reaches (shooting the moon), a scoring magnitude (the winner set is
  compared, never the returns), and an information structure that differs
  only in what a seat may infer rather than in what it is shown, all pass it
  unseen. `agrees_on_facts_compared` is not "is the real game".
- **The candidates.** Their real-game question is a rules read, not a
  measurement.
- **Whether a refusal names the fix.** `stands` says the model's edit did
  not address it; whether the words were at fault or the model was is the
  filer's read of the rounds.
