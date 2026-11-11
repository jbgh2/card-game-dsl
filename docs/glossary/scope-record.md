---
term: Scope Record
definition: The resolver's record, kept only when a caller asks for it (`resolve(scopes=...)`), of what a bare name written at each node it classifies would resolve to there -- every name its classifier resolves under that node's categories, with the classification, less those a positional Owner Guard refuses where the node is a name -- keyed by the node's place (`n.node_key`). The one source of "what is in scope here" outside the resolver; keeping it changes nothing the resolver decides.
layer: compiler
status: canonical
reserved: false
home: `cardlang/resolve/classifier.py` (`NamesInScope`, `_record_scope`)
see: [checker-query, type-record, resolve, ref-kind]
retired_spellings: []
findings: []
---

Read by the [[checker-query]]. Positional facts (the State Variables live at
a phase's position, the Pronouns a definition may not read) are recorded at a
name only, so at any other node the record lists every State Variable (issue
#1108).
