import time

import psutil
import pytest
from harbor.container import ContainerManager


@pytest.mark.parametrize(
    ("duration_seconds", "expected"),
    [
        (0.5, "Less than a second"),
        (1, "1 second"),
        (59, "59 seconds"),
        (60, "About a minute"),
        (59 * 60, "59 minutes"),
        (60 * 60, "About an hour"),
        (4 * 60 * 60, "4 hours"),
        (3 * 24 * 60 * 60, "3 days"),
    ],
)
def test_human_duration(duration_seconds: float, expected: str) -> None:
    assert ContainerManager._human_duration(duration_seconds) == expected


def test_status_uses_process_uptime_and_preserves_health(monkeypatch: pytest.MonkeyPatch) -> None:
    class FakeProcess:
        @staticmethod
        def create_time() -> float:
            return 4_600.0

    monkeypatch.setattr(psutil, "Process", lambda _pid: FakeProcess())
    monkeypatch.setattr(psutil, "boot_time", lambda: 1_000.0)
    monkeypatch.setattr(time, "monotonic", lambda: 10_800.0)

    status = ContainerManager._status_with_monotonic_uptime("Up 17 hours (healthy)", 42)

    assert status == "Up 2 hours (healthy)"


def test_status_falls_back_when_process_is_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_process(pid: int) -> None:
        raise psutil.NoSuchProcess(pid)

    monkeypatch.setattr(psutil, "Process", missing_process)

    status = ContainerManager._status_with_monotonic_uptime("Up 17 hours", 42)

    assert status == "Up 17 hours"
