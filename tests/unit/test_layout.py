"""The package layout from INSTRUCTIONS.md §7 exists and imports cleanly."""

import importlib

import pytest

PACKAGES = [
    "app",
    "app.domain",
    "app.intake",
    "app.rules",
    "app.calculator",
    "app.context",
    "app.ml",
    "app.rag",
    "app.explain",
    "app.review",
    "app.workflow",
    "app.audit",
    "app.db",
    "app.api",
    "app.core",
]


@pytest.mark.parametrize("name", PACKAGES)
def test_package_imports(name: str) -> None:
    assert importlib.import_module(name) is not None
