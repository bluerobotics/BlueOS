#! /usr/bin/env python3
import json
from typing import Any, Dict, List, Set

import uvicorn
from fastapi import Body, FastAPI, Response, status
from fastapi_versioning import VersionedFastAPI, version
from starlette.responses import Response as StarletteResponse

from ArduPilotManager import ArduPilotManager
from mavlink_proxy.Endpoint import Endpoint


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


app = FastAPI(default_response_class=PrettyJSONResponse)
autopilot = ArduPilotManager()


@app.get("/endpoints", response_model=List[Dict[str, Any]])
@version(1, 0)
def get_available_endpoints() -> Any:
    return [endpoint.asdict() for endpoint in autopilot.get_endpoints()]


@app.post("/endpoints", status_code=status.HTTP_201_CREATED)
@version(1, 0)
def create_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    if not autopilot.add_new_endpoints(endpoints):
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": "One or more endpoints already exists or is not supported. No changes were made."}


@app.delete("/endpoints", status_code=status.HTTP_204_NO_CONTENT)
@version(1, 0)
def remove_endpoints(response: Response, endpoints: Set[Endpoint] = Body(...)) -> Any:
    if not autopilot.remove_endpoints(endpoints):
        response.status_code = status.HTTP_409_CONFLICT
        return {"message": "One or more endpoints does not exist or is protected. No changes were made."}


app = VersionedFastAPI(app, version="1.0.0", prefix_format="/v{major}.{minor}", enable_latest=True)

if __name__ == "__main__":
    autopilot.run()
    uvicorn.run(app, host="0.0.0.0", port=8000)
