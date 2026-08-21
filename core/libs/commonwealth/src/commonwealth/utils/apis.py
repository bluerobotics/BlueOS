import json
from typing import Any, Callable, Coroutine, Dict, Optional

from commonwealth.utils.logs import stack_trace_message
from fastapi import HTTPException, Request, Response, status
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from loguru import logger


class PrettyJSONResponse(JSONResponse):
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
                if error.status_code >= status.HTTP_500_INTERNAL_SERVER_ERROR:
                    logger.exception(error)
                raise error
            except Exception as error:
                logger.error("Unhandled service exception.")
                logger.exception(error)
                error_msg = stack_trace_message(error)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg) from error

        return custom_route_handler


class StackedHTTPException(HTTPException):
    def __init__(self, status_code: int, error: BaseException, headers: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(status_code=status_code, detail=stack_trace_message(error), headers=headers)
