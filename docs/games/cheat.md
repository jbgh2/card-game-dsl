# Cheat

The companion formal file is [cheat.cardlang](cheat.cardlang); this is the
readable twin. Cheat — also known as I Doubt It, Bullshit, or Bluff — is a
shedding game where every play is a possible lie: cards go down **face
down**, called out as a rank the player may or may not actually be holding,
and the only way to find out is to accuse them. This corpus entry fixes the
**basic game** described on Pagat, at **four players** on a standard 52-card
deck. Source:
[Pagat](https://www.pagat.com/beating/cheat.html).

Setup and play:

- **Deal.** Shuffle and deal the whole deck out — 13 cards to each of the
  four hands. There is no stock; every card is in someone's hand.
- **The claim cycle.** Plays are called as ranks in a fixed ascending cycle
  that belongs to the table, not to any player: the first play is called
  "Aces", the second "Twos", the third "Threes", … then Jacks, Queens,
  Kings, and back to Aces. The cycle advances by exactly one step per play
  and never resets — a challenge does not restart it.
- **A turn.** Play goes clockwise from seat 0. On your turn you discard
  **one or more cards face down** onto the pile and call them as the
  cycle's current rank — "two Sevens". You may play as many as you hold:
  six Sevens go down as six. The count you announce is the count
  you played (miscounting is not part of this game); the *ranks* are
  your own business. You do not need to hold the called rank at all: with
  the wrong hand at the wrong point of the cycle, lying is not just
  allowed, it is forced.
- **The challenge window.** After each play, every other player — clockwise
  from the player's left — may call "Cheat!" or let it go; the first call
  closes the window. (Pagat's rule is a real-time race — whoever calls
  first; serializing it into a clockwise window is this corpus's standard
  faithful rendering of such races, the same one Coup uses. Seat order
  decides first refusal on a catch; nothing else changes.)
  - **A call.** The played cards — just this play, not the pile beneath —
    are turned **face up** for the whole table. If **every** one is the
    called rank, the claim was honest: the embarrassed challenger picks up
    those cards *and the entire pile* into their hand. If **any** card is
    not the called rank, the liar is caught and picks it all up instead.
  - **No call.** The cards join the pile face down, unseen, and stay
    unseen — a lie that draws no call is never found out.
- **After a play.** Challenged or not, the cycle advances one rank and the
  turn passes to the next player clockwise.
- **Winning.** The first player to empty their hand *and survive the
  challenge window on that final play* wins immediately. A caught lie on
  the final play refills the liar's hand from the pile; a final play that
  is called honestly, or not called at all, ends the game on the spot.

The turn structure runs on the kernel's `turns` form (decisions.md "The
`turns` form"): the form owns rotation, and each turn is one `offer` of the
single move `play_cards`, whose effect opens with a public integer decision
— `choose integer in 1 .. (number of cards in hand[actor])`, which announces
the *count* to the whole table — and then makes the hidden card decision,
`move chosen claim_count cards`. The claimed *rank* is not a decision at
all, because the cycle forces it: it is the public `claim_rank` state
everyone already reads. The whole adjudication — window, flip, verdict,
pickup, cycle step — is one
named procedure run from every play's effect, Coup's challenge-window shape
with an **open** claim vocabulary (all 13 ranks, where Coup's is five
characters). `play_cards` is unguarded and its count range is never empty,
so the turn-holder always has a legal move: an empty hand ends the game
before its owner is ever offered a turn.

Zones and visibility: `hand[player]` is a private `Hand<player>` — owner
sees all, others see a count. `played` (this play's face-down cards) and
`pile` (the accumulated unchallenged discards) are `FaceDownPile`s — bare
counts to everyone, *including* the player who played them, whose knowledge
of what they really played comes from their own choice events, not from the
zone. `flipped` is a `Discard` — identity to all — and is empty except for
the instant a challenge exposes a play: routing the played cards through it
IS the reveal, exactly what a reveal builtin would do under the projection
model. The claim itself — `claim_rank`, `claim_count`, `claimant`, and the
window state — is ordinary public state: decisions.md's modeling rule ("a
public assertion is a state variable *because* it is public, while the
concealed truth it may misrepresent sits in a face-down zone") in its purest
corpus form. Every field of that claim belongs to ONE play and is cleared
where the play resolves, so a seat asked to announce reads no claimant, no
count and no verdict: the settled play's record is in each observer's event
log, which is where a fact about the past belongs. `claim_rank` alone belongs
to the table rather than to a play, and steps once per play.

**The information-set point.** Cheat is the corpus's **compound
hidden-function probe** for
[structural-infoset-proofs](../open-questions/structural-infoset-proofs.md):
the challenge verdict is a public Boolean function of hidden content — *do
all the face-down cards match the public claim?* — followed by a reveal of
exactly the cards the function read. Everything an observer knows falls out
of the declared projections and the emitted events, with no per-game
observation rule anywhere: before any call, a bystander's information state
is provably identical whether the play was honest or a lie (the proof
module pins this — the call/allow decision is made under genuine
uncertainty); the instant the flip fires, every player's information state
gains the flipped identities and the verdict's public routing (whose hand
ate the pile); and a play nobody calls leaks nothing, ever. A pile pickup
lands in the loser's `Hand`, so the loser learns exactly what they
collected (owner-identity projection) while everyone else sees the count —
which is why a player who has eaten the pile can bluff *better* afterwards,
and why their opponents' models of the pile differ from each other's. This
line-dependence — whether a hidden card may vary depends on whether it was
played, flipped, or picked up, not on any fixed attribute — is what defeats
the readiness harness's per-card swap axes, and Cheat therefore anchors the
**constructive world generator** (`tests/openspiel_ready/worlds.py`): the
proof derives the pinned cards from the line itself and permutes the entire
remaining hidden set, certifying indistinguishability by construction for
every observer.
