import json
from pathlib import Path
from typing import Any, Callable, Coroutine, Dict, Optional

import fastapi.applications as fastapi_applications
import fastapi.openapi.docs as fastapi_docs
from commonwealth.utils.logs import stack_trace_message
from fastapi import FastAPI, HTTPException, Request, Response, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
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
            except RequestValidationError:
                raise
            except Exception as error:
                logger.error("Unhandled service exception.")
                logger.exception(error)
                error_msg = stack_trace_message(error)
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=error_msg) from error

        return custom_route_handler


def use_local_docs_assets(app: FastAPI, static_directory: str = "/usr/blueos/static") -> None:

    static_path = Path(static_directory)
    files = ("swagger-ui-bundle.js", "swagger-ui.css", "redoc.standalone.js")

    if not all((static_path / name).is_file() for name in files):
        return
    app.mount("/static-docs", StaticFiles(directory=static_directory), name="static-docs")

    # Check if the docs are already overridden
    if fastapi_applications.get_redoc_html is not fastapi_docs.get_redoc_html:
        return

    swagger_ui_html = fastapi_applications.get_swagger_ui_html
    redoc_html = fastapi_applications.get_redoc_html

    def get_swagger_ui_html(*args: Any, **kwargs: Any) -> HTMLResponse:
        kwargs["swagger_js_url"] = "/static-docs/swagger-ui-bundle.js"
        kwargs["swagger_css_url"] = "/static-docs/swagger-ui.css"
        return swagger_ui_html(*args, **kwargs)

    def get_redoc_html(*args: Any, **kwargs: Any) -> HTMLResponse:
        kwargs["redoc_js_url"] = "/static-docs/redoc.standalone.js"
        return redoc_html(*args, **kwargs)

    fastapi_applications.get_swagger_ui_html = get_swagger_ui_html
    fastapi_applications.get_redoc_html = get_redoc_html


class StackedHTTPException(HTTPException):
    def __init__(self, status_code: int, error: BaseException, headers: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(status_code=status_code, detail=stack_trace_message(error), headers=headers)
