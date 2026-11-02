---
term: Stop Result
definition: What a game is worth when it ends by a [[length-stop]] -- the game clause `at max_length:` written beside the bound, one of three members -- `tie` (every seat a [[winner]], every return 0), `as it stands` (the `winner:` clause read at the stopped position), or a ranking `highest <variable>` / `lowest <variable>` in the `winner:` clause's own shape. A game that declares none is a tie. Never read at an end the game's rules make; `as it stands` is refused on a game whose result is `loser:` (decisions.md, "Game result: `winner:` and `loser:`").
layer: kernel
status: canonical
reserved: false
home: `n.StopResult`, `driver._stopped_result`
see: [Length Stop, Winner]
retired_spellings: []
findings: []
---

**Kernel.** The Stop Result is read once, by the driver, when a Length Stop ends the game; a ranking reads its target from the game-level frame, the one declaration a result clause may name. `GameResult.scored_by` says which of the three shapes scored the game, and `rank_dir` the direction a ranking ranked by, which the OpenSpiel returns are signed by.

"Outcome" names the tagged result a phase produces and is never this clause's name.
