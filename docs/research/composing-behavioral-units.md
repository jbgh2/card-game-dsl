# Composition and Interaction of Independent Behavioral Units: A Landscape Survey

## TL;DR
- The literature on "behavior composition" lives in two largely disjoint communities: a **PL/SE side** (AOP, algebraic effects, FOP/SPL, traits, multimethods, object algebras, ECS, hooks, language workbenches, FRP, process calculi) that gives you mature, mechanically-checkable mechanisms but rarely promotes the *interaction itself* to a first-class entity; and a **game-studies side** (MDA, Björk & Holopainen patterns, Machinations, Salen & Zimmerman, Ludii, VGDL/PuzzleScript, feedback-loop vocabulary, Juul's emergence/progression) that has rich vocabulary for interactions but little of it is operational.
- The PL constructs that come closest to making "interactions between mechanics" a *first-class language construct* (rather than glue code) are **CLOS-style method combinations**, **algebraic effects + handlers**, **stackable traits / mixin composition with linearization**, **feature modules with explicit interaction declarations (FOP/SPL)**, and **object algebras / tagless-final** for extensibility. AOP is the canonical "interactions as units" pattern but is widely regarded as cautiously used and, outside Spring, niche.
- The game-design side names the *phenomena* (feedback loops, emergence, modulation, instantiation) but only **Machinations** and **Ludii** give you executable semantics; everyone else is descriptive/analytic.

---

## Key Findings

1. **There is no single dominant framework.** Each tradition addresses one or two of the four cross-cutting questions (open/closed, ordering, interposition, scoping) and is silent on the others.
2. **Two constructs treat interactions themselves as nameable, declarative entities**: CLOS method combinations with `:before/:after/:around` qualifiers, and algebraic-effect handlers. Stackable traits are a third, with the caveat that the interaction is encoded *implicitly* in linearization order.
3. **The "feature interaction problem"** has a 30-year named literature in telecoms (Zave 1993, Calder et al. 2003) and SPL (Apel, Batory, Kästner, Saake 2013). The N×N combinatorial blow-up is a known, unsolved problem; mitigation, not elimination, is the state of the art.
4. **First-class extension points scale to runtime plugin systems** (Eclipse, WordPress, Emacs) but at the cost of static reasoning. ECS schedulers (Bevy, Unity DOTS) push this further into a fine-grained data-flow graph.
5. **Process calculi and Petri nets** are the formal-methods home of compositional concurrency, but they price the rigor in expressiveness — they're heavy for application-level DSLs.
6. **Game-studies vocabulary is descriptive, not executable**, except for Machinations (game economies as nets with feedback loops) and Ludii (ludeme trees compile to Java behaviors).

---

## Details

### Programming-Language Side

#### 1. Aspect-Oriented Programming (AOP)

**Native domain:** logging, transactions, security checks, persistence — crosscutting concerns that scatter across an OO class hierarchy.

**Core model (AspectJ, AspectC++):** an *aspect* declares *pointcuts* (predicates over runtime/static *join points* — method calls, field gets, exception throws) and attaches *advice* (`before`, `after`, `around`) that runs at those points. *Weaving* combines aspects with base code: compile-time weaving (ajc), load-time weaving (LTW via a Java agent), or runtime (Spring AOP via dynamic proxies). The decisive idea is **quantification + obliviousness** — the aspect describes "wherever this pattern matches, also do X" without the base code knowing.

**What it solved:** clean modular logging/tracing, declarative transaction boundaries (the Spring `@Transactional` use case), policy enforcement.

**What it didn't:** the **fragile pointcut problem** — pointcuts are predicates over program syntax/structure (e.g., `call(* save*(..))`), so seemingly innocuous renames or refactors silently break matching. Kellens et al. (2006) and Koppen & Störzer ("PCDiff: Attacking the Fragile Pointcut Problem," EIWAS 2004) document that pointcut fragility "occurs when a pointcut unintentionally captures or misses a given join point as a consequence of seemingly safe modifications to the base code." The empirical study in *Empirical Software Engineering* (Springer, 2017) elaborates: "constructs such as pointcuts and advices can make the ripple effects in AO systems far more difficult to control than in object-oriented systems." Maintenance research (Rejuvenate Pointcut, AJ+, sentinel-based pointcuts) tries to harness "structural commonalities" to suggest pointcut updates as code evolves but has not eliminated the problem.

**Modern status:** alive in enterprise Java via Spring AOP, whose annotation-driven `@AspectJ` style "interprets the same annotations as AspectJ 5… The AOP runtime is still pure Spring AOP" (Spring Framework reference docs, 2024). Outside Spring, mindshare has eroded: JD Porterfield's 2023 industry write-up notes "no AspectJ plugin for Android is officially supported (i.e., maintained by Google, the AOSP, or even JetBrains)." The empirical conclusion in the *Empirical Software Engineering* study: "AOP is currently used in a very cautious way. This cautious usage could come from a partial failure of AspectJ to deliver all promises of AOP, in particular an increased software maintainability." Verdict: not dead, but niche; superseded in practice by annotations + DI + bytecode libraries (ByteBuddy) for crosscutting use cases.

**Where it stands on the cross-cutting questions:**
- Interaction as first-class: **yes** — the aspect *is* the interaction.
- Open/closed: open — new aspects don't require base modification.
- Ordering: explicit (`declare precedence`).
- Interposition: `around` advice with `proceed()` is the canonical interposition primitive.
- Scoping: pointcut predicates can be scoped by control flow (`cflow`), type, package.

**Cost:** compile-time weaving is mostly zero-runtime overhead; LTW adds class-load time; runtime proxying (Spring) costs a virtual call per advised invocation.

---

#### 2. Algebraic Effects and Effect Handlers

**Native domain:** structured concurrency, generators, parsers, exceptions, dependency injection — anywhere you'd reach for a monad or a callback.

**Core model:** computations *perform* operations (effects); a *handler* gives semantics by intercepting performs and deciding what to do with the **continuation** (the rest of the computation). They generalize exceptions with the twist that the handler may `resume` the continuation, possibly multiple times. Plotkin & Pretnar's "Handlers of Algebraic Effects," ESOP 2009 (LNCS 5502, pp. 80–94, DOI 10.1007/978-3-642-00590-9_7), is the seminal paper; it received the ETAPS Test of Time Award in April 2022.

**Implementations:**
- **Koka** (Daan Leijen, MS Research): static row-typed effects, compiles to C without a runtime via "evidence passing." (Per the Ante language blog: "Koka uses evidence passing and bubbles up effects to handlers to compile to C without a runtime.")
- **OCaml 5**: one-shot effects in the runtime, used as the substrate for `Eio` and `domainslib`. Sivaramakrishnan, Dolan, White, Kelly, Jaffer, Madhavapeddy, "Retrofitting Effect Handlers onto OCaml," PLDI '21 (pp. 206–221, arXiv:2104.00250) report that the implementation "imposes a mean 1% overhead on a comprehensive macro benchmark suite that does not use effect handlers." Notably, Multicore/OCaml 5 does not include a static effect type system, a known limitation.
- **Eff, Frank, Helium, Effekt, Unison, Flix, Ante**: research languages exploring static effects, shallow vs deep handlers (Lindley, McBride, McLaughlin, "Do Be Do Be Do," arXiv:1611.09259), multihandlers, modal calculi.
- **Library encodings** in Haskell (`fused-effects`, `polysemy`, `effectful`), Scala (cats-effect, Effekt-Scala), Racket.

**Composition story:** handlers nest; the outer handler sees effects the inner didn't handle. Compared with **monad transformers** (Liang/Hudak/Jones 1995), effects avoid the lifting boilerplate and the n² instance problem, and they handle the "scoped effects" gap less elegantly than initially hoped (Wu et al., "A Calculus for Scoped Effects & Handlers," arXiv:2304.09697).

**Cost:** delimited continuations historically expensive; modern implementations have closed most of the gap. Tail-resumptive handlers (the common case) compile to closure calls. Koka's evidence-passing approach and OCaml's one-shot restriction are the two main pragmatic compromises.

**Cross-cutting:**
- Interaction as first-class: **yes** — the handler is the interaction, and handlers are values.
- Open/closed: open — new effects, new handlers, no modification of existing code.
- Ordering: lexical nesting of handlers.
- Interposition: native (`resume` with transformed input/output).
- Scoping: handlers are dynamically scoped, like exceptions.

---

#### 3. Feature-Oriented Programming (FOP) and Software Product Lines (SPL)

**Native domain:** product families (Linux kernel features, automotive control software, telecom switches) where you ship many variants from a shared codebase.

**Core constructs:**
- **Feature model**: a tree/lattice of features with require/exclude constraints (Kang et al. FODA 1990).
- **Feature module**: a unit of code (potentially spanning classes, makefiles, XML, docs) that *refines* the base.
- **Composition by superimposition**: in **AHEAD** (Don Batory, "step-wise refinement") and **FeatureHouse** (Apel, Kästner et al., IEEE TSE'13), modules are merged by overlaying **Feature Structure Trees** — language-independent ASTs. The FeatureHouse project page documents: "FeatureHouse provides support for the superimposition of software artifacts written in Java, C#, C, Haskell, JavaCC, Alloy and UML."
- **Tooling**: **FeatureIDE** is the open Eclipse-based IDE; family-based verification (Classen, Apel et al.) tries to prove properties about all variants without enumerating them.

**The feature interaction problem:** the named curse of this field. Pamela Zave's "Feature interactions and formal specifications in telecommunications" (IEEE *Computer*, August 1993): an interaction "occurs when one telecommunications feature modifies or subverts the operation of another." Call-waiting × call-forwarding is the textbook example. The number of *potential* interactions is O(N²) in features, and detecting them statically is undecidable in general; the literature focuses on heuristic detection, family-based model checking, and architectural disciplines like the "Distributed Feature Composition" architecture (Jackson & Zave 1998). Calder, Kolberg, Magill & Reiff-Marganiec, "Feature interaction: a critical review and considered forecast," *Computer Networks* 41(1), 2003, pp. 115–141, surveys the telecom side; Apel, Batory, Kästner & Saake, *Feature-Oriented Software Product Lines* (Springer, 2013) is the SPL bible.

**Cost:** AHEAD/FeatureHouse weave at build time; cost is the cost of the resulting program. Verification is the expensive part: family-based model checking helps but does not scale to arbitrary domains.

**Cross-cutting:**
- Interaction as first-class: **partially** — features are first-class but interactions are usually *implicit*, detected after the fact. There are extensions (e.g., "interaction modules" in some research) that promote interactions to nameable units.
- Open/closed: open — you compose features at configuration time.
- Ordering: composition order is explicit (and affects semantics).
- Interposition: superimposition is fundamentally interposition.
- Scoping: a feature applies to the whole composed program.

---

#### 4. Mixins, Traits, Stackable Modifications

**Native domain:** OO reuse where single inheritance is too restrictive.

**Variants:**
- **Scala traits with linearization**: when you `extends A with B with C`, the language linearizes the class hierarchy via a deterministic algorithm. `super` calls follow the linearization, so `abstract override` methods can be *stacked*: each trait wraps the next. Bracha & Cook's "Mixin-based inheritance" (OOPSLA/ECOOP 1990) is the foundational paper. Odersky's Scala formalization is in *Programming in Scala*; the idiomatic name is "**stackable modifications**" — modify a method by mixing in a trait that overrides it and calls `super`. Canonical example: a `BasicIntQueue` mixed with `Doubling`, `Incrementing`, `Filtering` traits, each of which uses `abstract override def put(x: Int) = super.put(...)` to layer behavior.
- **Rust traits**: bounded ad-hoc polymorphism, no inheritance, no stacking (you compose via the orphan rule + blanket impls + supertraits).
- **Ruby mixins / modules**: ancestor chain with `prepend`/`include`; very dynamic, no static checking.
- **JavaScript / Self prototypes**: delegation chains; runtime stacking is trivial but unprincipled.
- **CLOS multiple inheritance + method combination** (see next section).

**The MRO problem:** multiple inheritance creates ambiguity ("diamond"). Languages settle it differently: Python's C3 linearization, Scala's right-to-left algorithm, C++'s virtual base classes. The MRO is a *deterministic* function of the declared parents; it is *not* user-customizable per-method (cf. CLOS, which lets you choose `:before/:after/:around` per generic function).

**Cost:** zero runtime overhead in Scala (compiled to JVM dispatch tables); in dynamic languages, a method lookup chain.

**Cross-cutting:**
- Interaction as first-class: **no**; the interaction is encoded in linearization order plus `super` calls.
- Open/closed: open for adding traits to a *new* combination, closed for modifying an existing class.
- Ordering: deterministic but textual; reordering changes semantics.
- Interposition: yes via `super` calls in `abstract override` methods.
- Scoping: per-method, per-class.

---

#### 5. Open Classes, Multimethods, Method Combinations

**Native domain:** scientific computing (Julia), symbolic systems (CLOS, Dylan), where dispatch should depend on more than one argument's type.

**Multiple dispatch:** in **Julia** and **CLOS**, the function selected for a call depends on the runtime types of *all* arguments. This makes binary operations like `intersect(circle, polygon)` natural without the double-dispatch contortions of Visitor.

**CLOS method combinations** (the under-appreciated feature for this survey). Per the Common Lisp Cookbook and Lamkins's *Successful Lisp* Ch. 14:
- Methods can be qualified with `:before`, `:after`, `:around`, or `:primary` (the default).
- Standard combination: **most-specific `:around` first** (it may call `call-next-method`); then **`:before` methods (most-specific first)**; then **the most-specific `:primary`**; then **`:after` methods (least-specific first)**; the `:around` then completes. Cookbook description: "Think of it as an onion, with all the `:around` methods in the outermost layer, `:before` and `:after` methods in the middle layer, and primary methods on the inside."
- Beyond `standard`, CLOS provides `progn`, `+`, `list`, `min`, `max`, `and`, `or` combinations — and you can `define-method-combination` to build your own. This is, conceptually, **AOP that was already shipping in 1988** in a fully-typed object model.

**Cost:** multiple dispatch has been a perennial implementation challenge; Julia compiles specialized methods on demand via JIT, often hitting C-like throughput. CLOS dispatch is fast in commercial Lisps and reasonable in SBCL.

**Cross-cutting:**
- Interaction as first-class: **yes** — qualifiers + combinations make "the interaction between primary methods" a nameable, customizable mechanism.
- Open/closed: open (new methods can be added without touching existing ones; the open-class property).
- Ordering: declarative via qualifiers + class specificity.
- Interposition: `:around` + `call-next-method`.
- Scoping: per generic function.

---

#### 6. Object Algebras and Tagless-Final

**Native domain:** embedded DSLs, extensible compilers, "the expression problem."

**The expression problem** (Wadler 1998): how do you add new *cases* (data variants) and new *operations* without modifying existing code and without losing static type safety? Standard OO solves new-cases-easy / new-ops-hard; standard ADTs flip it.

**Tagless-final** (Carette, Kiselyov, Shan, "Finally Tagless, Partially Evaluated," APLAS 2007 / *Journal of Functional Programming* 19(5), 2009, pp. 509–543): represent terms not as a data type but as polymorphic uses of a `Symantics` interface. Each interpreter is an instance; new interpretations and new syntactic constructs (by *extending* the interface) both compose modularly. Per Kiselyov's site: "The final encoding lets us add new language forms and interpretations without breaking the existing terms and interpreters."

**Object algebras** (Oliveira & Cook, "Extensibility for the Masses: Practical Extensibility with Object Algebras," ECOOP 2012): the OO Shadow Guard. An algebra is an interface of constructors parameterized by the result type; an interpreter is a concrete implementation; *combining* interpreters is itself an algebra. Per the paper abstract: a solution that works "in OO languages with simple generics (including Java or C#)" without "F-bounded quantification, wildcards and variance annotations."

Both techniques are the closest the type-system literature has come to **modular, statically-checked, open-ended composition of behaviors over a shared abstract syntax**. They scale to surprisingly complex DSLs (Oliveira & van der Storm have used them in industrial systems).

**Cost:** purely compile-time; no runtime overhead beyond the dispatch already present.

**Cross-cutting:**
- Interaction as first-class: **indirect** — interactions are encoded as algebra combinators.
- Open/closed: **fully open** in both axes (the explicit point).
- Ordering: not an issue at the model level.
- Interposition: easy — wrap one interpreter in another.
- Scoping: type-system-scoped.

---

#### 7. Language Workbenches and Mixin-Based Language Extension

**Native domain:** building DSLs and DSL families.

**Tools:** **Rascal** and **Spoofax** (Eclipse, generalized parsing, can compose arbitrary CFGs because the class is closed under union); **MPS** (JetBrains, projectional editing — no parser, so composition is unrestricted); **Xtext** (ANTLR-based, less compositional but mature); **Racket `#lang`** (every Racket file declares its language; new languages are libraries with their own readers, expanders, and macros); **MontiCore**, **Ensō**, **SugarJ**, **Eco**.

Voelter et al.'s "Evaluating and Comparing Language Workbenches" (2013) is the standard comparison. Key takeaway: **syntactic composition** is the hard problem; LL(*) parsers can't do it in general (Xtext), GLR/Earley can (Rascal, Spoofax — "syntactic composability through the use of generalized parsing technology, which is required because only the full class of context-free grammars is closed under union"), projectional editors sidestep it (MPS). **Semantic composition** — how do you combine the *meanings* of two language modules? — is even harder and far less standardized.

**Cost:** development-time cost of using the workbench is significant (you're learning a meta-tool); runtime cost is the cost of the generated language.

**Cross-cutting:** these tools build other tools; they're at the meta-level for the rest of this survey.

---

#### 8. Reactive Programming and FRP

**Native domain:** UIs, animation, robotics, dataflow.

**Core model (Elliott & Hudak, "Functional Reactive Animation," ICFP 1997):** programs are built from **behaviors** (time-varying values) and **events** (discrete occurrences). Behaviors compose pointwise; events compose via combinators (`merge`, `filter`, `switch`).

**Variants:**
- **Classic FRP** (Fran, Reactive): continuous semantics, behaviors as `Time → a`.
- **Arrowized FRP** (Yampa, Fruit): signals are conceptual; you program with signal functions `SF a b`.
- **Modal FRP** (Krishnaswami, Bahr, Møgelberg, "Simply RaTT," arXiv:1903.05879; Bahr et al. "Modal FRP for all"): types `○A` for "available next tick" to avoid space leaks.
- **Discrete reactive systems** (RxJS, ReactiveX, Sodium, the React/Vue reactivity systems): more pragmatic, often discrete, sometimes called "Rx-style" or "signals." Note: ReactiveX, per the Wikipedia entry, "is functional and reactive but differs from functional reactive programming."

**Composition story:** every reactive value is first-class; combinators give you pointwise composition, merging, switching, accumulation (`foldp`). This is excellent for the **interposition** question — a derived signal *is* an interposition on its inputs.

**Cost:** historically space leaks (retaining old values for combinators that look backward); modal FRP and careful library design (incremental computation libs like Adapton, salsa, Incremental in OCaml) address it. Performance for UIs is competitive.

**Cross-cutting:**
- Interaction as first-class: **partial** — combinators are values; structural interactions like "this signal can override that one" require explicit switching combinators.
- Open/closed: open.
- Ordering: implicit in the dependency graph.
- Interposition: native.
- Scoping: dynamic (via switching) or static (via combinators).

---

#### 9. Process Calculi and Petri Nets

**Native domain:** formal modeling of concurrent and distributed systems.

**CCS / CSP / π-calculus**: parallel composition (`P | Q`), restriction (`νx.P`), choice (`P + Q`), synchronization on channels. π-calculus adds *mobility* (channels can be sent over channels). The compositional reasoning here is among the best the field has: bisimulation gives you a notion of behavioral equivalence that lets you replace components freely. **Petri nets** are the graphical/concurrent cousin; their composition operators (place/transition fusion, modular nets) are well-studied (van der Aalst's work).

**Tradeoffs:** the calculi are unsurpassed for *reasoning* about interleaving and synchronization. They are clumsy for ergonomic programming — most languages give you channels (Go, Erlang, Rust) as a thin practical layer over the calculus rather than the calculus itself. Petri nets vs. π-calculus has a small literature of friendly fire (van der Aalst, "Pi calculus versus Petri nets: Let us eat 'humble pie' rather than further inflate the Pi hype," 2003): "Pi calculus has problems modeling [a Petri net with parallel-join] simple example" — Petri nets handle non-trivial joins (true concurrency) more naturally; π-calculus handles dynamic topology better.

**Cross-cutting:**
- Interaction as first-class: **yes** — composition operators are the language.
- Open/closed: closed under composition (open in that sense).
- Ordering: explicit via synchronization.
- Interposition: harder — you typically have to model interposition as another parallel process.
- Scoping: explicit (`ν`, restriction).

---

#### 10. Entity-Component-System (ECS)

**Native domain:** game engines, simulation. Bevy (Rust), Unity DOTS, EnTT (C++), Flecs, Specs.

**Core idea:**
- **Entities** are just IDs.
- **Components** are plain-old-data records attached to entities.
- **Systems** are functions that query for entities with a given set of components and mutate them.

The **interaction model** is: systems compose by **operating on shared component sets**. If `MovementSystem` reads `Velocity` and writes `Position`, and `CollisionSystem` reads `Position` and writes `Velocity`, the scheduler can derive the dependency.

**Scheduling:** Bevy's scheduler (per the crate docs and the Unofficial Bevy Cheat Book) builds a DAG; the "parallel executor considers dependencies between systems and (by default) run as many of them in parallel as possible." Systems with disjoint component sets run in parallel; explicit `.after(...)` / `.before(...)` / `system_sets` give ordering. Unity DOTS uses a similar job-graph: "ECS schedules jobs on the main thread in the order that your systems are in. When you schedule jobs, ECS keeps track of which jobs read and write which components" (Unity Entities 1.0 docs). The classic problem: defaults are non-deterministic when not constrained — see Bevy GitHub Discussion #10205, "Ordering of systems is hard." Update barriers (Bevy PR #10618) help.

**Cost:** archetypal ECS (Bevy, Unity DOTS) groups entities by component composition for cache-friendly iteration; tens of millions of entity-system operations per second is achievable.

**Cross-cutting:**
- Interaction as first-class: **partial** — systems are first-class; *interactions between systems* are inferred from data dependencies, not declared as units.
- Open/closed: very open — add a new system; if it touches existing components, scheduling adapts.
- Ordering: explicit, via the scheduler API.
- Interposition: clumsy — you must add an intermediate system that mutates the data between two existing systems, often using marker components.
- Scoping: stages / system sets / states (Bevy's `OnEnter`, `OnExit`).

---

#### 11. Hooks / Extension Points / Plugin Architectures

**Native domain:** large applications that want third-party extension. WordPress (actions + filters), Emacs (`add-hook`), Eclipse (`plugin.xml` extension points), VSCode (`contributes`), Drupal, IntelliJ.

**Pattern:** the host application *publishes* named extension points. Plugins *contribute* implementations. The host invokes contributions at specified moments. WordPress distinguishes **actions** (run side-effect callbacks at a moment) from **filters** (transform a value through a pipeline of callbacks — interposition is the whole point).

**Tradeoffs:** the simplest, most-shipped pattern in this whole survey; ergonomic for plugin authors; brittle if the host doesn't document its hooks; static reasoning is limited to "the hook exists / doesn't exist." Hooks tend to **accrete** over the project's life as more interaction is requested.

**Cost:** a hash-lookup-and-dispatch per hook firing. Negligible at human time scales.

**Cross-cutting:**
- Interaction as first-class: **yes** — the hook is a named extension point.
- Open/closed: open by construction.
- Ordering: usually via priority numbers (WordPress), `:before`/`:after` in Emacs `add-hook`.
- Interposition: native for filters / value-pipeline hooks.
- Scoping: the hook name is the scope.

---

#### 12. Aspect-like Type-System Extensions

**Type classes** (Wadler & Blott 1989): ad-hoc polymorphism with global coherence. Compose by superclass constraints. Not great for "this combination of instances *interacts* differently"; the orphan-instance problem is the named pain.

**Modular type classes** (Dreyer, Harper, Chakravarty) and **named instances** (Kiselyov, Shan) lift the coherence restriction; rarely deployed.

**ML modules and functors**: parametric modules. A functor `F(X : SIG)` takes an implementation of `SIG` and produces a new module. Composition is functor application. SML/OCaml functors are powerful but second-class; **1ML** (Rossberg) and **MixML** (Rossberg & Dreyer) make modules first-class and add **mix-in** semantics.

**Backpack** (Kilpatrick, Dreyer, Peyton Jones, Marlow, "Backpack: retrofitting Haskell with interfaces," POPL '14, San Diego, January 20–21, 2014, pp. 19–32, DOI 10.1145/2535838.2535884; production implementation by Edward Z. Yang in his 2017 Stanford PhD thesis and shipped in GHC 8.2 and cabal-install 2.0). Modules have *holes* (signatures) that are filled by other modules at link time. From the POPL'14 paper: "The design of Backpack is inspired by the MixML module calculus of Rossberg and Dreyer… Like MixML, Backpack supports interfaces, recursive linking, abstract data types." From Yang et al.'s 2016 follow-up "Backpack to Work": "an evolution of the Backpack mixin package system which respects the division between package manager and compiler… a mixin linking phase which computes a 'wiring diagram' of components indifferent to the actual Haskell source code." Not widely adopted in practice, but the design is the cleanest known account of "modules as mix-ins" in a typed setting.

**F-bounded polymorphism**: lets a class refer to itself in its own type parameter — important for self-types in fluent builders, but tangential to behavior interaction.

**Cost:** compile-time everything. Backpack adds a "mixin linking" phase to the build.

---

### Game Design / Game Studies Side

#### MDA (Hunicke, LeBlanc, Zubek, AAAI Workshop 2004)

**Mechanics** (rules and data) → **Dynamics** (run-time behavior of mechanics acting on input and on each other) → **Aesthetics** (player emotional response). Designer works left-to-right; player experiences right-to-left.

The key formulation for this survey, per the Wikipedia summary of the paper: "Dynamics are the run-time behavior of the mechanics acting on player input and 'cooperating' with other mechanics." The framework *names* interaction but stays purely descriptive — no operational model, no composition algebra.

**Status:** widely cited, taught in game-design curricula, criticized for the "8 kinds of fun" list being arbitrary.

---

#### Björk & Holopainen, *Patterns in Game Design* (Charles River Media, 2005, ISBN 1-58450-354-8)

A catalog of ~300 patterns with explicit **relations between patterns**: `Instantiates`, `Modulates`, `Instantiated by`, `Modulated by`, `Conflicting with`. This is one of the few places in the game-studies literature where **interactions between units of behavior are named, typed, and catalogued**. The book is essentially an ontology of mechanic relationships; an OWL2 representation has been built (Kowalski et al., CEUR Workshop Proceedings vol. 2451, paper 12, 2019).

A pattern can `Modulate` another (alter its behavior without instantiating it) or `Conflict with` it (the two cannot coexist). The Game Developer book excerpt: "This can be done by inserting new patterns that have the *instantiates* relation to the wanted pattern, by modifying existing patterns that have *instantiated by* or *modulated by* relations to the wanted pattern, or by introducing a pattern from scratch." The relations are at the pattern-description level, not the executable-system level.

---

#### Machinations (Dormans 2012; Adams & Dormans, *Game Mechanics: Advanced Game Design*, Peachpit/New Riders, 2012)

A **visual notation** for game economies: pools (resources), sources, drains, converters, gates, and edges with rate annotations. The notation makes **feedback loops** visible: a sub-graph that returns to its origin with the same or amplified sign.

Per Adams' Gamasutra/Game Developer column introducing the tool: Machinations lets designers prototype "the kinds of feedback loops and control systems that are available… different kinds of engines and friction systems, escalation patterns." The notation has been formalized as **Micro-Machinations** (van Rozen & Dormans, "Adapting Game Mechanics with Micro-Machinations," FDG 2014): "Micro-Machinations (MM) formalizes the meaning of core language elements of Machinations enabling reasoning about alternative behaviors and assessing quality, making it also suitable for software development."

**Status:** alive as an online tool (machinations.io); used in industry for economy balancing. The closest the game-design community gets to "executable composable mechanics" — but limited to economy/resource-flow dynamics, not arbitrary rules.

---

#### Salen & Zimmerman, *Rules of Play: Game Design Fundamentals* (MIT Press, 2004)

The vocabulary spine of contemporary game studies. They define "system" via Stephen W. Littlejohn's four elements (Ch. 5, p. 51): **Objects** ("the parts, elements, and variables within the system"), **Attributes** ("qualities or properties of the system and its objects"), **Internal relationships** ("the relations among the objects"), **Environment** ("the context that surrounds the system"). They organize game-design schemas into three **primary schemas** (Ch. 10): **RULES** ("a formal primary schema… focuses on the intrinsic mathematical structures of games"), **PLAY** ("an experiential primary schema… emphasizes the player's interaction with the game and other players"), **CULTURE** ("a contextual primary schema… highlights the cultural contexts into which any game is embedded"). Each frames interaction at a different level.

Chapter 14, "Games as Emergent Systems": emergence is "the phenomenon of unplanned patterns appearing from within a system" (p. 152), and "what makes a system emergent is that there is a special disconnect between the rules of the system and the ways those rules play out" (p. 160). On the designer's epistemic position (p. 168): "As a game designer, you are tackling a second-order design problem… you can never directly design play. You can only design the rules that give rise to it." Their canonical definition of game (p. 80/96): "A game is a system in which players engage in artificial conflict, defined by rules, that results in a quantifiable outcome."

Chapter 18, "Games as Cybernetic Systems," is where they connect to LeBlanc's feedback-loop vocabulary (see below): "Game designer Marc LeBlanc has done a great deal of thinking about the relationship between game design and feedback systems, and this schema is indebted to LeBlanc's important work on the subject."

---

#### Feedback Loops (LeBlanc 1999; Adams 2010/2014; Schreiber 2010)

Marc LeBlanc's 1999 GDC talk "Feedback Systems and the Dramatic Structure of Competition" (San Jose, March 1999) introduces the canonical game-design definitions:

- **Positive feedback loop**: destabilizes the game, drives it to an end, magnifies early success ("the rich get richer").
- **Negative feedback loop**: stabilizes the game, prolongs it, magnifies later successes (keeps games close — Mario Kart blue shell).

Ian Schreiber's *Game Balance Concepts* lecture series (gamebalanceconcepts.wordpress.com, summer 2010), Level 8 "Feedback Loops": "There are two types, positive feedback loops and negative feedback loops. These terms are borrowed from other fields such as control systems and biology, and they mean the same thing in games that they mean elsewhere." On the positive loop: "can be thought of as a reinforcing relationship. Something happens that causes the same thing to happen again, which causes it to happen yet again, getting stronger in each iteration — like a snowball that starts out small at the top of the hill and gets larger and faster as it rolls and collects more snow." Three named properties of positive loops: "(1) They tend to destabilize the game… (2) They cause the game to end faster. (3) They put emphasis on the early game, since the effects of early-game decisions are magnified over time."

Schreiber treats loops as **composable design building blocks**: "since kill-the-leader is a negative feedback loop, the 'textbook solution' is to add a compensating positive feedback loop that helps the leader to defend against attacks." Loops are thus explicitly named, composable, multi-step ("a positive feedback loop with four steps: players explore the map, which gives them access to more resources, which let them buy better technology, which let them build better units, which let them explore…").

Adams & Dormans, *Game Mechanics: Advanced Game Design* (New Riders, 2012), Ch. 4: "Negative feedback makes a system resistant to changes"; "Positive feedback creates an exponential curve… In games, this type of positive feedback is often used to create an arms race between multiple players." Adams' *Fundamentals of Game Design* (3rd ed., New Riders / Pearson, 2014, ISBN 978-0321929679) covers "Understanding Positive Feedback" at p. 429.

**Status:** widely used vocabulary, executable in Machinations, mostly descriptive elsewhere.

---

#### Ludeme Theory and Ludii (Browne, Parlett)

**Ludeme** (David Parlett's term, popularized by Cameron Browne): an atomic unit of game rules / equipment. **Ludii** (Browne et al., funded by the European Research Council's 2 million euro "Digital Ludeme Project" Consolidator Grant #771292, Maastricht University) is a general game system whose game description language is generated by a **class grammar** from the underlying Java class hierarchy — a 1:1 mapping between grammar non-terminals and Java classes. Games are LISP-like ludeme trees:

```
(game "Tic-Tac-Toe"
  (players 2)
  (equipment { (board (square 3)) (piece "Disc" Each) })
  (rules
    (play (move Add (to (sites Empty))))
    (end (if (is Line 3) (result Mover Win)))))
```

The class grammar mechanism is novel (Browne, "A Class Grammar for General Games," CG 2016): extending the grammar = extending the Java library. Composition between ludemes is by argument nesting and the typed-constructor protocol. Ludii (version 1.3.2) ships with over 1,000 predefined games.

**Status:** active research platform; the closest existing system to a "DSL where mechanics are first-class composable units" — though for board games, not card games.

---

#### Game Description Languages: VGDL, PuzzleScript

**VGDL** (Schaul, "A Video Game Description Language for Model-based or Interactive Learning," CIG 2013; py-vgdl): a high-level DSL for arcade-style games built on an ontology of sprite physics, movement, and pairwise interactions. Per the py-vgdl GitHub: "The aim is to decompose game descriptions into two parts: 1) a very high-level description, close to human language, to specify the dynamics, which builds on 2) an ontology of preprogrammed concepts for dynamics, interactions, control." Games are defined by four blocks: SpriteSet, InteractionSet (pairwise rules: "this sprite collides with that one → consequence"), LevelMapping, TerminationSet. The InteractionSet **promotes interactions to a first-class table** — possibly the cleanest example in this whole survey of "interaction as the unit of description."

**PuzzleScript** (Stephen Lavelle): a rule-rewriting DSL for tile-based puzzles. Rules of the form `[ > Player | Crate ] -> [ > Player | > Crate ]` are pattern-rewrite rules; the engine matches them iteratively. Interaction emerges from rule order and rule combination — a kind of declarative rewriting system. ScriptDoctor (Earle et al., "ScriptDoctor: Automatic Generation of PuzzleScript Games via Large Language Models and Tree Search," arXiv:2506.06524, IEEE Conference on Games 2025) is recent automated-generation work.

Both are executable, narrow-domain DSLs that have inspired but not been adopted as general game-DSL substrates.

---

#### Juul's Emergence vs Progression

Jesper Juul, *Half-Real: Video Games between Real Rules and Fictional Worlds* (MIT Press, 2005), Ch. 3, building on the 2002 paper "The Open and the Closed: Games of Emergence and Games of Progression" (Computer Games and Digital Cultures Conference, Tampere):

- **Games of emergence**: rules combine to produce variation; small rule set, large possibility space (chess, Go, most board games). Juul: "a number of simple rules combining to form interesting variations."
- **Games of progression**: pre-scripted sequence of challenges (adventure games, Myst). Juul: "the player has to perform a predefined set of actions in order to complete the game."

Juul's "rule interaction" is named as the simplest form of emergence — "Quake III: Rocket-jumping. (Fire rocket into the ground, fly on the blast.)" is rule interaction without designer intent. Useful vocabulary for the distinction between **interactions that are designer-authored vs interactions that emerge from the rules**.

---

## Comparison Matrix

Axes: **CT/RT** = primarily compile-time or runtime; **Open?** = can you add new interactions without modifying existing components; **1st-class interaction?** = is the interaction itself a nameable language entity; **Maturity** = production / research / niche.

| Approach | CT/RT | Open? | 1st-class interaction? | Maturity |
|---|---|---|---|---|
| AspectJ AOP | CT (weave) or RT (Spring) | Yes | Yes (aspect/advice) | Production (Java/Spring); declining elsewhere |
| Algebraic effects (Koka/OCaml 5/Effekt) | RT (handler dispatch; ~1% overhead in OCaml 5) | Yes | Yes (handler) | Production (OCaml 5 ships); Koka/Effekt research |
| FOP/FeatureHouse/AHEAD | CT (superimposition) | Yes | Partial (features yes; interactions implicit) | Mature research; modest industry |
| Scala traits (stackable) | CT | Partial | No (encoded in linearization) | Production |
| CLOS method combinations | RT | Yes | **Yes (qualifiers + combinations)** | Mature (Common Lisp) |
| Multimethods (Julia) | JIT | Yes | Partial (no qualifiers) | Production |
| Object algebras / tagless-final | CT | Yes | Indirect | Mature research |
| Language workbenches (Rascal/Spoofax/MPS) | CT meta | Yes | Yes (language modules) | Mature research; modest industry |
| FRP (Fran/Yampa/Reactive) | RT | Yes | Partial (combinators) | Mature in some niches (UI, animation) |
| Process calculi (CCS/CSP/π) | Formal model | n/a | Yes (composition ops) | Mature theory; rarely the implementation |
| ECS (Bevy/Unity DOTS) | RT scheduler | Yes | No (data deps, not interactions) | Production |
| Hooks/extension points (WordPress/Emacs/Eclipse) | RT | Yes | Yes (the hook itself) | Production, ubiquitous |
| Type classes / Backpack / ML functors | CT | Partial / Yes | No / Yes (modules) | Production (TC); niche (Backpack since GHC 8.2) |
| MDA | descriptive | n/a | No | Standard vocabulary |
| Björk & Holopainen patterns | descriptive | n/a | **Yes (typed relations)** | Reference catalog |
| Machinations / Micro-Machinations | tool + sim | Yes | Yes (nodes/edges + loops) | Niche industry tool |
| Ludii / class grammar | RT (Java) | Yes via class hierarchy | Yes (ludemes) | Active research; 1000+ games |
| VGDL / PuzzleScript | DSL compiler | Yes | **Yes (InteractionSet / rewrite rules)** | Niche research/tools |
| Salen & Zimmerman | descriptive | n/a | No | Standard vocabulary |
| LeBlanc / Adams / Schreiber feedback loops | descriptive (Machinations executable) | n/a | Partial (loops as units) | Standard vocabulary |
| Juul emergence/progression | descriptive | n/a | No | Standard vocabulary |

---

## Cross-Cutting Concepts as the Literature Names Them

**Interaction as a thing vs interaction as accidental:**
- Made explicit: AOP (aspects), algebraic effects (handlers), CLOS method combinations, hooks, VGDL InteractionSet, Björk & Holopainen relations.
- Implicit / emergent: trait linearization, ECS data dependencies, type-class instance resolution, FOP composition (the *fact* of interaction is named — "the feature interaction problem" — but the interactions themselves are usually discovered, not declared).

**Open vs Closed (Wadler's "expression problem"):**
- Both axes open: object algebras, tagless-final, algebraic effects, ECS, hooks.
- One axis open: classical OO (variants easy, ops hard); ADTs (ops easy, variants hard).
- Family-based variants: FOP/SPL (open at configuration time).

**Priority and ordering:**
- Declarative: CLOS qualifiers + specificity; AOP `declare precedence`; hooks via priority numbers; Bevy `.before/.after`.
- Computed: trait linearization (C3/Scala algorithm).
- Lexical: handler nesting.

**Interposition:**
- Native: AOP `around` + `proceed`; CLOS `:around` + `call-next-method`; algebraic effect handlers; FRP combinators; WordPress filters; stackable traits via `super`.
- Awkward: ECS (insert intermediate system); process calculi (insert a proxy process).

**Scoping:**
- Lexical: handler scopes, language workbenches.
- Dynamic via control flow: AOP `cflow`, CLOS qualifiers + class specificity.
- Phase/state: ECS stages, FOP composition variants, Bevy `OnEnter`/`OnExit`.

---

## What's Missing or Contested in the Literature

1. **Static checkability of interactions remains weak.** The feature-interaction problem has 30 years of literature (since Zave 1993) and no general solution. Family-based verification helps for bounded feature counts; for arbitrary interactions you're back to testing.

2. **There is no widely-accepted formal vocabulary that *both* PL theorists and game designers use.** Machinations and Ludii are close to a bridge but each is bound to its domain. MDA's "dynamics" is descriptive only.

3. **AOP-vs-effects debate is unsettled.** Effects look like the modern, type-safe AOP; but effects do not give you the *quantification* property (an aspect can match all calls to `*save*`). It's the difference between "I declare which calls to intercept" (AOP) and "I declare which kinds of operations to perform, and a handler decides what to do" (effects). The literature has not adequately compared them on the *interaction* axis.

4. **The "interaction as a first-class unit" idea is folk-philosophy.** Object algebras and Björk/Holopainen each *gesture* at it, but no language ships with an "Interaction" construct that lets you say "when mechanic A and mechanic B are both present, *this* additional behavior fires." The closest thing is CLOS method combinations + multimethods, which is from the 1980s and is not widely deployed.

5. **Scheduling discipline for behavior composition (ECS) is empirical, not theorized.** Bevy's community discussion on system ordering (GitHub Discussion #10205) is essentially saying "we don't yet know the principled way."

6. **Emergence is not engineered, it is observed.** Juul, Salen & Zimmerman, and Adams all treat emergence as a property that arises from the system; none of them provide a calculus for predicting *which* interactions will be emergent vs. brittle.

---

## Recommendations

Per the prompt, no synthesis or design proposal is offered — the survey is intentionally a landscape, not a recommendation. The reader is expected to apply these lessons to their target domain afterward.

If a follow-up is desired, the highest-leverage next steps to deepen the survey would be:

- **A direct head-to-head comparison of CLOS method combinations and algebraic effect handlers** on the four cross-cutting axes (the literature does not do this systematically).
- **A read of Apel/Batory/Kästner/Saake's 2013 textbook**, the *Feature-Oriented Software Product Lines* (Springer), which is the single most consolidated treatment of explicit feature interaction.
- **A hands-on experiment with Ludii's class grammar** and Machinations' Micro-Machinations formalization, to see how each handles the "ordering" and "interposition" questions when stretched.

---

## Caveats

- AOP literature is dated; the practitioner community has largely moved to annotations + DI. Empirical evidence on AOP's value is mixed and the negative studies (e.g., the 2017 *Empirical Software Engineering* study) are not unanimous.
- "Algebraic effects" as a static-typed language feature is still moving — Koka, Effekt, and Frank's interfaces differ enough that any "the right answer is X" claim should be treated as provisional.
- Several game-design citations (LeBlanc's 1999 GDC slides, Björk & Holopainen's relations) are not peer-reviewed primary literature; they are influential conference talks and trade books.
- The "feature interaction problem" framing comes mostly from telecom (1990s) and SPL (2000s); whether the same framing applies cleanly to game mechanics is plausible but not directly established.
- Ludii's class grammar is innovative but its mapping is tightly coupled to Java; portability is unstudied.
- Machinations is excellent for resource economies but does not natively express discrete-rule games (turns, trick-taking, etc.).
- Page numbers cited for Salen & Zimmerman's *Rules of Play* and Adams' *Fundamentals of Game Design* are from common editions but minor edition variation may apply.
- The OCaml 5 effect-system "~1% overhead" figure is the macro-benchmark mean from Sivaramakrishnan et al.'s PLDI'21 paper; specific applications may differ substantially.