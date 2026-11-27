# Pre-registration: the authoring benchmark

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

**Amended 2026-11-13, before any model was called.** This run measures the
checker as it stands with the epic's diagnostic parts on main. No run was
taken before those parts landed, so there is no before to compare it with:
the run reports a level, and its list of refusals a model could not act on
is the evidence the epic's finish line is read against. The amending commit
is checkable the same way:

```bash
git log --format='%h %aI %s' -- experiments/llm_eval/PREREGISTRATION_AUTHORING.md
```

**Amended 2026-11-16, after the first run and before the second.** This
amendment's dates are US Pacific; run ids are UTC. The first run
(`2026-11-17T04-28-54Z`, checker at `ff92fffa`) recorded these protocol
facts. 25 of 63 `claude-opus-5` replies came back HTTP 200 with
`stop_reason: "refusal"` and no output tokens. Two of those requests, sent
again outside the run on 2026-11-16 (not in the run's record), returned
`stop_details.category` `reasoning_extraction`. The API reference defines
that category as a request that pushes the model to reproduce its internal
reasoning in the response text, and says a prompt that has the model write
its reasoning into the reply in place of thinking may be declined. The
request ran thinking disabled at effort `high`, and the replies show the
models reasoning in the visible reply: 14 of 40 `claude-sonnet-5` replies
carry more than 2,000 characters outside the file (the reply's length less
the file's), and none of the 14 is a draft that was checked: six are
give-ups, three hold no file, and five were cut off at the output limit.
Six replies reach the 16,000-token output limit, five from
`claude-sonnet-5` and one from `claude-opus-5`. The rig read a declined
reply as a reply holding no file, counted it as one of the eight, and sent
the next request; it recorded `stop_reason` and neither the category nor
the request id. Four changes follow, and the sections below state the
design with them:

1. **Thinking on.** Both models run adaptive thinking at effort `high`,
   with a 64,000-token output limit for the thinking and the file, sent as
   a stream.
2. **History as a conversation.** A later round is sent as turns: the
   first user turn holds the references, the game and the request for file
   1; each earlier reply goes back as an assistant turn exactly as the API
   returned it, thinking blocks included, except a reply cut off at the
   output limit, which is not replayed; and the rig's answer (the checker's
   words for a draft, or why the reply held no file) is the next user turn,
   ending with the request for the next file. Each round records the types
   of its reply's content blocks and whether the reply was replayed, never
   the blocks themselves.
3. **The give-up line asks for the gap, not the process.** It asks for the
   rule and the construct the language lacks for it, where it asked for the
   rule and what the model tried. No other sentence of the task asks the
   model to explain its reasoning.
4. **A declined reply is its own outcome.** It ends its attempt at once,
   as `declined`, with the decline's category; every round records the
   decline's stop details and the request id; and the run stops once two
   attempts (`decline_limit`) have ended declined.

The first run's results stand as recorded and are reported with the
declines called out: `author_report` reads a decline from a round's stop
reason, so the first run's declined rounds, recorded as holding no file,
are listed with their category not recorded.

**Amended 2026-11-26, before the second run.** One attempt of this design
was run on 2026-11-26 as a live check of the rig, outside the results tree
and with the operator's approval: run id `2026-11-27T05-13-04Z`, Hearts,
`claude-opus-5`. It is part of neither run's results. It was green at reply
3, met no declined reply, and cost $1.67. Request 1 was sent at about
05:13:05Z and returned at 05:18:53Z with 27,143 output tokens, having
written 42,994 tokens to the cache; request 2 read nothing from the cache
and wrote 70,382; request 3, which returned 39 seconds after request 2
returned, read 70,382 and wrote 4,627. So a first reply that takes more than five minutes outlives
the five-minute cache entry the next request would read from. The first
run's spend log shows the other loss: 87% of its input tokens were read
from the cache, but the first call for every (game, model) wrote the whole
prompt of about 42,000 tokens again, ten full writes, although about
nine-tenths of it is the references block, the same for every game; the
one breakpoint sat after the game's own text, so the references were never
stored on their own. The request carries two cache breakpoints, both with
the one-hour lifetime: one on the references block and one on the
request's last block. A one-hour write is billed at 2.0 times the input
price, a five-minute write at 1.25; every round records the one-hour part
of its writes, priced at its rate, and the spend ceiling counts it. The
hard bound below is recomputed with every write at the one-hour rate.

## Design

| | |
|---|---|
| models | `frontier` = `claude-opus-5`, `mid` = `claude-sonnet-5` (the newest ids the playing rigs' configs carry) |
| request | `max_tokens: 64000`, `thinking: {type: adaptive}`, `output_config: {effort: high}`, streamed |
| prompt cache | two breakpoints, both one-hour (`ttl: 1h`): on the references block (the task text and the reference files, the same for every game) and on the request's last block |
| games | 3 corpus games withheld, 2 candidates (below) |
| attempts | 2 per (game, model), each a fresh conversation |
| round limit | 8 replies per attempt, the first included, a reply holding no file counted; the model is told the limit |
| a declined reply | ends its attempt, as `declined`; no further request is sent in that attempt |
| decline limit | the run stops once 2 attempts have ended declined (`decline_limit`); the limit counts across the run, and the run takes games, then models, then attempts in that order, so two declined attempts on the first model end the run before the second model is called |
| checker | `python -m cardlang check game.cardlang`, text form, this checkout |
| real-game check | 100 uniform-random playouts per file (`author_facts.py`) |
| ceiling | `max_cost_usd: 40` over the results tree's spend log in a rolling 24 hours (`window: 24h`), with token backstops |

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

**What the model is shown.** One conversation, cache-shaped
(`author_prompt.py`). Its first user turn: the task text;
`docs/authoring.md`; the three family libraries
(`docs/libraries/*.cardlang`); four corpus games as worked examples
(`spades`, `gops`, `cheat`, `five-card-draw`), none of them a held-out game;
the game's name, variant line, source URL and rules text; and the request
for file 1. Then, for each earlier round, the model's reply as the API
returned it, as an assistant turn (none for a reply cut off at the output
limit), and the checker's words verbatim (or why the reply held no file)
with the request for the next file, as a user turn.

**What the model is never shown.** A held-out game's corpus file or its
rulebook twin (`docs/games/<slug>.cardlang`, `docs/games/<slug>.md`). The
runner refuses a config whose references name either, for any game in the
run, before any model is called; the rules directory may not lie inside
`docs/games/`; and the prompt builder takes strings and the model's own
earlier replies only. Pinned by
`tests/test_author_run.py`: `test_a_withheld_file_is_refused_as_a_reference`,
and `test_no_shipped_prompt_shows_a_held_out_games_withheld_files`, which
drives this config through the runner with a fake provider and finds no
three-line window of a withheld file in any prompt that no allowed reference
also holds. Measured 2026-11-11 at this commit's parent, with the reference
set above, of the three-line windows of each corpus file the references
also hold (shared idioms, not leaks): `hearts` 4 of 121, `go-fish` 2 of 84,
`oh-hell` 14 of 104, most of them shared with `spades`. The static part of
the prompt is the first block of the first user turn,
`len(author_prompt._references_block(task_text(8), references))` over the
references above; measured 2026-11-16 at `5d618f2b`, 99,008 characters. The pin reads
first-round prompts; a later round adds the model's own replies and the
checker's words, unscrubbed, as a designer at a terminal gets them.

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
  `harness_error` (the checker exited 2, the rig's fault); `declined` (the
  API declined a request, `stop_reason: "refusal"`: the attempt ends at that
  reply, its category recorded, and it is the instrument's outcome, neither
  the checker's nor a refusal the model could not act on).
- **First draft green**: the attempt's first draft checks green.
- **Fix rounds to green**: the number of drafts after the first up to and
  including the green one; absent when no draft is green. A reply holding no
  draft (no fenced block, two of them, or cut off at the output limit) is a
  round and is not a draft; so is a declined reply, the last round of its
  attempt.
- **A refusal the model could not act on** (`stands`): an error the checker
  printed for draft *k* such that the next draft checked, draft *j*, is
  different from draft *k*, and draft *j*'s check prints an error with the
  same key at the line the draft-*k* error stood at, carried into draft *j*
  unedited. "Carried unedited" is `difflib`'s alignment of the two drafts'
  lines (`author_run.carried_line`): the line lies in a block the two
  drafts share, so a line moved by an edit above it is still the same line,
  and of two lines with the same text (two `}`) only the one the refusal
  stood at counts. The key is the diagnostic's message with the `did you mean`
  offers removed, since the rig reads the checker's text form, which prints
  no Diagnostic Code; a message that quotes a line number ("opened on line 9")
  changes its key when an edit moves that line, which can only lower the
  count. The definition is conservative on purpose: it counts only a
  refusal that stood still while the model edited something. Recorded and
  not counted: `persists` (the same key in draft *j*, at another line or an
  edited one), `gone`, `masked` (draft *j*'s
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
  each, the choices made (decisions offering two or more candidates), Length
  Stops, the number of seats sharing the win, and the mean number of card
  identities the deciding seat has been shown at each of its choices.
  Two-sample Kolmogorov-Smirnov per playout fact, family-wise level 0.001
  split evenly across the four. The engine's hands-played count is not a
  fact: it counts the runs of a phase named `scoring`, a name a faithful
  encoding need not use. A candidate's green file is played and
  left to a rules read. **`diverges` and `does_not_play` are failures of the
  attempt**, whatever the checker said: a green file that is a reduced game
  is not a pass. A `diverges` that a rules read finds to be an encoding
  difference (a choice offered as two decisions where the corpus file offers
  one) is overturned only by an amendment that names the attempt and the
  fact, never silently. Calibration, measured 2026-11-11: each corpus file
  against itself under disjoint seed ranges, 100 playouts a side:
  all three agree on every fact, the smallest p-value 0.34 (`go-fish`,
  `oh-hell`) against a per-fact level of 0.00025; `hearts`' 100 playouts take
  between one and two minutes, well inside the facts timeout of 900 seconds.

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
- A `declined` attempt is none of these: the report lists it with its
  category and request id, apart from the checker's refusals, and nothing
  is filed against #1043 for it.

## Stopping rule

Two attempts per (game, model), fixed here before the first call. No
re-run of an attempt for its result; no extension of the round limit on a
near-miss. The ceiling stops the run between calls, records the attempt it
stopped as `stopped_by_ceiling`, and the report states the partial N. The
decline limit stops the run after the second attempt that ends `declined`,
and the report states that partial N the same way.

Cost, at list prices with the prompt cache (`providers.PRICES`):

- **Estimate, 2026-11-11,** for a request with thinking disabled and a
  16,000-token output limit: the prompt sizes measured that day at about 4
  characters per token, a file of about 4,000 output tokens per reply, and
  all 8 replies used: about $1.40 an attempt on `claude-opus-5` and $0.85
  on `claude-sonnet-5`, about $22 for the 20 attempts. No estimate here
  prices thinking tokens, which are billed as output and, replayed, as
  input to every later round.
- **Hard bound, 2026-11-26,** for the request above. Every reply at the
  64,000-token output limit, every prompt written to the cache at the
  one-hour rate and none read from it, the conversation growing by a
  full-limit reply each round (an over-count, since a reply at the limit is
  cut off and not replayed), and about 31,000 tokens before the first
  round's history: about $33.20 an attempt on `claude-opus-5` and $19.90 on
  `claude-sonnet-5`, about $530 for the 20.

The $40 ceiling sits far below the bound, so a run far from the estimate
stops as a partial N rather than spending toward the bound.

## What would make the result unusable

- More than a quarter of rounds holding no draft (no block, or truncated):
  the run measures the reply format, not the language. Declined replies are
  not in this share; they are reported apart, and the decline limit holds a
  run to two.
- Any `harness_error`, or a `checker_failed` the rig caused.
- A corpus reference whose calibration above diverges from itself.
- A provider error rate above 10% of calls.

## What this run cannot settle

- **Two models, five games, two attempts.** A stand rate is a sample of the
  refusals these attempts reached; a refusal no attempt reached is not
  measured.
- **One thinking setting.** The request runs adaptive thinking at effort
  `high`, and the API returns the thinking blocks with their text omitted,
  so the rig neither shows nor measures what a model reasoned; another
  effort, or thinking off, is a separate run.
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
