import asyncio
import json
from typing import Any, AsyncGenerator, List, cast

from commonwealth.utils.zenoh_helper import ZenohRouter
from extension.extension import Extension
from loguru import logger


class ExtensionHandlers:
    INSTALL_PROGRESS_TOPIC = "extension/install/progress"

    def __init__(self, router: ZenohRouter) -> None:
        self.router = router
        self.router.ensure_publisher(self.INSTALL_PROGRESS_TOPIC)

    @staticmethod
    async def _install_progress_stream(identifier: str, extension: Extension) -> AsyncGenerator[str, None]:
        try:
            async for chunk in extension.install():
                try:
                    payload = json.loads(chunk)
                except (TypeError, ValueError) as e:
                    logger.debug(f"Failed to parse install progress chunk: {e}")
                    continue
                payload["identifier"] = identifier
                yield json.dumps(payload, default=str)
        except Exception as error:
            logger.exception(f"Install of {identifier} failed")
            yield json.dumps({"identifier": identifier, "error": str(error)}, default=str)

    async def install_handler(self, identifier: str, tag: str = "", stable: str = "true") -> dict[str, str]:
        """
        Install an extension by its identifier and tag, if tag is not provided it will install the latest stable version.
        """
        if tag:
            extension = cast(Extension, await Extension.from_manifest(identifier, tag))
        else:
            extension = await Extension.from_latest(identifier, stable.lower() == "true")

        on_complete = json.dumps({"identifier": identifier, "status": "complete"})
        self.router.publish_from_generator(
            self.INSTALL_PROGRESS_TOPIC,
            self._install_progress_stream(identifier, extension),
            on_complete=on_complete,
        )
        return {"status": "started", "identifier": identifier}

    async def uninstall_handler(self, identifier: str, tag: str = "") -> None:
        """
        Uninstall all versions of an extension by its identifier or just a specific version if a tag is provided.
        """
        if tag:
            extension = cast(Extension, await Extension.from_settings(identifier, tag))
            await extension.uninstall()
        else:
            extensions = cast(List[Extension], await Extension.from_settings(identifier))
            await asyncio.gather(*[ext.uninstall() for ext in extensions])

    async def enable_handler(self, identifier: str, tag: str) -> None:
        """
        Enables an extension by its identifier and tag.
        """
        extension = cast(Extension, await Extension.from_settings(identifier, tag))
        await extension.enable()

    async def disable_handler(self, identifier: str) -> None:
        """
        Disables current running extension by its identifier.
        """
        extension = await Extension.from_running(identifier)
        await extension.disable()

    async def restart_handler(self, identifier: str) -> None:
        """
        Restart current running extension by its identifier.
        """
        extension = await Extension.from_running(identifier)
        await extension.restart()

    async def fetch_handler(self) -> list[dict[str, Any]]:
        """
        List details of all installed extensions.
        """
        extensions = cast(List[Extension], await Extension.from_settings())
        return [ext.source.model_dump() for ext in extensions if ext.source.identifier != ""]

    async def keep_uploaded_extension_alive_handler(self, temp_tag: str) -> None:
        """
        Refresh the keep-alive timestamp for a temporary extension while the user is editing metadata.
        """
        Extension.keep_temporary_extension_alive(temp_tag)

    def register_queryables(self) -> None:
        self.router.add_queryable("extension/fetch", self.fetch_handler)
        self.router.add_queryable("extension/install", self.install_handler)
        self.router.add_queryable("extension/uninstall", self.uninstall_handler)
        self.router.add_queryable("extension/enable", self.enable_handler)
        self.router.add_queryable("extension/disable", self.disable_handler)
        self.router.add_queryable("extension/restart", self.restart_handler)
        self.router.add_queryable("extension/upload/keep-alive", self.keep_uploaded_extension_alive_handler)
