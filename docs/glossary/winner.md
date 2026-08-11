---
term: Winner
definition: The player a decision yields, at either scope: the game-level `winner:` clause (argmax over a state variable), and the player a trick or climb round yields — the trick form's `winner <fn>` clause, the value bound in round bodies, and the function that computes it (**winner function**), carried in `TrickRound.winner_fn`. An auction's tagged result is an Outcome, not a winner, and lives in `AuctionRound.outcome_fn`.
layer: kernel
status: canonical
reserved: false
home: `n.Winner`, `mechanics.py`
see: []
retired_spellings: []
findings: []
---

**Interop.** OpenSpiel calls it **returns** vector — translated in `replay.returns_for`.
