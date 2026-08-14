---
term: Pipeline
definition: extract → parse → resolve → typecheck → expand → check_capacity → emit. Use these seven stage names, nothing else. Expansion follows typecheck deliberately: a procedure's parameter types can only be enforced while its `run` site still exists (`pipeline.py`).
layer: compiler
status: canonical
reserved: false
home: `pipeline.py`
see: []
retired_spellings: []
findings: []
---
