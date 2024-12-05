import aiohttp
from aiocache import cached
from commonwealth.utils.Singleton import Singleton

from autopilot.exceptions import BackendIsOffline, InvalidAutopilotManifestData, InvalidAutopilotManifestURL, ManifestDataFetchFailed
from autopilot.firmwares.ardupilot.models import ArdupilotManifestData

class ArdupilotManifest(metaclass=Singleton):
    def __init__(self):
        self.manifest_url = "https://firmware.ardupilot.org/manifest.json.gz"

    @cached(ttl=3600, namespace="ArduPilotManifest")
    async def _fetch_manifest_gz_data(self, url: str) -> ArdupilotManifestData:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Accept": "application/json"}
                try:
                    async with session.get(url, headers=headers) as resp:
                        if resp.status != 200:
                            raise ManifestDataFetchFailed(
                                f"Failed to fetch manifest data from {url} with status {resp.status}"
                            )

                        try:
                            return ArdupilotManifestData.parse_obj(**(await resp.json(content_type=None)))
                        except Exception as e:
                            raise InvalidAutopilotManifestData(f"Failed to parse manifest data from {url}") from e
                except aiohttp.InvalidURL as e:
                    raise InvalidAutopilotManifestURL(f"Invalid ArduPilot manifest URL {url}") from e
        except aiohttp.ClientConnectionError as e:
            raise BackendIsOffline("Unable to fetch ArduPilot manifest, backend is offline") from e

    @cached(ttl=3600, namespace="ArduPilotManifest")
    async def fetch_boards(self) -> ArdupilotManifestData:
        pass

    async def fetch(self) -> ArdupilotManifestData:
        return await self._fetch_manifest_gz_data(self.manifest_url)
