import asyncio
from contextlib import contextmanager
from typing import (
    AsyncGenerator,
    Awaitable,
    Callable,
    Iterator,
    List,
    Optional,
    Sequence,
    Tuple,
)

from loguru import logger

OutputCallback = Callable[[str, str], Awaitable[None]]
JobStep = Callable[[OutputCallback], Awaitable[None]]


class InstallJobLocked(RuntimeError):
    """A firmware install job is already running."""


class FirmwareInstallJob:
    """Log of a firmware install, ending with a ("control", "done" | "error") line."""

    def __init__(self) -> None:
        self.log: List[Tuple[str, str]] = []
        self.finished = False
        self.task: Optional["asyncio.Task[None]"] = None
        self._changed = asyncio.Condition()

    async def emit(self, stream: str, line: str) -> None:
        async with self._changed:
            self.log.append((stream, line))
            self._changed.notify_all()

    async def finish(self, result: str) -> None:
        async with self._changed:
            self.log.append(("control", result))
            self.finished = True
            self._changed.notify_all()

    async def follow(self) -> AsyncGenerator[Tuple[str, str], None]:
        """Replay the log from the start and then follow it live until the job finishes.

        Closing the iterator (e.g. the HTTP client disconnecting) only stops following, the job keeps running.
        """
        sent = 0
        while True:
            async with self._changed:
                await self._changed.wait_for(lambda: sent < len(self.log) or self.finished)
                entries = self.log[sent:]
                finished = self.finished
            sent += len(entries)
            for entry in entries:
                yield entry
            if finished:
                return


class FirmwareInstallJobManager:
    """Runs at most one firmware install at a time, independently of the requests following it."""

    def __init__(self) -> None:
        self._job: Optional[FirmwareInstallJob] = None
        self._reserved = False

    @property
    def running_job(self) -> Optional[FirmwareInstallJob]:
        if self._job is None or self._job.finished:
            return None
        return self._job

    @contextmanager
    def reserve(self) -> Iterator[None]:
        """Hold the job slot while a request validates its input, so concurrent requests get InstallJobLocked."""
        if self._reserved or self.running_job is not None:
            raise InstallJobLocked("Operation already in progress.")
        self._reserved = True
        try:
            yield
        finally:
            self._reserved = False

    def start(
        self,
        operation: Callable[..., Awaitable[None]],
        post_success_steps: Sequence[JobStep] = (),
        cleanup_steps: Sequence[JobStep] = (),
    ) -> FirmwareInstallJob:
        """Start `operation(output_callback=...)` in the background.

        `post_success_steps` only run if the operation succeeded, `cleanup_steps` always run. The final control line
        is emitted after all of them.
        """
        if self.running_job is not None:
            raise InstallJobLocked("Operation already in progress.")
        job = FirmwareInstallJob()
        job.task = asyncio.create_task(self._run(job, operation, post_success_steps, cleanup_steps))
        self._job = job
        return job

    @staticmethod
    async def _run(
        job: FirmwareInstallJob,
        operation: Callable[..., Awaitable[None]],
        post_success_steps: Sequence[JobStep],
        cleanup_steps: Sequence[JobStep],
    ) -> None:
        succeeded = False
        try:
            # The autopilot manager stops the autopilot before the operation and starts it again afterwards
            await job.emit("stdout", "Stopping autopilot")
            await operation(output_callback=job.emit)
            await job.emit("stdout", "Autopilot restarted")
            for step in post_success_steps:
                await step(job.emit)
            succeeded = True
        except Exception as error:
            logger.error(f"Firmware install failed: {error}")
            await job.emit("stderr", f"Error: {error}")
        finally:
            for step in cleanup_steps:
                try:
                    await step(job.emit)
                except Exception as error:
                    logger.warning(f"Firmware install cleanup failed: {error}")
                    await job.emit("stderr", f"Cleanup failed: {error}")
            await job.finish("done" if succeeded else "error")
