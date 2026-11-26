import asyncio
from typing import Any, List, Tuple

import pytest
from firmware.install_job import (
    FirmwareInstallJob,
    FirmwareInstallJobManager,
    InstallJobLocked,
    OutputCallback,
)

pytestmark = [pytest.mark.asyncio, pytest.mark.timeout(5)]


async def collect(job: FirmwareInstallJob) -> List[Tuple[str, str]]:
    return [entry async for entry in job.follow()]


class Operation:
    """Install operation that prints a line and waits to be released."""

    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.started = asyncio.Event()
        self.release = asyncio.Event()

    async def __call__(self, output_callback: OutputCallback) -> None:
        await output_callback("stdout", "flashing")
        self.started.set()
        await self.release.wait()
        if self.error:
            raise self.error


def step(calls: List[str], name: str) -> Any:
    async def run(output_callback: OutputCallback) -> None:
        calls.append(name)
        await output_callback("stdout", name)

    return run


async def test_job_runs_steps_and_ends_with_done() -> None:
    manager = FirmwareInstallJobManager()
    operation = Operation()
    calls: List[str] = []
    job = manager.start(operation, post_success_steps=[step(calls, "switch")], cleanup_steps=[step(calls, "cleanup")])
    operation.release.set()

    assert await collect(job) == [
        ("stdout", "Stopping autopilot"),
        ("stdout", "flashing"),
        ("stdout", "Autopilot restarted"),
        ("stdout", "switch"),
        ("stdout", "cleanup"),
        ("control", "done"),
    ]
    assert calls == ["switch", "cleanup"]
    assert manager.running_job is None


async def test_failed_job_skips_post_success_steps_but_cleans_up() -> None:
    manager = FirmwareInstallJobManager()
    operation = Operation(RuntimeError("board not suitable"))
    calls: List[str] = []
    job = manager.start(operation, post_success_steps=[step(calls, "switch")], cleanup_steps=[step(calls, "cleanup")])
    operation.release.set()

    log = await collect(job)
    assert calls == ["cleanup"]
    assert ("stderr", "Error: board not suitable") in log
    assert log[-2:] == [("stdout", "cleanup"), ("control", "error")]


async def test_failing_cleanup_keeps_the_result() -> None:
    async def broken_cleanup(_output_callback: OutputCallback) -> None:
        raise OSError("busy")

    operation = Operation()
    job = FirmwareInstallJobManager().start(operation, cleanup_steps=[broken_cleanup])
    operation.release.set()
    assert (await collect(job))[-1] == ("control", "done")


async def test_subscriber_disconnect_does_not_cancel_job() -> None:
    manager = FirmwareInstallJobManager()
    operation = Operation()
    job = manager.start(operation)

    subscriber = job.follow()
    assert await anext(subscriber) == ("stdout", "Stopping autopilot")
    await subscriber.aclose()
    await operation.started.wait()
    assert manager.running_job is job

    operation.release.set()
    assert job.task is not None
    await job.task
    assert job.log[-1] == ("control", "done")


async def test_late_subscriber_gets_full_log() -> None:
    manager = FirmwareInstallJobManager()
    operation = Operation()
    job = manager.start(operation)
    await operation.started.wait()

    late_subscriber = asyncio.create_task(collect(job))
    await asyncio.sleep(0)
    operation.release.set()
    log = await late_subscriber
    assert log[:2] == [("stdout", "Stopping autopilot"), ("stdout", "flashing")]
    assert log == job.log
    assert log[-1] == ("control", "done")


async def test_only_one_job_at_a_time() -> None:
    manager = FirmwareInstallJobManager()
    operation = Operation()
    job = manager.start(operation)

    with pytest.raises(InstallJobLocked):
        manager.start(Operation())
    with pytest.raises(InstallJobLocked):
        with manager.reserve():
            pass

    operation.release.set()
    await collect(job)
    second = Operation()
    second.release.set()
    assert (await collect(manager.start(second)))[-1] == ("control", "done")


async def test_reservation_blocks_other_requests() -> None:
    manager = FirmwareInstallJobManager()
    with manager.reserve():
        with pytest.raises(InstallJobLocked):
            with manager.reserve():
                pass
        operation = Operation()
        operation.release.set()
        job = manager.start(operation)
    with pytest.raises(InstallJobLocked):
        with manager.reserve():
            pass
    await collect(job)
    with manager.reserve():
        pass
