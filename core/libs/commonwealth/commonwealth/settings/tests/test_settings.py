import pathlib
import tempfile
from typing import Any, Dict

import pykson  # type: ignore

from .. import settings


class Animal(pykson.JsonObject):
    name: str = pykson.StringField()
    animal_type: str = pykson.StringField()

    def __init__(self, *args: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)


class SettingsV1(settings.BaseSettings):
    VERSION = 1
    animal = pykson.ObjectField(
        Animal,
        default_value=Animal(
            name="bilica",
            animal_type="dog",
        ),
    )
    first_variable = pykson.IntegerField(default_value=42)

    def __init__(self, *args: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV1.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.VERSION:
            return

        if data["VERSION"] < SettingsV1.VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.VERSION
        data["animal"] = self.animal
        data["first_variable"] = self.first_variable


class SettingsV1Expanded(SettingsV1):
    new_variable = pykson.IntegerField(default_value=1992)


class SettingsV2(settings.BaseSettings):
    VERSION = 2
    first_variable = pykson.IntegerField(default_value=66)
    new_animal = pykson.ObjectField(
        Animal,
        default_value=Animal(
            name="bilica",
            animal_type="dog",
        ),
    )

    def __init__(self, *args: str, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)

        self.VERSION = SettingsV2.VERSION

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.VERSION:
            return

        if data["VERSION"] < SettingsV2.VERSION:
            SettingsV1().migrate(data)

        data["VERSION"] = SettingsV2.VERSION
        data["first_variable"] = self.first_variable

        # Update variable name
        data["new_animal_name"] = data["animal"]
        data.pop("animal")


def test_basic_settings_save_load() -> None:
    # Check basic access
    settings_v1 = SettingsV1()
    assert settings_v1.VERSION == 1
    assert settings_v1.first_variable == 42

    # pylint: disable=consider-using-with
    temporary_file = tempfile.NamedTemporaryFile().name
    file_path = pathlib.Path(temporary_file)

    # Check basic save and load
    settings_v1.first_variable = 66
    settings_v1.save(file_path)

    settings_v1_new = SettingsV1()
    settings_v1_new.load(file_path)
    assert settings_v1.first_variable == settings_v1_new.first_variable

    # Check for reset
    settings_v1_new.reset()
    settings_v1.save(file_path)

    settings_v1_new = SettingsV1()
    settings_v1_new.load(file_path)
    assert settings_v1.first_variable == 66


def test_nested_settings_save_load() -> None:
    # Check basic access
    settings_v1 = SettingsV1()
    assert settings_v1.animal.name == SettingsV1().animal.name
    assert settings_v1.animal.animal_type == SettingsV1().animal.animal_type

    # pylint: disable=consider-using-with
    temporary_file = tempfile.NamedTemporaryFile()
    file_path = pathlib.Path(temporary_file.name)

    # Check basic save and load
    settings_v1.first_variable = 66
    settings_v1.animal.name = "pingu"
    settings_v1.animal.animal_type = "penguin"

    assert settings_v1.first_variable == 66
    assert settings_v1.animal.name == "pingu"
    assert settings_v1.animal.animal_type == "penguin"

    settings_v1.save(file_path)
    settings_v1_new = SettingsV1()
    settings_v1_new.load(file_path)

    assert settings_v1.first_variable == settings_v1_new.first_variable
    assert settings_v1.animal.name == settings_v1_new.animal.name
    assert settings_v1.animal.animal_type == settings_v1_new.animal.animal_type


def test_simple_migration_settings_save_load() -> None:
    settings_v1 = SettingsV1()

    # pylint: disable=consider-using-with
    temporary_file = tempfile.NamedTemporaryFile()
    file_path = pathlib.Path(temporary_file.name)

    settings_v1.first_variable = 66
    settings_v1.animal.name = "pingu"
    settings_v1.animal.animal_type = "penguin"

    settings_v1.save(file_path)
    settings_v1_new = SettingsV1()
    settings_v1_new.load(file_path)

    # Check if migration works
    settings_v2 = SettingsV2()
    settings_v2.load(file_path)

    assert settings_v1.first_variable == settings_v2.first_variable
    assert settings_v1.animal.name == settings_v2.new_animal_name.name
    assert settings_v1.animal.animal_type == settings_v2.new_animal_name.animal_type


def test_simple_settings_expanded_save_load() -> None:
    settings_v1 = SettingsV1()

    # pylint: disable=consider-using-with
    temporary_file = tempfile.NamedTemporaryFile()
    file_path = pathlib.Path(temporary_file.name)

    settings_v1.first_variable = 66
    settings_v1.animal.name = "pingu"
    settings_v1.animal.animal_type = "penguin"

    # Load expanded settings with older settings structure
    settings_v1.save(file_path)
    settings_v1_expanded = SettingsV1Expanded()
    settings_v1_expanded.load(file_path)

    assert settings_v1.first_variable == settings_v1_expanded.first_variable
    assert settings_v1.animal.name == settings_v1_expanded.animal.name
    assert settings_v1.animal.animal_type == settings_v1_expanded.animal.animal_type
    assert settings_v1_expanded.new_variable == 1992
