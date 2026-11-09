"""Test configuration.

The parsing/pricing logic under test lives in modules that do not import Home
Assistant (``const``, ``models``, ``api``). To keep the test suite runnable
without a full Home Assistant install, we load just those modules under a
synthetic package name and expose them to the tests.
"""
from __future__ import annotations

import importlib.util
import pathlib
import sys
import types

import pytest

_COMPONENT_DIR = (
    pathlib.Path(__file__).resolve().parent.parent
    / "custom_components"
    / "electrohold_tariffs"
)
_PKG = "electrohold_core"


def _load_ha_free_modules() -> types.ModuleType:
    """Load const/models/api under ``electrohold_core`` and return ``api``."""
    if f"{_PKG}.api" in sys.modules:
        return sys.modules[f"{_PKG}.api"]

    # ``api`` imports aiohttp only for the (untested) fetch path. Stub it when
    # absent so the pure parser can be tested without the dependency.
    if "aiohttp" not in sys.modules:
        try:
            import aiohttp  # noqa: F401
        except ModuleNotFoundError:
            stub = types.ModuleType("aiohttp")
            stub.ClientError = type("ClientError", (Exception,), {})
            stub.ClientSession = type("ClientSession", (), {})
            stub.ClientTimeout = type("ClientTimeout", (), {})
            sys.modules["aiohttp"] = stub

    package = types.ModuleType(_PKG)
    package.__path__ = [str(_COMPONENT_DIR)]
    sys.modules[_PKG] = package

    for name in ("const", "models", "api"):
        spec = importlib.util.spec_from_file_location(
            f"{_PKG}.{name}", _COMPONENT_DIR / f"{name}.py"
        )
        module = importlib.util.module_from_spec(spec)
        sys.modules[f"{_PKG}.{name}"] = module
        spec.loader.exec_module(module)

    return sys.modules[f"{_PKG}.api"]


@pytest.fixture(scope="session")
def api():
    """Return the HA-free ``api`` module."""
    return _load_ha_free_modules()
