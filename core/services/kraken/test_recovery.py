import json
from types import SimpleNamespace
from typing import Any, Dict, List, Optional
from unittest import mock

import pytest
from commonwealth.settings.managers.pykson_manager import PyksonManager

from extension.extension import (  # type: ignore[attr-defined]
    TEMP_EXTENSION_TAG_PREFIX,
    Extension,
    ExtensionSettings,
)
from harbor import ContainerManager
from harbor.exceptions import ContainerNotFound
from kraken import Kraken
from manifest import ManifestManager
from recovery import LABEL_IDENTIFIER, LABEL_NAME, LABEL_PERMISSIONS
from recovery import TEMP_EXTENSION_TAG_PREFIX as RECOVERY_TEMP_PREFIX
from recovery import (
    keep_one_enabled_per_identifier,
    permissions_from_inspect,
    recovered_extension_from_inspect,
    split_image_name,
)

pytestmark = pytest.mark.asyncio

MAJOR_TOM = "public.ecr.aws/blueos/bcloud-agent"


def inspect_of(
    image: str,
    labels: Optional[Dict[str, str]] = None,
    running: bool = True,
    created: str = "2026-01-01T00:00:00Z",
    **config: Any,
) -> Dict[str, Any]:
    docker, tag = split_image_name(image) or ("", "")
    name = "extension-" + "".join(char for char in f"{docker}{tag}" if char.isalnum())
    return {
        "Name": f"/{name}",
        "Created": created,
        "State": {"Running": running},
        "Config": {"Image": image, "Labels": labels or {}, **config},
        "HostConfig": {},
    }


def entry_of(identifier: str, docker: str, tag: str = "1.0", permissions: Any = None) -> Any:
    return SimpleNamespace(
        identifier=identifier,
        name=identifier,
        docker=docker,
        versions={tag: SimpleNamespace(permissions=permissions)},
    )


def catalog_of(*entries: Any) -> Dict[str, Any]:
    return {entry.docker: entry for entry in entries}


def stored_extensions() -> List[ExtensionSettings]:
    stored = PyksonManager.load_from_file(Extension._manager.settings_type, Extension._manager.settings_file_path())
    return list(stored.extensions)


@pytest.fixture(autouse=True)
def clean_settings() -> None:
    Extension._settings.extensions = []
    Extension._manager.save()


@pytest.fixture(name="kraken")
def kraken_fixture() -> Kraken:
    return Kraken()


def test_split_image_name() -> None:
    assert split_image_name("bluerobotics/cockpit:v1.18.2") == ("bluerobotics/cockpit", "v1.18.2")
    assert split_image_name(f"{MAJOR_TOM}:2026-02-11") == (MAJOR_TOM, "2026-02-11")
    assert split_image_name("localhost:5000/foo/bar:tag") == ("localhost:5000/foo/bar", "tag")
    assert split_image_name("sha256:abc") is None
    assert split_image_name("") is None


def test_settings_share_one_manager() -> None:
    assert Extension._manager is ManifestManager._manager


def test_recover_from_labels() -> None:
    inspect = inspect_of(
        "bluerobotics/cockpit:v1.18.2",
        {
            LABEL_IDENTIFIER: "bluerobotics.cockpit",
            LABEL_NAME: "Cockpit",
            LABEL_PERMISSIONS: '{"ExposedPorts":{"8000/tcp":{}}}',
        },
    )
    recovered = recovered_extension_from_inspect(inspect)
    assert recovered is not None
    assert recovered["identifier"] == "bluerobotics.cockpit"
    assert recovered["name"] == "Cockpit"
    assert recovered["docker"] == "bluerobotics/cockpit"
    assert recovered["tag"] == "v1.18.2"
    assert recovered["enabled"] is True
    assert recovered["permissions"] == '{"ExposedPorts":{"8000/tcp":{}}}'


def test_unlabeled_identifier_comes_from_the_catalog_or_the_docker_name() -> None:
    inspect = inspect_of("williangalvani/blueos-dashcam:1.0")
    guessed = recovered_extension_from_inspect(inspect)
    assert guessed and guessed["identifier"] == "williangalvani.blueos-dashcam"

    known = recovered_extension_from_inspect(
        inspect, catalog_of(entry_of("williangalvani.dashcam", "williangalvani/blueos-dashcam"))
    )
    assert known and known["identifier"] == "williangalvani.dashcam"


def test_major_tom_mapping_wins_over_the_catalog() -> None:
    inspect = inspect_of(f"{MAJOR_TOM}:2026-02-11")
    for catalog in (None, catalog_of(entry_of("someone.else", MAJOR_TOM))):
        recovered = recovered_extension_from_inspect(inspect, catalog)
        assert recovered and recovered["identifier"] == "blueos.major_tom"
        assert recovered["name"] == "major_tom"


def test_skips_temporary_uploads_and_mismatched_names() -> None:
    assert RECOVERY_TEMP_PREFIX == TEMP_EXTENSION_TAG_PREFIX
    assert recovered_extension_from_inspect(inspect_of(f"foo/bar:{TEMP_EXTENSION_TAG_PREFIX}1")) is None

    mismatched = inspect_of("bluerobotics/cockpit:v1.18.2")
    mismatched["Name"] = "/extension-someoneelse"
    assert recovered_extension_from_inspect(mismatched) is None


def test_permissions_rebuilt_from_inspect_keep_what_the_extension_asked_for() -> None:
    inspect = inspect_of("foo/bar:1.0", Env=["FOO=bar", "PATH=/bin", "MAV_SYSTEM_ID=1"], Cmd=["run"])
    inspect["ImageConfig"] = {"Env": ["PATH=/bin"], "Cmd": ["sh"]}
    inspect["HostConfig"] = {
        "Binds": ["/a:/b"],
        "NetworkMode": "default",
        "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0},
        "ShmSize": 67108864,
        "Privileged": False,
    }
    assert json.loads(permissions_from_inspect(inspect)) == {
        "Env": ["FOO=bar"],
        "Cmd": ["run"],
        "HostConfig": {"Binds": ["/a:/b"], "RestartPolicy": {"Name": "unless-stopped", "MaximumRetryCount": 0}},
    }


def test_catalog_permissions_are_preferred_over_the_inspect() -> None:
    catalog = catalog_of(entry_of("foo.bar", "foo/bar", "1.0", {"HostConfig": {"NetworkMode": "host"}}))
    recovered = recovered_extension_from_inspect(inspect_of("foo/bar:1.0", Env=["X=1"]), catalog)
    assert recovered and recovered["permissions"] == '{"HostConfig": {"NetworkMode": "host"}}'


def test_only_one_tag_per_identifier_stays_enabled() -> None:
    def pair(tag: str, running: bool, created: str) -> Any:
        inspect = inspect_of(f"foo/bar:{tag}", running=running, created=created)
        return recovered_extension_from_inspect(inspect), inspect

    result = keep_one_enabled_per_identifier(
        [pair("old", False, "2026-03-01"), pair("running", True, "2026-01-01"), pair("new", False, "2026-02-01")]
    )
    assert {ext.tag: ext.enabled for ext in result} == {"old": False, "running": True, "new": False}


async def test_recovery_is_a_noop_when_settings_are_not_empty(kraken: Kraken) -> None:
    Extension._settings.extensions = [ExtensionSettings(identifier="a.b", docker="a/b", tag="1", enabled=True)]
    inspect = mock.AsyncMock(return_value=[inspect_of("foo/bar:1.0")])
    with mock.patch.object(ContainerManager, "inspect_extension_containers", inspect):
        await kraken.recover_lost_extensions()
    inspect.assert_not_awaited()
    assert [ext.identifier for ext in Extension._settings.extensions] == ["a.b"]


async def test_recovery_survives_docker_errors_and_unrecoverable_containers(kraken: Kraken) -> None:
    for outcome in (RuntimeError("docker is slow"), [], [inspect_of(f"foo/bar:{TEMP_EXTENSION_TAG_PREFIX}1")]):
        patch: Dict[str, Any] = (
            {"side_effect": outcome} if isinstance(outcome, Exception) else {"return_value": outcome}
        )
        with mock.patch.object(ContainerManager, "inspect_extension_containers", mock.AsyncMock(**patch)):
            await kraken.recover_lost_extensions()
        assert not Extension._settings.extensions


async def test_recovery_offline_guesses_identifiers_and_reconciliation_fixes_them(kraken: Kraken) -> None:
    containers = [inspect_of("williangalvani/blueos-dashcam:1.0"), inspect_of(f"{MAJOR_TOM}:2026-02-11")]
    with (
        mock.patch.object(ContainerManager, "inspect_extension_containers", mock.AsyncMock(return_value=containers)),
        mock.patch.object(kraken.manifest, "fetch_consolidated", mock.AsyncMock(side_effect=OSError("offline"))),
    ):
        await kraken.recover_lost_extensions()
        assert {ext.identifier for ext in stored_extensions()} == {
            "williangalvani.blueos-dashcam",
            "blueos.major_tom",
        }

        await kraken.reconcile_recovered_identifiers()
        assert "williangalvani.blueos-dashcam" in {ext.identifier for ext in Extension._settings.extensions}

    online = mock.AsyncMock(
        return_value=[
            SimpleNamespace(identifier="williangalvani.dashcam", name="Dashcam", docker="williangalvani/blueos-dashcam")
        ]
    )
    with mock.patch.object(kraken.manifest, "fetch_consolidated", online):
        await kraken.reconcile_recovered_identifiers()
    assert {ext.identifier for ext in stored_extensions()} == {"williangalvani.dashcam", "blueos.major_tom"}


async def test_recovered_list_survives_manifest_edits(kraken: Kraken) -> None:
    containers = [inspect_of("foo/bar:1.0", {LABEL_IDENTIFIER: "foo.bar"})]
    with (
        mock.patch.object(ContainerManager, "inspect_extension_containers", mock.AsyncMock(return_value=containers)),
        mock.patch.object(kraken.manifest, "fetch_consolidated", mock.AsyncMock(return_value=[])),
    ):
        await kraken.recover_lost_extensions()

    kraken.manifest._set_enabled("bluerobotics-production", False)

    assert [ext.identifier for ext in stored_extensions()] == ["foo.bar"]


async def test_cleaner_keeps_containers_while_settings_are_empty(kraken: Kraken) -> None:
    container = SimpleNamespace(name="/extension-foobar10")
    remove = mock.AsyncMock()
    with (
        mock.patch.object(ContainerManager, "get_running_containers", mock.AsyncMock(return_value=[container])),
        mock.patch.object(Extension, "remove", remove),
    ):
        await kraken.kill_dangling_containers()
        remove.assert_not_awaited()

        Extension._settings.extensions = [ExtensionSettings(identifier="a.b", docker="a/b", tag="1", enabled=True)]
        await kraken.kill_dangling_containers()
    remove.assert_awaited_once_with("extension-foobar10", False)


async def test_uninstall_keeps_the_entry_when_the_container_cannot_be_removed() -> None:
    ext = ExtensionSettings(
        identifier="a.b", name="b", docker="a/b", tag="1", permissions="{}", user_permissions="", enabled=True
    )
    Extension._settings.extensions = [ext]
    extension = await Extension.from_settings("a.b", "1")

    with mock.patch.object(Extension, "remove", mock.AsyncMock(side_effect=RuntimeError("docker is down"))):
        await extension.uninstall()  # type: ignore
    assert len(Extension._settings.extensions) == 1

    with mock.patch.object(Extension, "remove", mock.AsyncMock()):
        await extension.uninstall()  # type: ignore
    assert not Extension._settings.extensions

    Extension._settings.extensions = [ext]
    with (
        mock.patch.object(Extension, "remove", mock.AsyncMock(side_effect=ContainerNotFound("gone"))),
        mock.patch("extension.extension.DockerCtx"),
    ):
        await extension.uninstall()  # type: ignore
    assert not Extension._settings.extensions


async def test_recovery_stops_the_tags_it_leaves_disabled(kraken: Kraken) -> None:
    containers = [
        inspect_of("foo/bar:old", {LABEL_IDENTIFIER: "foo.bar"}, running=True, created="2026-01-01"),
        inspect_of("foo/bar:new", {LABEL_IDENTIFIER: "foo.bar"}, running=True, created="2026-02-01"),
    ]
    disable = mock.AsyncMock()
    with (
        mock.patch.object(ContainerManager, "inspect_extension_containers", mock.AsyncMock(return_value=containers)),
        mock.patch.object(kraken.manifest, "fetch_consolidated", mock.AsyncMock(return_value=[])),
        mock.patch.object(Extension, "disable", disable),
    ):
        await kraken.recover_lost_extensions()

    disable.assert_awaited_once()
    assert {ext.tag: ext.enabled for ext in stored_extensions()} == {"old": False, "new": True}


async def test_reconciliation_fixes_the_name_when_the_guessed_identifier_was_right(kraken: Kraken) -> None:
    Extension._settings.extensions = [
        ExtensionSettings(identifier="bluerobotics.cockpit", name="cockpit", docker="bluerobotics/cockpit", tag="1"),
        ExtensionSettings(identifier="a.b", name="B", docker="a/b", tag="1"),
    ]
    catalog = [
        SimpleNamespace(identifier="bluerobotics.cockpit", name="Cockpit", docker="bluerobotics/cockpit"),
        SimpleNamespace(identifier="x.y", name="Y", docker="a/b"),
    ]
    with mock.patch.object(kraken.manifest, "fetch_consolidated", mock.AsyncMock(return_value=catalog)):
        await kraken.reconcile_recovered_identifiers()

    assert {ext.identifier: ext.name for ext in stored_extensions()} == {
        "bluerobotics.cockpit": "Cockpit",
        "a.b": "B",
    }
