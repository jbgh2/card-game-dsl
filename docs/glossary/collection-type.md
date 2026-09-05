---
term: Collection Type
definition: The checker's `TCollection` as a DECLARED type — a value collection of one element type, spelled `Collection<Card>` in a [[primitives-block]] entry's two type slots and in every diagnostic that prints the type. What a [[zone]]'s contents, a card query's result, a list literal, and the joint-selection `cards` binder all evaluate to, and what a [[primitive]]'s collection [[parameter]] receives — the frozen elements, never the Zone that held them. A declared spelling carries no key and no zone facet (the checker's `key`/`zone` bookkeeping is about how a value may be addressed, never about what a parameter receives), and a collection is never optional — `is empty` is its absence. `Card` is the one spellable element, held equal to what registered Python takes. Contrast the [[zone]] type (`Hand<player>`), whose angle-bracket argument is an index domain, not an element: the head fixes which reading applies (decisions.md "Typed object model").
layer: compiler
status: canonical
reserved: false
home: `types.TCollection`, grammar `primitive_type`, `primitives_block.COLLECTION_ELEMENT_NAMES`
see: [primitives-block, parameter, primitive, zone]
retired_spellings: []
findings: []
---
