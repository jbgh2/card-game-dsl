"""The smuggling family library, bound against every member of its family.

`docs/libraries/smuggling.cardlang` is the tier's second library and the first
whose contract names ZONES. Its family lives in `experiments/green-lane/` and is
deliberately not corpus, so no corpus harness reaches it — without this module
the library would have no executing witness at all, which is the shape CLAUDE.md
names ("Execution finds what enumeration cannot"; implemented-but-never-executed
code is where the next silent defect is sitting).

Completeness ledger (decisions.md "Closed-domain completeness")
---------------------------------------------------------------
property: every member of the smuggling family binds the library — parses,
          resolves, typechecks and plays to a terminal state — and the import
          adds no observation, so the information sets a member derives are the
          ones its own text derives.
domain:   every `.cardlang` file under `experiments/green-lane/`, globbed. The
          family is a delta lattice whose members are added by writing a file,
          so the axis is the directory and never a list — `test_the_family_is_
          the_glob` pins that the glob is non-empty and that every member
          actually imports the library, which is what stops this module going
          vacuously green if a file is renamed out of reach.
registry: the glob, plus `cardlang.libraries.library_names()` for the library's
          own registration.
covered:  the full cross of member x {checks, plays} — `test_every_member_binds_
          the_library` and `test_every_member_plays_to_termination`. The
          contract's minimality and sufficiency are NOT re-asserted here: they
          are `tests/test_family_libraries.py`'s
          `test_every_library_contracts_for_exactly_what_it_reaches`, which is
          parametrized over `library_names()` and so picked this library up on
          arrival.
sampled:  one seed per member for the playout. The per-seed space is the
          family's own, not the import's, and the import is seed-independent by
          construction (nothing spliced consults the rng).

          The twelve digests below take only FOUR distinct values, and that is a
          fact about the family rather than a weak pin: v1's delta is scoring,
          v2's and v2b's are token bookkeeping, and none of the three is
          observable — only v3/v4's changed hand composition reaches the
          stream, and only the mini/full split changes its length. The pin still
          moves under any change to what an observer sees; what the collapse
          shows is that this family's variant lattice is almost entirely
          non-observational, which is why the import can be info-set-neutral
          across all of it.
residual: the byte-identical BEFORE/AFTER trace equality that proved the
          conversion neutral — 12 members x 12 seeds, every observation event
          and every decision point — cannot live here: CI has no "before". It is
          evidence in the change that introduced the library, and what remains
          in CI is the digest pin below, which holds the property going forward
          rather than backward. R4, and no issue: nothing a designer can reach.
"""

from __future__ import annotations

import hashlib
import random
from pathlib import Path
from typing import Any

import pytest

from cardlang.libraries import library_names
from cardlang.pipeline import check_dsl
from cardlang.runtime.driver import play_game

_FAMILY = Path(__file__).resolve().parent.parent / "experiments" / "green-lane"


def _members() -> list[Path]:
    return sorted(_FAMILY.rglob("*.cardlang"))


def _ids() -> list[str]:
    return [str(p.relative_to(_FAMILY)) for p in _members()]


def test_the_library_is_registered() -> None:
    assert "smuggling" in library_names()


def test_the_family_is_the_glob() -> None:
    """The axis below is a directory, so it can silently become empty — a file
    renamed, a directory moved — and every parametrized test would then pass by
    running zero cells. This is the pin that makes that loud, and it asserts the
    stronger property too: a member that stopped importing the library would
    leave the library with one fewer witness while the suite stayed green.

    red under: rename `experiments/green-lane/`, or drop the `uses smuggling`
    line from any member."""
    members = _members()
    assert len(members) >= 12, f"the smuggling family is {len(members)} files"
    for member in members:
        assert "uses smuggling" in member.read_text(), (
            f"{member.name} no longer imports the library it is a witness for"
        )


@pytest.mark.parametrize("member", _members(), ids=_ids())
def test_every_member_binds_the_library(member: Path) -> None:
    """The contract is met and the spliced game is well typed — the whole
    pipeline, in the channel a family author would meet."""
    check_dsl(member.read_text(), member.name)


@pytest.mark.parametrize("member", _members(), ids=_ids())
def test_every_member_plays_to_termination(member: Path) -> None:
    """Binding is not running. The imported `commit_shipment` holds the family's
    only decision site, so a member that checked but did not reach it would be a
    library proven by inspection alone."""
    game = check_dsl(member.read_text(), member.name)
    chose = 0

    def chooser(player: Any, candidates: list[Any], n: int) -> list[Any]:
        nonlocal chose
        chose += 1
        return rng.sample(candidates, n)

    rng = random.Random(0)
    play_game(game, rng, chooser=chooser)
    assert chose > 0, "no decision reached — the imported commit never ran"


def _trace_digest(member: Path, seed: int) -> str:
    """Every per-observer observation event of one playout, hashed. The
    information-set substrate, not a summary of it: the OpenSpiel adapter
    projects info sets from exactly this stream."""
    game = check_dsl(member.read_text(), member.name)
    events: list[str] = []
    rng = random.Random(seed)
    play_game(
        game,
        rng,
        observer=lambda p, ev: events.append(f"{int(p)}{ev!r}"),
        chooser=lambda p, c, k: rng.sample(c, k),
    )
    return hashlib.sha256("\n".join(events).encode()).hexdigest()[:16]


@pytest.mark.parametrize("member", _members(), ids=_ids())
def test_the_observation_stream_is_pinned(member: Path) -> None:
    """The import is claimed to carry no information-set implication. Here that
    claim becomes a pin: a change to the library that altered what any observer
    sees — a different zone type in the contract, a movement re-ordered, an
    `as` block dropped — moves this digest.

    Born green, so it carries its reddening edit rather than a red run.

    red under: change `warehouse[player]`'s contracted type in
    docs/libraries/smuggling.cardlang from `HiddenPile<player>` to
    `PlayerPile<player>` and the same in a member's `zones { }` — the waved
    shipment becomes public and every member's digest moves."""
    digest = _trace_digest(member, 0)
    assert digest == _DIGESTS[str(member.relative_to(_FAMILY))], (
        f"the observation stream of {member.name} moved — if that was intended, "
        f"say which observer now learns something they did not"
    )


# Captured from the converted family, whose streams are byte-identical to the
# pre-library ones (12 members x 12 seeds), so these digests pin the property
# forward from a state proven equal to the state before the import existed.
_DIGESTS: dict[str, str] = {
    "green-lane-mini.cardlang": "2b5c1383f48e2cbf",
    "green-lane.cardlang": "8dbb383e8f4af5b8",
    "variants/v1-impound-mini.cardlang": "2b5c1383f48e2cbf",
    "variants/v1-impound.cardlang": "8dbb383e8f4af5b8",
    "variants/v2-bounty-mini.cardlang": "2b5c1383f48e2cbf",
    "variants/v2-bounty.cardlang": "9dd5cce9c1644a88",
    "variants/v2b-delayed-bounty-mini.cardlang": "2b5c1383f48e2cbf",
    "variants/v2b-delayed-bounty.cardlang": "9dd5cce9c1644a88",
    "variants/v3-graded-mini.cardlang": "51d1f19873b4d74d",
    "variants/v3-graded.cardlang": "931c749a7507a2f1",
    "variants/v4-composed-mini.cardlang": "51d1f19873b4d74d",
    "variants/v4-composed.cardlang": "931c749a7507a2f1",
}
