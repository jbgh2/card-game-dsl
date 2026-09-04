# French Tarot

The companion formal file is [french-tarot.cardlang](french-tarot.cardlang);
this is the readable twin. Four-player French Tarot (FFT rules) on the 78-card
Tarot deck — four 14-card suits (K Q Cavalier J 10…1), 21 atouts (trumps), and
the Excuse. One player (the *taker*) plays alone against the other three, trying
to take enough card points in tricks to beat a threshold set by how many *bouts*
(the 1 of atouts, the 21, and the Excuse) they capture. Thirty-six hands are
played; the highest score wins. Source:
[Pagat](https://www.pagat.com/tarot/frtarot.html).

Each hand:

1. Deal 18 cards to each player and 6 to the *chien* (kitty).
2. **Bid** — one ascending bid per player: Petite < Garde < Garde sans le chien
   < Garde contre le chien. The highest bidder is the taker; if all pass, the
   hand is thrown in.
3. **Chien** — at Petite/Garde the taker takes the chien and discards six,
   HIDDEN from the opponents (the discards still count to the taker). The
   discard may never contain a King or a bout; atouts go in only when the
   taker holds fewer than six plain non-King cards, and any atout discarded
   is shown to the whole table first. At Garde sans the chien counts to the taker
   unseen; at Garde contre it counts to the opponents.
4. **Play** — eighteen tricks; atouts are trumps. Follow suit; if void you must
   trump, and you must over-trump if you can. The Excuse may be played at any
   time, never wins, and stays with its team (transferring a low card to the
   trick winner in compensation). Leading it is legal and sets no suit: the
   next player may play any card, and that card fixes the suit to follow.
5. **Score** — the threshold is 36/41/51/56 card points for 3/2/1/0 bouts.
   `pt = taker points − threshold`; with the petit-au-bout bonus `pb` (±10 if the
   1 of atouts falls in the last trick) and the bid multiplier `mu`
   (1/2/4/6), each opponent pays `(25 + pt + pb) × mu` and the taker collects
   three times that (zero-sum).

The whole hand runs in the DSL. The four-level bid runs on the kernel `round`
(a counterclockwise single-pass ring over the move vocabulary, settling
on a taker via `tarot_auction_outcome`). The chien discard is a filtered
movement (`move chosen 6 cards from hand[p] where is_pref_discard(card) to
discard[p]`) into a genuinely hidden `discard[player]` zone — a deliberate
departure from the printed rules' physical table layout, where the discard
sits face down in front of the taker but is not itself secret information the
opponents lack; here it is modelled as hidden because the opponents cannot see
which specific cards were set aside, only that six were. When fewer than six
plain non-Kings exist among the taker's 24, the forced branch moves every one
of them in and tops the discard up with chosen non-bout atouts routed through
`shown_atouts`, a public zone: each forced atout arrives there with identity
to all four seats before joining the hidden discard, so the opponents'
information sets carry exactly what the real game shows them — the forced
atouts — and nothing else of the discard. The atouts, the follow classes and
the card strengths are one declared `trick_order { }` block that the trick
winner, the follow demand and the over-trump comparison all read: the Excuse
belongs to no class, so it never wins and a led Excuse sets no suit — neither
restated by a rule, and the must-trump obligation reads the second off the
pile, binding only where the trick has an effective lead to be void in. The
eighteen tricks run on the trick form of `round`, legality narrowed by the
`ExcuseIsExempt`/`MustFollowEffectiveSuit`/`MustTrumpIfVoid`/`MustOverTrump`
rule cascade (the Excuse is exempt from every obligation via the `exempts:`
clause). The Excuse's special routing — it stays with its own side, repaying
the trick winner a low card when one is available — is ordinary body movements
after the round. `tarot_per_opp` computes the settlement (bouts threshold,
doubled card points from `captured` + the hidden `discard`, petit-au-bout, bid
multiplier); the `for each player` scoring statement applies it 3:1 zero-sum.
Card points are kept in doubled integer units (the 78 cards sum to 182); the
`card_points { }` clause carries the rank-keyed part of that table. poignée
declaration and the Excuse half-point IOU deferral are out of scope.
