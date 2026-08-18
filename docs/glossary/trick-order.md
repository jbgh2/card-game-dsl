---
term: Trick Order
definition: The three per-card facts a trick's resolution and follow legality derive from — is the card a trump, what class does it follow as ([[follow-class]]), how strong is it within that class ([[card-strength]]) — declared by a game's `trick_order { }` block as expressions over the implicit `card` binder. The language mints one reader per row (`is_trump`, `follow_class`, `card_strength`) and two Builtins over the whole declaration (`highest_by_trick_order`, `follows_lead`). A game either declares one and uses its vocabulary, or declares none and uses the round-configured one (`trump:` plus the standard winners); the presence partition refuses every mixture. Rows are hermetic — a fact of the card and public state, never of who is asking. Prefer it over `trump: <suit>` only where the order is not a printed suit; a fixed-suit trump game says so with the plain clause.
layer: kernel
status: canonical
reserved: false
home: `n.TrickOrder`
see: ["follow-class", "card-strength", "effective-lead", "first-of-equals", "arrival-record"]
retired_spellings: []
findings: []
---
