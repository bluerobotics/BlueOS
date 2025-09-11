import os
import pathlib
import tempfile
from typing import Any, Dict

from ..bases.pydantic_base import PydanticSettings
from ..managers.pydantic_manager import PydanticManager


class SettingsV1(PydanticSettings):
    version_1_variable: int = 42

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
        data["version_1_variable"] = self.version_1_variable


class SettingsV2(SettingsV1):
    version_2_variable: int = 66

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            SettingsV1().migrate(data)

        data["VERSION"] = SettingsV2.STATIC_VERSION
        data["version_2_variable"] = self.version_2_variable


class SettingsV3(SettingsV2):
    version_3_variable: int = 99

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV3.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV3.STATIC_VERSION:
            SettingsV2().migrate(data)

        data["VERSION"] = SettingsV3.STATIC_VERSION
        data["version_3_variable"] = self.version_3_variable


class SettingsV12(SettingsV3):
    version_12_variable: int = 1992

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV12.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV12.STATIC_VERSION:
            SettingsV3().migrate(data)

        data["VERSION"] = SettingsV12.STATIC_VERSION
        data["version_12_variable"] = self.version_12_variable


def test_basic_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v1 save
    settings_manager = PydanticManager("ManagerTest", SettingsV1, config_path)
    settings_manager.settings.version_1_variable = 2022
    settings_manager.save()

    assert settings_manager.settings.version_1_variable == 2022

    # Test v1 load
    settings_manager = PydanticManager("ManagerTest", SettingsV1, config_path)

    assert settings_manager.settings.version_1_variable == 2022

    # Test v2 load/save with migration from v1
    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 66

    settings_manager.settings.version_2_variable = 123
    settings_manager.save()

    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123

    # Test v3 load/save with migration from v2
    settings_manager = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 99

    settings_manager.settings.version_3_variable = 222
    settings_manager.save()

    settings_manager = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222

    # Test v12 load/save with migration from v3
    settings_manager = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222
    assert settings_manager.settings.version_12_variable == 1992

    settings_manager.settings.version_12_variable = 14
    settings_manager.save()

    settings_manager = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222
    assert settings_manager.settings.version_12_variable == 14

    assert len(os.listdir(config_path.joinpath("managertest"))) == 4


def test_fallback_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v12 with downgrade to v3
    settings_manager = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager.settings.version_3_variable == SettingsV3().version_3_variable
    assert settings_manager.settings.version_12_variable == SettingsV12().version_12_variable

    settings_manager.settings.version_1_variable = 1
    settings_manager.settings.version_2_variable = 2
    settings_manager.settings.version_3_variable = 3
    settings_manager.settings.version_12_variable = 12
    settings_manager.save()

    settings_manager = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager.settings.version_3_variable == SettingsV3().version_3_variable

    settings_manager.settings.version_1_variable = 10
    settings_manager.settings.version_2_variable = 20
    settings_manager.settings.version_3_variable = 30
    settings_manager.save()

    # Check if v3 loads previous v3 configuration
    settings_manager = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 10
    assert settings_manager.settings.version_2_variable == 20
    assert settings_manager.settings.version_3_variable == 30

    # Check if v12 loads previous v12 configuration without v3 migration
    settings_manager = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 1
    assert settings_manager.settings.version_2_variable == 2
    assert settings_manager.settings.version_3_variable == 3
    assert settings_manager.settings.version_12_variable == 12


def test_invalid_json_fallback_to_defaults_v1() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Create a settings file with invalid JSON
    settings_folder = config_path / "managertest"
    settings_folder.mkdir(parents=True, exist_ok=True)
    invalid_settings_file = settings_folder / "settings-1.json"
    with open(invalid_settings_file, "w", encoding="utf-8") as f:
        f.write('{"VERSION": 1, "version_1_variable": 999, "invalid_json": }')

    settings_manager = PydanticManager("ManagerTest", SettingsV1, config_path)

    # Verify that the manager falls back to default values
    assert settings_manager.settings.VERSION == 1
    assert settings_manager.settings.version_1_variable == 42

    # Verify that a v1 settings will be replaced
    settings_manager.save()
    assert len(os.listdir(settings_folder)) == 1


def test_invalid_json_fallback_to_defaults_v1_from_invalid_v2() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)
    settings_folder = config_path / "managertest"
    settings_folder.mkdir(parents=True, exist_ok=True)

    # Create a valid JSON from settings V1
    default_settings = SettingsV1()
    default_settings.version_1_variable = 369
    default_settings.save(settings_folder / "settings-1.json")

    # Create a invalid JSON from settings V2
    invalid_settings_file = settings_folder / "settings-2.json"
    with open(invalid_settings_file, "w", encoding="utf-8") as f:
        f.write('{"VERSION": 2, "version_2_variable": 999, "invalid_json": }')

    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)

    # Verify that the manager falls back to default values
    assert settings_manager.settings.VERSION == 2
    assert settings_manager.settings.version_1_variable == 369
    assert settings_manager.settings.version_2_variable == 66

    # Verify that a v2 settings will be replaced
    settings_manager.save()
    assert len(os.listdir(settings_folder)) == 2


def test_invalid_json_fallback_to_defaults_v2_from_invalid_v2_and_v1() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)
    settings_folder = config_path / "managertest"
    settings_folder.mkdir(parents=True, exist_ok=True)

    # Create a invalid JSON from settings V1
    invalid_settings_file = settings_folder / "settings-2.json"
    with open(invalid_settings_file, "w", encoding="utf-8") as f:
        f.write('{"VERSION": 1, "version_1_variable": 999, "invalid_json": }')

    # Create a invalid JSON from settings V2
    invalid_settings_file = settings_folder / "settings-2.json"
    with open(invalid_settings_file, "w", encoding="utf-8") as f:
        f.write('{"VERSION": 2, "version_2_variable": 999, "invalid_json": }')

    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)

    # Verify that the manager falls back to default values
    assert settings_manager.settings.VERSION == 2
    assert settings_manager.settings.version_1_variable == 42
    assert settings_manager.settings.version_2_variable == 66
