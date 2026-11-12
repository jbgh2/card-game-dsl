## Resource amount syntax

A resource quantity in a transfer is written `<count> <type>` — the
count (an integer expression, or `all`) followed by the resource type
name:

```text
move 1 coin       from treasury to coins[player]
move 7 coins      from coins[actor] to treasury
move amount coins from coins[target] to coins[actor]
move all coins    from coins[p] to treasury
```

Stud (`move 5 chips`, `move ante_amount chips`) and Coup
(`move 2 coins`, `move min(2, …) coins`) — the two
resource-using games in the corpus — both read this way, and both move
a single resource type per transfer. The `<count> <type>` form is the
canonical surface for that case.

For a transfer that moves *several* resource types at once, the
generalization is a map literal `{ type: count, … }`:

```text
move { wood: 2, brick: 1 } from bank to hand[player]
```

No corpus game moves multiple types in one transfer yet, but the map
form is the multi-entry generalization of the single-type form (which
is the one-entry case, written without braces) and is reserved for it.
The rejected alternative `type × count` overloads multiplication and
reads worse beside ordinary arithmetic in amount expressions.
