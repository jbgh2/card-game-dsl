---
term: Definition Contract
definition: A row of a library's `requires { }` that names a definition the including game defines and the library uses — a move type it offers (`fold : Move`), a function it calls (`is_contraband(card : Card) : Boolean`), or a procedure it runs (`settle_false_alarm() : Procedure`). The game's own definition is the only thing that answers the row. A mismatch is reported on the game's `uses` line, and the library's calls are typed against the row. Which kinds a row can name is derived as `resolve.CONTRACT_KINDS`. Contrast a keyed row, which names state or a zone the game declares.
layer: compiler
status: canonical
reserved: false
home: `n.MoveContract`, `n.FunctionContract`, `n.ProcedureContract`
see: [library, move-type]
retired_spellings: []
findings: []
---
