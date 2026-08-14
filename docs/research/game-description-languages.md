# A Survey of Game Description Languages, with a Focus on Card Games

## TL;DR

- **No off-the-shelf DSL cleanly covers the 52-card family.** GDL-II is the most theoretically complete option but verbose and slow; Ludii is the most ergonomic but only added rudimentary card support in a 2025 master's thesis (5 toy games, in a personal fork, perfect-information only); RBG is fast but deterministic-only; Zillions/Axiom never supported hidden information; and per-game libraries (RLCard, PokerKit, OpenSpiel, Forge) are APIs, not DSLs. There is a real gap to fill.
- **The deepest design lessons come from Ludii (ludemes as the right abstraction level), GDL-II (sees/random as a minimal-but-universal way to model hidden info), and RBG (compile a high-level description to an automaton for speed).** Card effects can in principle make a system Turing-complete (Magic: The Gathering proof, FUN 2021), so a usable card DSL must consciously choose to be sub-Turing for tractability.
- **Build on Ludii's ludemic style and class-grammar approach but design the type system around card-game primitives (zones, decks, hands, tricks, info-sets) from day one rather than retrofitting them.** Use GDL-II's `sees`/`random` semantics as the formal backbone for hidden information, and target an OpenSpiel- or RLCard-compatible runtime so existing imperfect-information MCTS / CFR algorithms work out of the box.

---

## Key Findings

1. **GDL/GDL-II (Stanford)** is the academic reference point: a Datalog-like declarative logic language. GDL-II's two added keywords (`sees`, `random`) are an elegantly minimal way to model hidden information and chance, and the language has been formally proven universal for finite n-player imperfect-information extensive-form games (Thielscher, IJCAI 2011). The price is verbosity and slow reasoning (model-checking ATL over propositional GDL is EXPTIME-complete; richer GDL fragments range up to 2EXPTIME).

2. **Ludii (Maastricht)** is the most practically usable successor. Its ludemic class-grammar lets you describe Tic-Tac-Toe in ~10 lines and chess in ~30. The official Ludii AI Competition GitHub repository (Ludeme/LudiiAICompetition) states: "The version used for this competition (1.3.2) of Ludii includes over 1,000 games"; the current release as of Feb 2025 is version 1.3.14. But it ships essentially zero proper card games — a 2025 UCLouvain master's thesis by Alexandre Verlaine added 5 simple card games and 11 new ludemes in a personal fork that is not merged upstream.

3. **Regular Boardgames (RBG, Wrocław)** trades expressiveness for speed: rules are a regular expression that defines the language of legal plays, compiled to a C++ reasoner. Kowalski et al. (arXiv:1910.00309, Oct 2019) report: "RBG is about 37 times faster than Ludii, and Ludii is about 3 times slower than a GDL propnet" — but RBG is deterministic and perfect-information by design. Its 2024 successor "Regular Games" extends the automata approach to imperfect information.

4. **Older systems (Metagame, Zillions/ZRF, Axiom)** are historically important but mostly cautionary. Zillions' ZRF (a Lisp-like S-expression DSL) cannot represent hidden information at all and lacks variables and arithmetic beyond Booleans. Axiom fixed this by embedding Forth — which tells you what happens when minimalist DSLs collapse under card-game complexity.

5. **Card-specific frameworks are libraries, not DSLs.** PokerKit (Toronto), RLCard (Rice/Texas A&M), OpenSpiel (DeepMind), and Forge/XMage/Cockatrice (MTG) all represent games as code (Python/C++/Java classes) or text-with-engine-runtime rather than as a declarative game description. CARDSTOCK/ReCycle (Bell & Goadrich 2016) is one of the few attempts at a true declarative card-game DSL and remains active.

6. **Hidden information and randomness are the central design axis** for a card DSL. The cleanest formalization remains GDL-II's: a special `random` role plus per-role `sees` predicates that determine each player's observation history (which collectively defines that player's information set). Ludii fakes this with a `hidden` vector per location, indexed per player.

7. **Card effects can be arbitrarily complex.** Churchill, Biderman, and Herrick (FUN 2021) proved Magic: The Gathering is Turing-complete *under standard tournament rules*, with all moves forced — meaning even single-step legality (Chatterjee & Ibsen-Jensen, ECAI 2016) is computationally hard. Any CCG-extension story must consciously give up universality.

8. **AI algorithms care about the DSL.** Modern card-game AI (Information-Set MCTS, determinization, CFR, deep RL) all need cheap access to: (a) the current information set, (b) a fast forward simulator, and (c) a way to sample concrete determinizations consistent with what a player has seen. DSLs that don't make these first-class are hostile to modern AI.

---

## Details

### 1. GDL and GDL-II: the Datalog approach

The Game Description Language was introduced by the Stanford Logic Group (Love, Hinrichs, Haley, Schkufza, Genesereth 2006) as the official language of the AAAI General Game Playing competition. It is a variant of Datalog: rules are Horn clauses, queries are decidable, semantics is purely declarative. Eight reserved predicates carry the entire framework:

- `(role ?r)` — declares a player
- `(init ?f)` — facts true in the start state
- `(true ?f)` — fact `?f` holds in the current state
- `(legal ?r ?m)` — `?r` may play move `?m`
- `(does ?r ?m)` — `?r` actually played `?m`
- `(next ?f)` — `?f` will hold in the successor state
- `(terminal)` — game has ended
- `(goal ?r ?n)` — `?r`'s payoff is `?n`

A fragment of Tic-Tac-Toe in GDL (canonical example from Stanford's GGP notes):

```lisp
(role xplayer)
(role oplayer)
(init (cell 1 1 b)) ... (init (cell 3 3 b))
(init (control xplayer))

(<= (legal ?p (mark ?x ?y))
    (true (cell ?x ?y b))
    (true (control ?p)))

(<= (next (cell ?x ?y x))
    (does xplayer (mark ?x ?y)))

(<= terminal (line x))
(<= (goal xplayer 100) (line x))
```

**GDL-II** (Thielscher, AAAI 2010 / IJCAI 2011) adds exactly two reserved symbols to handle chance and hidden information:

- A built-in role `random` that plays "nature's" moves (dealing, shuffling, dice).
- A predicate `(sees ?r ?p)` that says "in the next state, role `?r` perceives `?p`."

A GDL-II Texas Hold'em fragment looks like:

```lisp
(<= (sees ?player ?card)
    (does random (deal_face_down ?player ?card)))
(<= (sees ?r ?card)
    (role ?r)
    (does random (deal_river ?card)))
```

Each player's information set is then the set of game histories that produce the same sequence of `sees` perceptions for that player — a clean, model-theoretic story that lifts directly to extensive-form games of imperfect information.

**Takeaways for a software engineer:**

- The `sees`/`random` design is the most economical formalism for hidden info you'll find anywhere; copy it.
- Datalog-as-DSL is logically clean but operationally painful. Even a propositional fragment makes model-checking ATL EXPTIME-complete (Ruan, van der Hoek, Wooldridge, *Journal of Logic and Computation* 2009): "interpreting ATL formulae over propositional GDL descriptions is EXPTIME-complete." Full GDL fragments range from NP to 2EXPTIME (Cerexhe, Rajaratnam, Saffidine, Thielscher 2014).
- Stanford's GGP-Base reference implementation and the GDL-II spec are open source.
- **GDL-III** (Thielscher 2017) further adds introspective epistemic reasoning — rules that depend on what players *know* they know. Useful for bridge bidding or Hanabi-like games.

### 2. Regular Boardgames (RBG)

Kowalski, Mika, Sutowicz, Szykuła (AAAI 2019). The insight: every finite deterministic perfect-information turn-based game can be described as the *regular language of legal play sequences*. The RBG description is essentially a regular expression over an alphabet of board operations; the compiler converts it to a finite automaton and emits a C++ reasoner.

Performance: on chess RBG is roughly 37× faster than Ludii and orders of magnitude faster than GDL propnets (Kowalski et al., arXiv:1910.00309). The 2024–2025 successor "Regular Games" (Miernik, Szykuła, Kowalski et al., arXiv:2511.10593) extends the automata approach to imperfect information and adds a higher-level surface language (HRG) that compiles to the automaton core.

**Lesson for card-DSL design:** the two-level architecture is powerful — a high-level surface for humans, a stripped-down compiled core for the runtime. But pure automata struggle to express "draw 5 cards, choose any 3, shuffle the rest back" kinds of structured non-determinism, which is the bread and butter of card games.

### 3. Ludii: the ludemic approach

Ludii (Piette, Soemers, Stephenson, Sironi, Winands, Browne; ECAI 2020) is the most ergonomic of the modern systems. It is the centerpiece of the ERC-funded Digital Ludeme Project (Browne, Maastricht, ERC Consolidator Grant #771292).

**Ludemes** are "conceptual units of game-related information" — atomic, named, parameterizable building blocks like `(square)`, `(piece)`, `(step)`, `(slide)`, `(hop)`, `(line)`, `(deck)`, `(hand)`. A game is a tree of ludemes. Cardinally, Ludii uses a **class grammar**: the grammar is automatically derived from the Java class hierarchy of the ludeme library. Adding a new ludeme = adding a Java class.

Tic-Tac-Toe in Ludii:

```
(game "Tic-Tac-Toe"
  (players 2)
  (equipment {
    (board (square 3))
    (piece "Disc" P1) (piece "Cross" P2) })
  (rules
    (play (move Add (to (sites Empty))))
    (end (if (is Line 3) (result Mover Win)))))
```

For card games, Ludii defines `(hand ...)` containers (each owned by a player or shared), `(deck ...)` containers (a hand of a single site with a stack of cards), and `(card ...)` components parameterized by rank, value, trump-rank, trump-value. Game state vectors include a per-location `hidden` mask per player.

**State of card support (this matters):**

- As of pre-2025 Ludii officially ships no card games. Stephenson et al. (arXiv:2301.03913, "Measuring Board Game Distance"): "Ludii does not currently include any card games, even though many modern board games often use cards in some capacity."
- The 2025 master's thesis "Introducing Card Games in Ludii" (Alexandre Verlaine, supervisor Eric Piette, École polytechnique de Louvain) added 5 card games — Simplified Uno, Bataille (War), The Game, 5 Alive, Briscola — and 11 new ludemes (CardType, CardTable, DealCards, DealDeck, SetTrump, ValueCardType, ValuePot, Trump, HasAttribute, IsMaxAttribute, IsMinAttribute, CountCardType) plus a `FrenchCards` ludemeplex for a 52-card deck. The work lives in a personal fork (github.com/ALverlaine/Ludii), not merged into the official repository.
- The thesis is explicit about limitations: "Ludii employs an optimized approach to encoding game elements, limiting the number of distinct pieces to a maximum of 32" (a 32-piece bitset), and "Currently, the modeling is based on perfect information. Therefore, if games use imperfect information as a key gameplay mechanic, it would be necessary to modify the game rules to replace this mechanic." Skyjo and Stratego "cannot be elegantly implemented."
- Future work listed in the thesis: Poker (Texas Hold'em, Omaha), Hearts, Belote, and trading card games (MTG, Yu-Gi-Oh!).

**Verdict on Ludii as a base:** the ludeme/class-grammar idea is excellent and worth borrowing. But forking Ludii to be a serious card-game DSL would mean fighting the 32-piece bitset, redesigning the hidden-information story (which is currently shallow), and adding a CFR/IS-MCTS-friendly runtime. The Verlaine thesis essentially documents the difficulty.

### 4. Older systems: Metagame, Zillions/ZRF, Axiom, Ai Ai

- **Metagame / Metagamer (Pell, Cambridge, 1992)** — the historical originator of "general game playing"; a Prolog system that *generated* and played symmetric chess-like games from a grammar. It introduced the GDL term (later reused by Stanford). Source still available at github.com/barneypell/metagame. **Lesson:** PCG of game rules has been a goal since 1992; modern LLM-based game generation (GAVEL, NeurIPS 2024) is the latest iteration.
- **Zillions of Games / ZRF (Mallett & Lefler, 1998).** Lisp-like S-expression DSL; shipped with ~300 games and the community wrote ~2,500 more. **Critically: ZRF has no hidden-information support, no real variables, no arithmetic.** Wikipedia is blunt: "Zillions Of Games is designed to play perfect information games exclusively. This renders it of little or no use in fairly playing imperfect or hidden information games against the AI, such as card games or board games with hidden piece values like Stratego." **Lesson:** absence of variables and arithmetic is the root cause; do not repeat it.
- **Axiom Development Kit (Schmidt, 2007)** is a Zillions plug-in that replaces the ZRF interpreter with a Forth-based engine. **Lesson:** when your minimalist DSL hits the Owner Guard, embedding a real Turing-complete scripting language is the usual escape hatch. A card DSL should provide controlled extensibility from the start.
- **Ai Ai / MGL (Stephen Tavener)** is a modern descendant that runs hundreds of games via the "Modular Game Language." Less academically documented but practically substantial; Tavener has worked on both Zillions and Ludii, so MGL incorporates lessons from both.

### 5. Card-game-specific frameworks (libraries, not DSLs)

| System | Language | Approach | Card games | DSL? |
|---|---|---|---|---|
| **OpenSpiel** (DeepMind; Lanctot et al. 2019) | C++ / Python | Procedural extensive-form games | Kuhn poker, Leduc poker, Texas Hold'em (limit/no-limit), Goofspiel, Bridge, Hearts, Gin Rummy, etc. | No — C++ classes implementing a common interface |
| **RLCard** (Zha et al., IJCAI 2020; DATA Lab, Rice/Texas A&M) | Python | RL toolkit with per-game environments | Blackjack, Leduc Hold'em, Limit/No-Limit Texas Hold'em, Doudizhu, Mahjong, UNO, Gin Rummy, Bridge | No — one Python module per game |
| **PokerKit** (Kim, *IEEE Transactions on Games* 17(1):32–39, 2025; UofT CPRG) | Pure Python | Fine-grained state-machine API | 11+ named variants (NLHE, PLO, multiple Stud, Razz, Badugi, Deuce-to-Seven Draw, Short-deck, Courchevel, Greek hold'em, Kuhn Poker, etc.) plus custom variants | No — programmatic API; users configure via constructor parameters |
| **Forge** (Card-Forge/forge) | Java engine + text DSL | Each Magic card is a `.txt` file with key:value scripting (`Name:`, `ManaCost:`, `K:` keyword, `A:` ability, `T:` trigger, `SVar:`) | MTG — per the Forge wiki, "Over 99% (and counting) of all cards in Magic's existence are available, with the missing ones mostly being pointless to implement in the context (e.g. the notorious Chaos Orb) or impossible." | **Yes** — a real card-specific DSL parsed by a Java engine |
| **XMage** (magefree/mage) | Java | One Java class per card, composing reusable Ability/Effect classes | MTG — per xmage.today: "full rules enforcement for over 30 000 unique cards and more than 75 000 reprints from different editions" | No |
| **Cockatrice** | C++/Qt + XML | Pure data-driven `cards.xml`, **no rules enforcement** ("kitchen-table" model) | MTG | No |
| **CARDSTOCK / ReCycle** (Bell & Goadrich, "Automated Playtesting with RECYCLEd CARDSTOCK," *Game & Puzzle Design* 2(1):71–83, 2016) | Python | Declarative DSL with explicit hands/decks/zones — per github.com/mgoadric/cardstock, "There are currently 60+ games coded in RECYCLE, a mixture of classic and modern games, categorized by genre." | Generic card games (60+ implemented) | **Yes** — closest existing prior art for a generic card-game DSL |
| **Bridge bidding systems** (e.g., phiSgr/bidding-system-as-code) | Various | Hobbyist DSLs for bridge conventions | Bridge bidding only | Domain-specific |

**Takeaway:** the AI/RL world has settled on libraries with a common imperative API (OpenSpiel's `State`, `apply_action`, `legal_actions`, `information_state_tensor`, `chance_outcomes`) rather than declarative DSLs. The CCG world is split: Forge has a real DSL, XMage has Java-per-card, Cockatrice has data but no rules. **For a card DSL aimed at standard-deck games, CARDSTOCK/ReCycle is the most direct prior art and is worth a careful read; Forge's text scripting is the most mature example of "actual rules in a custom mini-language" at scale (tens of thousands of cards).**

### 6. Formal semantics: how games are modeled

The dominant formal model is the **extensive-form game with imperfect information** (Kuhn, 1950s), formalized as a tuple `(N, A, H, Z, χ, ρ, σ, u, I)`:

- `N` = players (including a "chance" player for randomness)
- `H` = histories (sequences of actions); `Z ⊂ H` = terminal histories
- `ρ: H \ Z → N` assigns the player to move at each non-terminal history
- `σ: chance histories → distributions` for random moves
- `u: Z → ℝ^|N|` payoffs
- `I_i` = partition of player `i`'s decision histories into **information sets** — histories `i` cannot distinguish

A 2019 paper by Kovařík and Lisý (arXiv:1906.06291) argues "the extensive-form game model isn't powerful enough to express all important aspects of imperfect information games" and recommends moving to **partially observable stochastic games (POSGs)** as the underlying model — explicit observations rather than information-set partitions. This is the direction OpenSpiel and modern card-AI papers are trending.

Most game DSLs encode this in one of three styles:

- **Logic-programming / Datalog** (GDL, GDL-II): rules are Horn clauses; state is a set of true ground facts.
- **Situation calculus / fluent calculus** (Reiter; Thielscher 1999, 2011): state is a first-order term, actions are functions on terms. Schiffel & Thielscher (AAAI 2011) gave a sound and complete embedding of GDL-II into the situation calculus with Scherl-Levesque knowledge fluents — useful for epistemic verification.
- **Operational / class-grammar** (Ludii, RBG): state is a vector, actions are imperative effects, semantics is "whatever the Java/C++ runtime does."

For a card-game DSL aimed at engineers, the operational style is more practical, but the GDL-II model should be the formal sanity check.

### 7. Complexity and expressiveness

Known results that bound the design space:

- **Generalized board games are intrinsically hard.** Generalized chess, Go (Japanese ko rules), and Checkers are EXPTIME-complete (Hearn & Demaine, *Games, Puzzles, and Computation*, 2009). Anything more expressive can only be harder.
- **GDL** corresponds to EXPTIME for verification problems. ATL model-checking over propositional GDL is EXPTIME-complete (Ruan, van der Hoek, Wooldridge, *J. Logic & Computation* 2009): "interpreting ATL formulae over propositional GDL descriptions is EXPTIME-complete."
- **GDL fragments** range from NP to EXPSPACE (single-agent) and PSPACE to 2EXPTIME (multi-agent), per Cerexhe et al. ("On the Complexity of General Game Playing", 2014).
- **GDL-II** is universal for finite n-player extensive-form games with chance and imperfect information (Thielscher, IJCAI 2011: "The General Game Playing Description Language Is Universal").
- **Magic: The Gathering is Turing-complete.** Churchill, Biderman, Herrick (FUN 2021, LIPIcs vol. 157, 9:1–9:19; arXiv:1904.09828): "optimal play in real-world Magic is at least as hard as the Halting Problem… we present a methodology for embedding an arbitrary Turing machine into a game of Magic such that the first player is guaranteed to win the game if and only if the Turing machine halts. Our result applies to how real Magic is played, can be achieved using standard-size tournament-legal decks, and does not rely on stochasticity or hidden information." Even deciding the legality of a single step is hard (Chatterjee & Ibsen-Jensen, ECAI 2016).

**Design implication:** for the *standard 52-card* corpus you're targeting, every game in scope is finite, has bounded state, and is at worst PSPACE-hard for the underlying decision problem. A DSL with strictly first-order, no-recursive-effect semantics will suffice. The Turing-completeness result applies only to CCG-style effect interactions, which justifies your decision to keep CCGs out of scope initially.

### 8. Related formal-language work

- **Process calculi (CCS, CSP)**: rarely directly applied to game description, but the "parallel composition" operator is exactly what you want for simultaneous moves.
- **Petri nets and Petri games**: applied to card-game modeling (Araújo & Roque, "Modeling Games with Petri Nets," 2009; Daniels & Mitra, "Implementing Timed Petri Net for Modeling and Simulation in Card Gameplay," CATA 2020, modeling a Texas Hold'em algorithm). **Petri games** (Finkbeiner & Olderog) add players and informedness; synthesis is decidable for restricted classes. Worth knowing about but probably overkill for a 52-card DSL.
- **Event calculus / situation calculus**: as above — formal verification backbone, not a surface syntax.
- **Linear logic / Ceptre** (Martens, 2015): rule-based DSL for "generative interactive systems" — explicitly designed to model multi-agent simulation with linear-logic rules where each fact is consumed once. Card draws and hand transitions map naturally to linear-logic resource consumption. Worth studying as a primitive set.
- **Machinations** (Dormans, 2011): visual game-mechanics diagrams; less formal but designer-friendly.
- **VGDL / PuzzleScript**: video-game DSLs (real-time arcade-style and tile-puzzle respectively); irrelevant to card games but their pattern-rewriting approaches are intellectually adjacent.

### 9. Hidden information and randomness: the central design axis

The three live approaches:

- **GDL-II style: explicit `sees`/`random`.** Each player's information set is the equivalence class of histories that produce the same observation trace for that player. Clean, universal, slow.
- **Ludii style: a per-location `hidden` mask** that records which players can see what. Easier to write, less formally crisp, and (per the Verlaine 2025 thesis) inadequate for games where imperfect information *is* the mechanic — the thesis notes Stratego requires "approximately 200 lines of code with complex tracking mechanisms. This reveals a significant gap between Ludii's design goals and its current capabilities for handling imperfect information." Skyjo cannot be elegantly implemented at all.
- **OpenSpiel / RLCard style: explicit `chance_outcomes()` and `information_state_tensor(player)`** methods that the game implementation supplies. Hands the burden to the game author but lets AI algorithms (CFR, IS-MCTS, deep RL) work uniformly.

**The right design choice for a card DSL** is probably to **combine all three**: declare information visibility per zone (Ludii-style), generate `sees` events automatically from zone visibility rules (GDL-II-style), and expose `information_state_tensor` and `chance_outcomes` to the runtime (OpenSpiel-style). Visibility is the primary abstraction — most card-game hidden info reduces to "which zone is this card in?" (hand vs. table vs. deck vs. discard) and "who can see which zones?"

### 10. Forward-looking: CCG-style effects

Card-driven CCGs introduce three structural problems standard-deck games don't have:

1. **Cards have rules text.** Each card is essentially its own micro-program. Forge's text DSL has fields like `K:Flying`, `A:AB$ DealDamage | Cost$ 2 R | NumDmg$ 3`, `T:Mode$ ChangesZone | Origin$ Battlefield | Destination$ Graveyard | Execute$ TrigDraw`. The Forge wiki notes that over 99% of all Magic cards are scripted this way.
2. **Effect stacks and replacement effects.** When multiple effects trigger simultaneously, ordering and replacement (e.g., "if a creature would die, exile it instead") create a small interpreter inside the rules engine.
3. **Turing-completeness.** As above; once you have triggered abilities with conditions referencing arbitrary game state, you cannot bound computation in general.

A reasonable extension story for the proposed card DSL: keep standard-deck cards as static "atoms" with no rules text (their meaning comes from the game's rules), and reserve a future second layer for CCG-style cards-with-text, where the rules-text language is a separately-versioned restricted DSL with bounded recursion. This mirrors how Forge is structured.

### 11. AI and the DSL: why it matters

AI techniques that work for card games and the DSL affordances they need:

- **Information-Set MCTS** (Cowling, Powley, Whitehouse, *IEEE TCIAIG* 2012): runs MCTS over information-set trees rather than state trees. Needs cheap access to `legal_actions(infoset)` and to draw determinizations consistent with the infoset.
- **Determinization + MCTS** (Cowling et al.; Magic paper IEEE 2012): sample concrete states consistent with what you know, solve the perfect-info game, vote. Needs the DSL to provide a "determinize" primitive.
- **Counterfactual Regret Minimization (CFR)** and variants (Libratus, Pluribus): solve poker-style games to ε-Nash. Needs cheap traversal of the game tree by information set, fast forward simulation, and good abstractions.
- **Deep RL / AlphaZero-style self-play** (extending to imperfect info via ReBeL, Player of Games).

**The DSL choice affects each:**

- A *Datalog* DSL (GDL) is slow per forward step; good for verification, bad for self-play.
- A *compiled* DSL (RBG, OpenSpiel) is fast per step but limits expressiveness.
- A *visibility-typed* DSL (what you want to design) can auto-derive information sets, making IS-MCTS and CFR work without per-game glue code.

The most important affordance to get right: **the DSL must let the runtime answer `chance_outcomes()`, `information_state(player)`, and `legal_actions(player)` in O(small) without re-running the rules.** Ludii achieves this with its precomputed state vectors; OpenSpiel forces the game author to do it manually; GDL forces propnet compilation. A good design takes Ludii's auto-derivation and combines it with OpenSpiel's API surface.

---

## Recommendations

**Stage 1 (now): build a prototype directly inspired by Ludii's class grammar but native to cards.**

- Use S-expression or JSON-like surface syntax (Ludii-style), parsed into a typed AST.
- Define first-class primitives: `Deck`, `Hand`, `Discard`, `Trick`, `Meld`, `Tableau`, `Player`, `Card(rank, suit)`. Each is a *zone* with a visibility relation `visible_to: Set<Player>`.
- Actions are atomic moves between zones (`move(from_zone, to_zone, predicate)`), structured non-deterministic dealing (`deal n from Deck to each Hand`), and condition checks (`if predicate then ... else ...`).
- Implement on top of a Python or Rust runtime that exposes an OpenSpiel-compatible interface (`State`, `legal_actions`, `apply_action`, `chance_outcomes`, `information_state_tensor`). This buys you free integration with CFR, IS-MCTS, and modern RL.
- **Benchmarks to hit before declaring success:** Crazy Eights, Hearts (full 4-player with passing), Klondike solitaire, Blackjack (with house rules as parameters), 5-card draw poker, Gin Rummy, Spades, Texas Hold'em. If you can do these in under ~200 lines each you've matched or beaten Ludii's ergonomics.

**Stage 2 (after Stage 1 lands ≥10 games): formalize the semantics.**

- Write a small-step operational semantics document mapping each ludeme to a GDL-II-style rule. This gives you a paper trail for arguing universality and helps catch bugs.
- Add a tagged-union `Observation` event stream per player. Make information sets *derived* from observations rather than declared; this is the GDL-II contribution and worth keeping.
- Add a deterministic-equivalent-game transform (for determinization-based AI) as a compiler pass.

**Stage 3 (CCG extension, only if needed): separate cards-with-text into a second tier.**

- Study Forge's text DSL in detail; it is the most mature precedent (covers >99% of MTG's card pool).
- Decide explicitly whether you allow Turing-completeness. If you don't, you need a static analyzer that rejects card text that could loop (e.g., a termination metric similar to Ludii's 10,000-move cap).
- Consider linear-logic style (Ceptre) for triggered effects: each "trigger" is a rewrite rule that consumes input facts and produces output facts.

**Benchmarks that would change these recommendations:**

- *If Ludii merges the Verlaine card-game extension and reaches ≥30 properly-supported card games with hidden-information support*, the rational move is to fork Ludii rather than start fresh — you get ~1,000 board games for free.
- *If OpenSpiel adds a declarative game-description front-end* (rumored periodically; not shipped as of May 2025), build on it.
- *If a new GGP-style language emerges with strong card-game support* (the "Regular Games" 2024 paper has potential), study it before committing.

**What to study or build on first, in this order:**

1. **Read the Ludii ECAI 2020 paper and the Verlaine 2025 thesis** to understand both the ludemic approach and where it breaks on cards.
2. **Read the GDL-II AAAI 2010 paper** (Thielscher) for the formal semantics of hidden info.
3. **Read the CARDSTOCK / RECYCLE paper** (Bell & Goadrich, *Game & Puzzle Design* 2016) and the project repo at github.com/mgoadric/cardstock — closest direct prior art with 60+ implemented games.
4. **Read PokerKit's API design** (Kim, *IEEE Transactions on Games* 17(1):32–39, 2025) to see what fine-grained card-game state methods look like in practice.
5. **Skim Forge's card-script DSL** (cards in github.com/Card-Forge/forge under `forge-gui/res/cardsfolder`) to see what scaling a card DSL to ~30,000 cards actually looks like.
6. **Use OpenSpiel as your runtime substrate** unless you have a strong reason otherwise — its API is the de facto standard for imperfect-information game AI research.

---

## Caveats

- **Ludii's card support is in flux.** The Verlaine 2025 thesis is the most recent data point; the situation may change quickly if Maastricht prioritizes a card-game release. Re-check ludii.games and the official Ludeme/Ludii GitHub before committing.
- **GDL is increasingly seen as a research artifact.** Per the Stanford GGP overview (ggp.stanford.edu): "The International GGP Competition was suspended after 2016. However, by then, the competition had served its primary purpose — it led to workshops on GGP at multiple international conferences and the publication of numerous research papers on GGP and its applications." Most active research (OpenSpiel, RLCard, Ludii) has moved on. Don't pick GDL as a runtime; do pick its formal semantics as a model.
- **"Universal" doesn't mean "practical."** Both GDL-II and Ludii are proven universal for finite extensive-form games with imperfect info, but in both cases the game descriptions blow up quickly for games that aren't a natural fit. Universality is necessary but not sufficient.
- **The Magic Turing-completeness result** (Churchill, Biderman, Herrick 2021) is sometimes overhyped. It requires very specific card combinations and shows undecidability *in principle*; real Magic play is bounded by life totals and deck sizes. But the result does establish that any CCG DSL must consciously trade expressiveness for tractability.
- **Performance numbers are contested.** The RBG-vs-Ludii benchmarks (arXiv:1910.00309 versus the Ludii team's responses in CoG 2019) have gone back and forth; both teams have valid points. Treat single-number speed claims with skepticism — they depend heavily on which game is benchmarked and which optimizations are enabled.
- **The Kovařík-Lisý (2019) critique of the extensive-form-game model** is important if you care about online game-solving and search decomposition; for offline DSL design it's less urgent but worth knowing.
- **CARDSTOCK/ReCycle's adoption is modest** despite being active. The 60+ games in the repository are mostly small designs, not full tournament-level implementations of Bridge or Hearts. Treat it as inspiration and a primitive set, not as a finished platform you can adopt wholesale.
- **AI integration is a moving target.** OpenSpiel, RLCard, and PettingZoo all have slightly different API conventions. A new DSL should target one of them as a primary interface but expect to add adapters.