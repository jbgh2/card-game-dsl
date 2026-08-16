---
term: Arrival Record
definition: The provenance a zone retains for each card now in it — the deciding [[actor]] (`None` when no seat decided), the card value, and the source [[zone-address]], in arrival order. The kernel records it at every movement it performs; consumers read it in place of re-deriving attribution (the seat-order zips this replaced). Values only: duplicate copies produce equal entries, so the record cannot over-distinguish what no observer could.
layer: kernel
status: canonical
reserved: false
home: `state.Zone`
see: ["zone-address", "actor", "transfer"]
retired_spellings: []
findings: []
---
