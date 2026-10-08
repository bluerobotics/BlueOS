import time

import psutil
import pytest
from harbor.container import ContainerManager


def test_uptime_uses_process_start_relative_to_boot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeProcess:
        @staticmethod
        def create_time() -> float:
            return 4_600.0

    monkeypatch.setattr(psutil, "Process", lambda _pid: FakeProcess())
    monkeypatch.setattr(psutil, "boot_time", lambda: 1_000.0)
    monkeypatch.setattr(time, "monotonic", lambda: 10_800.0)

    uptime = ContainerManager._monotonic_uptime(42)

    assert uptime == 7_200.0


def test_uptime_is_unavailable_when_process_is_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def missing_process(pid: int) -> None:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", missing_process)

    assert ContainerManager._monotonic_uptime(42) is None


def test_container_model_keeps_status_and_exposes_uptime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ContainerManager, "_monotonic_uptime", lambda _pid: 7_200.0)
    container = {
        "Names": ["/example"],
        "Image": "example/image:latest",
        "ImageID": "sha256:123",
        "Status": "Up 17 hours (healthy)",
    }

    model = ContainerManager._container_model(container, {"State": {"Pid": 42}})  # type: ignore[arg-type]

    assert model.status == "Up 17 hours (healthy)"
    assert model.uptime_seconds == 7_200.0
