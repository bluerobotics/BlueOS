from __future__ import annotations

import json
from typing import Any, AsyncGenerator, Optional
from urllib.parse import quote

import aiohttp

FILEBROWSER_URL = "http://127.0.0.1:7777/api"
FILEBROWSER_CREDENTIALS = {"username": "", "password": "", "recaptcha": ""}


class Filebrowser:
    """Minimal filebrowser client"""

    def __init__(self) -> None:
        self.auth_token: Optional[str] = None

    async def update_filebrowser_token(self) -> None:
        """Fetch filebrowser API for an authentication token and store it."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FILEBROWSER_URL}/login",
                json=FILEBROWSER_CREDENTIALS,
                timeout=aiohttp.ClientTimeout(total=10),
            ) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise RuntimeError(f"Could not authenticate to filebrowser API: {detail}")
                self.auth_token = self._parse_token(await response.text())

    async def filebrowser_token(self) -> str:
        """Helper to get the auth token, checking before if it was set."""
        if self.auth_token is None:
            await self.update_filebrowser_token()
            if self.auth_token is None:
                raise RuntimeError("Authentication token not set.")
        return self.auth_token

    def folder_zip_relative_url(self, folder_path: str) -> str:
        """Return the URL of a zip of a folder (without auth; use X-Auth header)."""
        path = quote(folder_path.strip("/"), safe="/")
        return f"{FILEBROWSER_URL}/raw/{path}/?algo=zip"

    async def download_folder(self, folder_path: str) -> AsyncGenerator[bytes, None]:
        """Stream a folder as a zip (frontend downloadFolder, without window.open)."""
        url = self.folder_zip_relative_url(folder_path)
        # total=None: zip size is unbounded; still fail fast if filebrowser is down.
        timeout = aiohttp.ClientTimeout(total=None, sock_connect=10)
        headers = {"X-Auth": await self.filebrowser_token()}
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers) as response:
                if response.status >= 400:
                    detail = await response.text()
                    raise RuntimeError(f"Could not download folder {folder_path}: {detail}")
                async for chunk in response.content.iter_chunked(64 * 1024):
                    yield chunk

    @staticmethod
    def _parse_token(raw_token: str) -> str:
        try:
            parsed_token: Any = json.loads(raw_token)
            if isinstance(parsed_token, str):
                return parsed_token
        except json.JSONDecodeError:
            pass
        return raw_token.strip().strip('"')


filebrowser = Filebrowser()
