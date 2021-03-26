#! /usr/bin/env python3
import json
from typing import Any, Dict, List

import uvicorn
from ArduPilotManager import ArduPilotManager
from fastapi import Body, FastAPI, Response, status
from mavlink_proxy.Endpoint import Endpoint
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
        ).encode("utf-8")


app = FastAPI(default_response_class=PrettyJSONResponse)
autopilot = ArduPilotManager()


@app.get("/endpoints", response_model=List[Dict[str, Any]])
def get_available_endpoints() -> Any:
    return [endpoint.asdict() for endpoint in autopilot.get_endpoints()]


@app.post("/endpoint", status_code=status.HTTP_201_CREATED)
def create_new_endpoint(response: Response, endpoint: Endpoint = Body(...)) -> Any:
    if not autopilot.add_new_endpoint(endpoint):
        response.status_code = status.HTTP_409_CONFLICT


@app.delete("/endpoint", status_code=status.HTTP_204_NO_CONTENT)
def remove_endpoint(response: Response, endpoint: Endpoint = Body(...)) -> Any:
    if not autopilot.remove_endpoint(endpoint):
        response.status_code = status.HTTP_404_NOT_FOUND


if __name__ == "__main__":
    autopilot.run()
    uvicorn.run(app, host="0.0.0.0", port=8000)
