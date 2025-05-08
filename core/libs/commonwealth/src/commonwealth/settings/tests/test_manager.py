import os
import pathlib
import tempfile
from typing import Any, Dict

import pykson  # type: ignore

from .. import manager, settings


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    version_1_variable = pykson.IntegerField(default_value=42)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
        data["version_1_variable"] = self.version_1_variable


class SettingsV2(SettingsV1):
    VERSION = 2
    version_2_variable = pykson.IntegerField(default_value=66)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV2.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.VERSION:
            return

        if data["VERSION"] < SettingsV2.VERSION:
            SettingsV1().migrate(data)

        data["VERSION"] = SettingsV2.VERSION
        data["version_2_variable"] = self.version_2_variable


class SettingsV3(SettingsV2):
    VERSION = 3
    version_3_variable = pykson.IntegerField(default_value=99)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV3.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV3.VERSION:
            return

        if data["VERSION"] < SettingsV3.VERSION:
            SettingsV2().migrate(data)

        data["VERSION"] = SettingsV3.VERSION
        data["version_3_variable"] = self.version_3_variable


class SettingsV12(SettingsV3):
    VERSION = 12
    version_12_variable = pykson.IntegerField(default_value=1992)

    def __init__(self, *args: str, **kwargs: int) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV12.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV12.VERSION:
            return

        if data["VERSION"] < SettingsV12.VERSION:
            SettingsV3().migrate(data)

        data["VERSION"] = SettingsV12.VERSION
        data["version_12_variable"] = self.version_12_variable


def test_basic_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v1 save
    settings_manager = manager.Manager("ManagerTest", SettingsV1, config_path)
    settings_manager.settings.version_1_variable = 2022
    settings_manager.save()

    assert settings_manager.settings.version_1_variable == 2022

    # Test v1 load
    settings_manager = manager.Manager("ManagerTest", SettingsV1, config_path)

    assert settings_manager.settings.version_1_variable == 2022

    # Test v2 load/save with migration from v1
    settings_manager = manager.Manager("ManagerTest", SettingsV2, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 66

    settings_manager.settings.version_2_variable = 123
    settings_manager.save()

    settings_manager = manager.Manager("ManagerTest", SettingsV2, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123

    # Test v3 load/save with migration from v2
    settings_manager = manager.Manager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 99

    settings_manager.settings.version_3_variable = 222
    settings_manager.save()

    settings_manager = manager.Manager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222

    # Test v12 load/save with migration from v3
    settings_manager = manager.Manager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222
    assert settings_manager.settings.version_12_variable == 1992

    settings_manager.settings.version_12_variable = 14
    settings_manager.save()

    settings_manager = manager.Manager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 2022
    assert settings_manager.settings.version_2_variable == 123
    assert settings_manager.settings.version_3_variable == 222
    assert settings_manager.settings.version_12_variable == 14

    assert len(os.listdir(config_path.joinpath("managertest"))) == 4


def test_fallback_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v12 with downgrade to v3
    settings_manager = manager.Manager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager.settings.version_3_variable == SettingsV3().version_3_variable
    assert settings_manager.settings.version_12_variable == SettingsV12().version_12_variable

    settings_manager.settings.version_1_variable = 1
    settings_manager.settings.version_2_variable = 2
    settings_manager.settings.version_3_variable = 3
    settings_manager.settings.version_12_variable = 12
    settings_manager.save()

    settings_manager = manager.Manager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager.settings.version_3_variable == SettingsV3().version_3_variable

    settings_manager.settings.version_1_variable = 10
    settings_manager.settings.version_2_variable = 20
    settings_manager.settings.version_3_variable = 30
    settings_manager.save()

    # Check if v3 loads previous v3 configuration
    settings_manager = manager.Manager("ManagerTest", SettingsV3, config_path)

    assert settings_manager.settings.version_1_variable == 10
    assert settings_manager.settings.version_2_variable == 20
    assert settings_manager.settings.version_3_variable == 30

    # Check if v12 loads previous v12 configuration without v3 migration
    settings_manager = manager.Manager("ManagerTest", SettingsV12, config_path)

    assert settings_manager.settings.version_1_variable == 1
    assert settings_manager.settings.version_2_variable == 2
    assert settings_manager.settings.version_3_variable == 3
    assert settings_manager.settings.version_12_variable == 12
