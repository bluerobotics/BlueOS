from ..monitor import (
    HealthCheckResult,
    HealthProblem,
    HealthStateTracker,
    evaluate_disk,
    merge_results,
)


def test_evaluate_disk_low_space() -> None:
    disks = [
        {
            "mount_point": "/",
            "total_space_B": 10 * 1024**3,
            "available_space_B": 1 * 1024**3,
        }
    ]
    result = evaluate_disk(disks, threshold_bytes=2 * 1024**3, threshold_percent=10, now=1_700_000_000_000)
    assert "disk.low_space" in result.active
    assert not result.resolved


def test_evaluate_disk_resolved() -> None:
    disks = [
        {
            "mount_point": "/",
            "total_space_B": 10 * 1024**3,
            "available_space_B": 5 * 1024**3,
        }
    ]
    result = evaluate_disk(disks, threshold_bytes=2 * 1024**3, threshold_percent=10, now=1_700_000_000_000)
    assert "disk.low_space" in result.resolved
    assert not result.active


def test_event_formatting_detected_and_resolved() -> None:
    tracker = HealthStateTracker()
    problem = HealthProblem(
        id="disk.low_space",
        severity="critical",
        title="Low disk space",
        details="Below threshold.",
        source="system",
        timestamp=1_700_000_000_000,
    )

    events = tracker.diff_and_update({"disk.low_space": problem}, {})
    assert events[0].type == "problem_detected"
    assert events[0].id == "disk.low_space"

    events = tracker.diff_and_update({}, {"disk.low_space": problem.copy(update={"timestamp": 1_700_000_000_500})})
    assert events[0].type == "problem_resolved"
    assert events[0].id == "disk.low_space"


def test_merge_results_with_tracker_flow() -> None:
    tracker = HealthStateTracker()
    now = 1_700_000_001_000
    disk_result = evaluate_disk(
        [{"mount_point": "/", "total_space_B": 10 * 1024**3, "available_space_B": 1 * 1024**3}],
        threshold_bytes=2 * 1024**3,
        threshold_percent=10,
        now=now,
    )
    memory_problem = HealthProblem(
        id="memory.high_usage",
        severity="warn",
        title="High memory usage",
        details="RAM usage high.",
        source="system",
        timestamp=now,
    )
    memory_result = HealthCheckResult(active={"memory.high_usage": memory_problem}, resolved={})
    merged = merge_results([disk_result, memory_result])

    events = tracker.diff_and_update(merged.active, merged.resolved)
    assert {event.id for event in events} == {"disk.low_space", "memory.high_usage"}
