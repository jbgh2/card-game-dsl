---
term: Card Strength
definition: How strong a card is within its class under a [[trick-order]] — the `card_strength:` row's value, an Integer, higher beating lower. Defaults to `rank_value(card)`, the game's `ranking:` order. Read for CANDIDATES ONLY: a card that can neither lead nor win is never asked, because under the default a class-less card may sit outside the game's `ranking:` altogether. The full-phrase sibling of [[card-points]] — what a card BEATS in a trick, against what it is WORTH when counted. Never bare "strength", "height" or "order". The game-local height Primitive `tarot_trump_height` computes this fact for French Tarot and is still live; it retires into a `card_strength:` row when that game migrates (issue #250 PR 5).
layer: kernel
status: canonical
reserved: false
home: `n.TrickOrderRow`
see: ["trick-order", "card-points", "first-of-equals"]
retired_spellings: []
findings: []
---
