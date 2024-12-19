import json
from pathlib import Path
from typing import Optional, Any, Callable

import aiohttp
from aiocache import cached


class ResourceUnavailable(Exception):
    pass


class CachedJsonFetcher:
    def __init__(
        self,
        url: str,
        backup: Optional[Path] = None,
        parse_fn: Callable[[Any], Any] = lambda x: x,
        update_backup: bool = True
    ) -> None:
        self.url = url
        self.backup = backup
        self.parse_fn = parse_fn
        self.update_backup = update_backup

    async def _fetch_from_url(self) -> Any:
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url, headers={"Accept": "application/json"}) as resp:
                resp.raise_for_status()
                return self.parse_fn(await resp.json(content_type=None))

    @cached(ttl=3600, namespace="CachedJsonFetcher")
    async def _fetch_and_update_resource(self) -> Any:
        data = await self._fetch_from_url()

        if self.update_backup:
            self._store_backup(data)

        return data

    def _store_backup(self, data: Any) -> None:
        if self.backup:
            try:
                with self.backup.open("w") as backup_file:
                    json.dump(data, backup_file)
            except Exception:
                pass

    def _load_backup(self) -> Any:
        if self.backup and self.backup.exists():
            with self.backup.open("r") as backup_file:
                return json.load(backup_file)
        raise ResourceUnavailable(f"Resource {self.url} is unavailable")

    async def fetch(self) -> Any:
        try:
            return await self._fetch_and_update_resource()
        except Exception:
            return self._load_backup()
