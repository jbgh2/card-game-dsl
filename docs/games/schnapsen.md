# Schnapsen

The companion formal file is [schnapsen.cardlang](schnapsen.cardlang); this is
the readable twin. Schnapsen is a two-player Ace-Ten point-trick game on a
20-card deck (A 10 K Q J in four suits; the `card_points` table prices it
A=11, 10=10, K=4, Q=3, J=2, so the deck holds 120 points). Each hand is a race to **66 card points**; the
match is played to **7 game points scored downward** — the first player to reach
0 wins. Source: [Pagat](https://www.pagat.com/marriage/schnaps.html).

How a hand goes:

- Deal 3 cards each, turn one up to fix **trump**, deal 2 more each; the rest is
  the face-down **talon**, drawn from after every trick.
- **Phase 1 (talon open).** The leader may lead any card — there is no
  obligation to follow suit. After each trick the winner draws the top of the
  talon, then the loser draws (the last draw is the face-up trump card, which
  goes to the loser). When on lead a player may also:
  - **declare a marriage** — lead the K or Q of a suit while holding both, for
    20 points (40 in trump); the points are *pending* until the declarer wins a
    trick;
  - **exchange the trump jack** — swap the jack of trump in hand for the turned-up
    trump card;
  - **close the talon** — stop the draw and switch immediately to strict play.
- **Phase 2 (talon closed or exhausted).** Strict play: follow suit and play a
  higher card of the led suit if you can; if void, you must trump; otherwise play
  anything. (Schnapsen has no over-trump obligation.)
- A player who reaches 66 **claims** and ends the hand.

Settlement, in game points deducted from the claimer's (or opponent's) score:

- **Correct claim, talon not closed** — 1 point, 2 if the opponent has fewer than
  33 card points (Schneider), 3 if the opponent took no trick (Schwarz).
- **Correct claim after closing** — the same tiers, but measured against the
  opponent's standing *at the moment of the close* (the Viennese snapshot).
- **Failed close** (the closer never reached 66) — the opponent scores 2, or 3 if
  shut out at the close.
- **No close, no claim, cards run out** — the last trick is worth 1 point.

The hand runs fully on the kernel. The leader's mixed turn — lead a card,
declare a marriage, exchange the trump jack, or close the talon — is one flat
candidate list on the **auction form of `round`** over a single-participant
ring: the free actions (exchange/close) leave `until trick_pile is not empty`
false, so the ring re-offers the leader until a card is led. `play_card(c :
Card)` enumerates the leader's live hand in hand order — the
state-dependent Card domain ([decisions.md](../decisions.md) "Declared
parameter domains"). The follower answers with a filtered chosen movement
over the in-file `follow_ok` cascade (strict follow-and-head once the talon is
closed or exhausted), and the trick, claim-at-66, and paired talon draws are
plain statements around the engine-core `highest_trump_or_led_suit` call,
which reads the trick pile's Arrival Record — the game carries no game-local
Python. The hand resolves three ways and produces a typed outcome —
`claimed`, `talon_closed`, or `open_play` — which the `play` phase declares
and the `scoring` phase settles with a `produces:` block (see
[decisions.md](../decisions.md) "Typed phase outcomes").
