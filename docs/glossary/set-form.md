---
term: Set Form
definition: The bare position query `<noun>s where <pred>` -- the members of a [[position-domain]] satisfying the predicate, in the Position Domain's member order, as a collection (`Collection<Cell>` over a board's `cell`, `Collection<Integer>` over an integer `positions { }` name). The position register's twin of `players where <pred>`; its collection twin, `<noun>s in <collection> where <pred>`, is the twin of `cards in <zone> where <pred>`, the members of its source satisfying the predicate in the source's order. Its noun is a Position Domain alone, never the board direction domain (decisions.md, "Boards and cells").
layer: kernel
status: canonical
reserved: false
home: `n.DomainQuery` with `kind` `"set"`
see: [Position Domain, Region Verb]
retired_spellings: []
findings: []
---

**Kernel.** The Set Form evaluates to a tuple, as a [[region-verb]]'s cells are, so `is` between the two compares by member. A membership test against it is parenthesized, `at in (cells where <pred>)`: a membership's right side sits below the query forms, so `at in cells where …` reads as the collection set over `at`, which resolve refuses where `at` is a value in scope.
