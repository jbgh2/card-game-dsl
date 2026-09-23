---
term: Hidden Read
definition: A read of a zone, in an expression whose value reaches a decision, that asks more than its decider's [[projection]] of the zone reveals -- whether the zone is empty, how many cards it holds, which cards, or the order they sit in. Under [[honest-play]] a hidden read is a mis-modelled rule, and the checker refuses it (`resolve._check_hidden_reads`): where no seat decides, every seat must see what the read needs; where a seat decides, that seat must, through a zone every seat sees or its own instance of a zone its owner sees. The positions it judges are the rows of `resolve.HIDDEN_READ_POSITIONS`; a read reached through a `let`, a function, a procedure, a Primitive's `reads` or a Builtin is judged where its value lands.
layer: check
status: canonical
reserved: false
home: `docs/decisions.md`, "Honest Play is assumed, so a rule reading concealed cards is mis-modelled"
see: [honest-play, projection, decider]
retired_spellings: []
findings: []
---
