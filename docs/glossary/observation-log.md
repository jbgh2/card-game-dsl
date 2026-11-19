---
term: Observation Log
definition: One seat's sequence of [[observation-event]]s, in the order they were delivered — what the seat has been told, and the perfect-recall part of its [[seat-view]]. The run keeps the table's logs, one per seat, on the [[world]] (`observe.ObservationLogs`): appended to by `Ctx.observe` alone and read as frozen snapshots (`observe.ObservationLog`), so every reader of a seat's knowledge reads the one log the run kept. Not the [[information-state]], the string that embeds it.
layer: kernel
status: canonical
reserved: false
home: `observe.py`
see: [observation-event, seat-view, information-state]
retired_spellings: []
findings: []
---

One seat's sequence of [[observation-event]]s, in delivery order: what the
seat has been told, and the perfect-recall part of its [[seat-view]]. The run
keeps the table's logs, one per seat, on the [[world]]
(`observe.ObservationLogs`); `Ctx.observe` is the one write, and a reader is
handed a frozen snapshot (`observe.logs_of`), so a replay, a paused run, a
live line and a resampled world all read the one log the run kept. The table's
logs together have no name of their own. Not the [[information-state]], the
string that embeds the log.
