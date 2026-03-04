"""CLI client for service-manager."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import httpx
from service_manager import __version__
from service_manager.client.http import ServiceManagerClient
from service_manager.client.spawn import ensure_daemon
from service_manager.config import AgentConfig


def get_client(config_path: Path | None = None) -> ServiceManagerClient:
    """Get HTTP client, ensuring daemon is running."""
    if not ensure_daemon(config_path):
        print("Error: Failed to start service-manager daemon", file=sys.stderr)
        sys.exit(1)

    config = AgentConfig.load_or_default(config_path)
    return ServiceManagerClient(config.base_url)


def cmd_list(args: argparse.Namespace) -> int:
    """List all services."""
    client = get_client(args.config)

    try:
        data = client.list_services()
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    services = data.get("services", [])

    if not services:
        print("No services configured")
        return 0

    # Print table
    print(f"{'NAME':<20} {'STATUS':<12} {'PID':<8} {'RESTARTS':<10} {'UPTIME':<15}")
    print("-" * 65)

    for svc in services:
        name = svc["name"][:20]
        status = svc["status"]
        pid = svc.get("pid") or "-"
        restarts = svc.get("restart_count", 0)
        uptime = svc.get("uptime_seconds")

        if uptime is not None:
            uptime_str = format_duration(uptime)
        else:
            uptime_str = "-"

        print(f"{name:<20} {status:<12} {str(pid):<8} {restarts:<10} {uptime_str:<15}")

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Get status of a specific service."""
    client = get_client(args.config)

    try:
        data = client.get_service(args.name)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    print(json.dumps(data, indent=2))
    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start a service."""
    client = get_client(args.config)

    try:
        data = client.start_service(args.name)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    print(data.get("message", "Started"))
    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop a service."""
    client = get_client(args.config)

    try:
        data = client.stop_service(args.name, force=args.force)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    print(data.get("message", "Stopped"))
    return 0


def cmd_restart(args: argparse.Namespace) -> int:
    """Restart a service."""
    client = get_client(args.config)

    try:
        data = client.restart_service(args.name)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    print(data.get("message", "Restarted"))
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Get logs for a service."""
    client = get_client(args.config)

    try:
        data = client.get_logs(args.name, tail=args.tail, stream=args.stream)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    lines = data.get("lines", [])

    for line in lines:
        timestamp = line.get("timestamp", "")[:19].replace("T", " ")
        stream = line.get("stream", "")
        text = line.get("line", "")

        if args.timestamps:
            prefix = f"[{timestamp}] "
        else:
            prefix = ""

        if stream == "stderr":
            print(f"{prefix}\033[31m{text}\033[0m")
        else:
            print(f"{prefix}{text}")

    return 0


def cmd_metrics(args: argparse.Namespace) -> int:
    """Get metrics for services."""
    client = get_client(args.config)

    try:
        data = client.get_metrics(args.name)
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(data, indent=2))
        return 0

    # Format as table
    if args.name:
        metrics = data.get("metrics")
        if metrics is None:
            print(f"No metrics available for {args.name}")
            return 0

        print(f"Service: {args.name}")
        print(f"  CPU:         {metrics['cpu_percent']:.1f}%")
        print(f"  Memory:      {metrics['memory_mb']:.1f} MB")
        print(f"  Memory Peak: {metrics['memory_peak_mb']:.1f} MB")
        print(f"  IO Read:     {metrics['io_read_mb']:.2f} MB ({metrics['io_read_rate_mbps']:.3f} MB/s)")
        print(f"  IO Write:    {metrics['io_write_mb']:.2f} MB ({metrics['io_write_rate_mbps']:.3f} MB/s)")
        print(f"  PIDs:        {metrics['pids']}")
    else:
        if not data:
            print("No metrics available")
            return 0

        print(f"{'SERVICE':<20} {'CPU%':<8} {'MEM MB':<10} {'IO R MB/s':<12} {'IO W MB/s':<12}")
        print("-" * 62)

        for name, metrics in data.items():
            print(
                f"{name:<20} "
                f"{metrics['cpu_percent']:<8.1f} "
                f"{metrics['memory_mb']:<10.1f} "
                f"{metrics['io_read_rate_mbps']:<12.3f} "
                f"{metrics['io_write_rate_mbps']:<12.3f}"
            )

    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Check daemon health."""
    client = get_client(args.config)

    try:
        data = client.health()
    except httpx.HTTPStatusError as e:
        print(f"Error: {e.response.text}", file=sys.stderr)
        return 1

    print(json.dumps(data, indent=2))
    return 0


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form."""
    if seconds < 60:
        return f"{int(seconds)}s"
    if seconds < 3600:
        return f"{int(seconds / 60)}m {int(seconds % 60)}s"
    if seconds < 86400:
        hours = int(seconds / 3600)
        mins = int((seconds % 3600) / 60)
        return f"{hours}h {mins}m"
    days = int(seconds / 86400)
    hours = int((seconds % 86400) / 3600)
    return f"{days}d {hours}h"


def main() -> int:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="svcmgr",
        description="Service Manager CLI",
    )
    parser.add_argument(
        "-c",
        "--config",
        type=Path,
        help="Path to config file",
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    # list
    p_list = subparsers.add_parser("list", help="List all services")
    p_list.set_defaults(func=cmd_list)

    # status
    p_status = subparsers.add_parser("status", help="Get service status")
    p_status.add_argument("name", help="Service name")
    p_status.set_defaults(func=cmd_status)

    # start
    p_start = subparsers.add_parser("start", help="Start a service")
    p_start.add_argument("name", help="Service name")
    p_start.set_defaults(func=cmd_start)

    # stop
    p_stop = subparsers.add_parser("stop", help="Stop a service")
    p_stop.add_argument("name", help="Service name")
    p_stop.add_argument("-f", "--force", action="store_true", help="Force kill")
    p_stop.set_defaults(func=cmd_stop)

    # restart
    p_restart = subparsers.add_parser("restart", help="Restart a service")
    p_restart.add_argument("name", help="Service name")
    p_restart.set_defaults(func=cmd_restart)

    # logs
    p_logs = subparsers.add_parser("logs", help="Get service logs")
    p_logs.add_argument("name", help="Service name")
    p_logs.add_argument("-n", "--tail", type=int, default=100, help="Number of lines")
    p_logs.add_argument("-s", "--stream", choices=["stdout", "stderr"], help="Filter by stream")
    p_logs.add_argument("-t", "--timestamps", action="store_true", help="Show timestamps")
    p_logs.set_defaults(func=cmd_logs)

    # metrics
    p_metrics = subparsers.add_parser("metrics", help="Get service metrics")
    p_metrics.add_argument("name", nargs="?", help="Service name (optional)")
    p_metrics.add_argument("--json", action="store_true", help="Output as JSON")
    p_metrics.set_defaults(func=cmd_metrics)

    # health
    p_health = subparsers.add_parser("health", help="Check daemon health")
    p_health.set_defaults(func=cmd_health)

    args = parser.parse_args()

    try:
        result: int = args.func(args)
        return result
    except KeyboardInterrupt:
        return 130
    except httpx.ConnectError:
        print("Error: Cannot connect to daemon", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
