---
term: Failure Channel
definition: How a layer reports a failure, fixed by the layer: the compile stages fail as diagnostics carrying a span and a designer-readable message, the runtime fails as typed exceptions, the proofs fail with a witness. An [[owner-guard]] speaks its own layer's channel; loud-but-wrong-layer ranks with silent. Distinct from the [[author]], who the failure is addressed to — a guard can use the right channel and still name the wrong person.
layer: check
status: canonical
reserved: false
home: `cardlang/runtime/errors.py`, `cardlang/diagnostics.py`
see: []
retired_spellings: [failure currency]
findings: [F-23]
---

Always the full phrase. Bare [[channel]] is reserved: a game's scoring channels,
the observation channel and a library's feeding channel are unrelated things.
