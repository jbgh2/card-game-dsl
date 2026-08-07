# cardlang

> A language for describing card games, compiled to
> [OpenSpiel](https://github.com/google-deepmind/open_spiel) so that
> imperfect-information AI — CFR, IS-MCTS, deep RL — runs on any game you
> can write down.

Source-available under a noncommercial license — see [License](#license)
before building on it.

## Usage

A game is a Markdown document with a fenced DSL block. Hearts begins:

```
game Hearts {
  players: 4
  cards: standard52

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }
  ...
}
```

Check a description:

```
cardlang docs/games/hearts.md        # parse + static checks; silent on success
```

Play it through OpenSpiel:

```python
import cardlang.openspiel.game  # registers the corpus with pyspiel
import pyspiel

game = pyspiel.load_game("cardlang_hearts")
state = game.new_initial_state()
state.apply_action(0)  # the deal, as a chance outcome

[state.action_to_string(0, a) for a in state.legal_actions()][:4]
# ['2♣', '3♣', '6♣', '7♣']

state.information_state_string(1)
# 'P1|deck=#0;trick_pile=[];captured[0]=[];captured[1]=[];captu...'
```

That last string is the point. Player 1's information state — what they
know, with the deck and other players' hands reduced to counts — is
derived from the zone types above and the observations moves emit. Nobody
wrote it by hand. That is what lets OpenSpiel's algorithms, which live and
die on correct information sets, run on a described game without per-game
adapter code.

## Background

Hidden hands, face-down cards, and concealed bids are the hard part of
compiling card games to OpenSpiel, and the part that goes quietly wrong
when adapters are written by hand. So it is proved, per game:
`tests/openspiel_ready/` checks indistinguishability under hidden-card
swaps, a per-fact soundness matrix, perfect recall, and agreement between
the DSL and the adapter.

The corpus drives the language. `docs/games/` holds one file per game —
each a complete description a non-player could pick up and play a hand
from — and constructs exist because a game needed them. The spec lives in
`docs/`: `principles.md` for the goal, `model.md` for how phases, rules,
and moves fit together, `decisions.md` for settled design.
`experiments/llm_eval/` is a pilot evaluation of language models playing
described games, with its transcripts and reports.

## Installation

```
pip install -e ".[dev,openspiel]"
pytest -q        # the full gate
```

Python 3.11+. The `openspiel` extra is optional for the core front end;
the adapter tests skip without it.

## Status

Working, and narrow on purpose. Open design questions live in
`docs/open-questions/`; deferred work is in the issue tracker. The
tracker and pull requests are maintained by the author; external
contributions are not being taken at present.

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md). The pilot evidence in
`experiments/llm_eval/results*/` is
[CC BY 4.0](experiments/llm_eval/LICENSE-pilot-evidence.md). There is a
standing commitment to relicense the repository under Apache 2.0 if the
associated grant is awarded.
