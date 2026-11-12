## `choose` as expression

`choose` elicits an integer decision from the acting player. Its one
form names an inclusive range, optionally capped, optionally less one
value:

```text
bid[p] := choose integer in 0 .. 13
```

Oh Hell caps the range — `choose integer in 0 .. hand_size up to 10` —
so the action space stays bounded when `hand_size` is large, and its
dealer's bid adds `excluding hand_size - total_bid`, the one number the
rulebook forbids (the clause's semantics: "The integer `choose` domain").
`choose`
is an expression: it appears wherever an `Integer` is expected — the
right-hand side of an assignment, a move argument — and, like the query
forms, it is parenthesized when it is an operator's operand. It emits a public
observation of the chosen value, and the chooser is the acting player
of the surrounding decision.

`choose` covers integer decisions only. The other decisions a game
elicits are not `choose`. Selecting which move to make is
`offer to <player> one of [move, …]`; the structured interactive forms
(an auction, a poll, trick play) are the kernel's decision forms — `offer`,
a `turns` ring of offers, the `round` — see "Interactive decisions: a
kernel and an in-DSL standard library". A decision that routes cards to a
chosen recipient runs as one of those move selections and reads its result
through an ordinary function: Pinochle's trump declaration is
`offer to high_bidder one of [declare_trump_suit]`,
and Tichu's Dragon gift is
`offer to outcome one of [dragon_to_left, dragon_to_right]`, not an
inline "chooses" subexpression.
