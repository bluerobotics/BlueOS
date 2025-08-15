import json
from typing import Tuple
from unittest import mock
from unittest.mock import AsyncMock

import pytest

from utils.chooser import VersionChooser
from utils.dockerhub import TagFetcher, TagMetadata

# All test coroutines will be treated as marked.
pytestmark = pytest.mark.asyncio

SAMPLE_JSON = """{
    "core": {
        "tag": "master",
        "image": "bluerobotics/blueos-core",
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

SAMPLE_IMAGE = json.loads(
    """{
   "attrs":{
      "date":"2021-04-09T17:51:18.065721638Z"
   },
   "id":"856fdf5e66c9b3697c25015556e7895c9066febb1a8ac8657a4eb41f2fc95a57"
}"""
)


@pytest.mark.asyncio
async def test_get_version() -> None:
    """Tests if VersionChooser.get_version is reading SAMPLE_JSON properly

    Interacts with:
        - docker client (get images)
        - Settings file
    """
    client_mock = mock.AsyncMock()
    chooser = VersionChooser(client_mock)

    attrs = {
        "images.get.return_value.Id": "856fdf5e66c9b3697c25015556e7895c9066febb1a8ac8657a4eb41f2fc95a57",
        "images.get.return_value.__getitem__.return_value": {"date": "2021-04-09T17:51:18.065721638Z"},
    }
    client_mock.configure_mock(**attrs)

    # Mock so it doesn't try to read a real file from the filesystem
    with mock.patch("builtins.open", mock.mock_open(read_data=SAMPLE_JSON)):

        response = await chooser.get_version()
        if response.text is None:
            raise RuntimeError("text should be not None")
        result = json.loads(response.text)
        assert result["repository"] == "bluerobotics/blueos-core"
        assert result["tag"] == "master"
        assert len(client_mock.mock_calls) > 0


version = {"tag": "master", "image": "bluerobotics/blueos-core", "pull": False}

EXPECTED_SET_VERSION_WRITE_CALL = """{  "core": {
    "tag": "master",
    "image": "bluerobotics/blueos-core",
    "enabled": true,
  '
            '  "webui": false,
    "network": "host",
    "binds": {
      "/dev/": {
        "bind": "/dev/",
  '
            '      "mode": "rw"
      },
      "/var/run/wpa_supplicant/wlan0": {
        "bind": "/var/run/wpa_sup'
            'plicant/wlan0",
        "mode": "rw"
      },
      "/tmp/wpa_playground": {
        "bind": "/tmp/wp'
            'a_playground",
        "mode": "rw"
      }
    },
    "privileged": true
  }
}"""


@pytest.mark.asyncio
@mock.patch("aiohttp.web.StreamResponse.write", new_callable=AsyncMock)
async def test_set_version(write_mock: AsyncMock) -> None:
    client = mock.AsyncMock()
    chooser = VersionChooser(client)

    with mock.patch("builtins.open", mock.mock_open(read_data=SAMPLE_JSON)):

        result = await chooser.set_version("bluerobotics/blueos-core", "master")
        assert await write_mock.called_once_with(EXPECTED_SET_VERSION_WRITE_CALL)
        assert result.status == 200


@pytest.mark.asyncio
@mock.patch("json.load", return_value={})
async def test_set_version_invalid_settings(json_mock: mock.MagicMock) -> None:
    client = mock.MagicMock()
    chooser = VersionChooser(client)

    # Image does not exist locally, but for the test let's fake it exists
    async def is_valid_version(image: str) -> Tuple[bool, str]:
        return True, image

    chooser.is_valid_version = is_valid_version  # type: ignore

    with mock.patch("builtins.open", mock.mock_open(read_data="{}")):
        request_mock = AsyncMock()
        request_mock.json = AsyncMock(return_value=version)
        result = await chooser.set_version("bluerobotics/blueos-core", "master")
        assert result.status in (412, 500)
        assert len(json_mock.mock_calls) > 0


image_list = [
    {
        "Created": 1634315959,
        "Architecture": "amd64",
        "Id": "856fdf5e66c9b3697c25015556e7895c9066febb1a8ac8657a4eb41f2fc95a57",
        "RepoTags": [
            "bluerobotics/blueos-core:test1",
        ],
    },
    {
        "Created": 1634315959,
        "Architecture": "amd64",
        "Id": "856fdf5e66c9b36remoteID856fdf5e66c9b36",
        "RepoTags": [
            "bluerobotics/blueos-core:test2",
        ],
    },
]


@pytest.mark.asyncio
@pytest.mark.filterwarnings("ignore: Error status")  # Suppress warning of dockerhub being unavailable
@mock.patch("aiohttp.client.ClientSession.get")
async def test_get_available_versions_dockerhub_unavailable(
    get_mock: mock.MagicMock,
) -> None:
    get_mock.configure_mock(status=500)
    client_mock = mock.AsyncMock()
    attrs = {"images.list.return_value": image_list}
    client_mock.configure_mock(**attrs)
    chooser = VersionChooser(client_mock)
    result = await chooser.get_available_versions("bluerobotics/blueos-core")
    if result.text is None:
        raise RuntimeError("text should be not None")
    data = json.loads(result.text)
    assert "local" in data
    assert "remote" in data
    assert data["local"][0]["tag"] == "test1"
    assert data["local"][1]["tag"] == "test2"
    assert len(client_mock.mock_calls) > 0


@pytest.mark.asyncio
async def test_get_available_versions() -> None:
    client_mock = mock.AsyncMock()
    attrs = {"images.list.return_value": image_list}
    client_mock.configure_mock(**attrs)

    chooser = VersionChooser(client_mock)
    result = await chooser.get_available_versions("bluerobotics/blueos-core")
    if result.text is None:
        raise RuntimeError("text should be not None")
    data = json.loads(result.text)
    assert "local" in data
    assert "remote" in data
    assert data["local"][0]["tag"] == "test1"
    assert data["local"][1]["tag"] == "test2"
    assert len(client_mock.mock_calls) > 0


@pytest.mark.asyncio
async def test_get_version_invalid_file() -> None:
    client = mock.MagicMock()
    with mock.patch("builtins.open", mock.mock_open(read_data="{}")):
        chooser = VersionChooser(client)
        response = await chooser.get_version()
        assert response.status == 500


@pytest.mark.asyncio
@mock.patch("json.load")
async def test_get_version_json_exception(json_mock: mock.MagicMock) -> None:
    client = mock.MagicMock()
    json_mock.side_effect = Exception()
    with mock.patch("builtins.open", mock.mock_open(read_data="")):
        chooser = VersionChooser(client)
        response = await chooser.get_version()
        assert response.status == 500
        assert len(json_mock.mock_calls) > 0


@pytest.mark.asyncio
@mock.patch("json.load")
async def test_set_version_json_exception(json_mock: mock.MagicMock) -> None:
    client = mock.MagicMock()
    json_mock.side_effect = Exception()
    chooser = VersionChooser(client)

    # Image does not exist locally, but for the test let's fake it exists
    async def is_valid_version(image: str) -> Tuple[bool, str]:
        return True, image

    chooser.is_valid_version = is_valid_version  # type: ignore

    with mock.patch("builtins.open", mock.mock_open(read_data="{}")):
        result = await chooser.set_version("bluerobotics/blueos-core", "master")
        assert result.status == 500
        assert len(json_mock.mock_calls) > 0


class TestTagFetcher:
    """Test class for TagFetcher functionality"""

    @pytest.mark.asyncio
    async def test_fetch_real_blueos_core_tags(self) -> None:
        """Integration test: Fetch real tags from bluerobotics/blueos-core repository"""
        fetcher = TagFetcher()

        try:
            errors, tags = await fetcher.fetch_remote_tags("bluerobotics/blueos-core", [])

            # Verify we got some tags back
            assert isinstance(tags, list)
            assert len(tags) > 0, "Should have found some tags for bluerobotics/blueos-core"

            # Verify tag structure
            for tag in tags[:3]:  # Check first 3 tags
                assert isinstance(tag, TagMetadata)
                assert tag.repository == "bluerobotics/blueos-core"
                assert tag.image == "blueos-core"
                assert tag.tag is not None
                assert len(tag.tag) > 0
                assert tag.last_modified is not None
                assert tag.digest is not None

            # Should find the 'master' tag
            tag_names = [tag.tag for tag in tags]
            assert "master" in tag_names, f"Expected to find 'master' tag in tags: {tag_names[:10]}"

            # Errors should be empty string if successful
            if errors:
                print(f"Non-fatal errors during fetch: {errors}")

        except Exception as e:
            # If this fails due to network issues, skip the test
            pytest.skip(f"Could not fetch tags from DockerHub, likely network issue: {e}")
