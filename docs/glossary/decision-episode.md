---
term: Decision Episode
definition: The span a [[state-variable]] describing a pending decision belongs to — from the move that opens it to the resolution that settles it. Cheat's is one play (announce, count, face-down discard, challenge window); Coup's is one turn action and the block and challenge windows it opens; Gin Rummy's is one showdown window; Tichu's and Doppelkopf's is one quiescence-lap poll; Belote's, Five Hundred's and Skat's is one auction ring. A variable scoped to one holds its idle value between two, so the [[observation-log]] string at a decision names nothing already settled; the frame it is declared in is always longer, so the idleness is the game's doing, never the frame's.
layer: kernel
status: canonical
reserved: false
home: `tests/test_window_state_freshness.py`, `tests/test_offering_round_state_freshness.py`
see: [Observation Log, State Variable]
retired_spellings: []
findings: []
---

**Kernel.** The span a [[state-variable]] describing a pending decision belongs to — from the move that opens it to the resolution that settles it. Cheat's is one play (announce, count, face-down discard, challenge window); Coup's is one turn action and the block and challenge windows it opens; Gin Rummy's is one showdown window; Tichu's and Doppelkopf's is one quiescence-lap poll; Belote's, Five Hundred's and Skat's is one auction ring.

A variable scoped to a Decision Episode holds its idle value between two of them, so the [[observation-log]] string at a decision names nothing already settled. The frame the variable is declared in is always longer than the episode — [[state-variable]] scoping is lexical and per-phase — so the idleness is the game's doing rather than the frame's, and clearing happens where the episode ends, not where the next one begins.

Which games run one is derived rather than listed: a game declares a flag window when an offer-bearing `repeat until` is gated on a declared Boolean [[state-variable]], and a poll game is classified against every `round offering` the corpus derives, so a poll nobody classified reddens. A window variable's idleness holds at the decision that opens the next episode (the flag window) and at every decision the episode does not own (the poll), and each is pinned in its home.
