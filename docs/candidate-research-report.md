# Forcing-function research pass (verified)

A rigorous re-survey of card games against the seven open questions that
are gated on a *forcing function* (a game whose **rules** require the
construct — not merely whose strategy involves it). Every load-bearing
claim below was verified against an authoritative source (Pagat or the
publisher's rulebook), fetched 2026-06-02. This report is for discussion;
nothing in `docs/` or `_candidates.md` has been changed yet.

The discipline applied throughout: *exercises the system* means a rule of
legality, resolution, or scoring must read the construct. Games that only
involve a concept strategically were debunked.

## Headline

Two results dominate:

1. **Doppelkopf is a two-for-one.** One in-scope game forces *both*
   `zone-access-syntax` and `optional-window-moves`, and forces each
   harder than the current best candidate. It's the highest-value single
   addition the pass found.

2. **`higher-order-knowledge` is not forced by any card game's rules.**
   The two canonical candidates (Hanabi, Sheepshead) were both debunked:
   their higher-order reasoning lives entirely in conventions/tactics. The
   honest resolution is to record this as a non-forced question rather
   than wait for a game that won't come.

Beyond those, the strongest forcing functions split cleanly by corpus
scope — the in-scope ones are traditional games; several of the cleanest
are dedicated-deck modern games currently out of scope.

| Open question | Strongest forcing function | Verdict | In current scope? |
|---|---|---|---|
| zone-access-syntax | **Doppelkopf** (Fox/Charlie/Re scoring read "the partner of the holder of ♣Q") | forced | yes (Skat family) |
| optional-window-moves | **Doppelkopf** Re/Kontra/no-90 ladder (at-any-time, personal hand-size threshold) | forced | yes |
| contextual-rank (special-cards residual) | **President/Daihinmin** single-joker variant ("one higher than the card below it") | forced (HARD shape) | yes (standard 52) |
| move-level-visibility | **Poker "show one, show all"** (Robert's Rules, Showdown §6) | forced, incl. replace-vs-merge | yes (poker already in corpus) |
| memory-event-syntax | **Hanabi** partial-identity hint over an inverted-visibility hand | forced (first non-composable event) | no (dedicated deck) |
| knowledge-events | **Mascarade** mask-swap; **Love Letter** Baron | forced | no (dedicated decks) |
| higher-order-knowledge | — none — | **not forced by any game's rules** | n/a |

---

## Per-question findings

### zone-access-syntax — FORCED (Doppelkopf; Königrufen second witness)

*Forcing mechanic: a rule whose subject is a multi-hop relational chain —
"the partner of the player holding card X" — composed from a card-holding
query and a relational step.*

**Doppelkopf — verified, strongest.** Partnerships are *computed*, not
declared: "the two players who hold the queens of clubs … are partners
against the other two." The chain is read by several **scoring** rules,
not just strategy:

- *Catching the Fox* — capturing the opponents' ♦A scores a point, and the
  rules explicitly defer evaluation: "It may not be clear when the trick
  is won whether the Ace came from the winner's partner or opponent, in
  which case it is left face up and turned over … when the partnership
  becomes clear." That is "the partner of the ♦A's player, relative to the
  trick winner's side," with evaluation *deferred until the ♣Q holdings
  resolve* — a two-hop relational chain over hidden state, in rule
  position.
- *Charlie Miller* and *gegen die Alten* scoring likewise branch on
  "the trick winner's side" relative to the ♣Q holders.

Source: https://www.pagat.com/schafkopf/doko.html

**Königrufen — verified, second witness, adds a twist.** The declarer
"names a suit, the holder of the king of that suit becomes declarer's
partner but does not tell anyone who they are." Same holding→side query,
but the queried card is **chosen at runtime**, and the rules name the
degenerate cases ("It is legal to call your own king"; "you also play
alone if the called king happens to be in the talon"). 54-card *Industrie
und Glück* Tarock pack — in the same family as French Tarot, so within
extended corpus scope. Source: https://en.wikipedia.org/wiki/K%C3%B6nigrufen

**Sheepshead — corroborates, doesn't force the depth.** Partner = holder
of the called ace / Jack of Diamonds (a real holding→side query), but no
scoring rule goes the second hop ("partner of the holder"); play-legality
rules are one hop ("the holder of X must do Y"). Source:
https://www.pagat.com/schafkopf/shep.html

### optional-window-moves — FORCED (Doppelkopf; existing candidates debunked)

*Forcing mechanic: an off-the-clock optional declaration — any player may
act at any time within a window ending at a personal threshold; the game
doesn't stop and wait; declining is fine. (Tichu's call-before-Nth-card is
the existing example.)*

**Doppelkopf Re/Kontra ladder — verified, stronger than Tichu.** The page
states the property verbatim: "announcements can be made **at any time**
during the play, provided that you have at least the requisite number of
cards, **not just when it is your turn to play**." The window is bounded
by a *personal hand-size threshold* (Re/Kontra at ≥11 cards, then no-90 at
≥10, no-60 at ≥9, no-30 at ≥8, Schwarz at ≥7) — the direct analogue of
Tichu's "before your Nth card." It's a harder case than Tichu because the
threshold can be *computed* (reduced by tricks taken to determine a
marriage). Source: https://www.pagat.com/schafkopf/doko.html

**Debunked (all fixed-moment, not windows):** Belote/Coinche declarations
("at the moment he plays his card during the first trick"); Klaberjass
"Bela" ("declared as the … card of K-Q of trump is played"); Schnapsen
marriage ("at the start of any trick by the player whose turn it is to
lead … must lead one of the two cards"); Skat Kontra (non-standard, and a
fixed early-trick cutoff where played). Strategy may involve *timing* a
declaration, but no rule grants an at-any-time window. Sources:
https://www.pagat.com/jass/belote.html, https://www.pagat.com/jass/bela.html,
https://www.pagat.com/marriage/schnaps.html

### contextual-rank — FORCED (President joker variant; Haggis/Dalmuti debunked as HARD)

*Forcing mechanic: a card whose rank-for-comparison is resolved at play
time RELATIVE TO the current play (the hard shape, like Tichu's Phoenix as
a single = half a rank above the last card), as opposed to a wild whose
rank is a chosen constant (the easy shape).*

**President / Scum / Daihinmin (single-joker variant) — verified HARD
shape.** Pagat (authoritative, updated Dec 2025): "When a joker is played
by itself, it is assumed to be **one higher than the card played before
it**; for instance, a joker played on top of a single 5 is effectively a
6." That is the Tichu-Phoenix shape in a standard-52 game. (A related
"transparent threes" variant sets the wild *equal to the rank it beats* —
also relative-to-play.) Note the behaviour is variant-gated, not core
President. Source: https://www.pagat.com/climbing/president.html

**Debunked as HARD:** *Haggis* — its wilds (each player's face-up J/Q/K)
stand for a chosen *lower* rank **inside a combination** — a constrained
chosen-constant (EASY), not relative-to-play. *Great Dalmuti* — the Jester
"take[s] on the rank of the other cards" in its set (EASY). If a prior
pass cited either as forcing the hard shape, that was inaccurate. Sources:
https://thespiel.net/files/haggis.pdf,
https://media.wizards.com/2015/downloads/ah/great_dalmuti_rules.pdf

### move-level-visibility — FORCED (poker; already in-corpus family)

*Forcing mechanic: a move that overrides a zone's default visibility for
SOME observers but not others, ideally naming some observers and leaving
others at the default — which forces the replace-vs-merge sub-question.*

**Poker "show one, show all" — verified, decisive.** Robert's Rules of
Poker (Showdown §6): a player may show one hole card to one player, but
"every player at the table has a right to see those cards," and crucially
"**If only a portion of the hand has been shown, there is no requirement
to show any of the unseen cards.**" This forces the construct on three
axes at once: (1) per-observer override of the zone default; (2) the
override names *some* cards/observers while the rest stay at default — a
**merge**, not a wholesale replace; (3) the audience is computed from
state (if the recipient still has a wagering decision, it must become
public immediately; otherwise withheld until betting ends). Because poker
(Seven-Card Stud) is already in the corpus, this is exercisable by a
poker variant without a new game family. Source:
https://www.pagat.com/docs/RobsPkrRules11.pdf

**Corroborates:** Cabo "Spy" (peek one opponent card — one observer
upgraded, rest unchanged) — but this is exactly the existing `peek`
semantics, so it confirms merge-as-default for the peek family without
extending the question. **Debunked:** Gin Rummy draw-from-discard
(public) vs draw-from-stock (private) is *two zones with different
defaults*, not a move override; Mexican Stud / roll-your-own flips are a
*symmetric* full reveal whose only twist is which card is chosen.

### memory-event-syntax — FORCED (Hanabi; Cabo a match but composable)

*The live sub-question: is a named custom memory event ever needed, or
does composition of the closed vocabulary always suffice? Stud and Coup
were both composable.*

**Hanabi — verified, the case the question was waiting for.** Two features
combine into the first corpus event that is neither a stdlib op nor a
clean composition: (1) the **inverted-visibility hand** — "Players may not
see their own hand … The fronts can only be seen by the other players"
(owner sees *less* than others, the inverse of every current zone); (2)
the **hint** — a color or value hint "must indicate **all** cards of that
color"/value, including the right to indicate *zero*. A hint is a
per-attribute, per-position, complete-information projection update to one
observer about cards they cannot see, and it carries *negative* information
("your other cards are not red"). That's not `peek` (no full identity),
not `reveal` (not common knowledge), not `announce` (not a whole-zone
proposition). 50-card deck, 5 colours × (1,1,1,2,2,3,3,4,4,5). Source:
https://www.ultraboardgames.com/hanabi/game-rules.php

**Cabo — verified match, but covered by existing primitives.** Its actions
map cleanly to stdlib: peek-own, peek-other (`peek`), reveal-on-failed-
match (`reveal`), and **blind-swap** (transfer with no observation). Blind-
swap is the one event the model currently handles only *implicitly*; Cabo
makes it a first-class, deliberate action, which argues for stating "move
cards **and** destroy per-slot identity knowledge, reveal nothing"
explicitly. It does *not* force custom-event declaration syntax. (Note: the
"King look-then-swap" power attributed to Cabo in the prior pipeline could
not be verified in any authoritative ruleset — it exists only in a
Malaysian standard-deck folk variant, and as a blind swap.) Sources:
https://www.cabogame.com/how-to-play, https://en.wikipedia.org/wiki/Cabo_(game)

### knowledge-events — FORCED (Mascarade; Love Letter Baron); 500 debunked

*Forcing mechanic: a phase/resolution OUTCOME observed unequally — some
observers learn it, others learn only a weaker projection.*

**Mascarade "Exchange your Mask" — verified, cleanest.** "without looking,
hold them under the table and **exchange or pretend to exchange** them."
The swap-or-not outcome is observed unequally by construction: the actor
knows whether the swap happened; the player whose card was taken does
*not*; the table sees only that an exchange action occurred. Even the actor
doesn't learn the card identities. The unequal observation is *structural
to the move*, not an optional peek. Source: Asmodee v2 rulebook PDF.

**Love Letter Baron — verified, strongest standard-shaped corroborator.**
"You and that player **secretly compare** your hands. Whoever has the
lower-value card is out." One resolution step produces three information
states: the two comparers learn each other's card; the table learns only
"who lost" (and then sees the loser's revealed card, never the winner's).
Priest (private look) also qualifies; Guard (public hit/miss) does not.
Source: official 2019 AEG rulebook.

**Debunked:** 500 open misère ("face up on the table **for all to see**")
and Pinochle/Belote meld declarations are *symmetric* reveals — the hand
becomes common knowledge to everyone at once. That's a visibility
transition, not an unequally-observed outcome. Source:
https://www.pagat.com/euchre/500.html

### higher-order-knowledge — NOT FORCED BY ANY GAME (recommend resolving)

*Forcing mechanic: a rule that reads "P knows that Q knows X" as input to
legality, resolution, or scoring.*

**No card game qualifies.** Hanabi's rules read only objective tile facts
("must give complete information … must point to ALL matching tiles"); the
famous higher-order reasoning is entirely in player *conventions*
(finesse, bluff), explicitly outside the rules. Sheepshead's called
partner is genuine *first-order* hidden information ("the identity of the
picker's partner is not known to anyone but the partner") but no rule
reads knowledge-of-knowledge. The structural reason: rulebooks route
everything through observable card facts and at most first-order private
information, precisely to stay refereeable. This is a strong signal to
resolve the question as "not forced by any in-scope game; do not add a
construct no game exercises" rather than keep waiting. Sources:
https://github.com/hanabi/hanabi.github.io/blob/main/misc/rules.md,
https://www.pagat.com/schafkopf/shep.html

---

## Corrections to existing `_candidates.md` facts

The pass turned up two genuine errors and several nuances in the current
pipeline file (verify before any future game file relies on them):

- **Cabo deck — wrong.** Listed as "standard 52 + 2 jokers." It is a
  *dedicated point deck*, suits numbered 0–13 (commonly four each of 1–12
  plus two 0s and two 13s), objective = minimise your sum. "4 cards each,
  peek 2" is correct. The standard-52 version is the folk game
  (Cambio/Pablo/Cactus). Source: https://en.wikipedia.org/wiki/Cabo_(game)
- **Doppelkopf deck — mislabelled.** Listed as "48-card double-pinochle
  deck." It is *two Skat packs with the 7s and 8s removed* (48 cards,
  ranks A 10 K Q J 9 ×2 per suit; the 40-card variant drops the 9s). A
  Pinochle deck has no 9s — different rank set. Source:
  https://en.wikipedia.org/wiki/Doppelkopf
- **Sheepshead deck — probably the same mislabel** ("32-card
  double-pinochle deck" is internally inconsistent — 32 ≠ 48). Not
  independently re-verified here; flag to check (it's a 32-card Skat pack).
- **Hanabi 6th suit — nuance.** The multicolour variant is usually a
  *short* 5-card suit (→55), occasionally a full 10-card suit (→60); the
  base game is 50.
- **Scopa capture — nuance.** Base Scopa *forces* the single-card match
  when one exists; free choice between rank-match and sum-capture is a
  variant (Cirulla / Scopa a Quindici).

---

## Recommended moves for the candidates file (for discussion)

Not applied yet — this is the agenda:

1. **Add Doppelkopf as the top in-scope recommendation**, tagged to *both*
   `zone-access-syntax` and `optional-window-moves`, replacing the
   weaker/uncertain prior tags. It's a Skat-family game (in scope) that
   forces two questions at once.
2. **Re-tag `contextual-rank`** to the President single-joker variant
   (HARD shape, in scope); demote Haggis/Dalmuti to "EASY-shape only."
3. **Re-tag `move-level-visibility`** to a poker "show one, show all"
   variant — notably exercisable within the *existing* poker corpus, so
   it may not need a new game at all.
4. **Resolve `higher-order-knowledge`** as not-forced (promote a short
   note to `decisions.md`, delete the open question), on the strength of
   the Hanabi/Sheepshead debunks.
5. **Flag the scope decision** for `memory-event-syntax` (Hanabi) and
   `knowledge-events` (Mascarade/Love Letter): the cleanest forcing
   functions are dedicated-deck games currently out of scope. Either
   widen scope to bring one in, or record that these two questions are
   blocked on a scope decision rather than on finding a game.
6. **Apply the deck-fact corrections** above.
