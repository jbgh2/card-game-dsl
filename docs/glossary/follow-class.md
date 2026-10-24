---
term: Follow Class
definition: The class a card follows as within a [[trick-order]] — the game's answer to `follow_class(card : Card) : Suit?`, where `none` means class-less (a card that neither sets the lead nor wins; French Tarot's Excuse). Defaults to the card's printed suit. It is NOT the printed suit in general: a trump follows as a trump by `is_trump`, whatever suit it is printed, and the class of a trump card is never consulted. Never bare "suit" for this sense — a card's printed suit is a different fact.
layer: kernel
status: canonical
reserved: false
home: `kernel_contracts.CONTRACTS["follow_class"]`
see: ["trick-order", "kernel-definition-contract", "effective-lead"]
retired_spellings: []
findings: []
---
