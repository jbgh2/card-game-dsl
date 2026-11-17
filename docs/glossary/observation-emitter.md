---
term: Observation Emitter
definition: The kernel code that turns what happens at the table into the [[observation-event]]s each seat is delivered through `Ctx.observe` — a card landing in a zone (`execute.deposit`, the one door a card lands by during play, through both sides' declared [[projection]]s), a decision (`chooser.decide`: the [[state-delta]], the `asked`, each `chose`), a public decision value (`observe.announce`) and a `reveal`. No game names its observers; which seat learns what follows from the zone declarations. Not "observer", which names the callback a caller installs to receive what the emitter delivers.
layer: kernel
status: canonical
reserved: false
home: `observe.py`
see: [observation-event, projection, state-delta]
retired_spellings: []
findings: []
---
