"""Daemon manager - PID lock, daemonization, signal handling."""
# pylint: disable=too-many-instance-attributes

from __future__ import annotations

import asyncio
import fcntl
import logging
import os
import signal
import sys
import threading
from pathlib import Path

import uvicorn
from service_manager.cgroup import CgroupController
from service_manager.config import AgentConfig, ConfigPersistence
from service_manager.metrics import MetricsSampler
from service_manager.output import OutputCapture
from service_manager.registry import ServiceRegistry
from service_manager.server import create_app
from service_manager.supervisor import ProcessSupervisor

log = logging.getLogger(__name__)


class PidLock:
    """PID file with exclusive lock for single-instance guarantee."""

    def __init__(self, path: Path):
        self.path = path
        self._fd: int | None = None

    def acquire(self) -> bool:
        """Acquire exclusive lock. Returns False if already held."""
        self.path.parent.mkdir(parents=True, exist_ok=True)

        try:
            self._fd = os.open(str(self.path), os.O_RDWR | os.O_CREAT, 0o644)
            fcntl.flock(self._fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.ftruncate(self._fd, 0)
            os.write(self._fd, f"{os.getpid()}\n".encode())
            os.fsync(self._fd)
            return True
        except OSError:
            if self._fd is not None:
                os.close(self._fd)
                self._fd = None
            return False

    def release(self) -> None:
        """Release lock and remove PID file."""
        if self._fd is not None:
            try:
                fcntl.flock(self._fd, fcntl.LOCK_UN)
                os.close(self._fd)
            except OSError:
                pass
            self._fd = None

        try:
            self.path.unlink(missing_ok=True)
        except OSError:
            pass

    @classmethod
    def read_pid(cls, path: Path) -> int | None:
        """Read PID from file, return None if not exists or invalid."""
        try:
            content = path.read_text().strip()
            return int(content)
        except (OSError, ValueError):
            return None

    @classmethod
    def is_running(cls, path: Path) -> bool:
        """Check if daemon is running based on PID file."""
        pid = cls.read_pid(path)
        if pid is None:
            return False

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            return False


def daemonize() -> None:
    """Classic double-fork daemonization."""
    # First fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Decouple from parent
    os.setsid()
    os.chdir("/")

    # Second fork
    pid = os.fork()
    if pid > 0:
        sys.exit(0)

    # Redirect standard file descriptors
    sys.stdout.flush()
    sys.stderr.flush()

    with open("/dev/null", "rb") as devnull:
        os.dup2(devnull.fileno(), sys.stdin.fileno())
    with open("/dev/null", "ab") as devnull:
        os.dup2(devnull.fileno(), sys.stdout.fileno())
        os.dup2(devnull.fileno(), sys.stderr.fileno())


class AgentDaemon:
    """Main daemon orchestrator."""

    def __init__(self, config_path: Path | None = None, foreground: bool = False):
        self.config_path = config_path
        self.foreground = foreground
        self.config: AgentConfig | None = None
        self._shutdown_event = asyncio.Event()
        self._pid_lock: PidLock | None = None

        # Components
        self._registry: ServiceRegistry | None = None
        self._cgroup: CgroupController | None = None
        self._output: OutputCapture | None = None
        self._supervisor: ProcessSupervisor | None = None
        self._sampler: MetricsSampler | None = None
        self._persistence: ConfigPersistence | None = None

    def _setup_logging(self) -> None:
        """Configure logging."""
        level = logging.DEBUG if self.foreground else logging.INFO
        logging.basicConfig(
            level=level,
            format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S",
        )
        # Suppress noisy Robyn debug messages
        logging.getLogger("robyn").setLevel(logging.INFO)

    def _setup_signals(self) -> None:
        """Install signal handlers."""
        loop = asyncio.get_running_loop()

        for sig in (signal.SIGTERM, signal.SIGINT):
            loop.add_signal_handler(sig, self._signal_shutdown, sig)

        loop.add_signal_handler(signal.SIGHUP, self._signal_reload)

    def _signal_shutdown(self, sig: signal.Signals) -> None:
        """Handle shutdown signal."""
        log.info(f"Received {sig.name}, initiating shutdown")
        self._shutdown_event.set()

    def _signal_reload(self) -> None:
        """Handle reload signal."""
        log.info("Received SIGHUP, reloading configuration")
        asyncio.create_task(self._reload_config())

    async def _reload_config(self) -> None:
        """Reload configuration from file."""
        try:
            new_config = AgentConfig.load_or_default(self.config_path)
            log.info(f"Reloaded config with {len(new_config.services)} services")

            if self._registry and self._supervisor:
                await self._reconcile_services(new_config)

            self.config = new_config
        except Exception as e:
            log.error(f"Failed to reload config: {e}")

    async def _reconcile_services(self, new_config: AgentConfig) -> None:
        """Reconcile running services with new configuration."""
        if not self._registry or not self._supervisor:
            return

        old_names = {s.name for s in self.config.services} if self.config else set()
        new_names = {s.name for s in new_config.services}

        # Stop removed services
        for name in old_names - new_names:
            log.info(f"Stopping removed service: {name}")
            await self._supervisor.stop_service(name)
            self._registry.remove(name)

        # Update or add services
        for spec in new_config.services:
            existing = self._registry.get(spec.name)
            if existing is None:
                # New service
                self._registry.register(spec)
                if spec.enabled:
                    log.info(f"Starting new service: {spec.name}")
                    await self._supervisor.start_service(spec.name)
            else:
                # Existing service - update spec
                old_spec = existing.spec
                self._registry.update_spec(spec)

                # Restart if command changed
                if old_spec.command != spec.command and existing.is_running:
                    log.info(f"Restarting service due to command change: {spec.name}")
                    await self._supervisor.restart_service(spec.name)

    async def _start_components(self) -> None:
        """Initialize and start all components."""
        self.config = AgentConfig.load_or_default(self.config_path)

        # Initialize components
        self._registry = ServiceRegistry()
        self._cgroup = CgroupController(self.config.cgroup_root)
        self._output = OutputCapture(self.config.log_buffer_lines)
        self._supervisor = ProcessSupervisor(self._registry, self._cgroup, self._output)
        self._sampler = MetricsSampler(
            self._registry,
            self._cgroup,
            self.config.metrics_interval_sec,
        )
        self._persistence = ConfigPersistence()

        # Ensure cgroup root exists
        await self._cgroup.ensure_root()

        # Reconcile with any orphan cgroups from previous run
        await self._reconcile_orphans()

        # Register services from config, applying user overrides
        for spec in self.config.services:
            self._persistence.apply_overrides(spec)
            self._registry.register(spec)

        # Start enabled services
        await self._supervisor.start_all_enabled()

        # Start metrics sampler
        asyncio.create_task(self._sampler.run(self._shutdown_event))

        # Start REST server in a thread (uvicorn runs its own event loop)
        log.info(f"Starting REST server on {self.config.host}:{self.config.port}")
        self._start_uvicorn_server()

    def _start_uvicorn_server(self) -> None:
        """Start uvicorn server in a background thread."""
        assert self._registry is not None
        assert self._supervisor is not None
        assert self._output is not None
        assert self._sampler is not None
        assert self._cgroup is not None
        assert self.config is not None

        app = create_app(
            self._registry,
            self._supervisor,
            self._output,
            self._sampler,
            self._cgroup,
            self._persistence,
        )

        config = self.config

        def run_server() -> None:
            uvicorn.run(app, host=config.host, port=config.port, log_level="warning")

        thread = threading.Thread(target=run_server, daemon=True)
        thread.start()

    async def _reconcile_orphans(self) -> None:
        """Detect and clean up orphan cgroups from previous run."""
        if not self._cgroup:
            return

        orphans = await self._cgroup.list_existing()
        for name in orphans:
            log.warning(f"Found orphan cgroup: {name}, cleaning up")
            await self._cgroup.destroy(name)

    async def _stop_components(self) -> None:
        """Stop all components gracefully."""
        if self._supervisor:
            log.info("Stopping all services")
            await self._supervisor.stop_all()

    async def run(self) -> None:
        """Main daemon loop."""
        self._setup_logging()

        config = AgentConfig.load_or_default(self.config_path)

        # In foreground mode, we handle PID lock here
        # In daemon mode (Linux), it's handled in __main__.py before asyncio starts
        if self.foreground:
            self._pid_lock = PidLock(config.pid_file)
            if not self._pid_lock.acquire():
                log.error("Another instance is already running")
                sys.exit(1)

        try:
            self._setup_signals()
            await self._start_components()
            await self._shutdown_event.wait()
            await self._stop_components()
        finally:
            if self._pid_lock:
                self._pid_lock.release()
            log.info("Daemon stopped")
