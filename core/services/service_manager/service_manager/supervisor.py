"""Process supervisor - manages service processes."""

from __future__ import annotations

import asyncio
import logging
import os
import signal
from typing import TYPE_CHECKING

from service_manager.registry import ServiceRegistry, ServiceStatus

if TYPE_CHECKING:
    from service_manager.cgroup import CgroupController
    from service_manager.output import OutputCapture

log = logging.getLogger(__name__)


class ProcessSupervisor:
    """Manages service processes with cgroup isolation."""

    def __init__(
        self,
        registry: ServiceRegistry,
        cgroup: CgroupController,
        output: OutputCapture,
    ):
        self._registry = registry
        self._cgroup = cgroup
        self._output = output
        self._monitor_tasks: dict[str, asyncio.Task[None]] = {}
        self._restart_scheduled: set[str] = set()
        self._stopping: set[str] = set()

    async def start_service(self, name: str) -> bool:
        """Start a service by name."""
        state = self._registry.get(name)
        if state is None:
            log.error(f"Unknown service: {name}")
            return False

        if state.is_running:
            log.warning(f"Service already running: {name}")
            return False

        spec = state.spec

        # Update status to starting
        await self._registry.update_status(name, ServiceStatus.STARTING)

        # Create cgroup with limits
        cgroup_path = await self._cgroup.create(name, spec.limits)

        # Prepare environment
        env = os.environ.copy()
        env.update(spec.env)

        # Prepare working directory
        cwd = str(spec.cwd) if spec.cwd else None

        try:
            # Create output buffer
            self._output.create(name)

            # Start process
            log.info(f"Starting service: {name} -> {' '.join(spec.command)}")

            process = await asyncio.create_subprocess_exec(
                *spec.command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env,
                cwd=cwd,
                start_new_session=True,  # Prevent signals from propagating
            )

            pid = process.pid
            log.info(f"Service {name} started with PID {pid}")

            # Add to cgroup if available
            if cgroup_path and pid:
                await self._cgroup.add_pid(name, pid)

            # Update registry with running status
            await self._registry.update_status(
                name,
                ServiceStatus.RUNNING,
                pid=pid,
                process=process,
            )

            # Start output capture
            await self._output.start_capture(name, process.stdout, process.stderr)

            # Start monitor task
            self._monitor_tasks[name] = asyncio.create_task(
                self._monitor_process(name, process),
                name=f"monitor-{name}",
            )

            return True

        except FileNotFoundError:
            log.error(f"Command not found for service {name}: {spec.command[0]}")
            await self._registry.update_status(name, ServiceStatus.FAILED)
            return False
        except PermissionError:
            log.error(f"Permission denied for service {name}: {spec.command[0]}")
            await self._registry.update_status(name, ServiceStatus.FAILED)
            return False
        except Exception as e:
            log.error(f"Failed to start service {name}: {e}")
            await self._registry.update_status(name, ServiceStatus.FAILED)
            return False

    async def _monitor_process(
        self,
        name: str,
        process: asyncio.subprocess.Process,
    ) -> None:
        """Monitor a process and handle its exit."""
        try:
            exit_code = await process.wait()
        except asyncio.CancelledError:
            return

        # Wait for output capture to finish
        await self._output.wait_for_capture(name)

        state = self._registry.get(name)
        if state is None:
            return

        # Clean up cgroup
        await self._cgroup.destroy(name)

        # Check if this was a requested stop
        if name in self._stopping:
            self._stopping.discard(name)
            log.info(f"Service {name} stopped (exit code: {exit_code})")
            await self._registry.update_status(
                name,
                ServiceStatus.STOPPED,
                exit_code=exit_code,
            )
            return

        # Unexpected exit
        if exit_code == 0:
            log.info(f"Service {name} exited normally")
            await self._registry.update_status(
                name,
                ServiceStatus.STOPPED,
                exit_code=exit_code,
            )
        else:
            log.warning(f"Service {name} exited with code {exit_code}")
            await self._registry.update_status(
                name,
                ServiceStatus.FAILED,
                exit_code=exit_code,
            )

        # Handle restart if configured
        if state.spec.restart and name not in self._restart_scheduled:
            self._restart_scheduled.add(name)
            self._registry.increment_restart_count(name)
            delay = state.spec.restart_delay_sec
            log.info(f"Scheduling restart for {name} in {delay}s")
            asyncio.create_task(self._delayed_restart(name, delay))

    async def _delayed_restart(self, name: str, delay: float) -> None:
        """Restart a service after a delay."""
        await asyncio.sleep(delay)
        self._restart_scheduled.discard(name)

        state = self._registry.get(name)
        if state is None:
            return

        # Only restart if still configured to do so and not already running
        if state.spec.restart and not state.is_running:
            log.info(f"Restarting service: {name}")
            await self.start_service(name)

    async def stop_service(self, name: str, force: bool = False) -> bool:
        """Stop a running service."""
        state = self._registry.get(name)
        if state is None:
            log.error(f"Unknown service: {name}")
            return False

        if not state.is_running:
            log.warning(f"Service not running: {name}")
            return True

        process = self._registry.get_process(name)
        if process is None:
            log.warning(f"No process found for service: {name}")
            await self._registry.update_status(name, ServiceStatus.STOPPED)
            return True

        self._stopping.add(name)
        await self._registry.update_status(name, ServiceStatus.STOPPING)

        timeout = state.spec.stop_timeout_sec

        if force:
            # Immediate SIGKILL
            log.info(f"Force killing service: {name}")
            try:
                process.kill()
            except ProcessLookupError:
                pass
        else:
            # Graceful SIGTERM with timeout
            log.info(f"Sending SIGTERM to service: {name}")
            try:
                process.terminate()
            except ProcessLookupError:
                pass

            try:
                await asyncio.wait_for(process.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                log.warning(f"Service {name} did not stop within {timeout}s, sending SIGKILL")
                try:
                    process.kill()
                except ProcessLookupError:
                    pass

        # Wait for monitor task to finish
        task = self._monitor_tasks.pop(name, None)
        if task and not task.done():
            try:
                await asyncio.wait_for(task, timeout=5.0)
            except asyncio.TimeoutError:
                task.cancel()

        return True

    async def restart_service(self, name: str) -> bool:
        """Restart a service."""
        state = self._registry.get(name)
        if state is None:
            log.error(f"Unknown service: {name}")
            return False

        if state.is_running:
            await self.stop_service(name)

        # Reset restart count on manual restart
        self._registry.reset_restart_count(name)

        return await self.start_service(name)

    async def start_all_enabled(self) -> None:
        """Start all enabled services."""
        for state in self._registry.all():
            if state.spec.enabled and not state.is_running:
                await self.start_service(state.spec.name)

    async def stop_all(self, timeout: float = 30.0) -> None:
        """Stop all running services."""
        running = self._registry.running_services()
        if not running:
            return

        log.info(f"Stopping {len(running)} services")

        # Send SIGTERM to all
        for state in running:
            process = self._registry.get_process(state.spec.name)
            if process:
                self._stopping.add(state.spec.name)
                await self._registry.update_status(state.spec.name, ServiceStatus.STOPPING)
                try:
                    process.terminate()
                except ProcessLookupError:
                    pass

        # Wait for all to exit
        async def wait_for_service(name: str) -> None:
            process = self._registry.get_process(name)
            if process:
                try:
                    await process.wait()
                except Exception:
                    pass

        try:
            await asyncio.wait_for(
                asyncio.gather(*[wait_for_service(s.spec.name) for s in running]),
                timeout=timeout,
            )
        except asyncio.TimeoutError:
            log.warning("Timeout waiting for services to stop, sending SIGKILL")
            for state in running:
                process = self._registry.get_process(state.spec.name)
                if process:
                    try:
                        process.kill()
                    except ProcessLookupError:
                        pass

        # Cancel all monitor tasks
        for task in self._monitor_tasks.values():
            if not task.done():
                task.cancel()

        self._monitor_tasks.clear()
        self._stopping.clear()

        # Clean up all cgroups
        for state in running:
            await self._cgroup.destroy(state.spec.name)

    async def signal_service(self, name: str, sig: signal.Signals) -> bool:
        """Send a signal to a running service."""
        process = self._registry.get_process(name)
        if process is None:
            return False

        try:
            process.send_signal(sig)
            return True
        except ProcessLookupError:
            return False
