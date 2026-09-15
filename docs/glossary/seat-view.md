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

It is the thing derived. Each way of showing a seat's knowledge is a
*rendering* of it: the [[observation-log]] string OpenSpiel keys on
(`render_information_state`), and the text a person reads
(`cardlang/play/view.py`, printed by `cardlang demo --view`). Each rendering
consumes the same value instead of deriving a seat's knowledge again beside the
others, because two derivations would be two implementations of the property
this project exists to guarantee, kept equal by review. It is what a renderer or
a policy is handed instead of the live [[world]], so leak-freeness is a property
of the type, not a claim about its reader.
