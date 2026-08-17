---
term: Permissive Top
definition: The type checker's top, `TAny`: compatible with every type in both directions, propagating through every operation without error rather than refusing (`types.py`). It means the TOP and never a failed lookup — a lookup miss raises at its producer instead of decaying into it (decisions.md, "`Any` means the top, never a failed lookup"). The **permissive-top gap** is the defect named after it, not another name for it: a value reaching the top silently satisfies every guard downstream, so an unrefined `infer` arm exempts the expression it types.
layer: check
status: canonical
reserved: false
home: `cardlang/types.py`
see: []
retired_spellings: []
findings: []
---

A union dispatched by permissive `isinstance` chains with no `assert_never` has
the same shape one level up: a new member falls through every consumer silently
instead of failing loudly. `Type` is the standing instance — `join`,
`coercible`, `subscriptable`, `_type_name` and the operand Owner Guards all fall
back rather than refuse. A closed union ending in `assert_never` has the opposite
property, so a change that widens a permissive one carries its own sweep rather
than trusting the type checker.
