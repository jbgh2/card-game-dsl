---
term: Permissive Top
definition: A union whose consumers dispatch by permissive `isinstance` chains with no `assert_never`, so a new member falls through EVERY check silently instead of failing loudly. `Type` is the standing instance — `join`, `coercible`, `subscriptable`, `_type_name` and the operand walls all fall back rather than refuse.
layer: check
status: canonical
reserved: false
home: `cardlang/types.py`
see: []
retired_spellings: []
findings: []
---

The name is for the defect class, not for any one fix. A closed union ending in
`assert_never` has the opposite property: a new member is a type error at every
consumer (see the round forms, where adding a node reddens four layers at once).
A Permissive Top has no such enumeration, so widening it is silent — which is why
a change that adds a member to one carries its own sweep rather than trusting the
type checker.
