---
term: Seat View
definition: Everything one [[seat]] knows at one position — its zones through their declared [[projection]]s, the public [[state-variable]]s, and its own [[observation-log]] — as a value with no hidden fields. What a renderer or a policy consumes instead of the live [[world]], so leak-freeness is a property of the type rather than a claim about the code that reads it.
layer: interop
status: canonical
reserved: false
home: `infostate.py`
see: [observation-log, projection, world]
retired_spellings: []
findings: []
---

**Interop.** Everything one [[seat]] knows at one position — its zones through
their declared [[projection]]s, the public [[state-variable]]s, and its own
[[observation-log]] — as a value with no hidden fields.

It is the thing derived; the [[observation-log]] string OpenSpiel keys on is
one *rendering* of it. A second rendering consumes the same value rather than
deriving a seat's knowledge again beside the first, because two derivations
would be two implementations of the property this project exists to guarantee,
kept equal by review. What a renderer or a policy is handed instead of the live
[[world]]: leak-freeness is a property of the type, not a claim about its
reader.
