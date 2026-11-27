import builtins
import pathlib
from typing import Any, Dict, List, Type

import pykson  # type: ignore
import pytest
from loguru import logger

from .. import settings, temp_files
from ..bases.pydantic_base import PydanticSettings
from ..managers.pydantic_manager import PydanticManager
from ..managers.pykson_manager import PyksonManager


class PyksonV1(settings.BaseSettings):
    VERSION = 1
    value = pykson.IntegerField(default_value=42)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        self.VERSION = PyksonV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        data["VERSION"] = PyksonV1.VERSION


class PyksonV2(PyksonV1):
    VERSION = 2

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        self.VERSION = PyksonV2.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        data["VERSION"] = PyksonV2.VERSION


class PyksonV2NoMigration(PyksonV1):
    VERSION = 2

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        self.VERSION = PyksonV2NoMigration.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        raise RuntimeError("Migration is not possible")


class PyksonBrokenInit(PyksonV1):
    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)
        raise RuntimeError("Broken settings class")


class PyksonWithSecret(PyksonV1):
    hotspot_password = pykson.StringField()


class PydanticV1(PydanticSettings):
    value: int = 42

    def migrate(self, data: Dict[str, Any]) -> None:
        data["VERSION"] = PydanticV1.STATIC_VERSION


class PydanticV2(PydanticV1):
    def migrate(self, data: Dict[str, Any]) -> None:
        data["VERSION"] = PydanticV2.STATIC_VERSION


class PydanticV2NoMigration(PydanticV1):
    def migrate(self, data: Dict[str, Any]) -> None:
        raise RuntimeError("Migration is not possible")


class PydanticWithSecretV1(PydanticV1):
    hotspot_password: str = ""


MANAGERS = [(PyksonManager, PyksonV1), (PydanticManager, PydanticV1)]
MANAGERS_V2 = [
    (PyksonManager, PyksonV1, PyksonV2),
    (PydanticManager, PydanticV1, PydanticV2),
]
MANAGERS_NO_MIGRATION = [(PyksonManager, PyksonV2NoMigration), (PydanticManager, PydanticV2NoMigration)]
INVALID_CONTENTS = [
    pytest.param(b'{"VERSION": 1, "value": 999, "broken": }', id="corrupt-json"),
    pytest.param(b"", id="zero-byte"),
    pytest.param(b'{"VERSION": 1, "value": "not a number"}', id="schema-invalid"),
]


@pytest.fixture(name="config_path")
def fixture_config_path(tmp_path: pathlib.Path) -> pathlib.Path:
    (tmp_path / "managertest").mkdir()
    return tmp_path


@pytest.fixture(name="logs")
def fixture_logs() -> Any:
    messages: List[str] = []
    handler_id = logger.add(lambda message: messages.append(str(message)), level="DEBUG")
    yield messages
    logger.remove(handler_id)


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
@pytest.mark.parametrize("content", INVALID_CONTENTS)
def test_invalid_file_is_renamed_aside(
    config_path: pathlib.Path,
    manager_type: Any,
    settings_type: Type[Any],
    content: bytes,
) -> None:
    folder = config_path / "managertest"
    (folder / "settings-1.json").write_bytes(content)

    manager = manager_type("ManagerTest", settings_type, config_path)

    assert manager.settings.value == 42
    aside = list(folder.glob("settings-1.json.invalid-*"))
    assert len(aside) == 1
    assert aside[0].read_bytes() == content
    assert (folder / "settings-1.json").exists()


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_second_boot_does_not_create_another_copy(
    config_path: pathlib.Path, manager_type: Any, settings_type: Type[Any]
) -> None:
    folder = config_path / "managertest"
    (folder / "settings-1.json").write_bytes(b"")

    manager_type("ManagerTest", settings_type, config_path)
    manager_type("ManagerTest", settings_type, config_path)

    assert len(list(folder.glob("*.invalid-*"))) == 1


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_identical_bad_file_is_not_copied_again(
    config_path: pathlib.Path, manager_type: Any, settings_type: Type[Any]
) -> None:
    folder = config_path / "managertest"
    for _ in range(3):
        (folder / "settings-1.json").write_bytes(b"{broken")
        manager_type("ManagerTest", settings_type, config_path)

    assert len(list(folder.glob("*.invalid-*"))) == 1


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_number_of_copies_is_bounded(config_path: pathlib.Path, manager_type: Any, settings_type: Type[Any]) -> None:
    folder = config_path / "managertest"
    for index in range(temp_files.MAX_INVALID_COPIES + 3):
        (folder / "settings-1.json").write_bytes(b"{broken %d" % index)
        manager_type("ManagerTest", settings_type, config_path)

    copies = sorted(folder.glob("*.invalid-*"))
    assert len(copies) == temp_files.MAX_INVALID_COPIES
    assert copies[0].read_bytes() == b"{broken 0"
    assert copies[-1].read_bytes() == b"{broken %d" % (temp_files.MAX_INVALID_COPIES + 2)


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_valid_file_is_not_renamed(config_path: pathlib.Path, manager_type: Any, settings_type: Type[Any]) -> None:
    folder = config_path / "managertest"
    manager_type("ManagerTest", settings_type, config_path).save()
    content = (folder / "settings-1.json").read_bytes()

    manager_type("ManagerTest", settings_type, config_path)

    assert not list(folder.glob("*.invalid-*"))
    assert (folder / "settings-1.json").read_bytes() == content


@pytest.mark.parametrize("manager_type,old_type,new_type", MANAGERS_V2)
def test_invalid_current_file_next_to_valid_older_one(
    config_path: pathlib.Path,
    manager_type: Any,
    old_type: Type[Any],
    new_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    old_manager = manager_type("ManagerTest", old_type, config_path)
    old_manager.settings.value = 7
    old_manager.save()
    old_content = (folder / "settings-1.json").read_bytes()
    (folder / "settings-2.json").write_bytes(b"{broken")

    manager = manager_type("ManagerTest", new_type, config_path)

    assert manager.settings.value == 7
    assert [path.name.rsplit("-", 1)[0] for path in folder.glob("*.invalid-*")] == ["settings-2.json.invalid"]
    assert next(folder.glob("*.invalid-*")).read_bytes() == b"{broken"
    assert (folder / "settings-1.json").read_bytes() == old_content


@pytest.mark.parametrize("manager_type,new_type", MANAGERS_NO_MIGRATION)
def test_migration_failure_is_renamed_like_a_parse_failure(
    config_path: pathlib.Path,
    manager_type: Any,
    new_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    content = b'{"VERSION": 1, "value": 7}'
    (folder / "settings-1.json").write_bytes(content)

    manager = manager_type("ManagerTest", new_type, config_path)

    assert manager.settings.value == 42
    aside = list(folder.glob("settings-1.json.invalid-*"))
    assert len(aside) == 1
    assert aside[0].read_bytes() == content


@pytest.mark.parametrize("manager_type,old_type", MANAGERS)
def test_future_version_file_is_kept_in_place(
    config_path: pathlib.Path, manager_type: Any, old_type: Type[Any]
) -> None:
    folder = config_path / "managertest"
    content = b'{"VERSION": 2, "value": 7}'
    (folder / "settings-2.json").write_bytes(content)

    manager = manager_type("ManagerTest", old_type, config_path)

    assert manager.settings.value == 42
    assert not list(folder.glob("*.invalid-*"))
    assert (folder / "settings-2.json").read_bytes() == content


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_failed_rename_keeps_the_original(
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    manager_type: Any,
    settings_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    content = b'{"VERSION": 1, "value": 7, "broken": }'
    (folder / "settings-1.json").write_bytes(content)

    def fail_rename(self: pathlib.Path, target: Any) -> None:
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(pathlib.Path, "rename", fail_rename)
    manager = manager_type("ManagerTest", settings_type, config_path)

    assert manager.settings.value == 42
    manager.settings.value = 7
    manager.save()
    assert (folder / "settings-1.json").read_bytes() == content


@pytest.mark.parametrize("manager_type,settings_type", MANAGERS)
def test_read_error_neither_renames_nor_overwrites_a_valid_file(
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    manager_type: Any,
    settings_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    manager_type("ManagerTest", settings_type, config_path).save()
    content = (folder / "settings-1.json").read_bytes()
    real_open = builtins.open

    def fail_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if str(file).endswith("settings-1.json"):
            raise OSError(24, "Too many open files")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_open)
    manager = manager_type("ManagerTest", settings_type, config_path)
    monkeypatch.undo()

    manager.settings.value = 7
    manager.save()

    assert not list(folder.glob("*.invalid-*"))
    assert (folder / "settings-1.json").read_bytes() == content


def test_broken_settings_class_does_not_rename_valid_files(
    config_path: pathlib.Path,
) -> None:
    folder = config_path / "managertest"
    PyksonManager("ManagerTest", PyksonV1, config_path).save()
    content = (folder / "settings-1.json").read_bytes()

    with pytest.raises(RuntimeError):
        PyksonManager("ManagerTest", PyksonBrokenInit, config_path)

    assert not list(folder.glob("*.invalid-*"))
    assert (folder / "settings-1.json").read_bytes() == content


@pytest.mark.parametrize(
    "manager_type,settings_type",
    [(PyksonManager, PyksonWithSecret), (PydanticManager, PydanticWithSecretV1)],
)
@pytest.mark.parametrize(
    "content",
    [
        b'{"hotspot_password": "s3cretPW"}',
        b'{"VERSION": 1, "hotspot_password": "s3cretPW", "value": "not a number"}',
        b'{"VERSION": 1, "hotspot_password": "s3cretPW", "broken": }',
    ],
)
def test_settings_values_are_not_logged(
    config_path: pathlib.Path,
    logs: List[str],
    manager_type: Any,
    settings_type: Type[Any],
    content: bytes,
) -> None:
    (config_path / "managertest" / "settings-1.json").write_bytes(content)

    manager_type("ManagerTest", settings_type, config_path)

    assert logs
    assert not any("s3cretPW" in message for message in logs)


@pytest.mark.parametrize("manager_type,old_type,new_type", MANAGERS_V2)
def test_unreadable_current_file_is_not_replaced_by_a_save_of_an_older_one(
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    manager_type: Any,
    old_type: Type[Any],
    new_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    old_manager = manager_type("ManagerTest", old_type, config_path)
    old_manager.save()
    new_manager = manager_type("ManagerTest", new_type, config_path)
    new_manager.settings.value = 7
    new_manager.save()
    content = (folder / "settings-2.json").read_bytes()
    real_open = builtins.open

    def fail_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        if str(file).endswith("settings-2.json"):
            raise OSError(5, "Input/output error")
        return real_open(file, *args, **kwargs)

    monkeypatch.setattr(builtins, "open", fail_open)
    manager = manager_type("ManagerTest", new_type, config_path)
    monkeypatch.undo()

    manager.save()
    assert (folder / "settings-2.json").read_bytes() == content


@pytest.mark.parametrize("manager_type,old_type,new_type", MANAGERS_V2)
def test_unmovable_invalid_current_file_is_not_replaced_by_a_save_of_an_older_one(
    config_path: pathlib.Path,
    monkeypatch: pytest.MonkeyPatch,
    manager_type: Any,
    old_type: Type[Any],
    new_type: Type[Any],
) -> None:
    folder = config_path / "managertest"
    manager_type("ManagerTest", old_type, config_path).save()
    content = b"{broken"
    (folder / "settings-2.json").write_bytes(content)

    def fail_rename(self: pathlib.Path, target: Any) -> None:
        raise OSError(30, "Read-only file system")

    monkeypatch.setattr(pathlib.Path, "rename", fail_rename)
    manager = manager_type("ManagerTest", new_type, config_path)
    monkeypatch.undo()

    manager.save()
    assert (folder / "settings-2.json").read_bytes() == content
