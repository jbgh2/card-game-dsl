---
term: Constructed World
definition: A [[world]] built to be indistinguishable to one [[seat]] from the one being played — the answer to OpenSpiel's `resample_from_infostate`, which the IS-MCTS family calls to determinize. A fresh [[shuffle-seed]] for every draw past the pause, a [[draw-script]] holding every card the seat has identified where the true draws put it, and the picks it did not see redrawn; accepted only when it renders that seat's information state byte-identically.
layer: interop
status: canonical
reserved: false
home: `openspiel/resample.py`
see: [draw-script, seat-view, world]
retired_spellings: []
findings: []
---

**Interop.** A [[world]] built to be indistinguishable to one [[seat]] from the
one being played — the answer to OpenSpiel's `resample_from_infostate`, which
the IS-MCTS family calls to determinize. A fresh [[shuffle-seed]] for every
draw past the pause, a [[draw-script]] holding every card the seat has identified where the true
draws put it, and the picks it did not see redrawn; accepted only when it
renders that seat's information state byte-identically.
