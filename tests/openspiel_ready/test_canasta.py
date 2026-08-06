"""Canasta (4 players, teams) — OpenSpiel readiness.

Depth 12 (the default): the seed-5 pause lands on seat 1 with seats 0/2/3
holding full hands, so the 4-player swap path has two swappable opponents.

`swap_axis="any"`: canasta publishes card identity only for cards that LEAVE
the hidden zones — discards, staged meld cards, pile flushes are all public
zone traffic, and no public observation is a per-rank function of a hidden
hand (no Go-Fish-style transfer-count ask). A swap between two bystander
hands touches no publicly-observed card, and the pauser's guards read only
their own hand plus public state.

`conformance_steps=150`: the full random_sim_test re-simulates the whole
(seed, history) state per action — a four-deal match runs ~1200 decisions,
the multi-hand score-target class (Bridge, Hearts, Gin) — so the bounded
random API walk is the sanctioned fallback. `adapter_terminal_steps=None`
for the same reason: the greedy line (draw + discard every turn, never
melding — the discard announce's action id sorts below every meld
announce) completes all four deals only after hundreds of steps.

The bound was 400 and is now 150. Canasta's per-decision cost is the
corpus's highest (its primitives read 15 zone families), and the walk is
quadratic in depth because each query re-simulates, so this one test was
311s — a quarter of the whole suite. Measured on the seed-7 line this walk
actually takes: **150 steps costs 35.8s against 400 at 311.3s**.

What the bound covers is ASSERTED, not measured once and written down:
`test_conformance_bounds.py` walks this line and fails loudly if any verb
outside `conformance_verbs_unreached` stops being applied, so a game-file
change that pushes a mechanic past step 150 reddens instead of quietly
covering less. The frontier has margin — the last new verb (`take_pile`)
lands at step 55. What steps 150-400 added was only further CARD IDS in the
action space (`3♠` first at 155, `A♠` at 211, `J♠` at 377): the same
announce shapes carrying a different card, and action-id round-tripping
over the whole space is owned by `tests/test_openspiel_encoding.py`, not by
this walk. What is genuinely given up is API conformance in LATE multi-deal
states — removed outright by issue #139 (the adapter re-simulates per
query, so the bound exists to buy back a quadratic, not to express a
coverage judgement).

Per-game caveat (recorded, not hidden): the greedy line never melds nor
takes the pile, so the meld/take projections are asserted by the dedicated
observational test below on a meld-preferring drive line, not by the
four-proof swap walk. What the dedicated test pins is Canasta's info-set
payload: THE WHOLE PILE-TAKE CHAIN IS COMMON KNOWLEDGE — the pile was
public as it accumulated, so taking it moves knowledge every observer
already holds (the flush event carries full card identity on its
pile_rest source side for every observer, while the receiving hand stays
count-only) — and the shared, growing team melds render with full identity
in every observer's information state while all four hands stay counts.
"""

from cardlang.openspiel.infostate import information_state
from cardlang.openspiel.replay import DecisionNode, load, run

from .harness import GAMES_DIR, GameSpec, ReadinessProofs


class TestReadiness(ReadinessProofs):
    spec = GameSpec(
        "cardlang_canasta",
        "canasta.cardlang",
        depth=12,
        swap_axis="any",
        conformance_steps=150,
        conformance_verbs_unreached=(
            ("decline_pile", ("the pile-take offer only arises when the discard "
                             "pile is takeable; the seed-7 line declines no "
                             "such offer within the bound. Both arms of the "
                             "offer are exercised by the 30-seed match sweep "
                             "in tests/test_playout_canasta.py")),
            ("meld_black3", ("melding black threes is legal only when going "
                            "out, which the bound stops well short of "
                            "(the same sweep plays four full deals per seed)")),
        ),
    )


def test_pile_take_and_melds_derive_public_knowledge() -> None:
    """Drive seed 0 with a meld-preferring policy (take the pile whenever
    legal, else the highest action id — which stages and closes melds before
    discarding). Within ~13 steps seat 2 takes the frozen pile (its side
    unmelded) with the natural-pair justification, stages two kings and two
    jokers beside the top K, and closes the meld. Assert the derived
    observations at every hop of the chain, for every observer."""
    path = str(GAMES_DIR / "canasta.cardlang")
    _, space = load(path)
    seed = 0

    history: list[int] = []
    r = run(path, seed, ())
    took = closed = False
    for _ in range(40):
        assert isinstance(r, DecisionNode)
        take = next((a for a in r.legal if space.to_string(a) == "take_pile"), None)
        action = take if take is not None else r.legal[-1]
        name = space.to_string(action)
        history.append(action)
        r = run(path, seed, tuple(history))
        took = took or name == "take_pile"
        if name == "close_meld":
            closed = True
            break
    assert took and closed, "seed 0 no longer reaches a pile take + close within 40 steps"
    assert isinstance(r, DecisionNode)

    for q, log in r.obs_logs.items():
        # The take: the pile's top card moves to the taker's public stage
        # zone with full identity for EVERY observer.
        top_move = next(
            e for e in log if e[0] == "move" and e[1] == "pile_top" and e[3] == "stage[2]"
        )
        assert isinstance(top_move[2], tuple) and isinstance(top_move[4], tuple)

        # Staging: each hand card ARRIVES in the public stage zone with
        # identity for every observer (melding at a table is open), while
        # the hand SOURCE side stays a bare count for everyone but the taker.
        stagings = [
            e for e in log if e[0] == "move" and e[1] == "hand[2]" and e[3] == "stage[2]"
        ]
        assert stagings
        for e in stagings:
            assert isinstance(e[4], tuple) and len(e[4]) == 1
            if q == 2:
                assert isinstance(e[2], tuple)
            else:
                assert isinstance(e[2], int)

        # The close: the staged cards land on the TEAM meld pile — the
        # shared, growing meld object — with full identity for everyone.
        close = next(
            e for e in log if e[0] == "move" and e[1] == "stage[2]" and str(e[3]).startswith("meld")
        )
        assert isinstance(close[2], tuple) and isinstance(close[4], tuple)
        meld_zone = str(close[3])  # e.g. "meldK[0]" — team-indexed

        # The flush: the REST of the pile enters the taker's hand. Its
        # identity is public on the pile_rest SOURCE side for every
        # observer — the pile accumulated publicly, so the take moves
        # knowledge everyone already holds — while the receiving hand shows
        # only a count to everyone but the taker.
        flush = next(
            e for e in log if e[0] == "move" and e[1] == "pile_rest" and e[3] == "hand[2]"
        )
        assert isinstance(flush[2], tuple) and len(flush[2]) >= 1
        if q == 2:
            assert isinstance(flush[4], tuple)
        else:
            assert isinstance(flush[4], int)

    # Rendered information states: the team meld pile is common knowledge —
    # identity in EVERY observer's state — while all four hands render as
    # counts to everyone but their owner.
    team = int(meld_zone.split("[")[1].rstrip("]"))
    assert team == r.rs.team_of[2]
    for q in range(4):
        info = information_state(q, r.rs, r.obs_logs[q])
        assert f"{meld_zone}=[" in info and f"{meld_zone}=#" not in info
        for other in range(4):
            n = len(r.rs.zones.instance("hand", other).cards)
            if other == q:
                assert f"hand[{other}]=[" in info
            else:
                assert f"hand[{other}]=#{n}" in info


def test_stock_draws_stay_hidden() -> None:
    """The counterpart channel: a stock draw reveals nothing but counts to
    the other three players (deck count-only on the source side, the hand's
    count-only non-owner projection on the destination side), while the
    drawer sees the drawn card."""
    path = str(GAMES_DIR / "canasta.cardlang")
    seed = 5
    history: list[int] = []
    r = run(path, seed, ())
    assert isinstance(r, DecisionNode)
    for _ in range(12):
        history.append(r.legal[0])
        nxt = run(path, seed, tuple(history))
        assert isinstance(nxt, DecisionNode)
        r = nxt

    draws = [
        (q, e)
        for q, log in r.obs_logs.items()
        for e in log
        if e[0] == "move" and e[1] == "deck" and str(e[3]).startswith("hand[")
    ]
    assert draws, "the greedy line drew from stock within 12 steps"
    for q, e in draws:
        drawer = int(str(e[3])[5:-1])
        assert isinstance(e[2], int)  # the stock face is hidden from everyone
        if q == drawer:
            assert isinstance(e[4], tuple), "drawer sees the drawn card"
        else:
            assert isinstance(e[4], int), "others see a count only"
