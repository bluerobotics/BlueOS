import json
from pathlib import Path
from typing import Any, Dict, Generator, List

from docker.errors import NotFound
from pyfakefs.fake_filesystem_unittest import TestCase

from bootstrap.bootstrap import Bootstrapper

SAMPLE_JSON = """{
    "core": {
        "tag": "master",
        "image": "bluerobotics/companion-core",
        "enabled": true,
        "webui": false,
        "network": "host",
        "binds": {
            "/dev/": {
                "bind": "/dev/",
                "mode": "rw"
            },
            "/var/run/wpa_supplicant/wlan0": {
                "bind": "/var/run/wpa_supplicant/wlan0",
                "mode": "rw"
            },
            "/tmp/wpa_playground": {
                "bind": "/tmp/wpa_playground",
                "mode": "rw"
            }
        },
        "privileged": true
    }
}"""


class FakeContainer:
    """Mocks a single Container from Docker-py"""

    def __init__(self, name: str) -> None:
        self.name: str = name
        self.client: Any

    def set_client(self, client: Any) -> None:
        self.client = client

    def remove(self) -> None:
        self.client.containers.remove(self.name)


class FakeContainers:
    """Mocks "Containers" class from docker-py"""

    def __init__(self, containers: List[FakeContainer]):
        self.containers: Dict[str, FakeContainer] = {container.name: container for container in containers}

    def get(self, container: str) -> FakeContainer:
        result = self.containers.get(container, None)
        if result is None:
            raise NotFound("Container not found")
        return result

    def remove(self, container: str) -> None:
        del self.containers[container]

    # suppress warnings as we need to keep the same signature
    # pylint: disable=unused-argument
    def run(self, image: str, name: str = "", **kargs: Dict[str, Any]) -> None:
        self.containers[name] = FakeContainer(name)

    def list(self) -> List[FakeContainer]:
        return list(self.containers.values())


# pylint: disable=too-few-public-methods
class FakeImages:
    @staticmethod
    def pull(_image: str) -> None:
        return


# pylint: disable=too-few-public-methods
class FakeClient:
    """Mocks a docker-py client for testing purposes"""

    def __init__(self) -> None:
        self.containers = FakeContainers([])
        self.images = FakeImages()

    def set_active_dockers(self, containers: List[FakeContainer]) -> None:
        for container in containers:
            container.set_client(self)
        self.containers = FakeContainers(containers)


# pylint: disable=too-few-public-methods
class FakeLowLevelAPI:

    progress_text: List[str] = [
        "Pretending we are pulling image {0}",
        "Almost there..",
        "Done!",
    ]

    def pull(self, image: str, stream: bool = True, decode: bool = True) -> Generator[Dict[str, Any], None, None]:
        if not stream or not decode:
            raise NotImplementedError
        for line in self.progress_text:
            yield {"status": line.format(image), "progressDetail": {}, "id": "e72ac664f4f0"}


# The "type: ignore" comment in the next line addresses the fact that TestCase is Any,
# which mypy disallows subclassing
class BootstrapperTests(TestCase):  # type: ignore
    def setUp(self) -> None:
        self.setUpPyfakefs()

    def test_start_core(self) -> None:
        self.fs.create_file(Bootstrapper.DOCKER_CONFIG_FILE_PATH, contents=SAMPLE_JSON)
        fake_client = FakeClient()
        bootstrapper = Bootstrapper(fake_client, FakeLowLevelAPI())
        bootstrapper.start_core()

    def test_start_core_no_config(self) -> None:
        self.fs.create_file(Bootstrapper.DEFAULT_FILE_PATH, contents=SAMPLE_JSON)
        self.fs.create_dir(Path(Bootstrapper.DOCKER_CONFIG_PATH))
        fake_client = FakeClient()
        bootstrapper = Bootstrapper(fake_client, FakeLowLevelAPI())
        bootstrapper.start_core()

    @staticmethod
    def test_is_running() -> None:
        fake_client = FakeClient()
        bootstrapper = Bootstrapper(fake_client, FakeLowLevelAPI())
        assert bootstrapper.core_is_running() is False
        fake_core = FakeContainer(Bootstrapper.CORE_CONTAINER_NAME)
        fake_client.set_active_dockers([fake_core])
        assert bootstrapper.core_is_running()

    @staticmethod
    def test_remove_core() -> None:
        fake_client = FakeClient()
        bootstrapper = Bootstrapper(fake_client, FakeLowLevelAPI())
        fake_core = FakeContainer(Bootstrapper.CORE_CONTAINER_NAME)
        fake_client.set_active_dockers([fake_core])
        assert bootstrapper.core_is_running() is True
        bootstrapper.remove_core()
        assert bootstrapper.core_is_running() is False

    def test_bootstrap_start(self) -> None:
        self.fs.create_file(Bootstrapper.DOCKER_CONFIG_FILE_PATH, contents=SAMPLE_JSON)
        bootstrapper = Bootstrapper(FakeClient(), FakeLowLevelAPI())
        assert bootstrapper.core_is_running() is False
        bootstrapper.run()
        assert bootstrapper.core_is_running()

    def test_bootstrap_start_bad_json(self) -> None:
        self.fs.create_file(Bootstrapper.DEFAULT_FILE_PATH, contents=SAMPLE_JSON)
        self.fs.create_file(Bootstrapper.DOCKER_CONFIG_FILE_PATH, contents=json.dumps({"potato": "bread"}))
        bootstrapper = Bootstrapper(FakeClient(), FakeLowLevelAPI())
        bootstrapper.run()
        assert bootstrapper.core_is_running()
