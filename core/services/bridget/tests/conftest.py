import sys
from pathlib import Path

import pytest

SERVICE_ROOT = str(Path(__file__).resolve().parents[1])
_FLAT = (
    "service",
    "adapters",
    "routes",
    "commands",
    "views",
    "schemas",
    "settings",
    "database",
    "ports",
    "main",
)


def _activate() -> None:
    for path in list(sys.path):
        normalized = path.rstrip("/")
        if normalized.endswith(("/bag_of_holding", "/bridget")) and path != SERVICE_ROOT:
            sys.path.remove(path)
    if SERVICE_ROOT in sys.path:
        sys.path.remove(SERVICE_ROOT)
    sys.path.insert(0, SERVICE_ROOT)
    for name in _FLAT:
        module = sys.modules.get(name)
        if module is None:
            continue
        module_file = getattr(module, "__file__", "") or ""
        if not module_file.startswith(SERVICE_ROOT):
            del sys.modules[name]


def pytest_collectstart(collector: pytest.Collector) -> None:
    path = str(getattr(collector, "path", "") or getattr(collector, "fspath", ""))
    if SERVICE_ROOT in path:
        _activate()


_activate()
