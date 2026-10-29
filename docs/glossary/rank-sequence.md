---
term: Rank Sequence
definition: The `sequence:` game clause — the deck's ranks in the order a run reads them, lowest place first, which a [[combination-shape]]'s `in sequence` and `not in sequence` read. A rank may stand at both ends (Big Two's `A 2 3 … K A`, the ace low and high) and nowhere else twice. Declared exactly where a row reads it.
layer: kernel
status: canonical
reserved: false
home: `cardlang/ast/nodes.py`, `RankSequence`; `cardlang/catalogue_pass.py`
see: ["combination-shape", "combination-catalogue"]
retired_spellings: []
findings: []
---

**Kernel.** The `sequence:` game clause: the deck's ranks in the order a run reads them, lowest place first. A [[combination-shape]]'s `N in sequence` names N cards whose ranks fill N consecutive places of it, and `not in sequence` refuses those. It is an order of its own, apart from `ranking:` (which orders strength): Big Two's `sequence: A 2 3 4 5 6 7 8 9 10 J Q K A` puts the ace low in A-2-3-4-5 and high in 10-J-Q-K-A, and nothing runs past it.

A rank may stand at both ends and nowhere else twice; every rank it names is a rank of the deck; and it is declared exactly where some row reads it, so a `sequence:` no row reads and a row reading an undeclared one are each refused.
