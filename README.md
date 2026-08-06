# cardlang

A language for describing card games played with standard 52-card decks,
compiling to [OpenSpiel](https://github.com/google-deepmind/open_spiel) so
that imperfect-information algorithms — CFR, IS-MCTS, deep RL — run on a
described game without per-game engine code.

The design bet is that information sets should be derived, never
hand-authored. A game description declares which players can see each zone
of cards; moves emit per-player observations through those declarations,
and what a player knows falls out of the two together. Getting that right
for hidden hands, face-down cards, and concealed bids is the hard part of
targeting OpenSpiel, and the part that goes wrong quietly when adapters
are written by hand. Here it is proved per game: `tests/openspiel_ready/`
checks indistinguishability under hidden-card swaps, a per-fact soundness
matrix, perfect recall, and agreement between the DSL and the OpenSpiel
adapter.

## Layout

- `docs/` — the spec. `principles.md` for the goal, `model.md` for how
  phases, rules, and moves fit together, `decisions.md` for settled
  design.
- `docs/games/` — the corpus. One file per game; each is a complete
  description a non-player could pick up and play a hand from. The corpus
  drives the language: constructs exist because a game needed them.
- `cardlang/` — parser, static checker, runtime, OpenSpiel adapter.
- `tests/` — the suite, including the per-game readiness proofs above.
- `experiments/llm_eval/` — a pilot evaluation of language models playing
  described games, with its transcripts and reports.

## Use

```
pip install -e ".[dev,openspiel]"
cardlang docs/games/hearts.md        # parse + check; silent on success
pytest -q                            # the full gate
```

Corpus files are Markdown with a fenced DSL block, so a game reads as a
document and runs as a program.

## Status

Working, and narrow on purpose. Open design questions live in
`docs/open-questions/`; deferred work is in the issue tracker. The tracker
and pull requests are maintained by the author; external contributions are
not being taken at present.

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md). The pilot evidence in
`experiments/llm_eval/results*/` is
[CC BY 4.0](experiments/llm_eval/LICENSE-pilot-evidence.md). There is a
standing commitment to relicense the repository under Apache 2.0 if the
associated grant is awarded.
