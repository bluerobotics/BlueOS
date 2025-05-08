import pathlib
import tempfile
from typing import Any, Dict, List

from pydantic import BaseModel

from ..bases.pydantic_base import PydanticSettings


class JsonExample(BaseModel):
    name: str = ""


class Animal(BaseModel):
    name: str = ""
    animal_type: str = ""
    parts: List[str] = []
    animal_json: List[JsonExample] = []


class SettingsV1(PydanticSettings):
    animal: Animal = Animal(
        name="bilica",
        animal_type="dog",
        parts=["finger", "eyes"],
        animal_json=[JsonExample.parse_obj({"name": "Json!"})],
    )
    first_variable: int = 42

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV1.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV1.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV1.STATIC_VERSION
        data["animal"] = self.animal
        data["first_variable"] = self.first_variable


class SettingsV1Expanded(SettingsV1):
    new_variable: int = 1992


class SettingsV2(PydanticSettings):
    first_variable: int = 66
    new_animal: Animal = Animal(
        name="bilica",
        animal_type="dog",
    )

    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV2.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV2.STATIC_VERSION:
            SettingsV1().migrate(data)

        data["VERSION"] = SettingsV2.STATIC_VERSION
        data["first_variable"] = self.first_variable

        # Update variable name
        data["new_animal"] = data["animal"]
        data.pop("animal")


class SettingsV3(SettingsV2):
    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV3.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV3.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV3.STATIC_VERSION


class SettingsV4(SettingsV3):
    def migrate(self, data: Dict[str, Any]) -> None:
        if data["VERSION"] == SettingsV4.STATIC_VERSION:
            return

        if data["VERSION"] < SettingsV4.STATIC_VERSION:
            super().migrate(data)

        data["VERSION"] = SettingsV4.STATIC_VERSION


def test_basic_settings_save_load() -> None:
    # Check basic access
    settings_v1 = SettingsV1()
    assert settings_v1.VERSION == 1
    assert settings_v1.first_variable == 42
    assert settings_v1.animal.name == "bilica"
    assert settings_v1.animal.animal_type == "dog"
    assert settings_v1.animal.parts == ["finger", "eyes"]
    assert settings_v1.animal.animal_json[0].name == "Json!"

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
    settings_v2.save(file_path)

    assert settings_v1.first_variable == settings_v2.first_variable
    assert settings_v1.animal.name == settings_v2.new_animal.name
    assert settings_v1.animal.animal_type == settings_v2.new_animal.animal_type

    settings_v3 = SettingsV3()
    settings_v3.load(file_path)
    settings_v3.save(file_path)

    settings_v4 = SettingsV4()
    settings_v4.load(file_path)
    settings_v4.save(file_path)

    assert settings_v2.first_variable == settings_v4.first_variable
    assert settings_v2.new_animal.name == settings_v4.new_animal.name
    assert settings_v2.new_animal.animal_type == settings_v4.new_animal.animal_type
    assert settings_v2.new_animal.parts[0] == settings_v4.new_animal.parts[0]
    assert settings_v2.new_animal.parts[1] == settings_v4.new_animal.parts[1]
    assert settings_v2.new_animal.animal_json[0].name == settings_v4.new_animal.animal_json[0].name


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
