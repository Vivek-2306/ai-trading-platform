"""Smoke test: the package imports and exposes a version."""

import app


def test_version_is_set() -> None:
    assert app.__version__ == "0.1.0"
