"""Output capture - ring buffer for service stdout/stderr."""

from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class OutputLine:
    """A single line of output with metadata."""

    timestamp: datetime
    stream: str  # "stdout" or "stderr"
    line: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "stream": self.stream,
            "line": self.line,
        }

    def __str__(self) -> str:
        return f"[{self.timestamp.strftime('%H:%M:%S')}] {self.line}"


@dataclass
class ServiceOutput:
    """Ring buffer for a single service's output."""

    max_lines: int
    lines: deque[OutputLine] = field(default_factory=deque)

    def __post_init__(self) -> None:
        self.lines = deque(maxlen=self.max_lines)

    def append(self, stream: str, line: str) -> None:
        """Append a line of output."""
        self.lines.append(
            OutputLine(
                timestamp=datetime.now(timezone.utc),
                stream=stream,
                line=line.rstrip("\n\r"),
            )
        )

    def get_lines(
        self,
        tail: int | None = None,
        stream: str | None = None,
    ) -> list[OutputLine]:
        """Get output lines, optionally filtered and limited."""
        lines = list(self.lines)

        if stream:
            lines = [line for line in lines if line.stream == stream]

        if tail is not None and tail > 0:
            lines = lines[-tail:]  # pylint: disable=invalid-unary-operand-type

        return lines

    def clear(self) -> None:
        """Clear all output."""
        self.lines.clear()


class OutputCapture:
    """Manages output capture for all services."""

    def __init__(self, max_lines: int = 10000):
        self.max_lines = max_lines
        self._outputs: dict[str, ServiceOutput] = {}
        self._tasks: dict[str, list[asyncio.Task[None]]] = {}

    def create(self, name: str) -> None:
        """Create output buffer for a service."""
        if name not in self._outputs:
            self._outputs[name] = ServiceOutput(max_lines=self.max_lines)
        else:
            # Clear existing buffer on restart
            self._outputs[name].clear()

    def get(self, name: str) -> ServiceOutput | None:
        """Get output buffer for a service."""
        return self._outputs.get(name)

    def get_lines(
        self,
        name: str,
        tail: int | None = None,
        stream: str | None = None,
    ) -> list[OutputLine]:
        """Get output lines for a service."""
        output = self._outputs.get(name)
        if output is None:
            return []
        return output.get_lines(tail=tail, stream=stream)

    def clear(self, name: str) -> None:
        """Clear output buffer for a service."""
        output = self._outputs.get(name)
        if output:
            output.clear()

    def remove(self, name: str) -> None:
        """Remove output buffer for a service."""
        self._outputs.pop(name, None)
        self._cancel_tasks(name)

    def _cancel_tasks(self, name: str) -> None:
        """Cancel capture tasks for a service."""
        tasks = self._tasks.pop(name, [])
        for task in tasks:
            if not task.done():
                task.cancel()

    async def start_capture(
        self,
        name: str,
        stdout: asyncio.StreamReader | None,
        stderr: asyncio.StreamReader | None,
    ) -> None:
        """Start capturing output from streams."""
        self.create(name)
        self._cancel_tasks(name)

        tasks = []

        if stdout:
            task = asyncio.create_task(
                self._capture_stream(name, stdout, "stdout"),
                name=f"capture-{name}-stdout",
            )
            tasks.append(task)

        if stderr:
            task = asyncio.create_task(
                self._capture_stream(name, stderr, "stderr"),
                name=f"capture-{name}-stderr",
            )
            tasks.append(task)

        self._tasks[name] = tasks

    async def _capture_stream(
        self,
        name: str,
        stream: asyncio.StreamReader,
        stream_name: str,
    ) -> None:
        """Capture lines from a stream into the ring buffer."""
        output = self._outputs.get(name)
        if output is None:
            return

        try:
            while True:
                line = await stream.readline()
                if not line:
                    break

                try:
                    text = line.decode("utf-8", errors="replace")
                except Exception:
                    text = str(line)

                output.append(stream_name, text)
        except asyncio.CancelledError:
            pass
        except Exception as e:
            log.error(f"Error capturing {stream_name} for {name}: {e}")

    async def wait_for_capture(self, name: str) -> None:
        """Wait for all capture tasks to complete."""
        tasks = self._tasks.get(name, [])
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._tasks.pop(name, None)
