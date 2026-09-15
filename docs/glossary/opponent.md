---
term: Opponent
definition: A [[seat-policy]] a person seats by name — a row of the opponent table (`seat_policy.OPPONENTS`) with a line saying what it does and how it is built from a session's seed. `cardlang play --vs WHO=OPPONENT` seats one at each [[seat]] the person does not take, a partner's seat included; the word is the flag's, not a claim about teams.
layer: interop
status: canonical
reserved: false
home: `seat_policy.py`
see: [seat-policy, seat, seat-view]
retired_spellings: []
findings: []
---

**Interop.** A [[seat-policy]] a person seats by name: a row of the opponent
table (`seat_policy.OPPONENTS`), with a line saying what it does and how it is
built from a session's seed.

`cardlang play --vs WHO=OPPONENT` seats one at each [[seat]] the person does not
take. WHO is a seat number, `all` or `rest`, and neither selector is ever an
opponent's name. A partner's seat in a team game is filled by an Opponent too:
the word is the flag's, not a claim about which side a seat is on.

The table is the one place an opponent is defined. The help, the refusal of a
missing `--vs` and the refusal of an unknown name all list it, and a saved
session records each seat's opponent by its name. The table sits beside the
Seat Policy type, so what an arena benchmarks is the object a person plays
against.

Not a "kind": that word is reserved (the IR node tag).
