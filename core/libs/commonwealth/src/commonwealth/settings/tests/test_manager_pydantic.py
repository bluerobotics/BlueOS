import multiprocessing as mp
import os
import pathlib
import stat
import tempfile
import threading
from multiprocessing.synchronize import Barrier
from typing import Any, Dict, Optional
from unittest.mock import patch

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


def _multiprocess_save_worker(
    file_path: str,
    barrier: Barrier,
    queue: "mp.Queue[tuple[str, Optional[str]]]",
) -> None:
    settings = SettingsV2()
    path = pathlib.Path(file_path)
    try:
        barrier.wait(timeout=30)
        for _ in range(100):
            settings.save(path)
        queue.put(("ok", None))
    except Exception as error:  # noqa: BLE001 - collect to assert on the main process
        queue.put(("err", f"{type(error).__name__}: {error}"))


def test_basic_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v1 save
    settings_manager_v1 = PydanticManager("ManagerTest", SettingsV1, config_path)
    settings_manager_v1.settings.version_1_variable = 2022
    settings_manager_v1.save()

    assert settings_manager_v1.settings.version_1_variable == 2022

    # Test v1 load
    settings_manager_v1 = PydanticManager("ManagerTest", SettingsV1, config_path)

    assert settings_manager_v1.settings.version_1_variable == 2022

    # Test v2 load/save with migration from v1
    settings_manager_v2 = PydanticManager("ManagerTest", SettingsV2, config_path)

    assert settings_manager_v2.settings.version_1_variable == 2022
    assert settings_manager_v2.settings.version_2_variable == 66

    settings_manager_v2.settings.version_2_variable = 123
    settings_manager_v2.save()

    settings_manager_v2 = PydanticManager("ManagerTest", SettingsV2, config_path)

    assert settings_manager_v2.settings.version_1_variable == 2022
    assert settings_manager_v2.settings.version_2_variable == 123

    # Test v3 load/save with migration from v2
    settings_manager_v3 = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager_v3.settings.version_1_variable == 2022
    assert settings_manager_v3.settings.version_2_variable == 123
    assert settings_manager_v3.settings.version_3_variable == 99

    settings_manager_v3.settings.version_3_variable = 222
    settings_manager_v3.save()

    settings_manager_v3 = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager_v3.settings.version_1_variable == 2022
    assert settings_manager_v3.settings.version_2_variable == 123
    assert settings_manager_v3.settings.version_3_variable == 222

    # Test v12 load/save with migration from v3
    settings_manager_v12 = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager_v12.settings.version_1_variable == 2022
    assert settings_manager_v12.settings.version_2_variable == 123
    assert settings_manager_v12.settings.version_3_variable == 222
    assert settings_manager_v12.settings.version_12_variable == 1992

    settings_manager_v12.settings.version_12_variable = 14
    settings_manager_v12.save()

    settings_manager_v12 = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager_v12.settings.version_1_variable == 2022
    assert settings_manager_v12.settings.version_2_variable == 123
    assert settings_manager_v12.settings.version_3_variable == 222
    assert settings_manager_v12.settings.version_12_variable == 14

    assert len(os.listdir(config_path.joinpath("managertest"))) == 4


def test_fallback_settings_save_load() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    # Test v12 with downgrade to v3
    settings_manager_v12 = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager_v12.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager_v12.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager_v12.settings.version_3_variable == SettingsV3().version_3_variable
    assert settings_manager_v12.settings.version_12_variable == SettingsV12().version_12_variable

    settings_manager_v12.settings.version_1_variable = 1
    settings_manager_v12.settings.version_2_variable = 2
    settings_manager_v12.settings.version_3_variable = 3
    settings_manager_v12.settings.version_12_variable = 12
    settings_manager_v12.save()

    settings_manager_v3 = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager_v3.settings.version_1_variable == SettingsV1().version_1_variable
    assert settings_manager_v3.settings.version_2_variable == SettingsV2().version_2_variable
    assert settings_manager_v3.settings.version_3_variable == SettingsV3().version_3_variable

    settings_manager_v3.settings.version_1_variable = 10
    settings_manager_v3.settings.version_2_variable = 20
    settings_manager_v3.settings.version_3_variable = 30
    settings_manager_v3.save()

    # Check if v3 loads previous v3 configuration
    settings_manager_v3 = PydanticManager("ManagerTest", SettingsV3, config_path)

    assert settings_manager_v3.settings.version_1_variable == 10
    assert settings_manager_v3.settings.version_2_variable == 20
    assert settings_manager_v3.settings.version_3_variable == 30

    # Check if v12 loads previous v12 configuration without v3 migration
    settings_manager_v12 = PydanticManager("ManagerTest", SettingsV12, config_path)

    assert settings_manager_v12.settings.version_1_variable == 1
    assert settings_manager_v12.settings.version_2_variable == 2
    assert settings_manager_v12.settings.version_3_variable == 3
    assert settings_manager_v12.settings.version_12_variable == 12


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


def test_concurrent_saves_preserve_all_updates() -> None:
    # Regression test for https://github.com/bluerobotics/BlueOS/issues/3998 two requests mutating and saving
    # the same settings object at once must not crash on the temporary file and must both end up persisted.
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)

    errors: list[Exception] = []
    start = threading.Barrier(2)

    def mutate_and_save(variable: str, value: int) -> None:
        try:
            start.wait()
            for _ in range(100):
                setattr(settings_manager.settings, variable, value)
                settings_manager.save()
        except Exception as error:  # noqa: BLE001 - collect to assert on the main thread
            errors.append(error)

    threads = [
        threading.Thread(target=mutate_and_save, args=("version_1_variable", 111)),
        threading.Thread(target=mutate_and_save, args=("version_2_variable", 222)),
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert not errors, f"Concurrent saves raised: {errors}"

    # Both updates must survive, and only the versioned settings file should remain (no leftover temp files).
    reloaded = PydanticManager("ManagerTest", SettingsV2, config_path)
    assert reloaded.settings.version_1_variable == 111
    assert reloaded.settings.version_2_variable == 222
    assert os.listdir(config_path.joinpath("managertest")) == ["settings-2.json"]


def test_concurrent_load_and_save_do_not_crash() -> None:
    # Regression test for https://github.com/bluerobotics/BlueOS/issues/4106 load() clearing *.tmp
    # while save() is writing must not raise FileNotFoundError on replace.
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)

    settings_manager = PydanticManager("ManagerTest", SettingsV2, config_path)
    settings_manager.settings.version_1_variable = 1
    settings_manager.save()

    errors: list[Exception] = []
    stop = threading.Event()

    def save_loop() -> None:
        try:
            for i in range(200):
                settings_manager.settings.version_1_variable = i
                settings_manager.save()
        except Exception as error:  # noqa: BLE001 - collect to assert on the main thread
            errors.append(error)

    def load_loop() -> None:
        try:
            while not stop.is_set():
                settings_manager.load()
        except Exception as error:  # noqa: BLE001 - collect to assert on the main thread
            errors.append(error)

    save_thread = threading.Thread(target=save_loop)
    load_thread = threading.Thread(target=load_loop)
    save_thread.start()
    load_thread.start()
    save_thread.join(timeout=30)
    stop.set()
    load_thread.join(timeout=30)

    assert not save_thread.is_alive(), "save thread did not finish"
    assert not load_thread.is_alive(), "load thread did not finish"
    assert not errors, f"Concurrent load and save raised: {errors}"
    assert os.listdir(config_path.joinpath("managertest")) == ["settings-2.json"]


def test_multiprocess_saves_do_not_collide_on_temp_file() -> None:
    # Regression for pytest-xdist workers sharing ~/.config/<service>/settings-N.tmp during collection.
    temporary_folder = tempfile.mkdtemp()
    target = pathlib.Path(temporary_folder) / "settings-2.json"
    workers = 8
    barrier: Barrier = mp.Barrier(workers)
    queue: "mp.Queue[tuple[str, Optional[str]]]" = mp.Queue()

    processes = [
        mp.Process(target=_multiprocess_save_worker, args=(str(target), barrier, queue)) for _ in range(workers)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=60)
        assert not process.is_alive(), f"process {process.pid} did not finish"

    results = [queue.get(timeout=5) for _ in processes]
    errors = [result for result in results if result[0] == "err"]
    assert not errors, f"Multiprocess saves raised: {errors}"
    assert target.exists()
    assert os.listdir(temporary_folder) == ["settings-2.json"]


def test_clear_temp_files_removes_legacy_keeps_unique() -> None:
    temporary_folder = tempfile.mkdtemp()
    config_path = pathlib.Path(temporary_folder)
    settings_folder = config_path / "managertest"
    settings_folder.mkdir()
    SettingsV2().save(settings_folder / "settings-2.json")

    # Match mkstemp's 8-character random segment used by PydanticSettings.save.
    unique = settings_folder / "settings-2.abcdefgh.tmp"
    unique.write_text("in-progress", encoding="utf-8")
    legacy = settings_folder / "settings-2.tmp"
    legacy.write_text("legacy", encoding="utf-8")

    PydanticManager("ManagerTest", SettingsV2, config_path)

    names = set(os.listdir(settings_folder))
    assert unique.name in names
    assert legacy.name not in names
    assert "settings-2.json" in names


def test_save_temp_random_segment_is_at_most_10_chars() -> None:
    temporary_folder = tempfile.mkdtemp()
    file_path = pathlib.Path(temporary_folder) / "settings-2.json"
    created: list[str] = []
    real_mkstemp = tempfile.mkstemp

    def tracking_mkstemp(*args: Any, **kwargs: Any) -> tuple[int, str]:
        fd, name = real_mkstemp(*args, **kwargs)
        created.append(pathlib.Path(name).name)
        return fd, name

    with patch("tempfile.mkstemp", tracking_mkstemp):
        SettingsV2().save(file_path)

    assert len(created) == 1
    name = created[0]
    assert name.startswith("settings-2.")
    assert name.endswith(".tmp")
    random_segment = name[len("settings-2.") : -len(".tmp")]
    assert 1 <= len(random_segment) <= 10
    assert os.listdir(temporary_folder) == ["settings-2.json"]


def test_save_preserves_settings_file_mode_0644() -> None:
    temporary_folder = tempfile.mkdtemp()
    file_path = pathlib.Path(temporary_folder) / "settings-2.json"
    file_path.write_text("{}", encoding="utf-8")
    os.chmod(file_path, 0o644)
    assert stat.S_IMODE(file_path.stat().st_mode) == 0o644

    SettingsV2().save(file_path)

    assert stat.S_IMODE(file_path.stat().st_mode) == 0o644
    assert os.listdir(temporary_folder) == ["settings-2.json"]


def test_save_creates_settings_file_with_mode_0644() -> None:
    temporary_folder = tempfile.mkdtemp()
    file_path = pathlib.Path(temporary_folder) / "settings-2.json"

    SettingsV2().save(file_path)

    assert file_path.exists()
    assert stat.S_IMODE(file_path.stat().st_mode) == 0o644
