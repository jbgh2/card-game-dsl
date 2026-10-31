---
term: Length Stop
definition: The end a game meets at its declared `max_length` instead of by its rules -- the run stops before the pick that would carry it past the bound, after exactly `max_length` picks on every route. A tie by default (every seat a [[winner]], no loser, every seat's return 0), carried as a fact of the result -- `GameResult.ended_by` is `length`, where a game its rules ended is `rules` -- and of the adapter's terminal node; never a refusal. A loop that makes no picks and never ends is not one: it is refused as its author's defect.
layer: kernel
status: canonical
reserved: false
home: `chooser.decide`, `driver.EndedBy`
see: [Winner, Chooser]
retired_spellings: []
findings: []
---

**Kernel.** The end a game meets at its declared `max_length` instead of by its rules (decisions.md, "Game length as a declared contract"). Every pick is counted once, where `chooser.decide` records it, and the pick that would carry the count past the bound ends the game before it is asked: a run that stops has made exactly `max_length` picks, whichever route made them, and a multi-pick call the bound cuts short applies none of its picks.

The result is a tie by default: every seat a [[winner]], no loser, every seat's return 0, with neither the `winner:` target nor the `loser:` selection read. It says how the game ended in every channel: `GameResult.ended_by` names one of two arms, `rules` or `length`; the adapter's terminal node and a live line's end carry the same; `demo` leads its summary with it and `play` names it when the game is over.

A Length Stop is an end, not a defect, and is never a refusal. What stays refused is a loop that makes no pick and never ends: the iteration guards count a loop's boundaries with no pick between them, and refuse past `max_length` of them.

**Interop.** OpenSpiel's `max_game_length` is the declared `max_length`, and the Length Stop is what makes it true: `is_terminal()` holds after at most that many non-chance actions on every line, as spiel.h's "maximum length of any one game (in terms of number of decision nodes visited in the game tree)" requires.

"Truncation" stays ordinary prose; it names no construct.
