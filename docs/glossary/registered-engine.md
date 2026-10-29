---
term: Registered Engine
definition: A climbing round's engine when its slots name a game-local Primitive lead query and its follows query (`PRIMITIVE_CLIMB_ENGINES`, keyed by the lead) — the [[declared-engine]]'s other arm in `ClimbRound.engine`, for a game whose plays no [[combination-catalogue]] declares yet (Tichu, issue #989). Its play universe is numbered by an arithmetic combo codec, and its registry row may declare Play Announcement tokens and an Interrupt Window decline.
layer: kernel
status: canonical
reserved: false
home: `cardlang/ast/nodes.py`, `RegisteredEngine`; `cardlang/builtins/functions.py`, `PRIMITIVE_CLIMB_ENGINES`
see: ["declared-engine", "combination-catalogue", "play-announcement", "interrupt-window"]
retired_spellings: []
findings: []
---

**Kernel.** A climbing round's engine when its slots name a game-local Primitive pair: a lead query returning every play a hand may lead, and its follows query returning those that beat the standing play, registered together in `PRIMITIVE_CLIMB_ENGINES` and keyed by the lead query. It serves a game whose plays no [[combination-catalogue]] declares yet — Tichu's runs of any length, runs of pairs, bombs and four special cards, issue #989.

Its play universe is too large to enumerate, so an arithmetic combo codec numbers it (`primitives.climb_codec_function`); its registry row may declare the tokens of a [[play-announcement]] and the decline of an [[interrupt-window]], neither of which a [[declared-engine]] has.
