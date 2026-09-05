# Cribbage

The companion formal file is [cribbage.cardlang](cribbage.cardlang); this is the
readable twin. Two-player six-card Cribbage — the corpus's first **counting**
game (no tricks). First to 121 points, scored from two streams: *pegging* during
play, and the *show* afterwards. Source:
[Pagat](https://www.pagat.com/adders/crib6.html). **Deck:** standard 52.

Each hand:

1. Deal six cards each; both players discard two to the dealer's **crib**.
2. Cut a **starter** card (the dealer scores 2 for *his heels* if it is a Jack).
3. **Pegging** — players alternate laying cards, calling the running total, which
   may not exceed 31. Score 2 for reaching fifteen or thirty-one, pairs (2/6/12
   for two/three/four of a kind in a row), runs (the run length for a run of 3+
   in the recent cards), and 1 for the last card of a round (a *go*).
4. **The show** — each player picks their four cards back up and counts, with the
   starter as a fifth card: fifteens (2 each), pairs (2 each), runs (length ×
   multiplicity), a flush (4, or 5 with the starter; the crib needs all five),
   and *his nob* (1 for the Jack of the starter's suit). The non-dealer counts
   first, then the dealer's hand, then the crib — and the count stops the instant
   a player reaches 121, so the first to 121 wins outright.

The whole hand — discard, cut, pegging, and the show — runs in the DSL. Both
players' discards and every pegging play are filtered card movements (`move
chosen … where …`); ordinary statement control flow (`repeat until`, `if`/`else`,
`skip to next hand`) reproduces the 121-point cutoff one scoring component at a
time. Pegging needs no `round` form of its own — no existing round fits its
per-play scoring plus forced-play flow — so the current sub-round's card
provenance (who played each `play_pile` card) is carried by two `Integer` state
variables (`seq_bits`/`seq_len`, public information: every player watched the
count) and decoded by the `peg_origin_of` Primitive at each close, which
routes the pile into `played[dealer]` / `played[nondealer]`. The combination
scorers (fifteens, pairs, runs, flush, his nob) and the pegging-count scorers are
Primitives, unit-tested against known hands (the 29-hand, runs with
multiplicity, flushes, his nob). The game declares all five, with what each
reads, in its own `primitives { }` block; `peg_origin_of` reads state from
`phase play` and from `phase hand_sequence` around it, which is what commits
it to being called where the pegging runs.
