---
term: Playout Policy
definition: A [[chooser]] that resolves a [[candidate]] list by a declared ranking instead of drawing uniformly, so playouts reach branches a uniform draw leaves unexercised. Its registry states, per Candidate kind, whether that kind is *ranked* or *delegated* to the uniform draw; a kind in neither is refused rather than silently delegated. Reads only the zones the deciding seat owns, at the key `zone_observer_key` gives it, so its playouts stay admissible as evidence.
layer: kernel
status: canonical
reserved: false
home: `tests/playout_policy.py`
see: [chooser, candidate]
retired_spellings: []
findings: []
---
