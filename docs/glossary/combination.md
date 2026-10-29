---
term: Combination
definition: A climbing play of a [[declared-engine]] — the cards a seat lays down together, one card multiset of its [[combination-catalogue]], and the label of the row that names it. The type of the [[follows-function]]'s two parameters, and a function parameter's type only (`Combination` / `Combination?`). Read as its cards (`cards in play`, `number of cards in play`, card membership) and its shape (`play.shape is <label>`); its identity is its [[play-identity]].
layer: kernel
status: canonical
reserved: false
home: `cardlang/runtime/values.py`, `Combination`; `cardlang/catalogue.py`, `COMBINATION_FIELDS`
see: ["combination-catalogue", "combination-shape", "follows-function", "play-identity", "declared-engine"]
retired_spellings: []
findings: []
---

**Kernel.** A climbing play of a [[declared-engine]]: the cards a seat lays down together, which are one card multiset its game's [[combination-catalogue]] names, and the label of the one row that names it. It is the type of the [[follows-function]]'s two parameters — the play a hand holds, and the play standing in the trick (`Combination?`, `none` at a lead) — and of the parameters of the helpers that function passes a play to; nothing else may hold one, since a play exists while a round asks its follows function about it.

A Combination is read as its cards — `cards in play`, `number of cards in play`, `any card in play where …`, an aggregation over `cards in play`, card membership — and as its shape, `play.shape is <label>`, the one readable field of `catalogue.COMBINATION_FIELDS`. Every other read is refused with its fix (decisions.md, "Combination Catalogues"). Its identity, which its action id is a function of, is its [[play-identity]].
