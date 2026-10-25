---
term: Trick Order
definition: The three per-card facts a trick's resolution and follow legality derive from — is the card a trump (`is_trump`), what class does it follow as ([[follow-class]]), how strong is it within that class ([[card-strength]]) — which a game answers as three [[kernel-definition-contract]]s, by writing the functions. Answering `is_trump` declares one; the other two default. Two Builtins read it (`highest_by_trick_order`, `follows_lead`). A game either declares one and uses its vocabulary, or declares none and uses the round-configured one (a round's `trump` clause plus the standard winners); the presence partition refuses every mixture. Its answers are hermetic — a fact of the card and public state, never of who is asking. Prefer it over a round's `trump <suit>` only where the order is not a printed suit; a fixed-suit trump game names the suit on its round. A `trick_order { }` block and a game-level `trump:` clause are each refused by a [[reject-with-replacement-twin]] naming the form that replaced it.
layer: kernel
status: canonical
reserved: false
home: `kernel_contracts.TRICK_ORDER_CONTRACTS`
see: ["kernel-definition-contract", "reject-with-replacement-twin", "follow-class", "card-strength", "effective-lead", "first-of-equals", "arrival-record"]
retired_spellings: ["trick_order { }", "trump:"]
findings: []
---
