---
term: Near Miss
definition: A declared name close in spelling to a name the checker or the command line refuses because nothing it was looked up in holds it — the set of zones, state variables, move types, decks, the commands, the extensions a game file's name ends in, or any other names held at that point — or a keyword close in spelling to a word the parser refuses, among the keywords the grammar accepts in its place. A refusal of a name carries at most three, ranked by one resemblance measure, and renders them as one `did you mean` clause. Made only by `near_misses` and carried by `Diagnostic.near_misses`; rendered only by `Diagnostic.format`. Never mechanically applicable: a Near Miss can name the wrong declared thing, so it is offered to the [[author]], never applied for them. Never a [[candidate]], which is a legal option at a decision point, and never a bare "suggestion" or "hint", which name any advice a refusal adds.
layer: check
status: canonical
reserved: false
home: `cardlang/diagnostics.py` (`near_misses`, `resemblance`, `Diagnostic.near_misses`, `DiagnosticBag.unknown`)
see: [author, failure-channel, candidate]
retired_spellings: []
findings: []
---

Always the full phrase: a bare "miss" reads as a lookup failure, which is the
refusal the Near Miss rides on, not the name it offers.
