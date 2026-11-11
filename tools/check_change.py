"""Select the checks a change's diff calls for. (Stub: the selection is not written yet.)"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from typing import Callable, Mapping


class Check(enum.Enum):
    TYPECHECK = "typecheck"
    LANGUAGE_SUITE = "language-suite"
    RIGS = "rigs"
    GOLDENS_FULL = "goldens-full-width"
    GAME_NAMED = "game-named-modules"
    CLASSIFIER_TABLES = "classifier-tables"
    CENSUS_PINS = "census-pins"
    DOC_SNIPPETS = "doc-snippets"
    ADR_RECORDS = "adr-records"
    CHANGED_TESTS = "changed-test-modules"


class Status(enum.Enum):
    ADDED = "A"
    MODIFIED = "M"
    DELETED = "D"


@dataclass(frozen=True)
class Change:
    status: Status
    path: str
    lane_classes: tuple[str, ...]
    cites_adr: bool = False


@dataclass(frozen=True)
class Tree:
    games: frozenset[str]
    library_consumers: Mapping[str, frozenset[str]]
    snippet_docs: frozenset[str]
    classifier_modules: tuple[str, ...]
    census_modules: tuple[str, ...]
    tests_naming: Callable[[str], tuple[str, ...]]


def triggered(changes: tuple[Change, ...], tree: Tree) -> dict[Check, tuple[str, ...]]:
    return {}


def read_tree(root: str) -> Tree:
    return Tree(frozenset(), {}, frozenset(), (), (), lambda name: ())


def lane_classes(root: str, paths: tuple[str, ...]) -> dict[str, tuple[str, ...]]:
    return {}


def lane_rows(root: str) -> tuple[tuple[str, str, str], ...]:
    return ()
