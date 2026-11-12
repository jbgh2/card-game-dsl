## Resource transfer failure

A `transfer` whose source lacks the requested amount is a hard error:
the move is illegal. The language provides no partial-fulfillment
primitive. A game that wants partial behaviour writes it explicitly,
with `min` or a conditional amount:

```text
// Coup steal — take 2, or 1 if that's all the target has:
let amount = min(2, coins[target].amount_of(coin))
move amount coins from coins[target] to coins[actor]
```

```text
// Stud all-in call — match the bet, or commit the whole stack:
let amount = min(bet_to_match - bet_by[actor], stack[actor].count)
move amount chips from stack[actor] to pots[0].contents
```

The two resource-using games converge on the same shape: compute the
deliverable amount at the game level, then transfer exactly that. The
complementary case — a payment that must *not* underflow (Coup's Coup
fee of 7, its Assassinate fee of 3) — is handled upstream by an
affordability rule that gates the action's legality, so the fee
transfer is always satisfiable when it runs. Neither case needs a
primitive; the explicit form reads correctly and keeps the failure
policy visible in the game file.
