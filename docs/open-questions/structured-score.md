# Structured score

**Tier 2 — high impact, blocked on a data point.**

Bridge has `ScoreDelta { above_line[partnership],
below_line[partnership] }` because the game-win threshold cares
specifically about below-the-line accumulation. Stud has a
different structured-score shape: a list of Pots with per-pot
eligibility, length data-dependent on all-in history.

These don't share a structural form. The minimal generalization
that fits both is "list of scoring channels with per-channel
eligibility":

```
type ScoreStructure = {
  channels  : List<ScoreChannel>
  per_channel_semantics : <channel evaluation function>
}

type ScoreChannel = {
  amount     : Integer
  eligible   : Set<Player|Team>
  // additional per-game metadata
}
```

**Blocker:** Two data points (Bridge, Stud) aren't enough. A third
structured-score game (Hi-Lo Stud, Tarot with round/tournament
scoring, Skat with multiple scoring categories) would tell us
whether the generalization is real or whether each game just
declares its own shape.
