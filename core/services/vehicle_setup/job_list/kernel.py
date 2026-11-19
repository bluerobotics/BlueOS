"""Runs each job in its own task, so it outlives the request that started it; only the job decides when it's done."""

import asyncio
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional

from job_list.bus import Bus
from job_list.job import (
    Deadline,
    Done,
    Io,
    IoFailed,
    Job,
    JobKind,
    JobRef,
    Publish,
    Refused,
    TimedOut,
)
from loguru import logger
from pydantic import BaseModel


class RunningJob(BaseModel):
    job_id: str
    job: str


class UnknownJob(Exception):
    pass


@dataclass
class Running:
    job: str
    kind: JobKind
    instance: Job
    inbox: "asyncio.Queue[Any]" = field(default_factory=asyncio.Queue)
    task: Optional["asyncio.Task[None]"] = None
    deadline: Optional[float] = None  # event loop time


class Kernel:
    def __init__(self, bus: Bus, kinds: Dict[str, JobKind]) -> None:
        self.bus = bus
        self.kinds = kinds
        self.running: Dict[str, Running] = {}
        self.published: Dict[str, Any] = {}
        self.publish_jobs()
        # A subscriber or GET gets null instead of nothing before the first job of each kind
        for kind in kinds.values():
            for name in kind.states:
                self.publish(name, None)

    async def submit(self, name: str, command: Any) -> JobRef:
        kind = self.kinds[name]
        if kind.limit is not None:
            if kind.limit.locked():
                raise Refused("busy: another job that can't run alongside this one is running")
            await kind.limit.acquire()
        try:
            if kind.precondition is not None:
                await kind.precondition()
            job_id = uuid.uuid4().hex
            running = Running(name, kind, kind.create(job_id, command))
        except BaseException:
            if kind.limit is not None:
                kind.limit.release()
            raise
        self.running[job_id] = running
        running.task = asyncio.create_task(self.run(job_id, running))
        self.publish_jobs()
        return JobRef(job_id=job_id)

    def signal(self, signal: JobRef) -> JobRef:
        running = self.running.get(signal.job_id)
        if running is None:
            raise UnknownJob(f"no job {signal.job_id}")
        running.inbox.put_nowait(signal)
        return JobRef(job_id=signal.job_id)

    async def stop(self) -> None:
        tasks = [running.task for running in self.running.values() if running.task is not None]
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)

    async def run(self, job_id: str, running: Running) -> None:
        kind, job = running.kind, running.instance
        done = False
        try:
            async with kind.io(running.inbox.put_nowait) as io:
                done = await self.apply(job_id, running, io, job.start())
                while not done:
                    done = await self.apply(job_id, running, io, job.handle(await self.next_event(running)))
            logger.info(f"Job {running.job} {job_id} finished")
        except asyncio.CancelledError:
            logger.info(f"Job {running.job} {job_id} cancelled")
        except Exception as error:
            logger.exception(f"Job {running.job} {job_id} failed: {error}")
            # After Done (e.g. the IO scope failing to close) the job's final state already stands
            if not done:
                self.fail(job_id, running, str(error))
        finally:
            if kind.limit is not None:
                kind.limit.release()
            self.running.pop(job_id, None)
            self.publish_jobs()

    @staticmethod
    async def next_event(running: Running) -> Any:
        try:
            async with asyncio.timeout_at(running.deadline):
                return await running.inbox.get()
        except TimeoutError:
            running.deadline = None
            return TimedOut()

    # An IO answer's outputs queue behind the ones the job already returned
    async def apply(self, job_id: str, running: Running, io: Io, outputs: Iterable[Any]) -> bool:
        pending = deque(outputs)
        while pending:
            match pending.popleft():
                case Done():
                    return True
                case Publish() as output:
                    self.publish_state(running.kind, output)
                case Deadline(seconds):
                    running.deadline = None if seconds is None else asyncio.get_running_loop().time() + seconds
                case request:
                    try:
                        answer = await io(request)
                    except Exception as error:
                        logger.error(f"Job {job_id} failed to run {request}: {error}")
                        answer = IoFailed(request, str(error))
                    pending.extend(running.instance.handle(answer))
        return False

    # The job is broken, so only its Publish outputs are trusted: no more IO or deadlines
    def fail(self, job_id: str, running: Running, error: str) -> None:
        try:
            outputs = list(running.instance.failed(error))
        except Exception as hook_error:
            logger.exception(f"Job {running.job} {job_id} failed to report its failure: {hook_error}")
            return
        for output in outputs:
            if isinstance(output, Publish):
                self.publish_state(running.kind, output)

    def publish_state(self, kind: JobKind, output: Publish) -> None:
        name = output.topic
        if name is None and len(kind.states) == 1:
            name = kind.states[0]
        if name is None or name not in kind.states:
            logger.error(f"Dropping a Publish to {output.topic}, not one of {kind.states}")
            return
        self.publish(name, output.payload.model_dump(mode="json"))

    def publish_jobs(self) -> None:
        jobs: List[Any] = [
            RunningJob(job_id=job_id, job=running.job).model_dump(mode="json")
            for job_id, running in self.running.items()
        ]
        self.publish("jobs", jobs)

    def publish(self, name: str, payload: Any) -> None:
        if name in self.published and self.published[name] == payload:
            return
        self.published[name] = payload
        try:
            self.bus.publish(name, payload)
        except Exception as error:
            logger.error(f"Failed to publish {name}: {error}")
