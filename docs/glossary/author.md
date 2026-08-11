---
term: Author
definition: The person who can act on a failure — whose artifact (game file, library, or engine) must change. Every failure is reported to its author: span in their file, message in their vocabulary, through a channel they'll actually see. Always the author of the *faulty artifact*, never of the diagnostic; in practice compound it: game author, library author, engine maintainer, primitive maintainer (`PrimitiveReadError`), and — for the engine's own data files, which load from the checkout — whoever installed it (`InstallationError`). Retired: `currency` (and its verb "denominated") (→ F-23); comment-only migration rides the alignment pass's docstring phase (issue #214); the "runtime's currency" raise-site cluster is absorbed by the exception-hierarchy rework (spec: issue #207).
layer: check
status: canonical
reserved: false
home:
see: []
retired_spellings: [currency, denominated]
findings: [F-23]
---
