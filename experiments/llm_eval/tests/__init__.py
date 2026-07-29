"""Offline unit tests for the harness. No network: the fake provider is the
only provider these use.

These live outside `tests/` deliberately — `pyproject.toml` sets
`testpaths = ["tests"]`, so a bare `pytest` (what CI runs) does not collect
them, and the experiment cannot redden the language's own gates. Run them
explicitly:

    pytest experiments/llm_eval/tests -q
"""
