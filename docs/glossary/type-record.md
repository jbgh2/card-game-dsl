---
term: Type Record
definition: The type checker's record, kept only when a caller asks for it (`typecheck(types=...)`), of every Type its inference returned during the check, by the expression's place (`n.node_key`). The sanctioned materialization of an expression's Type outside the type checker, whose Types are otherwise not kept; every expression the check reads has an entry, and keeping the record changes no verdict.
layer: compiler
status: canonical
reserved: false
home: `cardlang/typecheck.py` (`infer`, `typecheck`)
see: [checker-query, scope-record, permissive-top]
retired_spellings: []
findings: []
---

Read by the [[checker-query]]. One expression may hold more than one Type
where the check read it under more than one scope.
