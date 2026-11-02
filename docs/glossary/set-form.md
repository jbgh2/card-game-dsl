---
term: Set Form
definition: The bare position query `<noun>s where <pred>` -- the members of a [[position-domain]] satisfying the predicate, in the Position Domain's member order, as a collection (`Collection<Cell>` over a board's `cell`, `Collection<Integer>` over an integer `positions { }` name). The position register's twin of `players where <pred>` and `cards in <zone> where <pred>`; it takes no `in <collection>` source, and its noun is a Position Domain alone, never the board direction domain (decisions.md, "Boards and cells").
layer: kernel
status: canonical
reserved: false
home: `n.DomainQuery` with `kind` `"set"`
see: [Position Domain, Region Verb]
retired_spellings: []
findings: []
---

**Kernel.** The Set Form evaluates to a tuple, as a [[region-verb]]'s cells are, so `is` between the two compares by member. A membership test against it is parenthesized, `at in (cells where <pred>)`: a membership's right side sits below the query forms.
