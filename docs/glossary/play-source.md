---
term: Play Source
definition: The cards the player on turn plays from at a trick round's card decision — the acting seat's instance of the round's `source` family, or the zone `play_source_for` routes it to under Delegated Play. Inside a rule's clauses a bare `hand` names it, whatever the game calls its zones (`ref_kind` `play_source`); a subscripted `hand[p]` names the declared zone, and a function a rule calls cannot read it (decisions.md "Rule demand forms").
layer: kernel
status: canonical
reserved: false
home: `resolve._rewrite`, `runtime/evaluate._name`
see: []
retired_spellings: []
findings: []
---
