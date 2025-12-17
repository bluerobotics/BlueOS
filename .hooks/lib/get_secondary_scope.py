#!/usr/bin/env python3

from __future__ import annotations

import argparse
import pathlib
import sys
from typing import Iterable, List, Sequence


class TomlLoadError(RuntimeError):
    """Raised when the secondary-scope pyproject cannot be read."""


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Emit newline separated paths that belong to the secondary scope."
    )
    parser.add_argument("--core-dir", required=True, type=pathlib.Path)
    parser.add_argument("--pyproject", required=True, type=pathlib.Path)
    parser.add_argument(
        "--prefix",
        default="services/",
        help="Only include members that start with this relative path prefix.",
    )
    return parser.parse_args(argv)


def load_toml(pyproject: pathlib.Path) -> dict:
    try:
        import tomllib  # type: ignore[attr-defined]
    except ModuleNotFoundError:
        try:
            import tomli as tomllib  # type: ignore[assignment]
        except ModuleNotFoundError:
            raise TomlLoadError(
                "tomllib/tomli not available; install Python 3.11+ or `tomli`."
            )

    try:
        return tomllib.loads(pyproject.read_text())
    except Exception as exc:
        raise TomlLoadError(
            f"failed to parse {pyproject.as_posix()}: {exc}"
        ) from exc


def iter_scope_members(document: dict) -> Iterable[str]:
    tool = document.get("tool", {})
    uv = tool.get("uv", {})
    workspace = uv.get("workspace", {})
    members: List[str] = workspace.get("members", [])
    return members


def main(argv: Sequence[str]) -> int:
    args = parse_args(argv)
    core_dir = args.core_dir.resolve()
    pyproject = args.pyproject.resolve()
    prefix = args.prefix

    if not pyproject.exists():
        print(
            f"Error: {pyproject.as_posix()} does not exist; cannot load secondary scope.",
            file=sys.stderr,
        )
        return 1

    try:
        document = load_toml(pyproject)
    except TomlLoadError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    empty_scope = True
    for member in iter_scope_members(document):
        candidate = (pyproject.parent / member).resolve()
        try:
            rel = candidate.relative_to(core_dir)
        except ValueError:
            continue
        rel_posix = rel.as_posix()
        if rel_posix.startswith(prefix):
            print(rel_posix)
            empty_scope = False

    if empty_scope:
        print(
            f"Warning: secondary environment is empty (no '{prefix}' members in "
            f"{pyproject.as_posix()}).",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
