---
term: Play Identity
definition: What a combination play's combo-block action id is a function of — its card multiset, so a duplicate deck's copies stay distinct plays' cards, and the rank value a wildcard among them stands for (`None` without one). `primitives.play_identity`; a play's cards move, and a [[declared-engine]]'s candidates are offered, in the card-id order the ids are numbered by.
layer: interop
status: canonical
reserved: false
home: `cardlang/runtime/primitives.py`, `play_identity` / `card_multiset`
see: ["combination", "declared-engine", "registered-engine"]
retired_spellings: []
findings: []
---

**Interop.** What a combination play's id in the OpenSpiel combo block is a function of (`primitives.play_identity`): its card multiset (`primitives.card_multiset`), so copies of one card in a duplicate deck stay distinct members and a play never holds one card twice, and the rank value a wildcard among its cards stands for — `None` for a play with none, since a card set holding a wildcard can be two plays (Tichu's Phoenix). The id never reads the label a row or an engine gives the play.

A [[declared-engine]]'s catalogue is numbered by card count and then by sorted card ids (`primitives.action_order`), the order its candidates are offered in, and each play moves its cards in card-id order (`primitives.in_card_order`), so a candidate list and a movement observation are functions of the plays' cards, never of how they were generated.
