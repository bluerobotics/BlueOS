import os
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Optional, Tuple

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent))
_saved = sys.modules.pop("main", None)

import main as disk_usage

if _saved is not None:
    sys.modules["main"] = _saved
else:
    sys.modules.pop("main", None)

DISKTEST_OUTPUT = """Generated --seed abc123
Done. Wrote 1.00 MiB (1.05 MB, 1048576 bytes) @ 19.7 MiB/s.
Done. Verified 1.00 MiB (1.05 MB, 1048576 bytes) @ 86.7 MiB/s.
"""


@pytest.fixture(name="root")
def fixture_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path.resolve()
    monkeypatch.setattr(disk_usage, "FILESYSTEM_ROOT", root)
    (root / "big.bin").write_bytes(b"0" * 50_000)
    (root / "tiny.txt").write_bytes(b"0" * 10)
    (root / "sub" / "deep").mkdir(parents=True)
    (root / "sub" / "deep" / "nested.bin").write_bytes(b"0" * 20_000)
    return root


def test_resolve_accepts_paths_inside_root(root: Path) -> None:
    assert disk_usage.resolve_requested_path("sub") == root / "sub"
    assert disk_usage.resolve_requested_path(str(root / "sub" / "deep")) == root / "sub" / "deep"


@pytest.mark.parametrize("requested, status_code", [("..", 400), ("/etc", 400), ("escape", 400), ("missing", 404)])
def test_resolve_rejects_paths_outside_root_or_missing(root: Path, requested: str, status_code: int) -> None:
    (root / "escape").symlink_to("/etc")
    with pytest.raises(HTTPException) as error:
        disk_usage.resolve_requested_path(requested)
    assert error.value.status_code == status_code


@pytest.mark.parametrize(
    "path, protected",
    [
        ("/etc", True),
        ("/etc/passwd", True),
        ("/usr/lib/python3", True),
        ("/", True),
        ("/usr", True),
        ("/etcetera", False),
        ("/usr/local/bin", False),
        ("/home/pi", False),
    ],
)
def test_is_protected_target(path: str, protected: bool) -> None:
    assert disk_usage.is_protected_target(Path(path)) is protected


# Requires GNU du, BusyBox du has no -b flag.
@pytest.mark.asyncio
async def test_usage_tree_filters_small_entries_and_sorts_by_size(root: Path) -> None:
    usage = await disk_usage.get_disk_usage(path=str(root), depth=3, include_files=True, min_size_bytes=1000)
    assert (usage.root.name, usage.root.path) == ("/", str(root))
    assert usage.root.size_bytes >= 70_000
    big, sub = usage.root.children
    assert (big.name, big.size_bytes, big.is_dir) == ("big.bin", 50_000, False)
    assert (sub.name, sub.is_dir) == ("sub", True)
    assert sub.children[0].children[0].name == "nested.bin"


# Requires GNU du, BusyBox du has no -b flag.
@pytest.mark.asyncio
async def test_usage_tree_lists_symlinks_without_overwriting_targets(root: Path) -> None:
    (root / "link").symlink_to(root / "sub")
    usage = await disk_usage.get_disk_usage(path=str(root), depth=1, include_files=True, min_size_bytes=0)
    sizes = {child.name: child.size_bytes for child in usage.root.children}
    assert sizes["sub"] >= 20_000
    assert sizes["link"] < 1000


def test_build_tree_attaches_orphans_to_nearest_ancestor(root: Path) -> None:
    tree = disk_usage.build_tree({root / "sub" / "deep" / "nested.bin": 20_000}, root, min_size_bytes=0)
    assert tree.size_bytes == 20_000
    assert [child.name for child in tree.children] == ["nested.bin"]


def test_parse_du_output_skips_malformed_lines() -> None:
    output = b"100\t/a b\nnot-a-number\t/x\ngarbage\n\n42 /c\n"
    assert disk_usage.parse_du_output(output) == {Path("/a b"): 100, Path("/c"): 42}


@pytest.mark.asyncio
async def test_delete_removes_file(root: Path) -> None:
    await disk_usage.delete_path("big.bin")
    assert not (root / "big.bin").exists()


@pytest.mark.asyncio
async def test_delete_removes_folder_recursively(root: Path) -> None:
    await disk_usage.delete_path("sub")
    assert not (root / "sub").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize("target", ["sub", "big.bin", "missing"])
async def test_delete_removes_symlink_not_its_target(root: Path, target: str) -> None:
    (root / "link").symlink_to(root / target)
    target_existed = (root / target).exists()
    await disk_usage.delete_path("link")
    assert not (root / "link").is_symlink()
    assert (root / target).exists() is target_existed


@pytest.mark.asyncio
@pytest.mark.parametrize("requested", ["..", "sub/../..", "/etc", "escape/passwd"])
async def test_delete_rejects_paths_outside_root(root: Path, requested: str) -> None:
    (root / "escape").symlink_to("/etc")
    with pytest.raises(HTTPException) as error:
        await disk_usage.delete_path(requested)
    assert error.value.status_code == 400
    assert (root / "sub" / "deep" / "nested.bin").exists()


@pytest.mark.asyncio
async def test_delete_refuses_protected_path(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(disk_usage, "is_protected_target", lambda path: path == root / "tiny.txt")
    with pytest.raises(HTTPException) as error:
        await disk_usage.delete_path("tiny.txt")
    assert error.value.status_code == 400
    assert (root / "tiny.txt").exists()


@pytest.mark.parametrize(
    "output, expected",
    [
        (DISKTEST_OUTPUT, (19.7, 86.7, "abc123")),
        ("The generated --seed is: xyz\n", (None, None, "xyz")),
        ("", (None, None, None)),
    ],
)
def test_parse_disktest_speed(output: str, expected: Tuple[Optional[float], Optional[float], Optional[str]]) -> None:
    assert disk_usage.parse_disktest_speed(output) == expected


# Needs 500 MiB of free space in tmp_path, may fail on a small CI tmpfs.
@pytest.mark.asyncio
@pytest.mark.parametrize("exit_code", [0, 3])
async def test_speed_test_runs_disktest_and_cleans_up(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, exit_code: int
) -> None:
    binary = tmp_path / "bin" / "disktest"
    binary.parent.mkdir()
    binary.write_text(f"#!/bin/sh\ncat <<'EOF'\n{DISKTEST_OUTPUT}EOF\nexit {exit_code}\n", encoding="utf-8")
    binary.chmod(0o755)
    monkeypatch.setenv("PATH", f"{binary.parent}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setattr(tempfile, "tempdir", str(tmp_path))
    result = await disk_usage.run_single_speed_test(1024 * 1024)
    assert result.success is (exit_code == 0)
    if result.success:
        assert (result.write_speed_mbps, result.read_speed_mbps, result.seed) == (19.7, 86.7, "abc123")
    else:
        assert f"return code {exit_code}" in str(result.error)
    assert not list(tmp_path.glob("disktest_*"))


@pytest.mark.asyncio
async def test_speed_test_requires_disktest_binary(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _binary: None)
    with pytest.raises(HTTPException) as error:
        await disk_usage.run_single_speed_test(1024 * 1024)
    assert error.value.status_code == 503
