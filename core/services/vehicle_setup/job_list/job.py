"""What a job is, and the values it exchanges with the kernel. A job never does IO: it returns what it wants done."""

import asyncio
from contextlib import AbstractAsyncContextManager
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Iterable, List, Optional, Protocol

from pydantic import BaseModel


class JobRef(BaseModel):
    job_id: str


class Cancel(JobRef):
    pass


class Refused(Exception):
    pass


# Outputs: anything else a job returns is an IO request, whose answer comes back to it as an event
@dataclass(frozen=True)
class Publish:
    payload: BaseModel
    topic: Optional[str] = None  # one of the kind's states; None for a kind with a single state


@dataclass(frozen=True)
class Deadline:
    seconds: Optional[float]  # from now, replacing the previous Deadline; None disarms it


@dataclass(frozen=True)
class Done:
    pass


# Events the kernel sends itself
@dataclass(frozen=True)
class TimedOut:
    pass


@dataclass(frozen=True)
class IoFailed:
    request: Any
    error: str


class Job(Protocol):
    def start(self) -> Iterable[Any]:
        ...

    def handle(self, event: Any) -> Iterable[Any]:
        ...

    # Returns the Publish outputs that leave its states final, after start or handle raised
    def failed(self, error: str) -> Iterable[Any]:
        ...


Io = Callable[[Any], Awaitable[Any]]
# Given the function that delivers unsolicited events to the job, yields the job's IO for as long as it runs
IoScope = Callable[[Callable[[Any], None]], AbstractAsyncContextManager[Io]]


@dataclass
class JobKind:
    create: Callable[[str, Any], Job]
    io: IoScope
    states: List[str] = field(default_factory=list)  # the state names its Publish outputs go to
    # Shared by every kind that must not run alongside it; a taken lock refuses the job
    limit: Optional[asyncio.Lock] = None
    precondition: Optional[Callable[[], Awaitable[None]]] = None  # raises Refused before the job is accepted
