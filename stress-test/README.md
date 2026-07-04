# Language stress test — broad sweep (2026-07-04)

**This directory is an experiment, not part of the canonical corpus.**
Nothing here is held to the `docs/games/` lockstep rule, covered by CI, or
part of the spec. Do not cross-reference it from `docs/`.

## What this is

A breadth-first stress test of the DSL: 16 games *not* in the corpus, each
implemented by an independent lower-power agent using **the language only** —
no Python, no `instantiate` escape hatch — to see whether the language
generalizes or is being over-fitted to the corpus games.

The bar for each game:

1. `python -m cardlang.cli stress-test/games/<slug>.cardlang` passes
   (parse + typecheck).
2. `python stress-test/run_playout.py stress-test/games/<slug>.cardlang`
   completes random playouts without crashing.
3. Rules the language cannot express are marked `// GAP:` in the source and
   reported — silent simplification is treated as a failed run.

Each implementation was then audited by a second agent that re-ran the
checks, compared the file against the real rules (Pagat), and classified
every claimed language gap as *real-gap* / *construct-exists* /
*agent-error*.

## Games

Control (expected easy): Whist, Knockout Whist, Crazy Eights, Old Maid.
Moderate: Go Fish, Euchre, President, Gin Rummy, Blackjack, Ninety-Nine
(adding game), Palace/Shithead. Stress: Durak, Cheat, Texas Hold'em
(fixed-limit), Casino, Canasta.

Chosen for mechanism diversity: trick-taking with contextual ranks (Euchre's
bowers), climbing with roles (President), melding (Gin, Canasta), fishing
(Casino), banking (Blackjack), adding (Ninety-Nine), attack/defence (Durak),
false claims (Cheat), community-card poker (Hold'em), multi-deck (Canasta),
question-asking (Go Fish), blind draws (Old Maid), layered hands (Palace).

The synthesized findings live in the conversation/PR that produced this
branch, not here.
