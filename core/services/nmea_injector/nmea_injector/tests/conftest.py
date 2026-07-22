import sys
from pathlib import Path

import pytest

# services/nmea_injector (has main.py and the nmea_injector/ package)
SERVICE_ROOT = str(Path(__file__).resolve().parents[2])


def _activate() -> None:
    for path in list(sys.path):
        normalized = path.rstrip("/")
        if normalized.endswith(("/bag_of_holding", "/bridget")):
            sys.path.remove(path)
    if SERVICE_ROOT in sys.path:
        sys.path.remove(SERVICE_ROOT)
    sys.path.insert(0, SERVICE_ROOT)
    main = sys.modules.get("main")
    if main is not None:
        main_file = getattr(main, "__file__", "") or ""
        if not main_file.startswith(SERVICE_ROOT):
            del sys.modules["main"]


def pytest_collectstart(collector: pytest.Collector) -> None:
    path = str(getattr(collector, "path", "") or getattr(collector, "fspath", ""))
    if "nmea_injector" in path:
        _activate()


def pytest_runtest_setup(item: pytest.Item) -> None:
    path = str(getattr(item, "path", "") or getattr(item, "fspath", ""))
    if "nmea_injector" in path:
        _activate()


_activate()
