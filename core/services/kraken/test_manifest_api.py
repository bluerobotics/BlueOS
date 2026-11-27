# isort: skip_file
import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List
from unittest import mock

import pytest

_KRAKEN_DIR = str(Path(__file__).resolve().parent)
sys.path.insert(0, _KRAKEN_DIR)
# Root pytest also collects the other services, whose top-level `config` and
# `settings` modules would otherwise be the ones imported here.
_saved = {module_name: sys.modules.get(module_name) for module_name in ("config", "settings", "utils")}
for module_name in _saved:
    sys.modules.pop(module_name, None)

from fastapi import HTTPException  # noqa: E402
from fastapi.routing import APIRoute  # noqa: E402
from manifest.models import RepositoryEntry  # noqa: E402

try:
    import fastapi_versioning  # noqa: F401  # pylint: disable=unused-import
except ImportError:  # the root test environment does not carry the kraken service dependencies
    sys.modules["fastapi_versioning"] = mock.Mock(versioned_api_route=lambda *_: APIRoute)

# Loaded by path because importing the `api` package would start the whole service.
_spec = importlib.util.spec_from_file_location(
    "kraken_manifest_router_v2", Path(_KRAKEN_DIR) / "api/v2/routers/manifest.py"
)
manifest_api = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(manifest_api)  # type: ignore[union-attr]

for module_name, module in _saved.items():
    if module is not None:
        sys.modules[module_name] = module
    else:
        sys.modules.pop(module_name, None)

pytestmark = pytest.mark.asyncio

IDENTIFIER = "bluerobotics.some ext"


def make_entry() -> RepositoryEntry:
    version: Dict[str, Any] = {
        "type": "tool",
        "images": [],
        "authors": [],
        "filter_tags": [],
        "extra_links": {},
        "readme": "# Hello",
        "docs": "http://docs",
    }
    return RepositoryEntry(
        identifier=IDENTIFIER,
        name="Some ext",
        website="https://example.com",
        docker="bluerobotics/some-ext",
        description="desc",
        versions={"1.0.0": version, "1.1.0": {**version, "readme": "# Newer"}},
    )


@pytest.fixture(name="entries")
def fixture_entries() -> List[RepositoryEntry]:
    return [make_entry()]


@pytest.fixture(autouse=True)
def fixture_manager(entries: List[RepositoryEntry]) -> Any:
    with mock.patch.object(manifest_api.manifest_manager, "fetch_consolidated", mock.AsyncMock(return_value=entries)):
        yield


async def test_consolidated_keeps_readme_by_default() -> None:
    versions = (await manifest_api.fetch_consolidated())[0].versions
    assert versions["1.0.0"].readme == "# Hello"


async def test_consolidated_can_omit_readme_without_mutating_cache(entries: List[RepositoryEntry]) -> None:
    versions = (await manifest_api.fetch_consolidated(readme=False))[0].versions
    assert all(version.readme is None for version in versions.values())
    assert versions["1.0.0"].docs == "http://docs"
    assert entries[0].versions["1.0.0"].readme == "# Hello"
    assert await manifest_api.fetch_consolidated_readme(IDENTIFIER, "1.1.0") == "# Newer"


async def test_readme_of_selected_version() -> None:
    assert await manifest_api.fetch_consolidated_readme(IDENTIFIER, "1.0.0") == "# Hello"


@pytest.mark.parametrize("identifier,tag", [("unknown.ext", "1.0.0"), (IDENTIFIER, "9.9.9")])
async def test_readme_not_found(identifier: str, tag: str) -> None:
    with pytest.raises(HTTPException) as error:
        await manifest_api.fetch_consolidated_readme(identifier, tag)
    assert error.value.status_code == 404
