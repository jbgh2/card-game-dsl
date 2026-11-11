---
term: Checker Query
definition: What `cardlang query <file> --at LINE:COL` answers at one position of a game file the checker accepts, without playing the game -- the names a bare name written there resolves to, the Type the checker gives the expression there, and what each seat sees when the movement or decision there runs -- each read from the pass that owns the fact (the [[scope-record]], the [[type-record]], the zone types through the projection the emitter reads), or a [[told-diagnostic]] standing in its place that says what can be answered nearby. What each seat sees is the static answer, the [[projection]] each kind of seat sees each side of a movement through; which cards a seat saw on a played line is not part of it. A file the checker refuses gets the checker's refusal and no answer.
layer: check
status: canonical
reserved: false
home: `cardlang/query.py` (`Answer`, `ask`, `render`), `cardlang/records.py` (`query_envelope`)
see: [scope-record, type-record, record-envelope, projection, seat-view]
retired_spellings: []
findings: []
---

The text a designer reads and the Record Envelope a tool reads are rendered
from one `Answer`, so they cannot say different things. A Checker Query is
not a [[seat-view]]: a Seat View is what one seat knows at one position of a
played line, and the query names no cards.
