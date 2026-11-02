---
term: Prefix Walk
definition: The native-oracle differential's walk of one line against an OpenSpiel oracle that may end it earlier than the game does, by a draw rule the game does not play (a turn cap, a no-capture counter). `walk_paired_prefix` compares the two implementations at every decision of one live run, asks the caller's truncation predicate only of a terminal oracle to name the oracle's own end, closes the line with one paused replay of its history, and returns its [[line-end]]. The prefix is the stretch of the line both implementations play; past a truncation the oracle has no game to compare.
layer: check
status: canonical
reserved: false
home: `tests/native_oracle.py`
see: [line-end]
retired_spellings: []
findings: []
---
