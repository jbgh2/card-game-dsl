---
term: Card Points
definition: The points a game assigns its cards — the game's answer to the `card_points(card : Card) : Integer` [[kernel-definition-contract]], written as the `card_points { }` table (rank-keyed rows, optional `else:` row; unlisted ranks read 0), which lowers to the function, or as `function card_points(c : Card) = …` where points vary by more than rank. Read by `card_points(card)`, its one reader: an answer no call reads is refused, and the driver's card-point census totals it as an instrument, never as a reader. One source — a deck carries composition only, never points. Never bare "value(s)" (reserved).
layer: kernel
status: canonical
reserved: false
home: `kernel_contracts.CONTRACTS["card_points"]`
see: ["kernel-definition-contract", "card-strength"]
retired_spellings: ["card_value", "Deck.values", "rs.card_values"]
findings: []
---
