---
term: State Delta
definition: What a decision node tells every seat about the public state since the decision node before it — one `was` [[observation-event]] per State Variable slot whose rendering changed, carrying the rendering it had there (none for a slot not then in scope); an indexed variable is one slot per key. Delivered by `observe.state_delta` from `chooser.decide`, before the `asked`, so a seat's log fixes the public state it was shown at every earlier decision node. A value written and overwritten between two decision nodes appears in none.
layer: kernel
status: canonical
reserved: false
home: `observe.state_delta`
see: [observation-event, chooser]
retired_spellings: []
findings: []
---
