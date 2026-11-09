"""What a job is, and the values it exchanges with the kernel. A job never does IO: it returns what it wants done."""

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, List, Optional, Protocol

from pydantic import BaseModel


# The job: started and fed events by the kernel, it answers each with the effects it wants
class Job(Protocol):
    def start(self) -> Iterable["Effect"]:
        ...

    def handle(self, event: Any) -> Iterable["Effect"]:
        ...

    # Returns the Publish effects that leave its topics final, after start or handle raised
    def failed(self, error: str) -> Iterable["Effect"]:
        ...


# What a job returns: effects the kernel applies in order
@dataclass(frozen=True)
class Publish:
    payload: BaseModel
    topic: Optional[str] = None  # None for a kind with a single topic


@dataclass(frozen=True)
class Deadline:
    seconds: Optional[float]  # from now, replacing the previous Deadline; None disarms it


@dataclass(frozen=True)
class Done:
    pass


class IoRequest:
    """Base of what a job hands to its kind's IO; the answer comes back to the job as an event."""


Effect = Publish | Deadline | Done | IoRequest


# What a job receives from the kernel itself, besides client signals and what its IO delivers
@dataclass(frozen=True)
class TimedOut:
    pass


@dataclass(frozen=True)
class IoFailed:
    request: IoRequest
    error: str


KernelEvent = TimedOut | IoFailed


# Registering a kind: how to create its jobs, the IO they get, and when they may run
Io = Callable[[IoRequest], Awaitable[Any]]
# Given the function that delivers unsolicited events to the job, yields the job's IO for as long as it runs
IoScope = Callable[[Callable[[Any], None]], AbstractAsyncContextManager[Io]]


@dataclass
class JobKind:
    create: Callable[[str, Any], Job]
    io: IoScope
    # "jobs" is taken by the kernel's list of running jobs
    topics: List[str] = field(default_factory=list)
    # Shared by every kind that must not run alongside it; a taken lock refuses the job
    limit: Optional[asyncio.Lock] = None
    precondition: Optional[Callable[[], Awaitable[None]]] = None


# Talking to running jobs: what a client sends one, and the reply when a job can't start
class JobRef(BaseModel):
    job_id: str


class Cancel(JobRef):
    pass


class Refused(Exception):
    pass
