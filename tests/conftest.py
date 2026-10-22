"""Import plugin as a package exactly as Hermes does; no fake gateway modules."""
import importlib.util
import os
from pathlib import Path
import sys
import pytest


@pytest.fixture
def plugin():
    pytest.importorskip("gateway.platforms.base", reason="Run integration tests with the Hermes runtime; see README")
    name = "messenger_under_test"
    if name not in sys.modules:
        root = Path(__file__).resolve().parents[1]
        spec = importlib.util.spec_from_file_location(name, root / "__init__.py", submodule_search_locations=[str(root)])
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
    module = sys.modules[name]
    from gateway.platform_registry import platform_registry, PlatformEntry
    class Context:
        def register_platform(self, **kwargs):
            platform_registry.register(PlatformEntry(**kwargs))
    module.register(Context())
    return module
