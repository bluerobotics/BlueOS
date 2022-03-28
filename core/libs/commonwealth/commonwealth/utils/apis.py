import json
from typing import Any, Callable, Coroutine

from fastapi import HTTPException, Request, Response, status
from fastapi.routing import APIRoute
from loguru import logger
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


class GenericErrorHandlingRoute(APIRoute):
    def get_route_handler(self) -> Callable[[Request], Coroutine[Any, Any, Response]]:
        original_route_handler = super().get_route_handler()

        async def custom_route_handler(request: Request) -> Response:
            try:
                return await original_route_handler(request)
            except HTTPException as error:
                logger.exception(error)
                raise error
            except Exception as error:
                logger.error("Unhandled service exception.")
                logger.exception(error)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(error)) from error

        return custom_route_handler
