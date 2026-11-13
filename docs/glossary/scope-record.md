---
term: Scope Record
definition: The resolver's record, kept only when a caller asks for it (`resolve(scopes=...)`), of what a bare name written at each node it classifies would resolve to there -- every name its classifier resolves under that node's categories, with the classification, less those the scope rules refuse at the node (the State Variable scope rules, a Pronoun a function or procedure body may not read, what a `state { }` default may read) and, where the node is a name, those the positional Owner Guards joined to the position record refuse in the slot it fills -- keyed by the node's place (`n.node_key`). The one source of "what is in scope here" outside the resolver; keeping it changes nothing the resolver decides.
layer: compiler
status: canonical
reserved: false
home: `cardlang/resolve/classifier.py` (`NamesInScope`, `_record_scope`)
see: [checker-query, type-record, resolve, ref-kind]
retired_spellings: []
findings: []
---

Read by the [[checker-query]]. What the slot a name fills takes (a zone, a
State Variable, a name keyed by a subscript) is judged at a name only, so at
any other node the record lists what a name written there may read before
its slot narrows it. The rules of who is acting and of a Hosted Poll's body
are not applied (issue #1089), so the record lists `actor` where no player
acts, a bare zone family there, and `state` inside a Hosted Poll's body.
