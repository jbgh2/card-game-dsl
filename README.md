# cardlang

> A compiler that turns declarative card-game rules into hidden-information
> environments where automated checks confirm each player sees only what the
> rules allow, with game-theoretic baselines through
> [OpenSpiel](https://github.com/google-deepmind/open_spiel).

Source-available under a noncommercial license. See [License](#license)
before building on it.

## Three ways in

A game is a rules file. Hearts begins:

```
game Hearts {

  players: 4
  direction: clockwise
  max_length: 5000

  cards: standard52
  ranking: aces high

  zones {
    deck             : Deck
    hand[player]     : Hand<player>
    trick_pile       : TrickPile
    captured[player] : PlayerPile<player>
  }
  ...
}
```

### Write a game

Check a description, then play a hand of it:

```
cardlang check my-game.cardlang  # parse + static checks; silent on success
cardlang play my-game.cardlang --seed 7 --info-state 1
```

Both take any path. `play` is one uniform-random self-play: the outcome, the
decision count, and the seed that reproduces the run, plus that seat's derived
information state at the end of the game. `cardlang` is on PATH after the
editable install below, and `python -m cardlang` runs the same front end
straight from the source tree.

Your own game reaches OpenSpiel by registering it:

```python
from cardlang.openspiel import register_game_file
import pyspiel

name = register_game_file("my-game.cardlang")
game = pyspiel.load_game(name)
```

`register_game_file` checks the file, registers it under `cardlang_<stem>`,
and returns that short name. `CARDLANG_GAMES` does the same at import time: an
`os.pathsep`-separated list of game files or directories, registered when the
adapter loads. Your game does not go in `docs/games/`. That directory is the
corpus, and it is for contributing a game, not for using one;
`docs/maintaining.md`, "When the corpus changes" is the contributor's page.

The learning path is `docs/authoring.md`.

### Use a game as an environment

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

The last string is the point. Player 1's information state is derived from
the zone declarations above and the observations moves emit. The deck and
the other hands appear only as counts because that is what the rules let
player 1 see. Nobody wrote that string by hand, and a battery of tests
(`tests/openspiel_ready/`, one proof module per game) checks it holds:

- swap tests change hidden cards and check that what each player sees does
  not change,
- legal-action agreement checks that worlds a player cannot tell apart
  offer the same moves,
- a soundness matrix checks the other direction, that every entitled fact
  arrives,
- further checks confirm the shuffle leaves no trace and that information
  states never forget.

These are executable checks, exhaustive where domains are closed and
sampled where they are open. They are not theorem-prover proofs.

They are also corpus-bound. A game registered from outside `docs/games/`
gets the adapter's derived information states, but no readiness proof of its
own (issue #25).

`experiments/llm_eval/` is a worked example.

### Work on the language

```
pytest -q        # the language's own gate
```

`CLAUDE.md` is the entry: what the pieces are, where each doc lives, and the
three checks CI runs. From there, `docs/maintaining.md` for the docs and the
corpus, `docs/harness.md` for how work is claimed and merged.

## Why

Environments with hidden information are how multi-agent safety measures
deception, collusion, and rule-breaking. Hand-built environments cannot
show they keep secrets from the models they test: a bug in the observation
code can leak state to an agent that should not see it, and that
invalidates the result. Here visibility is declared in the rules and
observations are derived by one engine, so the checks above are possible
at all, and a new environment is a rules file that inherits them.

The corpus drives the language. `docs/games/` holds each game twice: the
executable rules (`.cardlang`) and a Markdown rulebook complete enough
that a non-player could pick it up and play a hand. Each rulebook links to
its `.cardlang` rather than repeating it, so only the game file says what the
game is. Constructs exist because a game needed them. The spec lives in
`docs/`; `decisions.md` is the settled design. `experiments/llm_eval/` is
the pilot evaluation of language models playing these games, with its
transcripts, audit files, and reports.

## Installation

```
pip install -e ".[dev,openspiel]"
```

Python 3.11+, in a virtualenv. The `openspiel` extra is optional for the
core front end; the adapter tests skip without it.

## Status

Working, and narrow on purpose. The language does not cover everything
yet: combination scoring and similar computations run as game-local Python
that receives values and returns a value, and a test pins that no engine
state reaches it. Open design questions live in `docs/open-questions/`;
deferred work is in the issue tracker. The tracker and pull requests are
maintained by the author; external contributions are not being taken at
present.

## License

[PolyForm Noncommercial 1.0.0](LICENSE.md). The pilot evidence in
`experiments/llm_eval/results*/` is
[CC BY 4.0](experiments/llm_eval/LICENSE-pilot-evidence.md).
