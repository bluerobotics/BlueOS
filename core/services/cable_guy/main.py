#! /usr/bin/env python3
import json
import os
import sys
from pathlib import Path
from typing import Any, List

import uvicorn
from api import manager
from api.manager import EthernetInterface
from fastapi import Body, FastAPI, HTTPException, status
from fastapi.staticfiles import StaticFiles
from fastapi_versioning import VersionedFastAPI, version
from starlette.responses import Response as StarletteResponse


class PrettyJSONResponse(StarletteResponse):
    media_type = "application/json"

    def render(self, content: Any) -> bytes:
        return json.dumps(
            content,
            ensure_ascii=False,
            allow_nan=False,
            indent=2,
            separators=(", ", ": "),
        ).encode(self.charset)


HTML_FOLDER = Path.joinpath(Path(__file__).parent.absolute(), "html")

app = FastAPI(
    title="Cable Guy API",
    description="Cable Guy is responsible for managing internet interfaces on Companion.",
    default_response_class=PrettyJSONResponse,
)


@app.get("/ethernet", response_model=List[EthernetInterface], summary="Retrieve ethernet interfaces.")
@version(1, 0)
def retrieve_interfaces() -> Any:
    """REST API endpoint to retrieve the configured ethernet interfaces."""
    return manager.ethernetManager.get_interfaces()


@app.post("/ethernet", response_model=EthernetInterface, summary="Configure a ethernet interface.")
@version(1, 0)
def configure_interface(interface: EthernetInterface = Body(...)) -> Any:
    """REST API endpoint to configure a new ethernet interface or modify an existing one."""
    if not manager.ethernetManager.set_configuration(interface):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Could not configure ethernet interface with provided configuration.",
        )

    manager.ethernetManager.save()
    return interface


app = VersionedFastAPI(
    app,
    version="1.0.0",
    prefix_format="/v{major}.{minor}",
)
app.mount("/", StaticFiles(directory=str(HTML_FOLDER), html=True))

if __name__ == "__main__":
    if os.geteuid() != 0:
        print("You need root privileges to run this script.\nPlease try again, this time using **sudo**. Exiting.")
        sys.exit(1)

    uvicorn.run(app, host="0.0.0.0", port=9090)
